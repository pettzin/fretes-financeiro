# coding: utf-8
import os
import sys
import json
import warnings
import logging
import pandas as pd
import streamlit as st

warnings.filterwarnings("ignore", ".*categorical.*")
logging.getLogger("matplotlib").setLevel(logging.ERROR)

BASE_DIR         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR      = os.path.join(BASE_DIR, "scripts")
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
PLANILHA_LOCAL   = os.path.join(BASE_DIR, "dados", "fretes.xlsx")

sys.path.insert(0, SCRIPTS_DIR)
sys.path.insert(0, BASE_DIR)

st.set_page_config(
    page_title="Controle de Fretes",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.metric-card{background:#f0f4fa;border-radius:12px;padding:18px 20px;border-left:5px solid #2E75B6;margin-bottom:10px;}
.metric-positivo{border-left-color:#375623;background:#eaf3e4;}
.metric-negativo{border-left-color:#C00000;background:#fce4d6;}
.metric-label{font-size:13px;color:#555;margin-bottom:4px;}
.metric-value{font-size:26px;font-weight:bold;color:#1a1a2e;}
.alerta-box{background:#FCE4D6;border-left:5px solid #C00000;border-radius:8px;padding:12px 16px;margin-bottom:8px;}
.alerta-titulo{color:#C00000;font-weight:bold;font-size:14px;}
.alerta-detalhe{color:#333;font-size:13px;margin-top:4px;}
</style>
""", unsafe_allow_html=True)


def carregar_do_drive():
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        if hasattr(st, "secrets") and "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        elif os.path.exists(CREDENTIALS_FILE):
            with open(CREDENTIALS_FILE) as f:
                creds_dict = json.load(f)
        else:
            return None, "credentials.json nao encontrado"

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)

        nome = "fretes"
        if hasattr(st, "secrets") and "nome_planilha" in st.secrets:
            nome = st.secrets["nome_planilha"]

        try:
            sh = gc.open(nome)
        except Exception:
            sh = gc.open("fretes.xlsx")

        aba = sh.worksheet("📋 Lançamentos")
        dados = aba.get_all_values()

        if len(dados) < 4:
            return pd.DataFrame(), None

        df = pd.DataFrame(dados[3:], columns=dados[2])
        return df, None

    except Exception as e:
        return None, str(e)


def carregar_local():
    try:
        df = pd.read_excel(PLANILHA_LOCAL, sheet_name="📋 Lançamentos", header=2)
        return df, None
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=60)
def carregar_dados():
    from validator import validar
    from calculator import calcular_tudo

    df_bruto, erro_drive = carregar_do_drive()
    fonte = "Google Drive"

    if df_bruto is None:
        df_bruto, erro_local = carregar_local()
        fonte = "arquivo local"
        if df_bruto is None:
            return None, [], {}, f"Erro Drive: {erro_drive}"

    df, avisos = validar(df_bruto)
    if df.empty:
        return None, avisos, {}, fonte

    resultados = calcular_tudo(df)
    return df, avisos, resultados, fonte


def obter_limites():
    """Lê limites do Streamlit secrets ou do config.py local."""
    MAPA_SECRETS = {
        "Combustivel":      "Combustivel",
        "Manutencao":       "Manutencao",
        "Troca_Oleo_Motor": "Troca Oleo Motor",
        "Troca_de_Pneu":    "Troca de Pneu",
        "Pedagio":          "Pedagio",
        "IPVA":             "IPVA",
        "Multa":            "Multa",
        "Seguro":           "Seguro",
        "Contador":         "Contador",
        "Oleo_KM":          "Oleo (KM)",
        "Taxa_do_CNPJ":     "Taxa do CNPJ",
    }
    try:
        if hasattr(st, "secrets") and "limites_alerta" in st.secrets:
            limites = {}
            for chave_secret, chave_sistema in MAPA_SECRETS.items():
                if chave_secret in st.secrets["limites_alerta"]:
                    limites[chave_sistema] = float(st.secrets["limites_alerta"][chave_secret])
            if limites:
                return limites
    except Exception:
        pass
    try:
        import config
        return config.LIMITES_ALERTA
    except Exception:
        return {}


def verificar_alertas_inline(df, mes, ano):
    """Verifica alertas diretamente no dashboard sem depender do alertas.py."""
    MAPA_ACENTO = {
        "Combustivel": "Combustivel", "Combustível": "Combustivel",
        "Manutencao": "Manutencao", "Manutenção": "Manutencao",
        "Troca Oleo Motor": "Troca Oleo Motor", "Troca Óleo Motor": "Troca Oleo Motor",
        "Troca de Pneu": "Troca de Pneu",
        "Pedagio": "Pedagio", "Pedágio": "Pedagio",
        "Oleo (KM)": "Oleo (KM)", "Óleo (KM)": "Oleo (KM)",
        "IPVA": "IPVA", "Multa": "Multa", "Seguro": "Seguro",
        "Contador": "Contador", "Taxa do CNPJ": "Taxa do CNPJ",
    }

    limites = obter_limites()
    if not limites:
        return []

    df_mes = df[
        (df["tipo"] == "Despesa") &
        (df["mes"] == mes) &
        (df["ano"] == ano)
    ].copy()

    if df_mes.empty:
        return []

    df_mes["cat_key"] = df_mes["categoria"].map(MAPA_ACENTO).fillna(df_mes["categoria"])
    gastos = df_mes.groupby("cat_key")["valor"].sum()

    alertas = []
    for cat_key, limite in limites.items():
        if cat_key not in gastos.index:
            continue
        gasto = gastos[cat_key]
        if gasto > limite:
            alertas.append({
                "categoria":  cat_key,
                "gasto":      round(float(gasto), 2),
                "limite":     float(limite),
                "excesso":    round(float(gasto - limite), 2),
                "percentual": round(float(gasto) / float(limite) * 100, 1),
            })

    alertas.sort(key=lambda x: x["excesso"], reverse=True)
    return alertas


def gerar_graficos_nuvem(resultados):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    COR_RECEITA  = "#2E75B6"
    COR_DESPESA  = "#C00000"
    COR_POSITIVO = "#70AD47"
    COR_NEGATIVO = "#FF0000"
    COR_LUCRO    = "#375623"
    CORES_CAT = ["#2E75B6","#ED7D31","#A9D18E","#FFC000",
                 "#5A9BD5","#FF7F7F","#9DC3E6","#F4B942",
                 "#B8860B","#6495ED","#DC143C","#20B2AA","#9370DB"]

    df_mensal  = resultados["mensal"]
    df_semanal = resultados["semanal"]
    df_cats    = resultados["categorias"]

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Receita vs Despesa", "📈 Lucro Mensal",
        "📉 Lucro Semanal", "📋 Evolução Acumulada", "🍕 Categorias",
    ])

    with tab1:
        if df_mensal.empty:
            st.info("Sem dados suficientes.")
        else:
            fig, ax = plt.subplots(figsize=(12, 5))
            x = range(len(df_mensal))
            w = 0.35
            ax.bar([i-w/2 for i in x], df_mensal["receita"], w, label="Receita", color=COR_RECEITA, alpha=0.9)
            ax.bar([i+w/2 for i in x], df_mensal["despesa"], w, label="Despesa", color=COR_DESPESA, alpha=0.9)
            ax.set_title("Receita vs Despesa por Mes", fontsize=13, fontweight="bold")
            ax.set_xticks(list(x))
            ax.set_xticklabels(df_mensal["mes_label"], rotation=30, ha="right", fontsize=9)
            ax.legend(); ax.grid(axis="y", linestyle="--", alpha=0.4)
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"R${v:,.0f}".replace(",",".")))
            fig.tight_layout(); st.pyplot(fig); plt.close(fig)

    with tab2:
        if df_mensal.empty:
            st.info("Sem dados suficientes.")
        else:
            fig, ax = plt.subplots(figsize=(12, 5))
            cores = [COR_POSITIVO if v >= 0 else COR_NEGATIVO for v in df_mensal["lucro"]]
            ax.bar(df_mensal["mes_label"], df_mensal["lucro"], color=cores, alpha=0.9)
            ax.axhline(0, color="#333", linewidth=0.8)
            ax.set_title("Lucro por Mes", fontsize=13, fontweight="bold")
            ax.set_xticks(range(len(df_mensal)))
            ax.set_xticklabels(df_mensal["mes_label"], rotation=30, ha="right", fontsize=9)
            ax.grid(axis="y", linestyle="--", alpha=0.4)
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"R${v:,.0f}".replace(",",".")))
            leg = [mpatches.Patch(color=COR_POSITIVO, label="Positivo"),
                   mpatches.Patch(color=COR_NEGATIVO, label="Negativo")]
            ax.legend(handles=leg)
            fig.tight_layout(); st.pyplot(fig); plt.close(fig)

    with tab3:
        if df_semanal.empty:
            st.info("Sem dados suficientes.")
        else:
            fig, ax = plt.subplots(figsize=(14, 5))
            cores_p = [COR_POSITIVO if v >= 0 else COR_NEGATIVO for v in df_semanal["lucro"]]
            ax.plot(df_semanal["ano_semana"], df_semanal["lucro"], color=COR_LUCRO, linewidth=2, marker="o", markersize=5)
            ax.scatter(df_semanal["ano_semana"], df_semanal["lucro"], color=cores_p, zorder=5, s=40)
            ax.axhline(0, color="#999", linewidth=0.8, linestyle="--")
            ax.fill_between(df_semanal["ano_semana"], df_semanal["lucro"], 0,
                            where=(df_semanal["lucro"] >= 0), alpha=0.12, color=COR_POSITIVO, interpolate=True)
            ax.fill_between(df_semanal["ano_semana"], df_semanal["lucro"], 0,
                            where=(df_semanal["lucro"] < 0), alpha=0.12, color=COR_NEGATIVO, interpolate=True)
            ax.set_title("Lucro por Semana", fontsize=13, fontweight="bold")
            step = max(1, len(df_semanal) // 20)
            ticks = df_semanal["ano_semana"].iloc[::step].tolist()
            ax.set_xticks(ticks)
            ax.set_xticklabels(ticks, rotation=45, ha="right", fontsize=8)
            ax.grid(linestyle="--", alpha=0.35)
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"R${v:,.0f}".replace(",",".")))
            fig.tight_layout(); st.pyplot(fig); plt.close(fig)

    with tab4:
        if df_mensal.empty:
            st.info("Sem dados suficientes.")
        else:
            fig, ax = plt.subplots(figsize=(12, 5))
            df_m = df_mensal.copy()
            df_m["lucro_acum"] = df_m["lucro"].cumsum()
            ax.plot(df_m["mes_label"], df_m["lucro_acum"], color=COR_RECEITA, linewidth=2.5, marker="o", markersize=6)
            ax.fill_between(df_m["mes_label"], df_m["lucro_acum"], alpha=0.15, color=COR_RECEITA)
            ax.axhline(0, color="#999", linewidth=0.7, linestyle="--")
            ax.set_title("Evolucao do Lucro Acumulado", fontsize=13, fontweight="bold")
            ax.set_xticks(range(len(df_m)))
            ax.set_xticklabels(df_m["mes_label"], rotation=30, ha="right", fontsize=9)
            ax.grid(linestyle="--", alpha=0.35)
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"R${v:,.0f}".replace(",",".")))
            if len(df_m) > 0:
                ultimo = df_m["lucro_acum"].iloc[-1]
                ax.annotate(f"Total: R${ultimo:,.2f}".replace(",","."),
                    xy=(df_m["mes_label"].iloc[-1], ultimo),
                    xytext=(-60, 20), textcoords="offset points",
                    fontsize=10, color=COR_LUCRO, fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color=COR_LUCRO, lw=1.5))
            fig.tight_layout(); st.pyplot(fig); plt.close(fig)

    with tab5:
        if df_cats.empty:
            st.info("Sem despesas registradas.")
        else:
            fig, (ax_pizza, ax_barra) = plt.subplots(1, 2, figsize=(14, 6))
            cores = CORES_CAT[:len(df_cats)]
            wedges, _, autotexts = ax_pizza.pie(
                df_cats["total"], labels=None, autopct="%1.1f%%",
                colors=cores, startangle=140, pctdistance=0.78,
                wedgeprops=dict(linewidth=0.5, edgecolor="white"))
            for at in autotexts:
                at.set_fontsize(9)
            ax_pizza.legend(wedges,
                [f"{r['categoria']} (R${r['total']:,.0f})".replace(",",".")
                 for _, r in df_cats.iterrows()],
                loc="center left", bbox_to_anchor=(-0.3, 0.5), fontsize=8)
            ax_pizza.set_title("Distribuicao de Despesas", fontsize=13, fontweight="bold")
            ax_barra.barh(df_cats["categoria"], df_cats["total"], color=cores, alpha=0.9)
            ax_barra.set_title("Valor por Categoria", fontsize=13, fontweight="bold")
            ax_barra.invert_yaxis()
            ax_barra.grid(axis="x", linestyle="--", alpha=0.4)
            ax_barra.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"R${v:,.0f}".replace(",",".")))
            fig.suptitle("Analise de Despesas por Categoria", fontsize=14, fontweight="bold", y=1.01)
            fig.tight_layout(); st.pyplot(fig); plt.close(fig)


# ── Header ────────────────────────────────────────────────────────────────────
col_titulo, col_btn = st.columns([5, 1])
with col_titulo:
    st.markdown("## 🚛 Controle Financeiro de Fretes")
    st.caption("Atualizado automaticamente a partir da planilha Excel")
with col_btn:
    if st.button("🔄 Atualizar", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.divider()

with st.spinner("Carregando dados..."):
    df, avisos, resultados, fonte = carregar_dados()

st.caption(f"Fonte: {fonte}")

avisos_erros = [a for a in avisos if "AVISO" in a or "CRITICO" in a]
if avisos_erros:
    with st.expander(f"⚠️ {len(avisos_erros)} aviso(s)", expanded=False):
        for a in avisos_erros:
            st.warning(a)

if df is None or df.empty:
    st.error("Nenhum dado valido encontrado. Verifique a planilha.")
    st.stop()

# Filtro por ano
anos = sorted(df["ano"].unique(), reverse=True)
col_f1, _ = st.columns([2, 4])
with col_f1:
    ano_sel = st.selectbox("Filtrar por ano:", ["Todos"] + [str(a) for a in anos])

from calculator import calcular_tudo
from datetime import date
df_filtrado = df if ano_sel == "Todos" else df[df["ano"] == int(ano_sel)]
res = calcular_tudo(df_filtrado)
t = res["totais"]
m = res["medias"]

# Cards
st.markdown("### 📈 Indicadores Gerais")

def fmt(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def card(col, label, valor, classe=""):
    col.markdown(
        f'<div class="metric-card {classe}">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-value">{valor}</div>'
        f'</div>', unsafe_allow_html=True)

c1, c2, c3, c4, c5 = st.columns(5)
card(c1, "💰 Total de Receitas", fmt(t["total_receitas"]))
card(c2, "💸 Total de Despesas", fmt(t["total_despesas"]), "metric-negativo")
card(c3, "📊 Lucro Total", fmt(t["lucro_total"]),
     "metric-positivo" if t["lucro_total"] >= 0 else "metric-negativo")
card(c4, "📅 Media Lucro/Mes", fmt(m["media_lucro_mensal"]),
     "metric-positivo" if m["media_lucro_mensal"] >= 0 else "metric-negativo")
card(c5, "📆 Media Lucro/Semana", fmt(m["media_lucro_semanal"]),
     "metric-positivo" if m["media_lucro_semanal"] >= 0 else "metric-negativo")

# Cards semanais
st.divider()
st.markdown("### 📅 Semana em Andamento e Última Semana")

try:
    sys.path.insert(0, SCRIPTS_DIR)
    from semana import calcular_semana, intervalo_semana_atual, intervalo_semana_anterior

    ini_atual, fim_atual   = intervalo_semana_atual()
    ini_ant,   fim_ant     = intervalo_semana_anterior()
    sem_atual = calcular_semana(df, ini_atual, fim_atual)
    sem_ant   = calcular_semana(df, ini_ant,   fim_ant)

    col_sa, col_sf = st.columns(2)

    def card_semana(titulo, cor_borda, emoji, ini, fim, dados):
        cor_lucro = "#375623" if dados["lucro"] >= 0 else "#C00000"
        return f"""
        <div style="background:#f0f4fa;border-radius:12px;padding:20px 22px;
                    border-left:5px solid {cor_borda};margin-bottom:10px;">
          <div style="font-size:14px;color:#333;font-weight:bold;margin-bottom:2px;">
            {emoji} {titulo}
          </div>
          <div style="font-size:11px;color:#888;margin-bottom:14px;">
            {ini.strftime("%d/%m/%Y")} a {fim.strftime("%d/%m/%Y")}
          </div>
          <table style="width:100%;border-collapse:collapse;">
            <tr>
              <td style="font-size:11px;color:#888;padding-bottom:2px;">Receita bruta</td>
              <td style="font-size:11px;color:#888;padding-bottom:2px;text-align:right;">Despesas</td>
            </tr>
            <tr>
              <td style="font-size:18px;font-weight:bold;color:#2E75B6;padding-bottom:12px;">
                {fmt(dados["receitas"])}
              </td>
              <td style="font-size:18px;font-weight:bold;color:#C00000;padding-bottom:12px;text-align:right;">
                {fmt(dados["despesas"])}
              </td>
            </tr>
            <tr>
              <td colspan="2" style="border-top:1px solid #ddd;padding-top:10px;">
                <span style="font-size:11px;color:#888;">Lucro liquido</span><br>
                <span style="font-size:22px;font-weight:bold;color:{cor_lucro};">
                  {fmt(dados["lucro"])}
                </span>
              </td>
            </tr>
            <tr>
              <td colspan="2" style="padding-top:10px;background:#e8f4e8;
                  border-radius:6px;padding:8px 10px;margin-top:8px;">
                <span style="font-size:11px;color:#555;">Parte de cada socio (50%)</span><br>
                <span style="font-size:16px;font-weight:bold;color:#375623;">
                  {fmt(dados["metade"])}
                </span>
              </td>
            </tr>
          </table>
        </div>"""

    with col_sa:
        st.markdown(
            card_semana("Semana em andamento", "#2E75B6", "📅",
                        ini_atual, fim_atual, sem_atual),
            unsafe_allow_html=True
        )

    with col_sf:
        st.markdown(
            card_semana("Ultima semana fechada", "#375623", "✅",
                        ini_ant, fim_ant, sem_ant),
            unsafe_allow_html=True
        )
except Exception as e:
    st.info(f"Dados semanais indisponiveis: {e}")

# Alertas — verifica o mes mais recente com dados no periodo filtrado
if not df_filtrado.empty:
    ultimo = df_filtrado.sort_values('data').iloc[-1]
    mes_verificar = int(ultimo['mes'])
    ano_verificar = int(ultimo['ano'])
else:
    hoje = date.today()
    mes_verificar = hoje.month
    ano_verificar = hoje.year

alertas = verificar_alertas_inline(df_filtrado, mes_verificar, ano_verificar)
if alertas:
    st.divider()
    st.markdown("### 🚨 Alertas de Despesa")
    for al in alertas:
        gasto_fmt  = fmt(al["gasto"])
        limite_fmt = fmt(al["limite"])
        excesso_fmt = fmt(al["excesso"])
        st.markdown(
            f'<div class="alerta-box">'
            f'<div class="alerta-titulo">⚠️ {al["categoria"]}</div>'
            f'<div class="alerta-detalhe">'
            f'Gasto: <b>{gasto_fmt}</b> &nbsp;|&nbsp; '
            f'Limite: <b>{limite_fmt}</b> &nbsp;|&nbsp; '
            f'Excesso: <b>{excesso_fmt}</b> ({al["percentual"]}% do limite)'
            f'</div></div>',
            unsafe_allow_html=True
        )

st.divider()

# Graficos
st.markdown("### 📊 Gráficos")
gerar_graficos_nuvem(res)

st.divider()

# Tabela
st.markdown("### 📋 Lançamentos Recentes")
df_exibir = df_filtrado[["data","tipo","categoria","valor","descricao"]].copy()
df_exibir = df_exibir.sort_values("data", ascending=False).head(50)
df_exibir["data"] = df_exibir["data"].dt.strftime("%d/%m/%Y")
df_exibir["valor"] = df_exibir["valor"].apply(
    lambda v: f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X","."))
df_exibir.columns = ["Data","Tipo","Categoria","Valor","Descricao"]
st.dataframe(df_exibir, use_container_width=True, hide_index=True)

st.divider()
st.caption(f"🚛 Controle de Fretes  •  {len(df_filtrado)} lancamentos")
