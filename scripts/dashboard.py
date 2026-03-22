# coding: utf-8
"""
dashboard.py
Dashboard Streamlit — lê a planilha direto do Google Drive via API.
"""

import os
import sys
import json
import tempfile
import pandas as pd
import streamlit as st

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
GRAFICOS_DIR = os.path.join(BASE_DIR, "saidas", "graficos")
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
PLANILHA_LOCAL = os.path.join(BASE_DIR, "dados", "fretes.xlsx")

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
    .metric-card {
        background: #f0f4fa;
        border-radius: 12px;
        padding: 18px 20px;
        border-left: 5px solid #2E75B6;
        margin-bottom: 10px;
    }
    .metric-positivo { border-left-color: #375623; background: #eaf3e4; }
    .metric-negativo { border-left-color: #C00000; background: #fce4d6; }
    .metric-label { font-size: 13px; color: #555; margin-bottom: 4px; }
    .metric-value { font-size: 26px; font-weight: bold; color: #1a1a2e; }
</style>
""", unsafe_allow_html=True)


def carregar_do_drive():
    """Lê a planilha direto do Google Drive via API."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        # Tenta ler credenciais dos secrets do Streamlit Cloud primeiro
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
        elif os.path.exists(CREDENTIALS_FILE):
            with open(CREDENTIALS_FILE) as f:
                creds_dict = json.load(f)
        else:
            return None, "Arquivo credentials.json não encontrado."

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)

        # Nome da planilha no Drive
        nome_planilha = st.secrets.get("nome_planilha", "fretes") if hasattr(st, "secrets") else "fretes"
        try:
            sh = gc.open(nome_planilha)
        except gspread.SpreadsheetNotFound:
            sh = gc.open("fretes.xlsx")

        aba = sh.worksheet("📋 Lançamentos")
        dados = aba.get_all_values()

        if len(dados) < 4:
            return pd.DataFrame(), "Planilha vazia."

        # Linha 3 (índice 2) é o cabeçalho
        df = pd.DataFrame(dados[3:], columns=dados[2])
        return df, None

    except Exception as e:
        return None, str(e)


def carregar_local():
    """Fallback: lê o arquivo local em dados/fretes.xlsx."""
    try:
        df = pd.read_excel(PLANILHA_LOCAL, sheet_name="📋 Lançamentos", header=2)
        return df, None
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=60)
def carregar_dados():
    from validator import validar
    from calculator import calcular_tudo

    # Tenta Drive primeiro, cai no local se falhar
    df_bruto, erro = carregar_do_drive()
    fonte = "Google Drive"

    if df_bruto is None or (isinstance(df_bruto, pd.DataFrame) and df_bruto.empty and erro):
        df_bruto, erro2 = carregar_local()
        fonte = "arquivo local"
        if df_bruto is None:
            return None, [], {}, f"Drive: {erro} | Local: {erro2}"

    df, avisos = validar(df_bruto)
    if df.empty:
        return None, avisos, {}, fonte

    resultados = calcular_tudo(df)
    return df, avisos, resultados, fonte


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

st.caption(f"Fonte dos dados: {fonte}")

avisos_problemas = [a for a in avisos if "AVISO" in a or "CRITICO" in a]
if avisos_problemas:
    with st.expander(f"⚠️ {len(avisos_problemas)} aviso(s)", expanded=False):
        for a in avisos_problemas:
            st.warning(a)

if df is None or df.empty:
    st.error("Nenhum dado válido encontrado.")
    st.stop()

# ── Filtro por ano ────────────────────────────────────────────────────────────
anos = sorted(df["ano"].unique(), reverse=True)
col_f1, _ = st.columns([2, 4])
with col_f1:
    ano_sel = st.selectbox("Filtrar por ano:", ["Todos"] + [str(a) for a in anos])

from calculator import calcular_tudo
df_filtrado = df if ano_sel == "Todos" else df[df["ano"] == int(ano_sel)]
res = calcular_tudo(df_filtrado)
t = res["totais"]
m = res["medias"]

# ── Cards ─────────────────────────────────────────────────────────────────────
st.markdown("### 📈 Indicadores Gerais")

def fmt(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def card(col, label, valor, classe=""):
    col.markdown(
        f'<div class="metric-card {classe}">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-value">{valor}</div>'
        f'</div>', unsafe_allow_html=True
    )

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

# ── Gráficos ──────────────────────────────────────────────────────────────────
st.markdown("### 📊 Gráficos")

def exibir_grafico(nome, titulo):
    caminho = os.path.join(GRAFICOS_DIR, nome)
    if os.path.exists(caminho):
        st.image(caminho, use_container_width=True)
    else:
        st.info(f"Execute o sistema local para gerar o gráfico '{titulo}'.")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Receita vs Despesa",
    "📈 Lucro Mensal",
    "📉 Lucro Semanal",
    "📋 Evolução Acumulada",
    "🍕 Categorias",
])
with tab1: exibir_grafico("01_receita_vs_despesa.png", "Receita vs Despesa")
with tab2: exibir_grafico("02_lucro_mensal.png", "Lucro Mensal")
with tab3: exibir_grafico("03_lucro_semanal.png", "Lucro Semanal")
with tab4: exibir_grafico("04_evolucao_acumulada.png", "Evolução Acumulada")
with tab5: exibir_grafico("05_categorias.png", "Categorias")

st.divider()

# ── Tabela ────────────────────────────────────────────────────────────────────
st.markdown("### 📋 Lançamentos Recentes")
df_exibir = df_filtrado[["data","tipo","categoria","valor","descricao"]].copy()
df_exibir = df_exibir.sort_values("data", ascending=False).head(50)
df_exibir["data"] = df_exibir["data"].dt.strftime("%d/%m/%Y")
df_exibir["valor"] = df_exibir["valor"].apply(
    lambda v: f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")
)
df_exibir.columns = ["Data","Tipo","Categoria","Valor","Descrição"]
st.dataframe(df_exibir, use_container_width=True, hide_index=True)

st.divider()
st.caption(f"🚛 Sistema de Controle de Fretes  •  {len(df_filtrado)} lançamentos")
