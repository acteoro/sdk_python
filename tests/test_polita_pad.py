"""Verificarea politei PAD (`acteo.casa.pad`), pe clientul sincron `Acteo`."""

import json
from datetime import datetime
from typing import Any

import pytest

from acteo import (
    Acteo,
    Cota,
    EroareServer,
    EroareTimeoutVerificare,
    EroareValidare,
    EroareVerificare,
    Limite,
)
from tests.conftest import CHEIE, CeasFals, ServerFals, json_raspuns

# CNP sintetic, valid doar ca cifra de control. Nu apartine nimanui.
CNP = "1900101400012"
ID = "3f2c8a54-0000-4000-8000-000000000000"
COTA = {
    "X-RateLimit-Limit-Day": "50",
    "X-RateLimit-Remaining-Day": "49",
    "X-RateLimit-Limit-Month": "300",
    "X-RateLimit-Remaining-Month": "299",
}
BAZA: dict[str, Any] = {
    "requestId": ID,
    "cnpMascat": "1*********012",
    "judet": "Cluj",
    "localitate": "Cluj-Napoca",
    "laData": "2026-11-03",
}
PORNITA = {
    **BAZA,
    "status": "processing",
    "queuedAt": "2026-11-03T10:00:00.000Z",
    "pollUrl": f"GET /api/public/v1/polita-pad?id={ID}",
}
IN_CURS = {**BAZA, "status": "processing", "queuedAt": "2026-11-03T10:00:00.000Z"}
GATA = {
    **BAZA,
    "status": "done",
    "valabila": False,
    "serieNumar": None,
    "distribuitor": None,
    "verificatLa": "2026-11-03T10:02:00.000Z",
}
ESUATA = {**BAZA, "status": "error", "code": "UPSTREAM_CHANGED", "error": "Sursa s-a schimbat."}
CERERE: dict[str, Any] = {"cnp": CNP, "judet": "Cluj", "localitate": "Cluj-Napoca", "acord": True}

CERERI_GRESITE: list[tuple[str, dict[str, Any], str]] = [
    ("cnp gresit", {**CERERE, "cnp": "1900101400013"}, "cnp"),
    ("fara acord", {**CERERE, "acord": False}, "acord"),
    ("data gresita", {**CERERE, "data": "03.11.2026"}, "data"),
    ("data inexistenta", {**CERERE, "data": "2026-02-30"}, "data"),
    ("callback gresit", {**CERERE, "callback_url": "ftp://example.com"}, "callback_url"),
]


def client(server: ServerFals, ceas: CeasFals | None = None) -> Acteo:
    return Acteo(api_key=CHEIE, http_client=server.client(), _ceas=ceas or CeasFals(), _aleator=lambda: 0.5)


def corp(server: ServerFals, i: int = 0) -> object:
    return json.loads(server.cereri[i].content)


def test_porneste_trimite_post_cu_corpul_normalizat_si_intoarce_202() -> None:
    server = ServerFals(json_raspuns(202, PORNITA, COTA))
    r = client(server).casa.pad.porneste(
        cnp="190 0101 400012",
        judet="Cluj",
        localitate="Cluj-Napoca",
        acord=True,
        callback_url="https://example.com/webhooks/pad",
    )
    c = server.cereri[0]
    assert c.method == "POST"
    assert c.url.path == "/api/public/v1/polita-pad"
    assert corp(server) == {
        "cnp": CNP,
        "judet": "Cluj",
        "localitate": "Cluj-Napoca",
        "acord": True,
        "callbackUrl": "https://example.com/webhooks/pad",
    }
    assert r.request_id == ID
    assert r.status == "processing"
    assert r.cnp_mascat == "1*********012"
    assert isinstance(r.queued_at, datetime)
    assert r.limite == Limite(zi=Cota(limita=50, ramase=49), luna=Cota(limita=300, ramase=299))


def test_porneste_trimite_sectorul_id_urile_si_data_doar_cand_sunt_date() -> None:
    server = ServerFals(json_raspuns(202, PORNITA))
    client(server).casa.pad.porneste(cnp=CNP, judet="B", sector=3, data="2026-10-01", acord=True)
    assert corp(server) == {"cnp": CNP, "judet": "B", "sector": 3, "data": "2026-10-01", "acord": True}

    server2 = ServerFals(json_raspuns(202, PORNITA))
    client(server2).casa.pad.porneste(cnp=CNP, judet_id="a" * 24, localitate_id="b" * 24, acord=True)
    assert corp(server2) == {"cnp": CNP, "judetId": "a" * 24, "localitateId": "b" * 24, "acord": True}


def test_rezultat_face_get_cu_id_si_nu_pune_cnp_ul_in_url() -> None:
    server = ServerFals(json_raspuns(200, GATA))
    r = client(server).casa.pad.rezultat(ID)
    c = server.cereri[0]
    assert c.method == "GET"
    assert c.url.path == "/api/public/v1/polita-pad"
    assert dict(c.url.params) == {"id": ID}
    assert CNP not in str(c.url)
    assert r.status == "done"
    assert r.valabila is False
    assert isinstance(r.verificat_la, datetime)


def test_rezultat_accepta_si_raspunsul_de_la_porneste() -> None:
    server = ServerFals(json_raspuns(202, PORNITA), json_raspuns(200, IN_CURS))
    acteo = client(server)
    p = acteo.casa.pad.porneste(**CERERE)
    r = acteo.casa.pad.rezultat(p)
    assert dict(server.cereri[1].url.params) == {"id": ID}
    assert r.status == "processing"
    assert r.valabila is None


def test_asteapta_repeta_pana_la_done() -> None:
    ceas = CeasFals()
    server = ServerFals(json_raspuns(200, IN_CURS), json_raspuns(200, IN_CURS), json_raspuns(200, GATA))
    r = client(server, ceas).casa.pad.asteapta(ID)
    assert r.status == "done"
    assert r.valabila is False
    assert len(server.cereri) == 3
    assert ceas.somnuri == [3000, 3000, 3000]


def test_verifica_porneste_si_asteapta() -> None:
    gata = {**GATA, "valabila": True, "serieNumar": "PAD-0001", "distribuitor": "Asigurator"}
    server = ServerFals(json_raspuns(202, PORNITA), json_raspuns(200, gata))
    r = client(server).casa.pad.verifica(**CERERE)
    assert (r.valabila, r.serie_numar, r.distribuitor) == (True, "PAD-0001", "Asigurator")
    assert len(server.cereri) == 2


def test_asteapta_depaseste_timeout_ms() -> None:
    ceas = CeasFals()
    server = ServerFals(*(json_raspuns(200, IN_CURS) for _ in range(3)))
    with pytest.raises(EroareTimeoutVerificare) as info:
        client(server, ceas).casa.pad.asteapta(ID, timeout_ms=7000)
    assert info.value.cod == "TIMEOUT_VERIFICARE"
    assert "7 secunde" in str(info.value)
    assert ceas.somnuri == [3000, 3000, 1000]


def test_status_error_devine_eroare_verificare_cu_codul_api() -> None:
    server = ServerFals(json_raspuns(200, ESUATA))
    with pytest.raises(EroareVerificare) as info:
        client(server).casa.pad.rezultat(ID)
    assert info.value.cod == "UPSTREAM_CHANGED"
    assert str(info.value) == "Sursa s-a schimbat."


def test_status_error_fara_cod_devine_verificare_esuata() -> None:
    fara_cod = {k: v for k, v in ESUATA.items() if k != "code"}
    server = ServerFals(json_raspuns(200, fara_cod))
    with pytest.raises(EroareVerificare) as info:
        client(server).casa.pad.rezultat(ID)
    assert info.value.cod == "VERIFICARE_ESUATA"


@pytest.mark.parametrize(("_nume", "cerere", "camp"), CERERI_GRESITE)
def test_validare_locala_fara_request(_nume: str, cerere: dict[str, Any], camp: str) -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare) as info:
        client(server).casa.pad.porneste(**cerere)
    assert info.value.cod == "VALIDARE_LOCALA"
    assert info.value.camp == camp
    assert "1900101400013" not in str(info.value)
    assert server.cereri == []


def test_rezultat_fara_id_e_respins_local() -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare):
        client(server).casa.pad.rezultat(" ")
    assert server.cereri == []


def test_verifica_nu_repeta_post_ul_la_500() -> None:
    server = ServerFals(json_raspuns(500, {"error": "Eroare interna."}), json_raspuns(202, PORNITA))
    with pytest.raises(EroareServer):
        client(server).casa.pad.verifica(**CERERE)
    assert len(server.cereri) == 1


def test_parseaza_rezultat_pad_citeste_webhook_ul() -> None:
    r = client(ServerFals()).webhooks.parseaza_rezultat_pad(json.dumps(GATA))
    assert r.status == "done"
    assert r.valabila is False
    assert isinstance(r.verificat_la, datetime)
