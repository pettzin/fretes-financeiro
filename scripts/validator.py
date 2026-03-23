"""
validator.py
Valida os dados lidos da planilha antes de qualquer cálculo.
Nunca lança exceção: retorna listas de erros para o chamador decidir o que fazer.
"""

import pandas as pd
from datetime import datetime

TIPOS_VALIDOS = {"Receita", "Despesa"}

CATEGORIAS_VALIDAS = {
    # Receita
    "Frete",
    # Despesa — nomes com acento (como aparecem na planilha)
    "Combustível", "Óleo (KM)", "Troca Óleo Motor",
    "Pedágio", "Manutenção", "Troca de Pneu",
    "IPVA", "Multa", "Seguro", "Contador",
    "Taxa do CNPJ", "Outros",
    # Compatibilidade com nome antigo
    "Troca de óleo",
}

# Migração de nomes antigos para novos
NORMALIZAR_CATEGORIA = {
    "Troca de óleo": "Troca Óleo Motor",
    "Troca de Oleo": "Troca Óleo Motor",
    "Troca Oleo Motor": "Troca Óleo Motor",
    "Oleo (KM)": "Óleo (KM)",
    "Pedagio": "Pedágio",
    "Manutencao": "Manutenção",
    "Combustivel": "Combustível",
}


def validar(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Recebe o DataFrame bruto da planilha.
    Retorna (df_valido, lista_de_avisos).
    Linhas com problemas críticos são descartadas.
    Problemas menores são corrigidos automaticamente.
    """
    avisos = []
    df = df.copy()

    # 1. Remover linhas completamente vazias
    df.dropna(how="all", inplace=True)

    # 2. Normalizar nomes de colunas
    df.columns = [str(c).strip().upper() for c in df.columns]

    # 3. Renomear para nomes internos padronizados
    mapa_colunas = {
        "DATA": "data",
        "TIPO": "tipo",
        "CATEGORIA": "categoria",
        "VALOR (R$)": "valor",
        "VALOR": "valor",
        "DESCRIÇÃO": "descricao",
        "DESCRICAO": "descricao",
        "MÊS/ANO": "mes_ano",
        "MES/ANO": "mes_ano",
    }
    df.rename(columns={k: v for k, v in mapa_colunas.items() if k in df.columns}, inplace=True)

    colunas_necessarias = ["data", "tipo", "categoria", "valor"]
    for col in colunas_necessarias:
        if col not in df.columns:
            avisos.append(f"CRÍTICO: Coluna '{col}' não encontrada na planilha.")
            return pd.DataFrame(), avisos

    # 4. Remover linhas sem data e sem valor (incompletas)
    antes = len(df)
    df.dropna(subset=["data", "valor"], inplace=True)
    removidas = antes - len(df)
    if removidas > 0:
        avisos.append(f"INFO: {removidas} linha(s) ignorada(s) por falta de data ou valor.")

    if df.empty:
        avisos.append("AVISO: Nenhum dado válido encontrado na planilha.")
        return df, avisos

    # 5. Converter e validar DATA
    def parse_data(val):
        if pd.isnull(val):
            return pd.NaT
        if isinstance(val, datetime):
            return val
        for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(str(val).strip(), fmt)
            except ValueError:
                continue
        return pd.NaT

    df["data"] = df["data"].apply(parse_data)
    datas_invalidas = df["data"].isna().sum()
    if datas_invalidas > 0:
        avisos.append(f"AVISO: {datas_invalidas} linha(s) com data inválida foram removidas.")
        df.dropna(subset=["data"], inplace=True)

    # 6. Converter e validar VALOR
    # SUA CORREÇÃO: remove ponto (milhar) antes de trocar vírgula por ponto decimal
    def parse_valor(val):
        try:
            v = float(str(val).replace(".", "").replace(",", ".").replace("R$", "").strip())
            return abs(v)  # garante positivo
        except (ValueError, AttributeError):
            return None

    df["valor"] = df["valor"].apply(parse_valor)
    valores_invalidos = df["valor"].isna().sum()
    if valores_invalidos > 0:
        avisos.append(f"AVISO: {valores_invalidos} linha(s) com valor inválido foram removidas.")
        df.dropna(subset=["valor"], inplace=True)

    # 7. Normalizar e validar TIPO
    df["tipo"] = df["tipo"].astype(str).str.strip().str.capitalize()
    tipos_invalidos = ~df["tipo"].isin(TIPOS_VALIDOS)
    if tipos_invalidos.any():
        n = tipos_invalidos.sum()
        avisos.append(
            f"AVISO: {n} linha(s) com tipo inválido (aceito: Receita/Despesa). "
            f"Valores encontrados: {df.loc[tipos_invalidos, 'tipo'].unique().tolist()}"
        )
        df = df[~tipos_invalidos]

    # 8. Normalizar CATEGORIA — migrar nomes antigos e padronizar
    df["categoria"] = df["categoria"].astype(str).str.strip()
    df["categoria"] = df["categoria"].replace(NORMALIZAR_CATEGORIA)

    categorias_desconhecidas = ~df["categoria"].isin(CATEGORIAS_VALIDAS)
    if categorias_desconhecidas.any():
        cats = df.loc[categorias_desconhecidas, "categoria"].unique().tolist()
        avisos.append(
            f"INFO: Categoria(s) não reconhecida(s) classificada(s) como 'Outros': {cats}"
        )
        df.loc[categorias_desconhecidas, "categoria"] = "Outros"

    # 9. Preencher descrição vazia
    if "descricao" in df.columns:
        df["descricao"] = df["descricao"].fillna("").astype(str).str.strip()
    else:
        df["descricao"] = ""

    # 10. Adicionar colunas de período para facilitar cálculos
    df["data"] = pd.to_datetime(df["data"])
    df["ano"] = df["data"].dt.year
    df["mes"] = df["data"].dt.month
    df["semana"] = df["data"].dt.isocalendar().week.astype(int)
    df["ano_semana"] = df["data"].dt.strftime("%Y-S%V")
    df["ano_mes"] = df["data"].dt.to_period("M").astype(str)
    df["mes_label"] = df["data"].dt.strftime("%b/%Y")

    df.reset_index(drop=True, inplace=True)

    avisos.append(f"OK: {len(df)} lançamento(s) válido(s) carregado(s).")
    return df, avisos
