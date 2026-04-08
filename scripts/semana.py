# coding: utf-8
"""
semana.py
Calcula indicadores semanais e gera PDF do extrato semanal.
Semana: domingo a sabado.
"""

import os
import sys
import io
from datetime import date, timedelta
import pandas as pd

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

BASE_DIR       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELATORIOS_DIR = os.path.join(BASE_DIR, "saidas", "relatorios", "semanal")

AZUL      = colors.HexColor("#2E75B6")
AZUL_CL   = colors.HexColor("#EBF3FB")
VERDE_CL  = colors.HexColor("#EAF3E4")
VERM_CL   = colors.HexColor("#FCE4D6")
CINZA     = colors.HexColor("#F2F2F2")
CINZA_ESC = colors.HexColor("#595959")


def domingo_da_semana(referencia: date = None) -> date:
    """Retorna o domingo de inicio da semana da data de referencia."""
    ref = referencia or date.today()
    # weekday(): 0=segunda ... 6=domingo
    # isoweekday(): 1=segunda ... 7=domingo
    dias_desde_domingo = ref.isoweekday() % 7  # domingo=0, segunda=1, ...
    return ref - timedelta(days=dias_desde_domingo)


def intervalo_semana_atual() -> tuple[date, date]:
    """Retorna (domingo, hoje) da semana atual."""
    hoje = date.today()
    inicio = domingo_da_semana(hoje)
    return inicio, hoje


def intervalo_semana_anterior() -> tuple[date, date]:
    """Retorna (domingo, sabado) da semana anterior fechada."""
    hoje = date.today()
    domingo_atual = domingo_da_semana(hoje)
    sabado_ant = domingo_atual - timedelta(days=1)
    domingo_ant = domingo_da_semana(sabado_ant)
    return domingo_ant, sabado_ant


def calcular_semana(df: pd.DataFrame, inicio: date, fim: date) -> dict:
    """Calcula receitas, despesas e lucro de um periodo."""
    mask = (df["data"].dt.date >= inicio) & (df["data"].dt.date <= fim)
    df_periodo = df[mask]

    receitas = df_periodo.loc[df_periodo["tipo"] == "Receita", "valor"].sum()
    despesas = df_periodo.loc[df_periodo["tipo"] == "Despesa", "valor"].sum()
    lucro    = receitas - despesas

    return {
        "inicio":   inicio,
        "fim":      fim,
        "receitas": round(receitas, 2),
        "despesas": round(despesas, 2),
        "lucro":    round(lucro, 2),
        "metade":   round(lucro / 3, 2),
        "lancamentos": len(df_periodo),
    }


def fmt(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_pdf_semanal(df: pd.DataFrame, inicio: date, fim: date) -> str:
    """Gera PDF simples do extrato semanal. Retorna caminho do arquivo."""
    os.makedirs(RELATORIOS_DIR, exist_ok=True)

    dados = calcular_semana(df, inicio, fim)

    nome_arquivo = f"semana_{inicio.strftime('%Y_%m_%d')}.pdf"
    caminho      = os.path.join(RELATORIOS_DIR, nome_arquivo)

    styles = getSampleStyleSheet()

    titulo = ParagraphStyle("titulo",
        fontSize=18, fontName="Helvetica-Bold",
        textColor=AZUL, alignment=TA_CENTER, spaceAfter=4)

    subtitulo = ParagraphStyle("sub",
        fontSize=11, fontName="Helvetica",
        textColor=CINZA_ESC, alignment=TA_CENTER, spaceAfter=16)

    secao = ParagraphStyle("secao",
        fontSize=11, fontName="Helvetica-Bold",
        textColor=AZUL, spaceBefore=12, spaceAfter=6)

    rodape = ParagraphStyle("rodape",
        fontSize=8, fontName="Helvetica",
        textColor=colors.grey, alignment=TA_CENTER)

    doc = SimpleDocTemplate(
        caminho, pagesize=A4,
        leftMargin=3*cm, rightMargin=3*cm,
        topMargin=2.5*cm, bottomMargin=2.5*cm
    )
    story = []

    # Cabecalho
    story.append(Paragraph("Extrato Semanal de Fretes", titulo))
    story.append(Paragraph(
        f"{inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}",
        subtitulo
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=AZUL))
    story.append(Spacer(1, 0.6*cm))

    # Resumo financeiro
    story.append(Paragraph("Resumo Financeiro", secao))

    cor_lucro = VERDE_CL if dados["lucro"] >= 0 else VERM_CL

    tabela = [
        ["Indicador", "Valor"],
        ["Total de Receitas",  fmt(dados["receitas"])],
        ["Total de Despesas",  fmt(dados["despesas"])],
        ["Lucro da Semana",    fmt(dados["lucro"])],
    ]

    tab = Table(tabela, colWidths=[8*cm, 5*cm])
    tab.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), AZUL),
        ("TEXTCOLOR",     (0,0), (-1,0), colors.white),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME",      (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE",      (0,0), (-1,-1), 10),
        ("ALIGN",         (1,0), (1,-1), "RIGHT"),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.white, CINZA]),
        ("BACKGROUND",    (0,3), (-1,3), cor_lucro),
        ("FONTNAME",      (0,3), (-1,3), "Helvetica-Bold"),
        ("GRID",          (0,0), (-1,-1), 0.3, colors.lightgrey),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
    ]))
    story.append(tab)
    story.append(Spacer(1, 0.8*cm))

    # Divisao 33/33
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph("Divisao 33/33 sobre o Lucro", secao))

    tab_divisao = [
        ["",         "Valor"],
        ["Cada socio recebe", fmt(dados["metade"])],
    ]

    tab2 = Table(tab_divisao, colWidths=[8*cm, 5*cm])
    tab2.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), AZUL),
        ("TEXTCOLOR",     (0,0), (-1,0), colors.white),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME",      (0,1), (-1,-1), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 11),
        ("ALIGN",         (1,0), (1,-1), "RIGHT"),
        ("BACKGROUND",    (0,1), (-1,1), VERDE_CL if dados["lucro"] >= 0 else VERM_CL),
        ("GRID",          (0,0), (-1,-1), 0.3, colors.lightgrey),
        ("TOPPADDING",    (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
    ]))
    story.append(tab2)
    story.append(Spacer(1, 0.4*cm))

    # Nota
    story.append(Paragraph(
        f"* Baseado em {dados['lancamentos']} lancamento(s) no periodo.",
        ParagraphStyle("nota", fontSize=8, fontName="Helvetica",
                       textColor=colors.grey, spaceBefore=4)
    ))

    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Spacer(1, 0.2*cm))
    from datetime import datetime
    story.append(Paragraph(
        f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} — Sistema de Controle Financeiro de Fretes",
        rodape
    ))

    doc.build(story)
    return caminho


def verificar_e_gerar(df: pd.DataFrame) -> str:
    """
    Verifica se o PDF da semana anterior ja existe.
    Se nao existir, gera automaticamente — independente do dia.
    Idempotente: pode rodar qualquer dia, nao gera duplicatas.
    """
    inicio, fim = intervalo_semana_anterior()

    # Verificar se ja foi gerado
    nome = f"semana_{inicio.strftime('%Y_%m_%d')}.pdf"
    caminho = os.path.join(RELATORIOS_DIR, nome)
    if os.path.exists(caminho):
        return ""

    # So gera se houver lancamentos no periodo
    mask = (df["data"].dt.date >= inicio) & (df["data"].dt.date <= fim)
    if df[mask].empty:
        return ""

    return gerar_pdf_semanal(df, inicio, fim)
