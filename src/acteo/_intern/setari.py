"""Configuratia validata a clientului. Constructorul nu face cereri pe retea."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, fields
from urllib.parse import urlsplit

from .._versiune import URL_IMPLICIT, URL_IMPLICIT_LEGACY, VERSIUNE_SDK
from ..erori import EroareConfigurare


@dataclass(frozen=True)
class SetariRetry:
    """Reincercarile pentru erori trecatoare: backoff exponential (x2) cu jitter.

    `incercari` = numarul maxim de reincercari dupa prima cerere; `intarziere_initiala_ms` = prima
    pauza; `intarziere_maxima_ms` = plafonul unei singure pauze.
    """

    incercari: int = 3
    intarziere_initiala_ms: int = 500
    intarziere_maxima_ms: int = 10_000


@dataclass(frozen=True)
class Setari:
    api_key: str
    base_url: str
    timeout_ms: float
    retry: SetariRetry | None
    user_agent: str


@dataclass(frozen=True)
class Profil:
    """Ce difera intre clientul `Acteo` si cel legacy `VerificRca`."""

    url_implicit: str
    variabile_cheie: tuple[str, ...]
    """Variabilele de mediu citite pentru cheie, in ordine."""
    agent: str
    """Prefixul din `User-Agent`."""
    unde_cheie: str
    """Unde se genereaza cheia, aratat cand lipseste."""


PROFIL_ACTEO = Profil(
    url_implicit=URL_IMPLICIT,
    variabile_cheie=("ACTEO_API_KEY", "VERIFICRCA_API_KEY"),
    agent="acteo-sdk-python",
    unde_cheie="https://app.acteo.ro/api/chei",
)
PROFIL_LEGACY = Profil(
    url_implicit=URL_IMPLICIT_LEGACY,
    variabile_cheie=("VERIFICRCA_API_KEY",),
    agent="verificrca-sdk-python",
    unde_cheie="https://www.verificrca.ro/dashboard/api",
)


def _cheie_din_mediu(profil: Profil) -> str:
    for nume in profil.variabile_cheie:
        valoare = os.environ.get(nume, "").strip()
        if valoare:
            return valoare
    return ""


_CHEI_RETRY = tuple(f.name for f in fields(SetariRetry))


def _verifica_retry(retry: SetariRetry) -> SetariRetry:
    for nume in _CHEI_RETRY:
        valoare = getattr(retry, nume)
        if isinstance(valoare, bool) or not isinstance(valoare, int) or valoare < 0:
            raise EroareConfigurare(f"`retry.{nume}` trebuie sa fie un numar intreg pozitiv sau zero.")
    return retry


def _construieste_retry(retry: SetariRetry | Mapping[str, int] | bool | None) -> SetariRetry | None:
    if retry is False:
        return None
    if retry is None or retry is True:
        return SetariRetry()
    if isinstance(retry, SetariRetry):
        return _verifica_retry(retry)
    if isinstance(retry, Mapping):
        necunoscute = sorted(str(k) for k in retry if k not in _CHEI_RETRY)
        if necunoscute:
            raise EroareConfigurare(f"Optiuni `retry` necunoscute: {', '.join(necunoscute)}.")
        return _verifica_retry(SetariRetry(**retry))
    raise EroareConfigurare("`retry` trebuie sa fie SetariRetry, un dict, True sau False.")


def construieste_setari(
    *,
    api_key: str | None,
    base_url: str,
    timeout_ms: float,
    retry: SetariRetry | Mapping[str, int] | bool | None,
    user_agent: str | None,
    profil: Profil = PROFIL_LEGACY,
) -> Setari:
    cheie = (api_key if api_key is not None else _cheie_din_mediu(profil)).strip()
    if not cheie:
        raise EroareConfigurare(
            f"Lipseste cheia API. Trimite `api_key` sau seteaza variabila de mediu {profil.variabile_cheie[0]}.",
            hint=f"Cheia se genereaza din {profil.unde_cheie}",
        )
    if not cheie.isascii() or any(c.isspace() or not c.isprintable() for c in cheie):
        raise EroareConfigurare("Cheia API contine caractere neacceptate (spatii sau caractere non-ASCII).")
    if not 16 <= len(cheie) <= 128:
        raise EroareConfigurare("Cheia API are un format invalid (intre 16 si 128 de caractere).")

    try:
        parti = urlsplit(base_url)
        valid = parti.scheme in ("http", "https") and bool(parti.hostname)
    except (ValueError, AttributeError):
        valid = False
    if not valid:
        raise EroareConfigurare(f"`base_url` invalid: {base_url}")

    if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, (int, float)) or not timeout_ms > 0:
        raise EroareConfigurare("`timeout_ms` trebuie sa fie pozitiv.")

    if user_agent and not (user_agent.isascii() and user_agent.isprintable()):
        raise EroareConfigurare("`user_agent` contine caractere neacceptate (doar ASCII tiparibil).")

    agent = f"{profil.agent}/{VERSIUNE_SDK}" + (f" {user_agent}" if user_agent else "")
    return Setari(cheie, base_url.rstrip("/"), timeout_ms, _construieste_retry(retry), agent)
