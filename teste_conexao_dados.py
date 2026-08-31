"""
Teste isolado: só verifica se dá pra buscar cotação (Yahoo Finance, via
yfinance) e provento oficial (B3, endpoint público) rodando num servidor
de nuvem (GitHub Actions) -- sem tocar em nada do app de verdade. Roda
sozinho, várias vezes por dia, por 1-2 semanas, e vai anotando o
resultado em resultados.csv.

Usa PETR4 só como ação de teste (bem líquida, sempre tem dado) -- não é
sobre a carteira real, é só pra ver se o SERVIDOR consegue falar com
Yahoo Finance e com a B3 sem ser bloqueado.
"""

from __future__ import annotations

import base64
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

TICKER_TESTE = "PETR4"

ARQUIVO_RESULTADOS = Path(__file__).parent / "resultados.csv"


def testar_yahoo_finance() -> tuple[bool, str]:
    try:
        import yfinance as yf

        hist = yf.Ticker(f"{TICKER_TESTE}.SA").history(period="5d")
        if hist is None or hist.empty:
            return False, "resposta vazia (sem dado, mas sem erro de rede)"
        ultimo_preco = hist["Close"].iloc[-1]
        return True, f"ok, ultimo fechamento: {ultimo_preco:.2f}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"[:200]


def testar_b3_publico() -> tuple[bool, str]:
    try:
        payload = json.dumps({"issuingCompany": TICKER_TESTE[:4], "language": "pt-br"})
        codificado = base64.b64encode(payload.encode()).decode()
        url = (
            "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/"
            f"CompanyCall/GetListedSupplementCompany/{codificado}"
        )
        cabecalhos = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://sistemaswebb3-listados.b3.com.br/listedCompaniesPage/main",
        }
        r = requests.get(url, headers=cabecalhos, timeout=12)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        dados = r.json()
        # A B3 às vezes devolve um objeto único, às vezes uma lista com um
        # objeto dentro -- o mesmo tratamento que o app de verdade usa
        # (core/b3_publico.py::_parsear_cash_dividends).
        item = dados[0] if isinstance(dados, list) and dados else dados
        if not isinstance(item, dict) or "cashDividends" not in item:
            return False, "resposta em formato inesperado"
        return True, f"ok, {len(item.get('cashDividends') or [])} proventos no retorno"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"[:200]


def main() -> None:
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    yahoo_ok, yahoo_detalhe = testar_yahoo_finance()
    b3_ok, b3_detalhe = testar_b3_publico()

    novo = not ARQUIVO_RESULTADOS.exists()
    with open(ARQUIVO_RESULTADOS, "a", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f, delimiter=";")
        if novo:
            escritor.writerow(
                ["data_hora_utc", "yahoo_finance_ok", "yahoo_finance_detalhe", "b3_ok", "b3_detalhe"]
            )
        escritor.writerow(
            [agora, "SIM" if yahoo_ok else "NAO", yahoo_detalhe, "SIM" if b3_ok else "NAO", b3_detalhe]
        )

    print(f"Yahoo Finance: {'OK' if yahoo_ok else 'FALHOU'} - {yahoo_detalhe}")
    print(f"B3 (proventos): {'OK' if b3_ok else 'FALHOU'} - {b3_detalhe}")


if __name__ == "__main__":
    main()
