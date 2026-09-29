"""Logica verificarilor fara I/O: cererile, interpretarea raspunsului si cota din headere."""

from __future__ import annotations

from typing import Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import AwareDatetime

from ..erori import EroareTimeoutVerificare, EroareVerificare
from ..modele import Baza, Cota, Limite, ReferintaVerificare, VerificareFinala, VerificareInCurs
from ..tipuri import TipVerificare
from ..validare import TintaVerificare
from .cereri import CerereHttp
from .raspunsuri import Raspuns, decodeaza

CALE = "/api/public/v1/verificare"
INTERVAL_IMPLICIT_MS = 3_000
INTERVAL_MINIM_MS = 2_000
TIMEOUT_IMPLICIT_MS = 300_000

Referinta = VerificareInCurs | ReferintaVerificare


class _CorpInCurs(Baza):
    tip: TipVerificare
    query: str
    status: Literal["processing"]
    request_id: str | None = None
    queued_at: AwareDatetime | None = None
    poll_url: str | None = None
    hint: str | None = None


class _CorpEsuat(Baza):
    tip: TipVerificare
    query: str
    status: Literal["error"]
    error: str
    hint: str | None = None


def cerere_porneste(t: TintaVerificare) -> CerereHttp:
    corp: dict[str, object] = {"tip": t.tip.value, "query": t.query}
    if t.serie_sasiu:
        corp["serieSasiu"] = t.serie_sasiu
    if t.callback_url:
        corp["callbackUrl"] = t.callback_url
    return CerereHttp("POST", CALE, False, corp=corp)


def cerere_rezultat(ref: Referinta) -> CerereHttp:
    return CerereHttp(
        "GET",
        CALE,
        True,
        {
            "tip": ref.tip.value,
            "query": ref.query,
            "serieSasiu": ref.serie_sasiu if ref.tip is TipVerificare.ROVINIETA and ref.serie_sasiu else None,
            "since": str(ref.since) if ref.since is not None else None,
        },
    )


def _intreg(valoare: str | None) -> int | None:
    if valoare is None:
        return None
    text = valoare.strip()
    return int(text) if text.isascii() and text.isdigit() else None


def limite_din(r: Raspuns) -> Limite | None:
    """Cat mai ai din cota, din headerele `X-RateLimit-*`; None daca lipseste vreunul."""
    valori = [
        _intreg(r.header(nume))
        for nume in (
            "x-ratelimit-limit-day",
            "x-ratelimit-remaining-day",
            "x-ratelimit-limit-month",
            "x-ratelimit-remaining-month",
        )
    ]
    if any(v is None for v in valori):
        return None
    zi_limita, zi_ramase, luna_limita, luna_ramase = (v or 0 for v in valori)
    return Limite(zi=Cota(limita=zi_limita, ramase=zi_ramase), luna=Cota(limita=luna_limita, ramase=luna_ramase))


def since_din_poll_url(poll_url: str | None) -> int | None:
    """Citeste `since` din `pollUrl`, ca pollingul sa foloseasca ceasul serverului."""
    if not poll_url or "?" not in poll_url:
        return None
    valoare = _intreg(parse_qs(urlsplit(poll_url).query).get("since", [None])[0])
    return valoare if valoare else None


def interpreteaza(
    r: Raspuns, serie_sasiu: str | None, since_implicit: int | None, acum_ms: int
) -> VerificareFinala | VerificareInCurs:
    limite = limite_din(r)
    status = r.corp.get("status") if isinstance(r.corp, dict) else None
    if status == "error":
        esuat = decodeaza(_CorpEsuat, r)
        raise EroareVerificare(esuat.error, cod="VERIFICARE_ESUATA", hint=esuat.hint, raspuns=r.corp)
    if status == "processing":
        c = decodeaza(_CorpInCurs, r)
        since = since_din_poll_url(c.poll_url)
        if since is None:
            since = since_implicit if since_implicit is not None else acum_ms
        return VerificareInCurs(
            tip=c.tip,
            query=c.query,
            serie_sasiu=serie_sasiu if c.tip is TipVerificare.ROVINIETA else None,
            since=since,
            request_id=c.request_id,
            queued_at=c.queued_at,
            hint=c.hint,
            limite=limite,
        )
    final = decodeaza(VerificareFinala, r)
    return final.model_copy(update={"limite": limite}) if limite else final


def eroare_depasit(ref: Referinta, timeout_ms: float) -> EroareTimeoutVerificare:
    return EroareTimeoutVerificare(
        f"Verificarea {ref.tip.value} pentru {ref.query} nu s-a finalizat in {round(timeout_ms / 1000)} secunde.",
        cod="TIMEOUT_VERIFICARE",
    )
