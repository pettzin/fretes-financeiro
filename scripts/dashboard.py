# coding: utf-8
import os
import sys
import json
import pandas as pd
import streamlit as st

# Caminhos — funciona tanto local quanto no Streamlit Cloud
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
GRAFICOS_DIR = os.path.join(BASE_DIR, "saidas", "graficos")
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
PLANILHA_LOCAL = os.path.join(BASE_DIR, "dados", "fretes.xlsx")

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

        # Streamlit Cloud: lê dos secrets
        if hasattr(st, "secrets") and "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            # Corrigir private_key que pode vir com \\n literal
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

        # Tenta abrir a planilha pelo nome
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


# Header
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
from reporter import gerar_todos 

df_filtrado = df if ano_sel == "Todos" else df[df["ano"] == int(ano_sel)]
res = calcular_tudo(df_filtrado)

gerar_todos(res)  

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

# Gráficos
st.markdown("### 📊 Gráficos")

def exibir_grafico(nome, titulo):
    caminho = os.path.join(GRAFICOS_DIR, nome)
    if os.path.exists(caminho):
        st.image(caminho, use_container_width=True)
    else:
        st.info(f"Gráfico '{titulo}' ainda não gerado. Execute o sistema no PC.")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Receita vs Despesa", "📈 Lucro Mensal",
    "📉 Lucro Semanal", "📋 Evolução Acumulada", "🍕 Categorias",
])
with tab1: exibir_grafico("01_receita_vs_despesa.png", "Receita vs Despesa")
with tab2: exibir_grafico("02_lucro_mensal.png", "Lucro Mensal")
with tab3: exibir_grafico("03_lucro_semanal.png", "Lucro Semanal")
with tab4: exibir_grafico("04_evolucao_acumulada.png", "Evolucao Acumulada")
with tab5: exibir_grafico("05_categorias.png", "Categorias")

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
