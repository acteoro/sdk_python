"""Teste pe API-ul real. Configurarea sta in .env.e2e (vezi .env.e2e.example).

Testele care costa (cota, verificari pe surse) ruleaza doar cu flag explicit.
"""

from __future__ import annotations

import os
from pathlib import Path

from verificrca import URL_IMPLICIT, VerificRca


def _incarca_env(cale: Path) -> None:
    if not cale.is_file():
        return
    for linie in cale.read_text(encoding="utf-8").splitlines():
        linie = linie.strip()
        if not linie or linie.startswith("#") or "=" not in linie:
            continue
        cheie, valoare = linie.split("=", 1)
        os.environ.setdefault(cheie.strip(), valoare.strip())


_incarca_env(Path(__file__).resolve().parent.parent / ".env.e2e")


def _env(nume: str) -> str | None:
    return (os.environ.get(nume) or "").strip() or None


CHEIE = _env("VERIFICRCA_API_KEY")
BASE_URL = _env("VERIFICRCA_BASE_URL")
NUMAR = _env("VERIFICRCA_E2E_NUMAR")
VIN = _env("VERIFICRCA_E2E_VIN")
CU_VERIFICARI = os.environ.get("VERIFICRCA_E2E_VERIFICARI") == "1"
CU_FLOTA = os.environ.get("VERIFICRCA_E2E_FLOTA") == "1"


def client(api_key: str | None = CHEIE) -> VerificRca:
    return VerificRca(api_key=api_key, base_url=BASE_URL or URL_IMPLICIT, user_agent="e2e")
