# coding: utf-8
"""
alertas.py
Verifica se alguma categoria ultrapassou o limite mensal.
- Local: lê os limites do config.py
- Streamlit Cloud: lê dos st.secrets["limites_alerta"]
"""

import os
import sys
import pandas as pd
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MAPA_ACENTO = {
    "Combustivel":      "Combustivel",
    "Combustível":      "Combustivel",
    "Manutencao":       "Manutencao",
    "Manutenção":       "Manutencao",
    "Troca Oleo Motor": "Troca Oleo Motor",
    "Troca Óleo Motor": "Troca Oleo Motor",
    "Troca de Pneu":    "Troca de Pneu",
    "Pedagio":          "Pedagio",
    "Pedágio":          "Pedagio",
    "Oleo (KM)":        "Oleo (KM)",
    "Óleo (KM)":        "Oleo (KM)",
    "IPVA":             "IPVA",
    "Multa":            "Multa",
    "Seguro":           "Seguro",
    "Contador":         "Contador",
    "Taxa do CNPJ":     "Taxa do CNPJ",
}

# Mapeamento de chaves dos secrets (sem caracteres especiais) para chaves do sistema
MAPA_SECRETS = {
    "Combustivel":    "Combustivel",
    "Manutencao":     "Manutencao",
    "Troca_Oleo_Motor": "Troca Oleo Motor",
    "Troca_de_Pneu":  "Troca de Pneu",
    "Pedagio":        "Pedagio",
    "IPVA":           "IPVA",
    "Multa":          "Multa",
    "Seguro":         "Seguro",
    "Contador":       "Contador",
    "Oleo_KM":        "Oleo (KM)",
    "Taxa_do_CNPJ":   "Taxa do CNPJ",
}


def _carregar_limites() -> dict:
    """
    Tenta carregar limites do Streamlit secrets primeiro.
    Cai no config.py local se não estiver na nuvem.
    """
    # Streamlit Cloud
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "limites_alerta" in st.secrets:
            limites = {}
            for chave_secret, chave_sistema in MAPA_SECRETS.items():
                if chave_secret in st.secrets["limites_alerta"]:
                    limites[chave_sistema] = float(st.secrets["limites_alerta"][chave_secret])
            if limites:
                return limites
    except Exception:
        pass

    # Local — config.py
    try:
        import config
        return config.LIMITES_ALERTA
    except (ImportError, AttributeError):
        return {}


def verificar_alertas(df: pd.DataFrame, mes: int = None, ano: int = None) -> list:
    """
    Verifica os gastos do mês contra os limites configurados.
    Retorna lista de dicionários com os alertas disparados.
    """
    limites = _carregar_limites()
    if not limites:
        return []

    hoje = date.today()
    mes  = mes  or hoje.month
    ano  = ano  or hoje.year

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
                "gasto":      round(gasto, 2),
                "limite":     limite,
                "excesso":    round(gasto - limite, 2),
                "percentual": round(gasto / limite * 100, 1),
            })

    alertas.sort(key=lambda x: x["excesso"], reverse=True)
    return alertas
