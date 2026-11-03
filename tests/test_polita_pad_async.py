"""Verificarea politei PAD (`acteo.casa.pad`), pe clientul `AsyncActeo`."""

import json
from datetime import datetime
from typing import Any

import pytest

from acteo import AsyncActeo, EroareServer, EroareTimeoutVerificare, EroareValidare, EroareVerificare
from tests.conftest import CHEIE, CeasFalsAsync, ServerFals, json_raspuns
from tests.test_polita_pad import CERERE, CERERI_GRESITE, CNP, ESUATA, GATA, ID, IN_CURS, PORNITA

pytestmark = pytest.mark.anyio


def client(server: ServerFals, ceas: CeasFalsAsync | None = None) -> AsyncActeo:
    return AsyncActeo(
        api_key=CHEIE, http_client=server.client_async(), _ceas=ceas or CeasFalsAsync(), _aleator=lambda: 0.5
    )


def corp(server: ServerFals, i: int = 0) -> object:
    return json.loads(server.cereri[i].content)


async def test_porneste_trimite_post_cu_corpul_normalizat_si_intoarce_202() -> None:
    server = ServerFals(json_raspuns(202, PORNITA))
    r = await client(server).casa.pad.porneste(
        cnp="190 0101 400012", judet="Cluj", localitate="Cluj-Napoca", acord=True
    )
    assert server.cereri[0].method == "POST"
    assert server.cereri[0].url.path == "/api/public/v1/polita-pad"
    assert corp(server) == {"cnp": CNP, "judet": "Cluj", "localitate": "Cluj-Napoca", "acord": True}
    assert r.request_id == ID
    assert isinstance(r.queued_at, datetime)


async def test_rezultat_face_get_cu_id_si_nu_pune_cnp_ul_in_url() -> None:
    server = ServerFals(json_raspuns(200, GATA))
    r = await client(server).casa.pad.rezultat(ID)
    assert dict(server.cereri[0].url.params) == {"id": ID}
    assert CNP not in str(server.cereri[0].url)
    assert r.status == "done"


async def test_asteapta_repeta_pana_la_done() -> None:
    ceas = CeasFalsAsync()
    server = ServerFals(json_raspuns(200, IN_CURS), json_raspuns(200, IN_CURS), json_raspuns(200, GATA))
    r = await client(server, ceas).casa.pad.asteapta(ID)
    assert r.valabila is False
    assert len(server.cereri) == 3
    assert ceas.somnuri == [3000, 3000, 3000]


async def test_verifica_porneste_si_asteapta() -> None:
    server = ServerFals(json_raspuns(202, PORNITA), json_raspuns(200, {**GATA, "valabila": True}))
    r = await client(server).casa.pad.verifica(**CERERE)
    assert r.valabila is True
    assert len(server.cereri) == 2


async def test_asteapta_depaseste_timeout_ms() -> None:
    ceas = CeasFalsAsync()
    server = ServerFals(*(json_raspuns(200, IN_CURS) for _ in range(3)))
    with pytest.raises(EroareTimeoutVerificare) as info:
        await client(server, ceas).casa.pad.asteapta(ID, timeout_ms=7000)
    assert info.value.cod == "TIMEOUT_VERIFICARE"


async def test_status_error_devine_eroare_verificare_cu_codul_api() -> None:
    server = ServerFals(json_raspuns(200, ESUATA))
    with pytest.raises(EroareVerificare) as info:
        await client(server).casa.pad.rezultat(ID)
    assert info.value.cod == "UPSTREAM_CHANGED"


@pytest.mark.parametrize(("_nume", "cerere", "camp"), CERERI_GRESITE)
async def test_validare_locala_fara_request(_nume: str, cerere: dict[str, Any], camp: str) -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare) as info:
        await client(server).casa.pad.porneste(**cerere)
    assert info.value.camp == camp
    assert server.cereri == []


async def test_verifica_nu_repeta_post_ul_la_500() -> None:
    server = ServerFals(json_raspuns(500, {"error": "Eroare interna."}), json_raspuns(202, PORNITA))
    with pytest.raises(EroareServer):
        await client(server).casa.pad.verifica(**CERERE)
    assert len(server.cereri) == 1


async def test_parseaza_rezultat_pad_citeste_webhook_ul() -> None:
    r = client(ServerFals()).webhooks.parseaza_rezultat_pad(GATA)
    assert r.status == "done"
