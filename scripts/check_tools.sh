#!/usr/bin/env bash
# Verifica ferramentas CLI necessárias para o projeto football-analytics.
#
# Uso:
#   bash scripts/check_tools.sh

set -euo pipefail

VERDE="\033[92m"
VERMELHO="\033[91m"
AMARELO="\033[93m"
RESET="\033[0m"
NEGRITO="\033[1m"

FALHAS=0

ok() {
    local descricao="$1"
    local detalhe="${2:-}"
    local sufixo=""
    [[ -n "$detalhe" ]] && sufixo=" ($detalhe)"
    echo -e "  ${VERDE}✓${RESET} ${descricao}${sufixo}"
}

falha() {
    local descricao="$1"
    local detalhe="${2:-}"
    local sufixo=""
    [[ -n "$detalhe" ]] && sufixo=" → $detalhe"
    echo -e "  ${VERMELHO}✗${RESET} ${descricao}${sufixo}"
    FALHAS=$((FALHAS + 1))
}

aviso() {
    local descricao="$1"
    local detalhe="${2:-}"
    local sufixo=""
    [[ -n "$detalhe" ]] && sufixo=" → $detalhe"
    echo -e "  ${AMARELO}~${RESET} ${descricao}${sufixo}"
}

echo -e "${NEGRITO}=== Verificação de Ferramentas CLI ===${RESET}"

# Python
echo -e "\n${NEGRITO}Python${RESET}"
if command -v python3 &>/dev/null; then
    versao=$(python3 --version 2>&1)
    minor=$(python3 -c "import sys; print(sys.version_info.minor)")
    if [[ "$minor" -ge 10 ]]; then
        ok "python3 disponível" "$versao"
    else
        falha "python3 versão insuficiente" "requer 3.10+, encontrado: $versao"
    fi
else
    falha "python3 não encontrado" "instale Python 3.10+"
fi

# Virtualenv
if [[ -d ".venv" ]]; then
    ok "Virtualenv .venv existe"
else
    aviso ".venv não existe" "crie com: python3 -m venv .venv"
fi

# pip / requirements instalados
if [[ -f ".venv/bin/pip" ]]; then
    ok "pip disponível no .venv"
else
    aviso "pip não disponível no .venv" "ative o venv e rode: pip install -r requirements.txt"
fi

# ruff
echo -e "\n${NEGRITO}Linter${RESET}"
if command -v ruff &>/dev/null; then
    versao=$(ruff --version 2>&1)
    ok "ruff disponível" "$versao"
else
    aviso "ruff não encontrado no PATH" "ative o virtualenv: source .venv/bin/activate"
fi

# Google Cloud CLI
echo -e "\n${NEGRITO}Google Cloud${RESET}"
if command -v gcloud &>/dev/null; then
    versao=$(gcloud --version 2>&1 | head -1)
    ok "gcloud CLI disponível" "$versao"
else
    falha "gcloud CLI não encontrado" "instale em: https://cloud.google.com/sdk/docs/install"
fi

if command -v bq &>/dev/null; then
    ok "bq CLI disponível"
else
    falha "bq CLI não encontrado" "incluído no gcloud SDK — verifique a instalação"
fi

# ADC (Application Default Credentials)
if gcloud auth application-default print-access-token &>/dev/null 2>&1; then
    ok "Application Default Credentials configuradas"
else
    falha "ADC não configurado" "rode: gcloud auth application-default login"
fi

# dbt
echo -e "\n${NEGRITO}dbt${RESET}"
if command -v dbt &>/dev/null; then
    versao=$(dbt --version 2>&1 | head -1)
    ok "dbt disponível" "$versao"
else
    aviso "dbt não encontrado no PATH" "ative o virtualenv: source .venv/bin/activate"
fi

# Git
echo -e "\n${NEGRITO}Git${RESET}"
if command -v git &>/dev/null; then
    versao=$(git --version)
    ok "git disponível" "$versao"
else
    falha "git não encontrado" "instale git"
fi

# Resumo
echo -e "\n${NEGRITO}Resumo${RESET}"
if [[ "$FALHAS" -eq 0 ]]; then
    echo -e "  ${VERDE}${NEGRITO}Todas as ferramentas CLI estão disponíveis.${RESET}"
else
    echo -e "  ${VERMELHO}$FALHAS ferramenta(s) com problema — corrija antes de continuar.${RESET}"
    exit 1
fi
