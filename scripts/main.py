"""
main.py
Ponto de entrada do sistema de controle financeiro de fretes.

Uso:
  python main.py                  → processa + abre dashboard no navegador
  python main.py --sem-dashboard  → só processa (chamado pelo watcher.py)

Fluxo:
  1. Backup automático da planilha
  2. Leitura dos dados
  3. Validação
  4. Cálculos
  5. Geração dos gráficos
  6. (Opcional) Dashboard Streamlit
"""

import os
import sys
import shutil
import logging
import argparse
import traceback
from datetime import datetime
import pandas as pd

# ── Caminhos ─────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
sys.path.insert(0, SCRIPTS_DIR)
sys.path.insert(0, BASE_DIR)

# Tenta carregar config.py (presente quando watcher está configurado)
try:
    import config
    DADOS_DIR  = config.DADOS_DIR
    BACKUP_DIR = config.BACKUP_DIR
    LOGS_DIR   = config.LOGS_DIR
    PLANILHA   = config.PLANILHA_LOCAL
    MAX_BACKUPS = config.MAX_BACKUPS
except ImportError:
    DADOS_DIR   = os.path.join(BASE_DIR, "dados")
    BACKUP_DIR  = os.path.join(DADOS_DIR, "backups")
    LOGS_DIR    = os.path.join(BASE_DIR, "logs")
    PLANILHA    = os.path.join(DADOS_DIR, "fretes.xlsx")
    MAX_BACKUPS = 30

DASHBOARD = os.path.join(SCRIPTS_DIR, "dashboard.py")

for pasta in [DADOS_DIR, BACKUP_DIR, LOGS_DIR]:
    os.makedirs(pasta, exist_ok=True)

# ── Flag --sem-dashboard (usado pelo watcher) ─────────────────────────────────
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--sem-dashboard", action="store_true",
                    help="Processa os dados sem abrir o navegador.")
args, _ = parser.parse_known_args()
ABRIR_DASHBOARD = not args.sem_dashboard

# ── Logging ───────────────────────────────────────────────────────────────────
log_file = os.path.join(LOGS_DIR, f"execucao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)


# ── Funções ───────────────────────────────────────────────────────────────────

def fazer_backup() -> bool:
    if not os.path.exists(PLANILHA):
        log.error(f"Planilha não encontrada em: {PLANILHA}")
        return False
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = os.path.join(BACKUP_DIR, f"fretes_backup_{ts}.xlsx")
    shutil.copy2(PLANILHA, destino)
    log.info(f"Backup criado: {os.path.basename(destino)}")
    backups = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.endswith(".xlsx")],
        reverse=True
    )
    for antigo in backups[MAX_BACKUPS:]:
        os.remove(os.path.join(BACKUP_DIR, antigo))
        log.info(f"Backup antigo removido: {antigo}")
    return True


def ler_planilha() -> pd.DataFrame:
    aba = "📋 Lançamentos"
    df = pd.read_excel(PLANILHA, sheet_name=aba, header=2)
    log.info(f"Planilha lida: {len(df)} linhas brutas.")
    return df


def limpar_logs_antigos(manter=30):
    logs = sorted(
        [f for f in os.listdir(LOGS_DIR) if f.startswith("execucao_") and f.endswith(".log")],
        reverse=True
    )
    for antigo in logs[manter:]:
        os.remove(os.path.join(LOGS_DIR, antigo))


def pausar_se_interativo():
    """Só chama input() se não for chamado pelo watcher (modo interativo)."""
    if ABRIR_DASHBOARD:
        input("\nPressione ENTER para fechar...")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("SISTEMA DE CONTROLE FINANCEIRO DE FRETES")
    log.info(f"Execução: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    log.info(f"Modo: {'interativo' if ABRIR_DASHBOARD else 'automático (sem dashboard)'}")
    log.info("=" * 60)

    # 1. Backup
    log.info("Etapa 1/5: Criando backup...")
    if not fazer_backup():
        pausar_se_interativo()
        sys.exit(1)

    # 2. Leitura
    log.info("Etapa 2/5: Lendo planilha...")
    try:
        df_bruto = ler_planilha()
    except Exception as e:
        log.error(f"Erro ao ler planilha: {e}")
        log.error(traceback.format_exc())
        pausar_se_interativo()
        sys.exit(1)

    # 3. Validação
    log.info("Etapa 3/5: Validando dados...")
    try:
        from validator import validar
        df, avisos = validar(df_bruto)
        for aviso in avisos:
            if "CRÍTICO" in aviso:
                log.error(aviso)
            elif "AVISO" in aviso:
                log.warning(aviso)
            else:
                log.info(aviso)
        if df.empty:
            log.warning("Nenhum dado válido. Verifique a planilha.")
            pausar_se_interativo()
            sys.exit(0)
    except Exception as e:
        log.error(f"Erro na validação: {e}")
        log.error(traceback.format_exc())
        pausar_se_interativo()
        sys.exit(1)

    # 4. Cálculos
    log.info("Etapa 4/5: Calculando indicadores...")
    try:
        from calculator import calcular_tudo
        resultados = calcular_tudo(df)
        t = resultados["totais"]
        log.info(f"  Receitas : R$ {t['total_receitas']:,.2f}")
        log.info(f"  Despesas : R$ {t['total_despesas']:,.2f}")
        log.info(f"  Lucro    : R$ {t['lucro_total']:,.2f}  ({t['margem_pct']}%)")
    except Exception as e:
        log.error(f"Erro nos cálculos: {e}")
        log.error(traceback.format_exc())
        pausar_se_interativo()
        sys.exit(1)

    # 5. Gráficos
    log.info("Etapa 5/5: Gerando gráficos...")
    try:
        from reporter import gerar_todos
        graficos = gerar_todos(resultados)
        log.info(f"  {len(graficos)} gráfico(s) gerado(s).")
    except Exception as e:
        log.warning(f"Erro ao gerar gráficos (não crítico): {e}")

    limpar_logs_antigos()

    # 6. Dashboard (somente se não for chamado pelo watcher)
    if not ABRIR_DASHBOARD:
        log.info("Processamento automático concluído. Dashboard será atualizado.")
        sys.exit(0)

    log.info("Abrindo dashboard no navegador...")
    log.info("Para fechar o dashboard, pressione Ctrl+C nesta janela.")
    try:
        import subprocess
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", DASHBOARD,
            "--server.headless", "false",
            "--browser.gatherUsageStats", "false",
            "--server.port", "8501",
        ])
    except KeyboardInterrupt:
        log.info("Dashboard encerrado pelo usuário.")
    except FileNotFoundError:
        log.error("Streamlit não encontrado. Execute: pip install streamlit")
        input("\nPressione ENTER para fechar...")


if __name__ == "__main__":
    main()
