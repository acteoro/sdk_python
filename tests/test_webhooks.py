import json
from collections.abc import Iterator
from datetime import datetime, timezone

import httpx
import pytest

from acteo import (
    HEADER_CHEIE,
    HEADER_EVENIMENT,
    EroareWebhook,
    StatusWebhook,
    TipVerificare,
    WebhookAsigurareSchimbare,
    WebhookDocumentExpira,
    WebhookDosarEveniment,
    WebhookDosarTermen,
    WebhookFirmaDosar,
    WebhookFirmaSchimbare,
    WebhookMarcaExpira,
    WebhookMarcaSchimbare,
    WebhookTermenExpira,
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
    ev = verifica_webhook_notificare(corp, {"x-acteo-key": CHEIE}, CHEIE)  # type: ignore[arg-type]
    assert isinstance(ev, WebhookDocumentExpira)
    assert (ev.document, ev.zile_ramase, ev.vehicul.numar_inmatriculare) == (TipVerificare.RCA, 14, "B123ABC")


@pytest.mark.parametrize(
    "headere",
    [
        {"X-Acteo-Key": CHEIE},
        {"X-ACTEO-KEY": CHEIE},
        {"x-acteo-key": [CHEIE]},
        {"HTTP_X_ACTEO_KEY": CHEIE, "CONTENT_TYPE": "application/json"},
        httpx.Headers({"x-acteo-key": CHEIE}),
        HeadereCaWerkzeug([("Content-Type", "application/json"), ("X-Acteo-Key", CHEIE)]),
        # Numele vechi, citit doar cand lipseste cel nou.
        {"X-Verificrca-Key": CHEIE},
        {"HTTP_X_VERIFICRCA_KEY": CHEIE},
        httpx.Headers({"x-verificrca-key": CHEIE}),
        HeadereCaWerkzeug([("X-Verificrca-Key", CHEIE)]),
    ],
)
def test_headere_din_framework_uri(headere: object) -> None:
    assert isinstance(verifica_webhook_notificare(TEST, headere, CHEIE), WebhookTest)


def test_numele_headerelor() -> None:
    assert (HEADER_CHEIE, HEADER_EVENIMENT) == ("x-acteo-key", "x-acteo-event")


def test_headerul_nou_are_prioritate_fata_de_cel_vechi() -> None:
    # O cheie veche corecta nu salveaza una noua gresita.
    headere = {"X-Acteo-Key": "whsec_gresit", "X-Verificrca-Key": CHEIE}
    assert cod_eroare(TEST, headere, CHEIE) == "CHEIE_INVALIDA"


def test_mesajul_cheii_invalide_numeste_headerul_nou() -> None:
    with pytest.raises(EroareWebhook, match="X-Acteo-Key"):
        verifica_webhook_notificare(TEST, {}, CHEIE)


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


COMUN = {"id": "liv_2", "trimisLa": "2026-10-30T10:00:00.000Z"}
EVENIMENTE: list[tuple[dict[str, object], type]] = [
    (
        {
            "event": "dosar.eveniment",
            **COMUN,
            "dosar": {"id": "d1", "numar": "1234/3/2024", "eticheta": None},
            "eveniment": {"tip": "termen_nou", "descriere": "Termen nou", "institutie": "Tribunalul Bucuresti"},
        },
        WebhookDosarEveniment,
    ),
    (
        {
            "event": "dosar.termen",
            **COMUN,
            "dosar": {"id": "d1", "numar": "1234/3/2024", "eticheta": "Litigiu"},
            "sedinta": {"data": "2026-11-02T00:00:00.000Z", "ora": "09:00", "institutie": None, "complet": "C1"},
            "zileRamase": 3,
        },
        WebhookDosarTermen,
    ),
    (
        {
            "event": "firma.schimbare",
            **COMUN,
            "firma": {"id": "f1", "denumire": "Exemplu SRL"},
            "schimbari": [
                {"camp": "platitor_tva", "valoareVeche": "nu", "valoareNoua": "da", "dataEfect": "2026-11-01"}
            ],
        },
        WebhookFirmaSchimbare,
    ),
    (
        {
            "event": "firma.dosar",
            **COMUN,
            "firma": {"id": "f1", "denumire": "Exemplu SRL"},
            "dosar": {
                "numar": "99/2/2026",
                "institutie": "Tribunalul Cluj",
                "calitateParte": "Parat",
                "obiect": None,
                "categorie": None,
                "insolventa": None,
            },
        },
        WebhookFirmaDosar,
    ),
    (
        {
            "event": "marca.schimbare",
            **COMUN,
            "marca": {"id": "m1", "st13": "RO500000000000001", "nume": "EXEMPLU", "oficiu": "RO", "numarDepozit": "M1"},
            "schimbare": "reinnoita",
            "valoareVeche": "2026-11-01",
            "valoareNoua": "2036-11-01",
        },
        WebhookMarcaSchimbare,
    ),
    (
        {
            "event": "marca.expira",
            **COMUN,
            "marca": {"id": "m1", "st13": "EM500000000000001", "nume": "EXEMPLU", "oficiu": "EM", "numarDepozit": "1"},
            "expiraLa": "2027-01-01",
            "prag": "3l",
            "reinnoirePanaLa": None,
        },
        WebhookMarcaExpira,
    ),
    (
        {
            "event": "asigurare.schimbare",
            **COMUN,
            "persoana": {"id": "p1", "nume": "Ion Popescu"},
            "statut": "neasigurat",
            "areCard": None,
            "verificatLa": "2026-10-30T09:00:00.000Z",
        },
        WebhookAsigurareSchimbare,
    ),
    (
        {
            "event": "termen.expira",
            **COMUN,
            "termen": {
                "id": "t1",
                "categorie": "personale",
                "tip": "pasaport",
                "eticheta": "Pasaport",
                "al": None,
                "expiraLa": "2026-11-29",
            },
            "zileRamase": 30,
            "prag": 30,
        },
        WebhookTermenExpira,
    ),
]


@pytest.mark.parametrize(("corp", "model"), EVENIMENTE, ids=[str(e[0]["event"]) for e in EVENIMENTE])
def test_evenimentele_celorlalte_servicii(corp: dict[str, object], model: type) -> None:
    ev = verifica_webhook_notificare(json.dumps(corp), {"X-Acteo-Key": CHEIE}, CHEIE)
    assert isinstance(ev, model)
    assert ev.event == corp["event"]
    assert isinstance(ev.trimis_la, datetime)


def test_datele_iso_devin_datetime_cele_calendaristice_raman_text() -> None:
    termen = verifica_webhook_notificare(EVENIMENTE[1][0], {HEADER_CHEIE: CHEIE}, CHEIE)
    assert isinstance(termen, WebhookDosarTermen)
    assert termen.sedinta.data == datetime(2026, 11, 2, tzinfo=timezone.utc)
    assert termen.zile_ramase == 3
    marca = verifica_webhook_notificare(EVENIMENTE[5][0], {HEADER_CHEIE: CHEIE}, CHEIE)
    assert isinstance(marca, WebhookMarcaExpira)
    assert marca.expira_la == "2027-01-01"
    asigurare = verifica_webhook_notificare(EVENIMENTE[6][0], {HEADER_CHEIE: CHEIE}, CHEIE)
    assert isinstance(asigurare, WebhookAsigurareSchimbare)
    assert isinstance(asigurare.verificat_la, datetime)
    assert asigurare.are_card is None


@pytest.mark.parametrize(
    "corp",
    [
        {**EVENIMENTE[1][0], "zileRamase": 2},
        {**EVENIMENTE[4][0], "schimbare": "furata"},
        {**EVENIMENTE[6][0], "verificatLa": "2026-10-30"},
        {k: v for k, v in EVENIMENTE[7][0].items() if k != "termen"},
    ],
)
def test_evenimente_noi_invalide(corp: object) -> None:
    assert cod_eroare(corp, {HEADER_CHEIE: CHEIE}, CHEIE) == "PAYLOAD_INVALID"
