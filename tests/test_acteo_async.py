"""Clientul `AsyncActeo`: aceleasi cazuri ca `Acteo`, prin asyncio."""

import json

import httpx
import pytest

from acteo import (
    AsyncActeo,
    AsyncVerificRca,
    EroareConfigurare,
    EroareValidare,
    RezultatItp,
    RezultatRca,
    StatusDocument,
    TipVerificare,
    VerificareInCurs,
    VerificareInCursItp,
)
from tests.conftest import CHEIE, CeasFalsAsync, ServerFals, json_raspuns

pytestmark = pytest.mark.anyio

VIN = "WVWZZZ1JZXW000001"
TALON = "I00639603F"
FINAL = {
    "tip": "rca",
    "query": "B123ABC",
    "numarInmatriculare": "B123ABC",
    "serieSasiu": None,
    "checkedAt": "2026-09-29T08:00:00.000Z",
    "status": "valid",
    "expiresAt": "2027-03-01T00:00:00.000Z",
}
FINAL_VIN = {**FINAL, "query": VIN, "numarInmatriculare": None, "serieSasiu": VIN}
IN_CURS_ITP = {"tip": "itp", "query": VIN, "status": "processing"}


@pytest.fixture(autouse=True)
def _fara_chei_in_mediu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ACTEO_API_KEY", raising=False)
    monkeypatch.delenv("VERIFICRCA_API_KEY", raising=False)


def client(server: ServerFals, ceas: CeasFalsAsync | None = None) -> AsyncActeo:
    return AsyncActeo(
        api_key=CHEIE, http_client=server.client_async(), _ceas=ceas or CeasFalsAsync(), _aleator=lambda: 0.5
    )


def corp(server: ServerFals, i: int = 0) -> object:
    return json.loads(server.cereri[i].content)


async def test_adresa_implicita_si_user_agent() -> None:
    server = ServerFals(json_raspuns(200, FINAL))
    await client(server).auto.rca.verifica("B123ABC")
    assert str(server.cereri[0].url) == "https://api.acteo.ro/api/public/v1/verificare"
    assert server.cereri[0].headers["user-agent"].startswith("acteo-sdk-python/")


async def test_cheia_din_acteo_api_key_apoi_din_verificrca_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERIFICRCA_API_KEY", CHEIE)
    server = ServerFals(json_raspuns(200, {"vehicule": []}))
    await AsyncActeo(http_client=server.client_async()).auto.flota.lista()
    assert server.cereri[0].headers["authorization"] == f"Bearer {CHEIE}"

    monkeypatch.setenv("ACTEO_API_KEY", "acteo_cheie_0123456789abcdef")
    server2 = ServerFals(json_raspuns(200, {"vehicule": []}))
    await AsyncActeo(http_client=server2.client_async()).auto.flota.lista()
    assert server2.cereri[0].headers["authorization"] == "Bearer acteo_cheie_0123456789abcdef"


async def test_fara_cheie_eroarea_numeste_acteo_api_key() -> None:
    with pytest.raises(EroareConfigurare, match="ACTEO_API_KEY"):
        AsyncActeo()


async def test_clientul_legacy_ramane_neschimbat() -> None:
    server = ServerFals(json_raspuns(200, {"vehicule": []}))
    await AsyncVerificRca(api_key=CHEIE, http_client=server.client_async()).vehicule.lista()
    assert str(server.cereri[0].url).startswith("https://www.verificrca.ro/")
    assert server.cereri[0].headers["user-agent"].startswith("verificrca-sdk-python/")


async def test_rca_cu_numar() -> None:
    server = ServerFals(json_raspuns(200, FINAL))
    r = await client(server).auto.rca.verifica("b-123 abc")
    assert corp(server) == {"tip": "rca", "query": "B123ABC"}
    assert isinstance(r, RezultatRca)


async def test_rca_text_de_17_caractere_e_vin() -> None:
    server = ServerFals(json_raspuns(200, FINAL_VIN))
    await client(server).auto.rca.verifica(VIN.lower())
    assert corp(server) == {"tip": "rca", "query": VIN}


async def test_rca_cu_numar_si_vin() -> None:
    server = ServerFals(json_raspuns(200, FINAL_VIN))
    await client(server).auto.rca.verifica(numar="B123ABC", vin=VIN)
    assert corp(server) == {"tip": "rca", "query": "B123ABC", "serieSasiu": VIN}


async def test_rca_fara_identificator_respins_local_fara_cerere() -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare):
        await client(server).auto.rca.verifica()
    assert server.cereri == []


async def test_itp_cere_vin_numarul_e_respins_local() -> None:
    server = ServerFals(json_raspuns(200, {**FINAL_VIN, "tip": "itp"}))
    assert isinstance(await client(server).auto.itp.verifica(VIN), RezultatItp)
    assert corp(server) == {"tip": "itp", "query": VIN}
    gol = ServerFals()
    with pytest.raises(EroareValidare):
        await client(gol).auto.itp.verifica("B123ABC")
    assert gol.cereri == []


async def test_arr_trimite_numarul() -> None:
    server = ServerFals(json_raspuns(200, {**FINAL, "tip": "arr"}))
    r = await client(server).auto.arr.verifica("B123ABC")
    assert corp(server) == {"tip": "arr", "query": "B123ABC"}
    assert r.tip is TipVerificare.ARR


async def test_rovinieta_trimite_numarul_vin_si_talonul() -> None:
    server = ServerFals(json_raspuns(200, {**FINAL, "tip": "rovinieta", "serieSasiu": VIN}))
    await client(server).auto.rovinieta.verifica(numar="B123ABC", vin=VIN, serie_talon=TALON)
    assert corp(server) == {"tip": "rovinieta", "query": "B123ABC", "serieSasiu": VIN, "serieTalon": TALON}


async def test_porneste_cu_callback_url() -> None:
    poll = f"GET /api/public/v1/verificare?tip=itp&query={VIN}&since=9"
    server = ServerFals(json_raspuns(202, {**IN_CURS_ITP, "requestId": "req_1", "pollUrl": poll}))
    r = await client(server).auto.itp.porneste(VIN, callback_url="https://example.com/hook")
    assert corp(server) == {"tip": "itp", "query": VIN, "callbackUrl": "https://example.com/hook"}
    assert isinstance(r, VerificareInCursItp)
    assert (r.since, r.request_id) == (9, "req_1")


async def test_asteapta_pastreaza_since() -> None:
    poll = f"GET /api/public/v1/verificare?tip=itp&query={VIN}&since=5"
    server = ServerFals(
        json_raspuns(202, {**IN_CURS_ITP, "pollUrl": poll}),
        json_raspuns(200, IN_CURS_ITP),
        json_raspuns(200, {**FINAL_VIN, "tip": "itp"}),
    )
    acteo = client(server)
    pornit = await acteo.auto.itp.porneste(VIN)
    assert isinstance(pornit, VerificareInCurs)
    r = await acteo.auto.itp.asteapta(pornit)
    assert r.status is StatusDocument.VALID
    assert [c.url.params.get("since") for c in server.cereri[1:]] == ["5", "5"]


async def test_rezultat_rca_cu_vin_interogheaza_dupa_vin() -> None:
    server = ServerFals(json_raspuns(200, FINAL_VIN))
    await client(server).auto.rca.rezultat(numar="B123ABC", vin=VIN)
    assert server.cereri[0].method == "GET"
    assert dict(server.cereri[0].url.params) == {"tip": "rca", "query": VIN}


async def test_rezultat_rovinieta_trimite_serie_sasiu_nu_talonul() -> None:
    server = ServerFals(json_raspuns(200, {**FINAL, "tip": "rovinieta", "serieSasiu": VIN}))
    await client(server).auto.rovinieta.rezultat(numar="b123abc", vin=VIN, serie_talon=TALON)
    assert dict(server.cereri[0].url.params) == {"tip": "rovinieta", "query": "B123ABC", "serieSasiu": VIN}


async def test_flota_si_webhooks() -> None:
    server = ServerFals(json_raspuns(200, {"vehicule": []}))
    acteo = client(server)
    assert await acteo.auto.flota.lista() == []
    assert server.cereri[0].url.path == "/api/public/v1/vehicule"
    corp_test = {"event": "webhook.test", "id": "t1", "mesaj": "ok", "trimisLa": "2026-09-29T07:00:00.000Z"}
    ev = acteo.webhooks.verifica_notificare(
        json.dumps(corp_test), httpx.Headers({"x-acteo-key": "whsec_0123456789"}), "whsec_0123456789"
    )
    assert ev.id == "t1"


async def test_context_manager_async() -> None:
    async with AsyncActeo(api_key=CHEIE) as acteo:
        assert acteo.auto.itp is not None
