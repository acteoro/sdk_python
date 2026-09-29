import httpx
import pytest

from tests.conftest import CHEIE, CeasFals, ServerFals, json_raspuns, setari_test
from verificrca import (
    EroareConflict,
    EroareHttp,
    EroareLimita,
    EroareRetea,
    EroareServer,
    EroareTimeoutVerificare,
    SetariRetry,
)
from verificrca._intern.cereri import CerereHttp
from verificrca._intern.http_sync import Http

GET = CerereHttp("GET", "/api/public/v1/vehicule", True, {"tip": "rca", "gol": None})
POST = CerereHttp("POST", "/api/public/v1/verificare", False, corp={"tip": "rca", "query": "B123ABC"})


def http(server: ServerFals, ceas: CeasFals | None = None, **setari: object) -> Http:
    return Http(setari_test(**setari), server.client(), ceas or CeasFals(), lambda: 0.5)


def test_get_trimite_headere_si_query() -> None:
    server = ServerFals(json_raspuns(200, {"ok": True}, {"X-Test": "1"}))
    r = http(server).trimite(GET)
    assert (r.status, r.corp, r.header("x-test")) == (200, {"ok": True}, "1")
    c = server.cereri[0]
    assert (c.method, str(c.url)) == ("GET", "https://api.example.com/api/public/v1/vehicule?tip=rca")
    assert c.headers["authorization"] == f"Bearer {CHEIE}"
    assert c.headers["accept"] == "application/json"
    assert c.headers["user-agent"].startswith("verificrca-sdk-python/")
    assert "content-type" not in c.headers


def test_post_trimite_json() -> None:
    server = ServerFals(json_raspuns(200, {}))
    http(server).trimite(POST)
    c = server.cereri[0]
    assert c.headers["content-type"] == "application/json"
    assert c.content == b'{"tip":"rca","query":"B123ABC"}'


def test_post_nu_se_repeta_la_500() -> None:
    server = ServerFals(json_raspuns(500, {"error": "Boom"}))
    with pytest.raises(EroareServer):
        http(server).trimite(POST)
    assert len(server.cereri) == 1


@pytest.mark.parametrize(
    "exc",
    [
        httpx.ReadTimeout("t"),
        httpx.RemoteProtocolError("inchis"),
        httpx.ReadError("rupt"),
    ],
)
def test_post_nu_se_repeta_dupa_ce_a_plecat(exc: Exception) -> None:
    server = ServerFals(exc)
    with pytest.raises(EroareRetea) as info:
        http(server).trimite(POST)
    assert len(server.cereri) == 1
    assert info.value.__cause__ is exc


@pytest.mark.parametrize(
    "prima",
    [json_raspuns(503, {"error": "x"}), httpx.ConnectError("refuzat"), httpx.ConnectTimeout("t")],
)
def test_post_se_repeta_cand_nu_a_ajuns(prima: httpx.Response | Exception) -> None:
    ceas = CeasFals()
    server = ServerFals(prima, json_raspuns(200, {"gata": True}))
    assert http(server, ceas).trimite(POST).corp == {"gata": True}
    assert len(server.cereri) == 2
    assert ceas.somnuri == [500]


def test_get_se_repeta_de_trei_ori_apoi_renunta() -> None:
    ceas = CeasFals()
    server = ServerFals(*[json_raspuns(500, {"error": "x"}) for _ in range(4)])
    with pytest.raises(EroareServer):
        http(server, ceas).trimite(GET)
    assert len(server.cereri) == 4
    assert ceas.somnuri == [500, 1000, 2000]


def test_fara_retry() -> None:
    server = ServerFals(json_raspuns(500, {"error": "x"}))
    with pytest.raises(EroareServer):
        http(server, retry=False).trimite(GET)
    assert len(server.cereri) == 1


def test_throttle_respecta_retry_after() -> None:
    ceas = CeasFals()
    server = ServerFals(json_raspuns(429, {"error": "Prea des"}, {"Retry-After": "3"}), json_raspuns(200, {}))
    http(server, ceas).trimite(GET)
    assert ceas.somnuri == [3000]


def test_cota_atinsa_nu_se_repeta() -> None:
    server = ServerFals(json_raspuns(429, {"error": "Cota", "dailyUsage": "3/3"}, {"Retry-After": "1"}))
    with pytest.raises(EroareLimita) as info:
        http(server).trimite(GET)
    assert info.value.cod == "COTA_ATINSA"
    assert len(server.cereri) == 1


def test_409_nu_se_repeta() -> None:
    server = ServerFals(json_raspuns(409, {"error": "Exista", "code": "VEHICUL_EXISTENT"}))
    with pytest.raises(EroareConflict):
        http(server).trimite(GET)
    assert len(server.cereri) == 1


def test_redirectul_nu_se_urmeaza() -> None:
    server = ServerFals(httpx.Response(302, headers={"Location": "https://alt.example.com/"}))
    with pytest.raises(EroareHttp) as info:
        http(server).trimite(GET)
    assert info.value.status == 302
    assert len(server.cereri) == 1


def test_eroare_de_decodare_gzip_devine_eroare_retea() -> None:
    server = ServerFals(
        httpx.Response(200, headers={"Content-Encoding": "gzip"}, stream=httpx.ByteStream(b"nu e gzip"))
    )
    with pytest.raises(EroareRetea) as info:
        http(server, retry=False).trimite(GET)
    assert isinstance(info.value.__cause__, httpx.DecodingError)


def test_pauza_peste_termen_opreste_reincercarile() -> None:
    ceas = CeasFals()
    server = ServerFals(json_raspuns(503, {"error": "x"}))
    with pytest.raises(EroareTimeoutVerificare) as info:
        http(server, ceas, retry=SetariRetry(3, 5000, 10_000)).trimite(GET, termen_ms=1000)
    assert info.value.cod == "TIMEOUT_VERIFICARE"
    assert isinstance(info.value.__cause__, EroareServer)
    assert ceas.somnuri == []
