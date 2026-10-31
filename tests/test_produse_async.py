"""Decodare VIN, numere disponibile si poze de masini, pe clientul `AsyncActeo`."""

import json

import httpx
import pytest

from acteo import AsyncActeo, EroareServer, EroareTimeoutVerificare, EroareValidare
from tests.conftest import CHEIE, CeasFalsAsync, ServerFals, json_raspuns
from tests.test_produse import COTA, DECODARE, IMAGINE_GATA, IMAGINE_IN_LUCRU, LIMITE, NUMAR_LIBER

pytestmark = pytest.mark.anyio


def client(server: ServerFals, ceas: CeasFalsAsync | None = None) -> AsyncActeo:
    return AsyncActeo(
        api_key=CHEIE, http_client=server.client_async(), _ceas=ceas or CeasFalsAsync(), _aleator=lambda: 0.5
    )


def corp(server: ServerFals, i: int = 0) -> object:
    return json.loads(server.cereri[i].content)


async def test_decodeaza() -> None:
    server = ServerFals(json_raspuns(200, DECODARE, COTA))
    d = await client(server).auto.vin.decodeaza("wvwzzz1kzbw000000")
    assert server.cereri[0].url.path == "/api/public/v1/decodare-vin"
    assert corp(server) == {"vin": "WVWZZZ1KZBW000000"}
    assert d.marca == "Volkswagen"
    assert d.limite == LIMITE


async def test_decodeaza_opreste_local_vin_invalid() -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare):
        await client(server).auto.vin.decodeaza("123")
    assert server.cereri == []


async def test_numere_cu_timeout_minim_si_ocupat_reincercat() -> None:
    ceas = CeasFalsAsync()
    server = ServerFals(
        json_raspuns(503, {"error": "Ocupat", "code": "OCUPAT"}, {"Retry-After": "10"}),
        json_raspuns(200, NUMAR_LIBER, COTA),
    )
    r = await client(server, ceas).auto.numere.verifica("bv07abc")
    assert r.disponibil is True
    assert r.limite == LIMITE
    assert ceas.somnuri == [10_000]
    assert corp(server, 1) == {"numar": "BV07ABC"}
    assert server.cereri[1].extensions["timeout"]["read"] == 150.0


async def test_numere_nu_repeta_5xx_cu_cod() -> None:
    server = ServerFals(json_raspuns(504, {"error": "x", "code": "TIMEOUT"}))
    with pytest.raises(EroareServer) as info:
        await client(server).auto.numere.verifica("BV07ABC")
    assert info.value.cod == "TIMEOUT"
    assert len(server.cereri) == 1


async def test_numere_respins_422() -> None:
    server = ServerFals(json_raspuns(422, {"error": "Respins", "code": "NUMAR_RESPINS"}))
    with pytest.raises(EroareValidare) as info:
        await client(server).auto.numere.verifica("BV07ABC")
    assert info.value.cod == "NUMAR_RESPINS"


async def test_obtine_si_in_lucru() -> None:
    server = ServerFals(json_raspuns(200, IMAGINE_IN_LUCRU, {"Retry-After": "15"}))
    p = await client(server).auto.imagini.obtine(marca="Volkswagen", model="Golf", an=2015, unghi="profil")
    assert corp(server) == {"marca": "Volkswagen", "model": "Golf", "an": 2015, "unghi": "profil"}
    assert (p.status, p.retry_after_ms) == ("in-lucru", 15_000)


async def test_obtine_valideaza_local() -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare) as info:
        await client(server).auto.imagini.obtine(marca="VW", model="Golf", an=2015, unghi="sus")  # type: ignore[arg-type]
    assert info.value.camp == "unghi"
    assert server.cereri == []


async def test_asteapta_cere_din_nou_dupa_retry_after() -> None:
    ceas = CeasFalsAsync()
    server = ServerFals(
        json_raspuns(200, IMAGINE_IN_LUCRU, {"Retry-After": "20"}),
        json_raspuns(200, IMAGINE_GATA),
    )
    p = await client(server, ceas).auto.imagini.asteapta(marca="Volkswagen", model="Golf", an=2015)
    assert p.status == "gata"
    assert ceas.somnuri == [20_000]


async def test_asteapta_renunta_dupa_timeout() -> None:
    server = ServerFals(
        json_raspuns(200, IMAGINE_IN_LUCRU, {"Retry-After": "10"}),
        json_raspuns(200, IMAGINE_IN_LUCRU, {"Retry-After": "10"}),
    )
    with pytest.raises(EroareTimeoutVerificare):
        await client(server).auto.imagini.asteapta(marca="Volkswagen", model="Golf", an=2015, timeout_ms=15_000)
    assert len(server.cereri) == 2


async def test_client_httpx_injectat_e_folosit() -> None:
    server = ServerFals(json_raspuns(200, NUMAR_LIBER))
    acteo = AsyncActeo(api_key=CHEIE, http_client=httpx.AsyncClient(transport=httpx.MockTransport(server)))
    assert (await acteo.auto.numere.verifica("BV07ABC")).numar == "BV07ABC"
