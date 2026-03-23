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
GRAFICOS_DIR     = os.path.join(BASE_DIR, "saidas", "graficos")
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
PLANILHA_LOCAL   = os.path.join(BASE_DIR, "dados", "fretes.xlsx")

sys.path.insert(0, SCRIPTS_DIR)

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


def gerar_graficos_nuvem(resultados):
    """
    Gera os 5 gráficos inline com matplotlib — funciona local e na nuvem.
    Usado quando os arquivos .png não estão disponíveis (Streamlit Cloud).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    COR_RECEITA  = "#2E75B6"
    COR_DESPESA  = "#C00000"
    COR_POSITIVO = "#70AD47"
    COR_NEGATIVO = "#FF0000"
    COR_LUCRO    = "#375623"
    CORES_CAT = [
        "#2E75B6","#ED7D31","#A9D18E","#FFC000",
        "#5A9BD5","#FF7F7F","#9DC3E6","#F4B942",
        "#B8860B","#6495ED","#DC143C","#20B2AA","#9370DB"
    ]

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
            ax.bar([i-w/2 for i in x], df_mensal["receita"], w,
                   label="Receita", color=COR_RECEITA, alpha=0.9)
            ax.bar([i+w/2 for i in x], df_mensal["despesa"], w,
                   label="Despesa", color=COR_DESPESA, alpha=0.9)
            ax.set_title("Receita vs Despesa por Mês", fontsize=13, fontweight="bold")
            ax.set_xticks(list(x))
            ax.set_xticklabels(df_mensal["mes_label"], rotation=30, ha="right", fontsize=9)
            ax.legend(); ax.grid(axis="y", linestyle="--", alpha=0.4)
            ax.yaxis.set_major_formatter(
                plt.FuncFormatter(lambda v, _: f"R${v:,.0f}".replace(",",".")))
            fig.tight_layout(); st.pyplot(fig); plt.close(fig)

    with tab2:
        if df_mensal.empty:
            st.info("Sem dados suficientes.")
        else:
            fig, ax = plt.subplots(figsize=(12, 5))
            cores = [COR_POSITIVO if v >= 0 else COR_NEGATIVO for v in df_mensal["lucro"]]
            ax.bar(df_mensal["mes_label"], df_mensal["lucro"], color=cores, alpha=0.9)
            ax.axhline(0, color="#333", linewidth=0.8)
            ax.set_title("Lucro por Mês", fontsize=13, fontweight="bold")
            ax.set_xticks(range(len(df_mensal)))
            ax.set_xticklabels(df_mensal["mes_label"], rotation=30, ha="right", fontsize=9)
            ax.grid(axis="y", linestyle="--", alpha=0.4)
            ax.yaxis.set_major_formatter(
                plt.FuncFormatter(lambda v, _: f"R${v:,.0f}".replace(",",".")))
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
            ax.plot(df_semanal["ano_semana"], df_semanal["lucro"],
                    color=COR_LUCRO, linewidth=2, marker="o", markersize=5)
            ax.scatter(df_semanal["ano_semana"], df_semanal["lucro"],
                       color=cores_p, zorder=5, s=40)
            ax.axhline(0, color="#999", linewidth=0.8, linestyle="--")
            ax.fill_between(df_semanal["ano_semana"], df_semanal["lucro"], 0,
                            where=(df_semanal["lucro"] >= 0),
                            alpha=0.12, color=COR_POSITIVO, interpolate=True)
            ax.fill_between(df_semanal["ano_semana"], df_semanal["lucro"], 0,
                            where=(df_semanal["lucro"] < 0),
                            alpha=0.12, color=COR_NEGATIVO, interpolate=True)
            ax.set_title("Lucro por Semana", fontsize=13, fontweight="bold")
            step = max(1, len(df_semanal) // 20)
            ticks = df_semanal["ano_semana"].iloc[::step].tolist()
            ax.set_xticks(ticks)
            ax.set_xticklabels(ticks, rotation=45, ha="right", fontsize=8)
            ax.grid(linestyle="--", alpha=0.35)
            ax.yaxis.set_major_formatter(
                plt.FuncFormatter(lambda v, _: f"R${v:,.0f}".replace(",",".")))
            fig.tight_layout(); st.pyplot(fig); plt.close(fig)

    with tab4:
        if df_mensal.empty:
            st.info("Sem dados suficientes.")
        else:
            fig, ax = plt.subplots(figsize=(12, 5))
            df_m = df_mensal.copy()
            df_m["lucro_acum"] = df_m["lucro"].cumsum()
            ax.plot(df_m["mes_label"], df_m["lucro_acum"],
                    color=COR_RECEITA, linewidth=2.5, marker="o", markersize=6)
            ax.fill_between(df_m["mes_label"], df_m["lucro_acum"],
                            alpha=0.15, color=COR_RECEITA)
            ax.axhline(0, color="#999", linewidth=0.7, linestyle="--")
            ax.set_title("Evolução do Lucro Acumulado", fontsize=13, fontweight="bold")
            ax.set_xticks(range(len(df_m)))
            ax.set_xticklabels(df_m["mes_label"], rotation=30, ha="right", fontsize=9)
            ax.grid(linestyle="--", alpha=0.35)
            ax.yaxis.set_major_formatter(
                plt.FuncFormatter(lambda v, _: f"R${v:,.0f}".replace(",",".")))
            ultimo = df_m["lucro_acum"].iloc[-1]
            ax.annotate(
                f"Total: R${ultimo:,.2f}".replace(",","."),
                xy=(df_m["mes_label"].iloc[-1], ultimo),
                xytext=(-60, 20), textcoords="offset points",
                fontsize=10, color=COR_LUCRO, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=COR_LUCRO, lw=1.5)
            )
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
            ax_pizza.legend(
                wedges,
                [f"{r['categoria']} (R${r['total']:,.0f})".replace(",",".")
                 for _, r in df_cats.iterrows()],
                loc="center left", bbox_to_anchor=(-0.3, 0.5), fontsize=8)
            ax_pizza.set_title("Distribuição de Despesas", fontsize=13, fontweight="bold")
            ax_barra.barh(df_cats["categoria"], df_cats["total"], color=cores, alpha=0.9)
            ax_barra.set_title("Valor por Categoria", fontsize=13, fontweight="bold")
            ax_barra.invert_yaxis()
            ax_barra.grid(axis="x", linestyle="--", alpha=0.4)
            ax_barra.xaxis.set_major_formatter(
                plt.FuncFormatter(lambda v, _: f"R${v:,.0f}".replace(",",".")))
            fig.suptitle("Análise de Despesas por Categoria",
                         fontsize=14, fontweight="bold", y=1.01)
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
    st.error("Nenhum dado válido encontrado. Verifique a planilha.")
    st.stop()

# Filtro por ano
anos = sorted(df["ano"].unique(), reverse=True)
col_f1, _ = st.columns([2, 4])
with col_f1:
    ano_sel = st.selectbox("Filtrar por ano:", ["Todos"] + [str(a) for a in anos])

from calculator import calcular_tudo
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
card(c4, "📅 Média Lucro/Mês", fmt(m["media_lucro_mensal"]),
     "metric-positivo" if m["media_lucro_mensal"] >= 0 else "metric-negativo")
card(c5, "📆 Média Lucro/Semana", fmt(m["media_lucro_semanal"]),
     "metric-positivo" if m["media_lucro_semanal"] >= 0 else "metric-negativo")

st.divider()

# Gráficos — gerados direto na nuvem (sem depender de arquivos .png)
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
st.caption(f"🚛 Controle de Fretes  •  {len(df_filtrado)} lançamentos")
