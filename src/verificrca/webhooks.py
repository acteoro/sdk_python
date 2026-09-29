"""Citirea webhook-urilor trimise de verificrca: rezultatul unei verificari si notificarile de expirare."""

from __future__ import annotations

import hmac
import json
from collections.abc import Mapping
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from ._intern.decodare import cale_eroare
from .erori import EroareWebhook
from .modele import WebhookDocumentExpira, WebhookRezultat, WebhookTest

HEADER_CHEIE = "x-verificrca-key"
"""Headerul cu cheia de webhook a contului (`whsec_...`)."""
HEADER_EVENIMENT = "x-verificrca-event"
"""Headerul cu numele evenimentului (`document.expira`, `webhook.test`)."""

M = TypeVar("M", bound=BaseModel)
Corp = str | bytes | bytearray | Mapping[str, Any]


def _parseaza_corp(corp: object) -> object:
    if not isinstance(corp, (str, bytes, bytearray)):
        return corp
    try:
        return json.loads(corp)
    except ValueError as e:
        raise EroareWebhook("Corpul webhook-ului nu e JSON valid.", cod="JSON_INVALID") from e


def _decodeaza(model: type[M], date: object) -> M:
    try:
        return model.model_validate(date)
    except ValidationError as e:
        raise EroareWebhook(f"Payload webhook invalid: {cale_eroare(e)}", cod="PAYLOAD_INVALID", raspuns=date) from e


def _prima_valoare(valoare: object) -> str | None:
    if isinstance(valoare, str):
        return valoare
    if isinstance(valoare, bytes):
        return valoare.decode("latin-1")
    if isinstance(valoare, (list, tuple)) and valoare:
        return _prima_valoare(valoare[0])
    return None


def _citeste_header(headere: Any, nume: str) -> str | None:
    """Cauta headerul in orice forma: dict, headere case-insensitive, WSGI/Django META."""
    meta = "HTTP_" + nume.upper().replace("-", "_")
    variante = (nume, nume.title(), meta)
    get = getattr(headere, "get", None)
    if callable(get):
        for cheie in variante:
            valoare = _prima_valoare(get(cheie))
            if valoare:
                return valoare
    items = getattr(headere, "items", None)
    if callable(items):
        for cheie, valoare in items():
            if isinstance(cheie, str) and cheie.lower() in (nume, meta.lower()):
                gasita = _prima_valoare(valoare)
                if gasita:
                    return gasita
    return None


def parseaza_webhook_rezultat(corp: Corp) -> WebhookRezultat:
    """Citeste rezultatul trimis la `callback_url` dupa o verificare.

    Foloseste un `callback_url` pe HTTPS, greu de ghicit (de exemplu cu un token secret in cale),
    si potriveste `request_id` cu cel primit la `porneste()` inainte sa ai incredere in continut.
    Arunca `EroareWebhook` (`JSON_INVALID`, `PAYLOAD_INVALID`).
    """
    return _decodeaza(WebhookRezultat, _parseaza_corp(corp))


def verifica_webhook_notificare(corp: Corp, headere: Any, cheie: str) -> WebhookDocumentExpira | WebhookTest:
    """Verifica si citeste o notificare `document.expira` sau un `webhook.test`.

    Cheia vine in headerul `X-Verificrca-Key` si e comparata in timp constant cu cea din dashboard.
    `headere` poate fi `request.headers` (Django, Flask, FastAPI/Starlette), `request.META` sau un dict.
    Arunca `EroareWebhook` (`CHEIE_NECONFIGURATA`, `CHEIE_INVALIDA`, `JSON_INVALID`, `PAYLOAD_INVALID`).
    """
    if not cheie:
        raise EroareWebhook("Lipseste cheia de webhook (argumentul `cheie`).", cod="CHEIE_NECONFIGURATA")
    primita = _citeste_header(headere, HEADER_CHEIE)
    if not primita or not hmac.compare_digest(
        primita.encode("utf-8", "surrogatepass"), cheie.encode("utf-8", "surrogatepass")
    ):
        raise EroareWebhook("Cheia din headerul X-Verificrca-Key lipseste sau nu se potriveste.", cod="CHEIE_INVALIDA")
    date = _parseaza_corp(corp)
    eveniment = date.get("event") if isinstance(date, Mapping) else None
    if eveniment == "document.expira":
        return _decodeaza(WebhookDocumentExpira, date)
    if eveniment == "webhook.test":
        return _decodeaza(WebhookTest, date)
    raise EroareWebhook("Payload webhook invalid: eveniment necunoscut.", cod="PAYLOAD_INVALID", raspuns=date)
