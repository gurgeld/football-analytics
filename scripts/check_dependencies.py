"""Script de verificação de dependências do projeto football-analytics.

Verifica conectividade com BigQuery e API Football-Data.org,
além de variáveis de ambiente obrigatórias.

Uso:
    source .venv/bin/activate
    python scripts/check_dependencies.py
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

VERDE = "\033[92m"
VERMELHO = "\033[91m"
AMARELO = "\033[93m"
RESET = "\033[0m"
NEGRITO = "\033[1m"

resultados: list[tuple[str, bool, str]] = []


def ok(descricao: str, detalhe: str = "") -> None:
    """Registra verificação bem-sucedida."""
    resultados.append((descricao, True, detalhe))
    sufixo = f" ({detalhe})" if detalhe else ""
    print(f"  {VERDE}✓{RESET} {descricao}{sufixo}")


def falha(descricao: str, detalhe: str = "") -> None:
    """Registra verificação com falha."""
    resultados.append((descricao, False, detalhe))
    sufixo = f" → {detalhe}" if detalhe else ""
    print(f"  {VERMELHO}✗{RESET} {descricao}{sufixo}")


def aviso(descricao: str, detalhe: str = "") -> None:
    """Registra verificação com aviso (não bloqueia)."""
    sufixo = f" → {detalhe}" if detalhe else ""
    print(f"  {AMARELO}~{RESET} {descricao}{sufixo}")


def verificar_env_vars() -> None:
    """Verifica variáveis de ambiente obrigatórias."""
    print(f"\n{NEGRITO}Variáveis de Ambiente{RESET}")

    env_file = os.path.exists(".env")
    if env_file:
        ok(".env encontrado")
    else:
        falha(".env não encontrado", "copie .env.example para .env e preencha os valores")

    obrigatorias = [
        ("FOOTBALL_DATA_API_KEY", "Token da Football-Data.org"),
        ("GCP_PROJECT_ID", "ID do projeto GCP"),
        ("BIGQUERY_DATASET_RAW", "Dataset raw no BigQuery"),
    ]

    for var, descricao in obrigatorias:
        valor = os.getenv(var, "")
        if valor and valor not in ("seu_token_aqui", "seu-projeto-gcp"):
            ok(f"{var} definida", descricao)
        else:
            falha(f"{var} não definida ou com valor padrão", f"configure em .env — {descricao}")


def verificar_bigquery() -> None:
    """Verifica conectividade com BigQuery."""
    print(f"\n{NEGRITO}Google Cloud / BigQuery{RESET}")

    try:
        from google.cloud import bigquery  # noqa: PLC0415
    except ImportError:
        falha("google-cloud-bigquery instalado", "pip install google-cloud-bigquery")
        return

    ok("google-cloud-bigquery instalado")

    project_id = os.getenv("GCP_PROJECT_ID", "")
    if not project_id:
        falha("Conectividade BigQuery", "GCP_PROJECT_ID não definido")
        return

    try:
        client = bigquery.Client(project=project_id)
        datasets = list(client.list_datasets())
        ok(f"Conectado ao projeto {project_id}", f"{len(datasets)} dataset(s) encontrado(s)")

        dataset_raw = os.getenv("BIGQUERY_DATASET_RAW", "raw")
        dataset_ids = [d.dataset_id for d in datasets]
        if dataset_raw in dataset_ids:
            ok(f"Dataset '{dataset_raw}' existe")
        else:
            aviso(
                f"Dataset '{dataset_raw}' não encontrado",
                f"datasets disponíveis: {dataset_ids or 'nenhum'}",
            )
    except Exception as exc:
        falha("Conectividade BigQuery", str(exc))


def verificar_api_football() -> None:
    """Verifica acesso à API Football-Data.org."""
    print(f"\n{NEGRITO}API Football-Data.org{RESET}")

    try:
        import requests  # noqa: PLC0415
    except ImportError:
        falha("requests instalado", "pip install requests")
        return

    ok("requests instalado")

    api_key = os.getenv("FOOTBALL_DATA_API_KEY", "")
    if not api_key or api_key == "seu_token_aqui":
        falha("Token da API configurado", "defina FOOTBALL_DATA_API_KEY no .env")
        return

    try:
        resposta = requests.get(
            "https://api.football-data.org/v4/competitions",
            headers={"X-Auth-Token": api_key},
            timeout=10,
        )
        if resposta.status_code == 200:
            dados = resposta.json()
            total = dados.get("count", "?")
            ok("Acesso à API confirmado", f"{total} competições disponíveis")
        elif resposta.status_code == 400:
            falha("Acesso à API", f"HTTP {resposta.status_code} — token inválido")
        else:
            falha("Acesso à API", f"HTTP {resposta.status_code}")
    except requests.exceptions.ConnectionError:
        falha("Acesso à API", "sem conexão com a internet")
    except requests.exceptions.Timeout:
        falha("Acesso à API", "timeout — tente novamente")


def verificar_dbt_profile() -> None:
    """Verifica se o perfil dbt está configurado."""
    print(f"\n{NEGRITO}dbt{RESET}")

    profile_path = os.path.expanduser("~/.dbt/profiles.yml")
    if os.path.exists(profile_path):
        ok("~/.dbt/profiles.yml encontrado")
    else:
        falha(
            "~/.dbt/profiles.yml não encontrado",
            "copie dbt/profiles.yml.template para ~/.dbt/profiles.yml e configure",
        )

    dbt_dir = os.path.exists("dbt")
    if dbt_dir:
        ok("Diretório dbt/ existe no repositório")
    else:
        aviso("Diretório dbt/ não existe ainda", "será criado ao inicializar o projeto dbt")


def main() -> None:
    """Executa todas as verificações e imprime o resumo."""
    print(f"{NEGRITO}=== Verificação de Dependências — Football Analytics ==={RESET}")

    verificar_env_vars()
    verificar_bigquery()
    verificar_api_football()
    verificar_dbt_profile()

    total = len(resultados)
    aprovados = sum(1 for _, passou, _ in resultados if passou)
    reprovados = total - aprovados

    print(f"\n{NEGRITO}Resumo{RESET}")
    print(f"  {VERDE}✓ {aprovados}/{total}{RESET} verificações aprovadas")

    if reprovados > 0:
        print(f"  {VERMELHO}✗ {reprovados}/{total}{RESET} verificações com falha")
        print(f"\n{AMARELO}Corrija os itens acima antes de iniciar o desenvolvimento.{RESET}")
        sys.exit(1)
    else:
        print(f"\n{VERDE}{NEGRITO}Ambiente pronto para desenvolvimento!{RESET}")


if __name__ == "__main__":
    main()
