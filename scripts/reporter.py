"""
reporter.py
Gera todos os gráficos a partir dos resultados calculados.
Salva as imagens na pasta saidas/graficos/.
"""

import os
import matplotlib
matplotlib.use("Agg")  # renderização sem interface gráfica (compatível com servidor)
import warnings
import logging
logging.getLogger("matplotlib").setLevel(logging.ERROR)
import matplotlib.pyplot as plt
warnings.filterwarnings("ignore", ".*categorical.*")
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
import pandas as pd

PASTA_GRAFICOS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "saidas", "graficos"
)

# Paleta de cores consistente
COR_RECEITA  = "#2E75B6"   # azul
COR_DESPESA  = "#C00000"   # vermelho escuro
COR_LUCRO    = "#375623"   # verde escuro
COR_POSITIVO = "#70AD47"   # verde claro (barra lucro positivo)
COR_NEGATIVO = "#FF0000"   # vermelho (barra lucro negativo)
CATEGORIAS_CORES = [
    "#2E75B6", "#ED7D31", "#A9D18E", "#FFC000",
    "#5A9BD5", "#FF7F7F", "#9DC3E6"
]

def _formatar_reais(ax, eixo="y"):
    """Aplica formato R$ nos ticks do eixo."""
    fmt = mticker.FuncFormatter(lambda x, _: f"R$ {x:,.0f}".replace(",", "."))
    if eixo == "y":
        ax.yaxis.set_major_formatter(fmt)
    else:
        ax.xaxis.set_major_formatter(fmt)

def _salvar(fig, nome: str):
    os.makedirs(PASTA_GRAFICOS, exist_ok=True)
    caminho = os.path.join(PASTA_GRAFICOS, nome)
    fig.savefig(caminho, dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return caminho


def grafico_receita_despesa_mensal(df_mensal: pd.DataFrame) -> str:
    """Barras agrupadas: Receita vs Despesa por mês."""
    if df_mensal.empty:
        return ""

    fig, ax = plt.subplots(figsize=(12, 5))
    x = range(len(df_mensal))
    largura = 0.35

    b1 = ax.bar([i - largura/2 for i in x], df_mensal["receita"],
                largura, label="Receita", color=COR_RECEITA, alpha=0.9)
    b2 = ax.bar([i + largura/2 for i in x], df_mensal["despesa"],
                largura, label="Despesa", color=COR_DESPESA, alpha=0.9)

    ax.set_title("Receita vs Despesa por Mês", fontsize=14, fontweight="bold", pad=16)
    ax.set_xticks(list(x))
    ax.set_xticklabels(df_mensal["mes_label"], rotation=30, ha="right", fontsize=9)
    ax.legend(fontsize=10)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    _formatar_reais(ax)

    # Valor no topo das barras
    for bar in list(b1) + list(b2):
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, h + 20,
                    f"R${h:,.0f}".replace(",", "."),
                    ha="center", va="bottom", fontsize=7, color="#333")

    fig.tight_layout()
    return _salvar(fig, "01_receita_vs_despesa.png")


def grafico_lucro_mensal(df_mensal: pd.DataFrame) -> str:
    """Barras de lucro por mês com cores condicionais."""
    if df_mensal.empty:
        return ""

    fig, ax = plt.subplots(figsize=(12, 5))
    cores = [COR_POSITIVO if v >= 0 else COR_NEGATIVO for v in df_mensal["lucro"]]

    bars = ax.bar(df_mensal["mes_label"], df_mensal["lucro"], color=cores, alpha=0.9)
    ax.axhline(0, color="#333", linewidth=0.8)
    ax.set_title("Lucro por Mês", fontsize=14, fontweight="bold", pad=16)
    ax.set_xticks(range(len(df_mensal)))
    ax.set_xticklabels(df_mensal["mes_label"], rotation=30, ha="right", fontsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    _formatar_reais(ax)

    legenda = [
        mpatches.Patch(color=COR_POSITIVO, label="Lucro positivo"),
        mpatches.Patch(color=COR_NEGATIVO, label="Lucro negativo"),
    ]
    ax.legend(handles=legenda, fontsize=10)

    for bar in bars:
        h = bar.get_height()
        offset = 30 if h >= 0 else -60
        ax.text(bar.get_x() + bar.get_width() / 2, h + offset,
                f"R${h:,.0f}".replace(",", "."),
                ha="center", va="bottom", fontsize=7, color="#333")

    fig.tight_layout()
    return _salvar(fig, "02_lucro_mensal.png")


def grafico_lucro_semanal(df_semanal: pd.DataFrame) -> str:
    """Linha de lucro por semana."""
    if df_semanal.empty:
        return ""

    fig, ax = plt.subplots(figsize=(14, 5))
    cores_ponto = [COR_POSITIVO if v >= 0 else COR_NEGATIVO for v in df_semanal["lucro"]]

    ax.plot(df_semanal["ano_semana"], df_semanal["lucro"],
            color=COR_LUCRO, linewidth=2, marker="o", markersize=5, alpha=0.85)
    ax.scatter(df_semanal["ano_semana"], df_semanal["lucro"],
               color=cores_ponto, zorder=5, s=40)
    ax.axhline(0, color="#999", linewidth=0.8, linestyle="--")
    ax.fill_between(df_semanal["ano_semana"], df_semanal["lucro"], 0,
                    where=(df_semanal["lucro"] >= 0),
                    alpha=0.12, color=COR_POSITIVO, interpolate=True)
    ax.fill_between(df_semanal["ano_semana"], df_semanal["lucro"], 0,
                    where=(df_semanal["lucro"] < 0),
                    alpha=0.12, color=COR_NEGATIVO, interpolate=True)

    ax.set_title("Lucro por Semana", fontsize=14, fontweight="bold", pad=16)
    step = max(1, len(df_semanal) // 20)
    ticks = df_semanal["ano_semana"].iloc[::step].tolist()
    ax.set_xticks(ticks)
    ax.set_xticklabels(ticks, rotation=45, ha="right", fontsize=8)
    ax.grid(linestyle="--", alpha=0.35)
    _formatar_reais(ax)

    fig.tight_layout()
    return _salvar(fig, "03_lucro_semanal.png")


def grafico_evolucao_anual(df_mensal: pd.DataFrame) -> str:
    """Linha de evolução do lucro acumulado ao longo dos meses."""
    if df_mensal.empty:
        return ""

    fig, ax = plt.subplots(figsize=(12, 5))
    df_mensal = df_mensal.copy()
    df_mensal["lucro_acum"] = df_mensal["lucro"].cumsum()

    ax.plot(df_mensal["mes_label"], df_mensal["lucro_acum"],
            color=COR_RECEITA, linewidth=2.5, marker="o", markersize=6)
    ax.fill_between(df_mensal["mes_label"], df_mensal["lucro_acum"],
                    alpha=0.15, color=COR_RECEITA)
    ax.axhline(0, color="#999", linewidth=0.7, linestyle="--")

    ax.set_title("Evolução do Lucro Acumulado", fontsize=14, fontweight="bold", pad=16)
    ax.set_xticks(range(len(df_mensal)))
    ax.set_xticklabels(df_mensal["mes_label"], rotation=30, ha="right", fontsize=9)
    ax.grid(linestyle="--", alpha=0.35)
    _formatar_reais(ax)

    # Anotar o valor final
    ultimo = df_mensal["lucro_acum"].iloc[-1]
    ax.annotate(
        f"Total: R${ultimo:,.2f}".replace(",", "."),
        xy=(df_mensal["mes_label"].iloc[-1], ultimo),
        xytext=(-60, 20), textcoords="offset points",
        fontsize=10, color=COR_LUCRO, fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=COR_LUCRO, lw=1.5)
    )

    fig.tight_layout()
    return _salvar(fig, "04_evolucao_acumulada.png")


def grafico_categorias(df_categorias: pd.DataFrame) -> str:
    """Pizza de distribuição de despesas por categoria."""
    if df_categorias.empty:
        return ""

    fig, (ax_pizza, ax_barra) = plt.subplots(1, 2, figsize=(14, 6))

    # Pizza
    wedges, texts, autotexts = ax_pizza.pie(
        df_categorias["total"],
        labels=None,
        autopct="%1.1f%%",
        colors=CATEGORIAS_CORES[:len(df_categorias)],
        startangle=140,
        pctdistance=0.78,
        wedgeprops=dict(linewidth=0.5, edgecolor="white")
    )
    for at in autotexts:
        at.set_fontsize(9)
    ax_pizza.legend(
        wedges,
        [f"{r['categoria']} (R${r['total']:,.0f})".replace(",", ".")
         for _, r in df_categorias.iterrows()],
        loc="center left", bbox_to_anchor=(-0.25, 0.5), fontsize=9
    )
    ax_pizza.set_title("Distribuição de Despesas", fontsize=13, fontweight="bold")

    # Barras horizontais
    cores = CATEGORIAS_CORES[:len(df_categorias)]
    ax_barra.barh(df_categorias["categoria"], df_categorias["total"],
                  color=cores, alpha=0.9)
    ax_barra.set_title("Valor por Categoria", fontsize=13, fontweight="bold")
    ax_barra.invert_yaxis()
    ax_barra.grid(axis="x", linestyle="--", alpha=0.4)
    _formatar_reais(ax_barra, eixo="x")

    for i, (_, row) in enumerate(df_categorias.iterrows()):
        ax_barra.text(row["total"] + 5, i,
                      f"R${row['total']:,.0f}".replace(",", "."),
                      va="center", fontsize=8)

    fig.suptitle("Análise de Despesas por Categoria", fontsize=14,
                 fontweight="bold", y=1.01)
    fig.tight_layout()
    return _salvar(fig, "05_categorias.png")


def gerar_todos(resultados: dict) -> list[str]:
    """
    Ponto de entrada único. Recebe o dicionário de resultados do calculator
    e gera todos os gráficos. Retorna lista de caminhos gerados.
    """
    gerados = []
    gerados.append(grafico_receita_despesa_mensal(resultados["mensal"]))
    gerados.append(grafico_lucro_mensal(resultados["mensal"]))
    gerados.append(grafico_lucro_semanal(resultados["semanal"]))
    gerados.append(grafico_evolucao_anual(resultados["mensal"]))
    gerados.append(grafico_categorias(resultados["categorias"]))
    return [c for c in gerados if c]  # remove strings vazias
