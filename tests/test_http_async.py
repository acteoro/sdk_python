import httpx
import pytest

from acteo import EroareRetea, EroareServer, EroareTimeoutVerificare, SetariRetry
from acteo._intern.cereri import CerereHttp
from acteo._intern.http_async import HttpAsync
from tests.conftest import CeasFalsAsync, ServerFals, json_raspuns, setari_test

pytestmark = pytest.mark.anyio

GET = CerereHttp("GET", "/api/public/v1/vehicule", True)
POST = CerereHttp("POST", "/api/public/v1/verificare", False, corp={"tip": "rca"})


def http(server: ServerFals, ceas: CeasFalsAsync | None = None, **setari: object) -> HttpAsync:
    return HttpAsync(setari_test(**setari), server.client_async(), ceas or CeasFalsAsync(), lambda: 0.5)


async def test_get_ok() -> None:
    server = ServerFals(json_raspuns(200, {"ok": True}))
    r = await http(server).trimite(GET)
    assert r.corp == {"ok": True}
    assert server.cereri[0].headers["authorization"].startswith("Bearer vrca_")


async def test_post_nu_se_repeta_la_500() -> None:
    server = ServerFals(json_raspuns(500, {"error": "x"}))
    with pytest.raises(EroareServer):
        await http(server).trimite(POST)
    assert len(server.cereri) == 1


async def test_post_se_repeta_la_connect_error() -> None:
    ceas = CeasFalsAsync()
    server = ServerFals(httpx.ConnectError("refuzat"), json_raspuns(200, {}))
    await http(server, ceas).trimite(POST)
    assert (len(server.cereri), ceas.somnuri) == (2, [500])


async def test_post_nu_se_repeta_la_read_timeout() -> None:
    server = ServerFals(httpx.ReadTimeout("t"))
    with pytest.raises(EroareRetea) as info:
        await http(server).trimite(POST)
    assert info.value.timeout is True
    assert len(server.cereri) == 1


async def test_get_backoff() -> None:
    ceas = CeasFalsAsync()
    server = ServerFals(*[json_raspuns(502, {}) for _ in range(4)])
    with pytest.raises(EroareServer):
        await http(server, ceas).trimite(GET)
    assert ceas.somnuri == [500, 1000, 2000]


async def test_termen() -> None:
    server = ServerFals(json_raspuns(503, {}))
    with pytest.raises(EroareTimeoutVerificare):
        await http(server, retry=SetariRetry(3, 5000, 10_000)).trimite(GET, termen_ms=1000)
