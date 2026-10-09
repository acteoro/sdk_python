import json

import httpx
import pytest

from tests.conftest import CHEIE, CeasFalsAsync, ServerFals, json_raspuns
from verificrca import (
    AsyncVerificRca,
    EroareTimeoutVerificare,
    EroareValidare,
    EroareVerificare,
    ReferintaVerificare,
    StatusDocument,
    VerificareInCurs,
)

pytestmark = pytest.mark.anyio

FINAL = {
    "tip": "itp",
    "query": "WVWZZZ1JZXW000001",
    "numarInmatriculare": None,
    "serieSasiu": "WVWZZZ1JZXW000001",
    "checkedAt": "2026-09-29T08:00:00.000Z",
    "status": "warning",
    "expiresAt": "2026-10-10T00:00:00.000Z",
}
IN_CURS = {"tip": "itp", "query": "WVWZZZ1JZXW000001", "status": "processing"}


def client(server: ServerFals, ceas: CeasFalsAsync | None = None) -> AsyncVerificRca:
    return AsyncVerificRca(
        api_key=CHEIE, http_client=server.client_async(), _ceas=ceas or CeasFalsAsync(), _aleator=lambda: 0.5
    )


async def test_verifica_si_asteapta() -> None:
    ceas = CeasFalsAsync()
    server = ServerFals(json_raspuns(202, IN_CURS), json_raspuns(200, IN_CURS), json_raspuns(200, FINAL))
    r = await client(server, ceas).verificari.verifica_si_asteapta(tip="itp", query="WVWZZZ1JZXW000001")
    assert r.status is StatusDocument.WARNING
    assert ceas.somnuri == [3000, 3000]
    assert [c.method for c in server.cereri] == ["POST", "GET", "GET"]


async def test_porneste_intoarce_in_curs() -> None:
    server = ServerFals(json_raspuns(202, IN_CURS))
    r = await client(server).verificari.porneste(tip="itp", query="WVWZZZ1JZXW000001")
    assert isinstance(r, VerificareInCurs)


async def test_rovinieta_cu_serie_talon() -> None:
    vin = "WVWZZZ1JZXW000001"
    rov = {**FINAL, "tip": "rovinieta", "query": "B123ABC", "numarInmatriculare": "B123ABC", "status": "valid"}
    server = ServerFals(json_raspuns(200, rov))
    r = await client(server).verificari.verifica_si_asteapta(
        tip="rovinieta", query="B123ABC", serie_sasiu=vin, serie_talon="I00639603F"
    )
    assert r.status is StatusDocument.VALID
    assert json.loads(server.cereri[0].content)["serieTalon"] == "I00639603F"
    with pytest.raises(EroareValidare):
        await client(ServerFals()).verificari.porneste(tip="rovinieta", query="B123ABC", serie_sasiu=vin)


async def test_status_error_cu_cod_sursa() -> None:
    corp = {"tip": "rovinieta", "query": "B123ABC", "status": "error", "error": "Refuzat.", "cod": "numar_invalid"}
    server = ServerFals(json_raspuns(200, corp))
    with pytest.raises(EroareVerificare) as info:
        await client(server).verificari.porneste(
            tip="rovinieta", query="B123ABC", serie_sasiu="WVWZZZ1JZXW000001", serie_talon="I00639603F"
        )
    assert (info.value.cod, info.value.cod_sursa) == ("VERIFICARE_ESUATA", "numar_invalid")


async def test_validare_locala() -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare):
        await client(server).verificari.porneste(tip="arr", query="WVWZZZ1JZXW000001")
    assert server.cereri == []


async def test_timeout() -> None:
    server = ServerFals(*[json_raspuns(200, IN_CURS) for _ in range(3)])
    with pytest.raises(EroareTimeoutVerificare):
        await client(server).verificari.asteapta(
            ReferintaVerificare(tip="itp", query="WVWZZZ1JZXW000001"), timeout_ms=5000
        )


async def test_context_manager_async() -> None:
    injectat = httpx.AsyncClient()
    async with AsyncVerificRca(api_key=CHEIE, http_client=injectat):
        pass
    assert not injectat.is_closed
    await injectat.aclose()
    async with AsyncVerificRca(api_key=CHEIE) as vrca:
        propriu = vrca._client
    assert propriu.is_closed


async def test_asteapta_timeout_nan() -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare):
        await client(server).verificari.asteapta(
            ReferintaVerificare(tip="itp", query="WVWZZZ1JZXW000001"), timeout_ms=float("nan")
        )
