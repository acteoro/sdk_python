import json

import pytest

from tests.conftest import CHEIE, setari_test
from verificrca import (
    EroareAutentificare,
    EroareConflict,
    EroareHttp,
    EroareInterzis,
    EroareLimita,
    EroareNegasit,
    EroarePlanInactiv,
    EroareRaspunsInvalid,
    EroareServer,
    EroareValidare,
    Vehicul,
)
from verificrca._intern.cereri import CerereHttp, pregateste
from verificrca._intern.raspunsuri import (
    Raspuns,
    citeste_retry_after,
    construieste_raspuns,
    decodeaza,
    eroare_din_raspuns,
)

ACUM = 1_700_000_000_000


def corp(**kw: object) -> bytes:
    return json.dumps(kw).encode()


def test_raspuns_2xx_cu_json() -> None:
    r = construieste_raspuns(200, {"x-a": "1"}, corp(a=1), ACUM)
    assert (r.status, r.corp, r.header("X-A")) == (200, {"a": 1}, "1")


def test_raspuns_2xx_gol() -> None:
    assert construieste_raspuns(204, {}, b"", ACUM).corp is None


def test_raspuns_2xx_care_nu_e_json() -> None:
    with pytest.raises(EroareRaspunsInvalid) as info:
        construieste_raspuns(200, {}, b"<html>", ACUM)
    assert info.value.mesaj == "API-ul a raspuns cu un corp care nu e JSON."
    assert info.value.raspuns == "<html>"
    assert isinstance(info.value.__cause__, ValueError)


def test_raspuns_2xx_non_utf8() -> None:
    with pytest.raises(EroareRaspunsInvalid):
        construieste_raspuns(200, {}, b"\xfa\xfb\xfc", ACUM)


def test_non_2xx_care_nu_e_json_pastreaza_textul() -> None:
    with pytest.raises(EroareServer) as info:
        construieste_raspuns(502, {}, b"Bad gateway \xff", ACUM)
    assert info.value.mesaj == "Cererea a esuat cu HTTP 502."
    assert info.value.raspuns == "Bad gateway \ufffd"


@pytest.mark.parametrize(
    ("status", "clasa"),
    [
        (400, EroareValidare),
        (401, EroareAutentificare),
        (402, EroarePlanInactiv),
        (403, EroareInterzis),
        (404, EroareNegasit),
        (409, EroareConflict),
        (429, EroareLimita),
        (500, EroareServer),
        (503, EroareServer),
        (302, EroareHttp),
        (418, EroareHttp),
    ],
)
def test_mapare_status(status: int, clasa: type) -> None:
    e = eroare_din_raspuns(status, {}, {"error": "Mesaj API", "hint": "Indicatie", "code": "COD"}, ACUM)
    assert type(e) is clasa
    assert (e.mesaj, e.status, e.hint, e.cod) == ("Mesaj API", status, "Indicatie", "COD")


def test_corp_de_eroare_cu_tipuri_gresite_e_ignorat() -> None:
    e = eroare_din_raspuns(404, {}, {"error": "x", "hint": 5}, ACUM)
    assert (e.mesaj, e.hint) == ("Cererea a esuat cu HTTP 404.", None)
    assert e.raspuns == {"error": "x", "hint": 5}


def test_400_cu_acceptate() -> None:
    e = eroare_din_raspuns(400, {}, {"error": "tip", "accepted": ["rca", "itp"]}, ACUM)
    assert isinstance(e, EroareValidare)
    assert e.acceptate == ["rca", "itp"]


def test_403_cu_limita() -> None:
    e = eroare_din_raspuns(403, {}, {"error": "Limita", "code": "LIMIT_ATINS", "limita": 5}, ACUM)
    assert isinstance(e, EroareInterzis)
    assert e.limita == 5


def test_429_cota() -> None:
    e = eroare_din_raspuns(429, {"retry-after": "30"}, {"error": "Cota", "dailyUsage": "300/300"}, ACUM)
    assert isinstance(e, EroareLimita)
    assert (e.cod, e.retry_after_ms, e.utilizare_zi, e.utilizare_luna) == ("COTA_ATINSA", 30_000, "300/300", None)


def test_429_throttle_fara_corp() -> None:
    e = eroare_din_raspuns(429, {}, None, ACUM)
    assert isinstance(e, EroareLimita)
    assert (e.cod, e.retry_after_ms) == ("PREA_MULTE_CERERI", None)


def test_429_cod_din_corp_are_prioritate() -> None:
    e = eroare_din_raspuns(429, {}, {"error": "Flota", "code": "LIMITA_FLOTA_ATINSA", "dailyUsage": "5/5"}, ACUM)
    assert e.cod == "LIMITA_FLOTA_ATINSA"


def test_retry_after() -> None:
    assert citeste_retry_after({"retry-after": "2"}, ACUM) == 2000
    assert citeste_retry_after({"retry-after": "1.5"}, ACUM) == 1500
    assert citeste_retry_after({"retry-after": "-3"}, ACUM) == 0
    assert citeste_retry_after({}, ACUM) is None
    assert citeste_retry_after({"retry-after": "curand"}, ACUM) is None
    assert citeste_retry_after({"retry-after": "inf"}, ACUM) is None
    data = "Tue, 14 Nov 2023 22:13:30 GMT"  # ACUM + 10 s
    assert citeste_retry_after({"retry-after": data}, ACUM) == 10_000


def test_decodeaza() -> None:
    r = Raspuns(200, {}, {"id": "x"})
    with pytest.raises(EroareRaspunsInvalid) as info:
        decodeaza(Vehicul, r)
    assert info.value.mesaj.startswith("Raspunsul API-ului nu are forma asteptata: ")
    assert info.value.status == 200
    with pytest.raises(EroareRaspunsInvalid) as info:
        decodeaza(Vehicul, Raspuns(200, {}, [1]))
    assert info.value.mesaj == "Raspunsul API-ului nu are forma asteptata: corpul nu e un obiect JSON."


def test_pregateste_get() -> None:
    p = pregateste(
        setari_test(), CerereHttp("GET", "/api/public/v1/verificare", True, {"tip": "rca", "serieSasiu": None})
    )
    assert (p.metoda, p.url, p.params, p.continut) == (
        "GET",
        "https://api.example.com/api/public/v1/verificare",
        {"tip": "rca"},
        None,
    )
    assert p.headere["Authorization"] == f"Bearer {CHEIE}"
    assert p.headere["Accept"] == "application/json"
    assert p.headere["User-Agent"].startswith("verificrca-sdk-python/")
    assert "Content-Type" not in p.headere


def test_pregateste_post() -> None:
    p = pregateste(setari_test(), CerereHttp("POST", "/x", False, corp={"query": "B123ABC", "nume": "\u0219"}))
    assert p.headere["Content-Type"] == "application/json"
    assert p.continut is not None
    assert json.loads(p.continut) == {"query": "B123ABC", "nume": "\u0219"}


def test_pregateste_text_non_utf8() -> None:
    with pytest.raises(EroareValidare) as info:
        pregateste(setari_test(), CerereHttp("POST", "/x", False, corp={"callbackUrl": "https://example.com/\ud800"}))
    assert (info.value.cod, info.value.mesaj) == (
        "VALIDARE_LOCALA",
        "Datele trimise contin text care nu e UTF-8 valid.",
    )
