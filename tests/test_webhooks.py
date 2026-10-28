import json
from collections.abc import Iterator

import httpx
import pytest

from acteo import (
    HEADER_CHEIE,
    EroareWebhook,
    StatusWebhook,
    TipVerificare,
    WebhookDocumentExpira,
    WebhookTest,
    parseaza_webhook_rezultat,
    verifica_webhook_notificare,
)

CHEIE = "whsec_test_0123456789"
EXPIRA = {
    "event": "document.expira",
    "id": "livrare_1",
    "vehicul": {"id": "veh_1", "numarInmatriculare": "B123ABC", "serieSasiu": None},
    "document": "rca",
    "expiraLa": "2026-10-13T00:00:00.000Z",
    "zileRamase": 14,
    "prag": 14,
    "trimisLa": "2026-09-29T07:00:00.000Z",
}
TEST = {
    "event": "webhook.test",
    "id": "test_1",
    "mesaj": "Webhook configurat corect.",
    "trimisLa": "2026-09-29T07:00:00Z",
}
REZULTAT = {
    "requestId": "req_1",
    "tip": "rca",
    "query": "B123ABC",
    "serieSasiu": None,
    "status": "valid",
    "result": {
        "tip": "rca",
        "query": "B123ABC",
        "numarInmatriculare": "B123ABC",
        "serieSasiu": None,
        "checkedAt": "2026-09-29T08:00:00.000Z",
        "status": "valid",
        "expiresAt": "2027-03-01T00:00:00.000Z",
        "requestId": "req_1",
    },
    "checkedAt": "2026-09-29T08:00:00.000Z",
}


class HeadereCaWerkzeug:
    """Imita `werkzeug.datastructures.Headers`: get() case-insensitive, iterarea da tupluri."""

    def __init__(self, perechi: list[tuple[str, str]]) -> None:
        self._perechi = perechi

    def get(self, cheie: str, default: object = None) -> object:
        for k, v in self._perechi:
            if k.lower() == cheie.lower():
                return v
        return default

    def items(self) -> list[tuple[str, str]]:
        return list(self._perechi)

    def __iter__(self) -> Iterator[tuple[str, str]]:
        return iter(self._perechi)


@pytest.mark.parametrize(
    "corp", [json.dumps(EXPIRA), json.dumps(EXPIRA).encode(), bytearray(json.dumps(EXPIRA).encode()), EXPIRA]
)
def test_document_expira_din_orice_corp(corp: object) -> None:
    ev = verifica_webhook_notificare(corp, {"x-verificrca-key": CHEIE}, CHEIE)  # type: ignore[arg-type]
    assert isinstance(ev, WebhookDocumentExpira)
    assert (ev.document, ev.zile_ramase, ev.vehicul.numar_inmatriculare) == (TipVerificare.RCA, 14, "B123ABC")


@pytest.mark.parametrize(
    "headere",
    [
        {"X-Verificrca-Key": CHEIE},
        {"X-VERIFICRCA-KEY": CHEIE},
        {"x-verificrca-key": [CHEIE]},
        {"HTTP_X_VERIFICRCA_KEY": CHEIE, "CONTENT_TYPE": "application/json"},
        httpx.Headers({"x-verificrca-key": CHEIE}),
        HeadereCaWerkzeug([("Content-Type", "application/json"), ("X-Verificrca-Key", CHEIE)]),
    ],
)
def test_headere_din_framework_uri(headere: object) -> None:
    assert isinstance(verifica_webhook_notificare(TEST, headere, CHEIE), WebhookTest)


def test_eveniment_test() -> None:
    ev = verifica_webhook_notificare(json.dumps(TEST), {HEADER_CHEIE: CHEIE}, CHEIE)
    assert isinstance(ev, WebhookTest)
    assert ev.mesaj == "Webhook configurat corect."


def cod_eroare(corp: object, headere: object, cheie: str) -> str | None:
    with pytest.raises(EroareWebhook) as info:
        verifica_webhook_notificare(corp, headere, cheie)  # type: ignore[arg-type]
    return info.value.cod


def test_cheie_neconfigurata() -> None:
    assert cod_eroare(TEST, {HEADER_CHEIE: CHEIE}, "") == "CHEIE_NECONFIGURATA"


@pytest.mark.parametrize("headere", [{}, {HEADER_CHEIE: "whsec_alta"}, {HEADER_CHEIE: ""}, {HEADER_CHEIE: CHEIE + "x"}])
def test_cheie_invalida(headere: dict[str, str]) -> None:
    assert cod_eroare(TEST, headere, CHEIE) == "CHEIE_INVALIDA"


def test_cheie_invalida_nu_citeste_corpul() -> None:
    assert cod_eroare("{nu e json", {}, CHEIE) == "CHEIE_INVALIDA"


@pytest.mark.parametrize("corp", ["{nu e json", b"\xfa\xfb\xfc", ""])
def test_json_invalid(corp: object) -> None:
    assert cod_eroare(corp, {HEADER_CHEIE: CHEIE}, CHEIE) == "JSON_INVALID"


@pytest.mark.parametrize(
    "corp",
    [
        {"event": "altceva"},
        [1, 2],
        {**EXPIRA, "document": "casco"},
        {**EXPIRA, "trimisLa": "2026-09-29T07:00:00"},
        {k: v for k, v in EXPIRA.items() if k != "vehicul"},
    ],
)
def test_payload_invalid(corp: object) -> None:
    assert cod_eroare(corp, {HEADER_CHEIE: CHEIE}, CHEIE) == "PAYLOAD_INVALID"


def test_payload_invalid_spune_campul() -> None:
    corp = {k: v for k, v in EXPIRA.items() if k != "zileRamase"}
    with pytest.raises(EroareWebhook) as info:
        verifica_webhook_notificare(corp, {HEADER_CHEIE: CHEIE}, CHEIE)
    assert info.value.mesaj == "Payload webhook invalid: zileRamase: lipseste"
    assert info.value.raspuns == corp


def test_rezultat_valid() -> None:
    r = parseaza_webhook_rezultat(json.dumps(REZULTAT))
    assert r.status is StatusWebhook.VALID
    assert r.result is not None
    assert r.result.request_id == "req_1"


def test_rezultat_cu_eroare() -> None:
    corp = {**REZULTAT, "status": "error", "result": None, "checkedAt": None, "error": "Sursa nu raspunde."}
    r = parseaza_webhook_rezultat(corp)
    assert (r.status, r.result, r.error) == (StatusWebhook.ERROR, None, "Sursa nu raspunde.")


def test_rezultat_invalid() -> None:
    with pytest.raises(EroareWebhook) as info:
        parseaza_webhook_rezultat(b"[]")
    assert info.value.cod == "PAYLOAD_INVALID"
    with pytest.raises(EroareWebhook) as info:
        parseaza_webhook_rezultat("nu")
    assert info.value.cod == "JSON_INVALID"
