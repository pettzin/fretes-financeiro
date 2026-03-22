"""
calculator.py
Calcula todos os indicadores financeiros a partir do DataFrame validado.
Todas as funções retornam dicionários ou DataFrames — nunca imprimem nada.
"""

import pandas as pd


def calcular_totais(df: pd.DataFrame) -> dict:
    """Totais gerais: receitas, despesas, lucro."""
    receitas = df.loc[df["tipo"] == "Receita", "valor"].sum()
    despesas = df.loc[df["tipo"] == "Despesa", "valor"].sum()
    return {
        "total_receitas": round(receitas, 2),
        "total_despesas": round(despesas, 2),
        "lucro_total": round(receitas - despesas, 2),
        "margem_pct": round((receitas - despesas) / receitas * 100, 1) if receitas > 0 else 0.0,
    }


def calcular_por_mes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Retorna DataFrame com receita, despesa e lucro por mês.
    Ordenado cronologicamente.
    """
    if df.empty:
        return pd.DataFrame(columns=["ano_mes", "mes_label", "receita", "despesa", "lucro"])

    receitas = (
        df[df["tipo"] == "Receita"]
        .groupby(["ano_mes", "mes_label"])["valor"]
        .sum()
        .rename("receita")
    )
    despesas = (
        df[df["tipo"] == "Despesa"]
        .groupby(["ano_mes", "mes_label"])["valor"]
        .sum()
        .rename("despesa")
    )

    mensal = pd.concat([receitas, despesas], axis=1).fillna(0).reset_index()
    mensal["lucro"] = mensal["receita"] - mensal["despesa"]
    mensal = mensal.sort_values("ano_mes").reset_index(drop=True)

    for col in ["receita", "despesa", "lucro"]:
        mensal[col] = mensal[col].round(2)

    return mensal


def calcular_por_semana(df: pd.DataFrame) -> pd.DataFrame:
    """
    Retorna DataFrame com receita, despesa e lucro por semana do ano.
    """
    if df.empty:
        return pd.DataFrame(columns=["ano_semana", "receita", "despesa", "lucro"])

    receitas = (
        df[df["tipo"] == "Receita"]
        .groupby("ano_semana")["valor"]
        .sum()
        .rename("receita")
    )
    despesas = (
        df[df["tipo"] == "Despesa"]
        .groupby("ano_semana")["valor"]
        .sum()
        .rename("despesa")
    )

    semanal = pd.concat([receitas, despesas], axis=1).fillna(0).reset_index()
    semanal["lucro"] = semanal["receita"] - semanal["despesa"]
    semanal = semanal.sort_values("ano_semana").reset_index(drop=True)

    for col in ["receita", "despesa", "lucro"]:
        semanal[col] = semanal[col].round(2)

    return semanal


def calcular_por_ano(df: pd.DataFrame) -> pd.DataFrame:
    """Resumo anual."""
    if df.empty:
        return pd.DataFrame(columns=["ano", "receita", "despesa", "lucro"])

    receitas = df[df["tipo"] == "Receita"].groupby("ano")["valor"].sum().rename("receita")
    despesas = df[df["tipo"] == "Despesa"].groupby("ano")["valor"].sum().rename("despesa")

    anual = pd.concat([receitas, despesas], axis=1).fillna(0).reset_index()
    anual["lucro"] = anual["receita"] - anual["despesa"]
    anual = anual.sort_values("ano").reset_index(drop=True)
    for col in ["receita", "despesa", "lucro"]:
        anual[col] = anual[col].round(2)
    return anual


def calcular_por_categoria(df: pd.DataFrame) -> pd.DataFrame:
    """Gastos totais por categoria de despesa."""
    despesas = df[df["tipo"] == "Despesa"]
    if despesas.empty:
        return pd.DataFrame(columns=["categoria", "total", "percentual"])

    por_cat = (
        despesas.groupby("categoria")["valor"]
        .sum()
        .reset_index()
        .rename(columns={"valor": "total"})
        .sort_values("total", ascending=False)
    )
    total_geral = por_cat["total"].sum()
    por_cat["percentual"] = (por_cat["total"] / total_geral * 100).round(1)
    por_cat["total"] = por_cat["total"].round(2)
    return por_cat.reset_index(drop=True)


def calcular_medias(df_mensal: pd.DataFrame, df_semanal: pd.DataFrame) -> dict:
    """Médias de lucro por semana e por mês."""
    media_mensal = df_mensal["lucro"].mean() if not df_mensal.empty else 0.0
    media_semanal = df_semanal["lucro"].mean() if not df_semanal.empty else 0.0
    return {
        "media_lucro_mensal": round(media_mensal, 2),
        "media_lucro_semanal": round(media_semanal, 2),
    }


def calcular_tudo(df: pd.DataFrame) -> dict:
    """
    Ponto de entrada único: recebe o DataFrame validado
    e retorna um dicionário com todos os resultados.
    """
    mensal = calcular_por_mes(df)
    semanal = calcular_por_semana(df)

    return {
        "totais": calcular_totais(df),
        "mensal": mensal,
        "semanal": semanal,
        "anual": calcular_por_ano(df),
        "categorias": calcular_por_categoria(df),
        "medias": calcular_medias(mensal, semanal),
    }
