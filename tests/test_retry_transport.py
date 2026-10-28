import httpx
import pytest

from acteo import (
    EroareHttp,
    EroareLimita,
    EroareRetea,
    EroareServer,
    EroareValidare,
    SetariRetry,
    VerificRcaError,
)
from acteo._intern.retry import pauza_ms, se_poate_reincerca
from acteo._intern.transport import eroare_retea

R = SetariRetry(incercari=3, intarziere_initiala_ms=500, intarziere_maxima_ms=10_000)


@pytest.mark.parametrize(
    ("idempotenta", "eroare", "asteptat"),
    [
        (True, EroareRetea("x"), True),
        (False, EroareRetea("x"), False),
        (False, EroareRetea("x", timeout=True), False),
        (False, EroareRetea("x", neajunsa=True), True),
        (True, EroareServer("x", status=500), True),
        (False, EroareServer("x", status=500), False),
        (False, EroareServer("x", status=502), True),
        (False, EroareServer("x", status=503), True),
        (False, EroareServer("x", status=504), True),
        (True, EroareLimita("x", cod="PREA_MULTE_CERERI", retry_after_ms=2000), True),
        (True, EroareLimita("x", cod="PREA_MULTE_CERERI"), True),
        (True, EroareLimita("x", cod="PREA_MULTE_CERERI", retry_after_ms=60_000), False),
        (False, EroareLimita("x", cod="PREA_MULTE_CERERI"), False),
        (True, EroareLimita("x", cod="COTA_ATINSA"), False),
        (True, EroareValidare("x"), False),
        (True, EroareHttp("x", status=418), False),
    ],
)
def test_se_poate_reincerca(idempotenta: bool, eroare: VerificRcaError, asteptat: bool) -> None:
    assert se_poate_reincerca(idempotenta, eroare, R) is asteptat


def test_pauza_creste_exponential_cu_jitter() -> None:
    e = EroareServer("x", status=500)
    assert pauza_ms(R, 0, e, lambda: 0.5) == 500
    assert pauza_ms(R, 1, e, lambda: 0.5) == 1000
    assert pauza_ms(R, 0, e, lambda: 0.0) == 400
    assert pauza_ms(R, 0, e, lambda: 0.999999) == 600
    assert pauza_ms(R, 10, e, lambda: 0.999999) == 10_000
    assert pauza_ms(R, 200, e, lambda: 0.5) == 10_000


def test_pauza_nu_coboara_sub_retry_after() -> None:
    e = EroareLimita("x", cod="PREA_MULTE_CERERI", retry_after_ms=4000)
    assert pauza_ms(R, 0, e, lambda: 0.5) == 4000


def cerere() -> httpx.Request:
    return httpx.Request("POST", "https://api.example.com/x")


@pytest.mark.parametrize(
    ("exc", "timeout", "neajunsa"),
    [
        (httpx.ConnectError("refuzat", request=cerere()), False, True),
        (httpx.ConnectTimeout("t", request=cerere()), True, True),
        (httpx.PoolTimeout("t", request=cerere()), True, True),
        (httpx.ReadTimeout("t", request=cerere()), True, False),
        (httpx.WriteTimeout("t", request=cerere()), True, False),
        (httpx.ReadError("rupt", request=cerere()), False, False),
        (httpx.RemoteProtocolError("inchis", request=cerere()), False, False),
        (httpx.DecodingError("gzip", request=cerere()), False, False),
    ],
)
def test_eroare_retea(exc: httpx.RequestError, timeout: bool, neajunsa: bool) -> None:
    e = eroare_retea(exc, "POST", "/x")
    assert (e.timeout, e.neajunsa) == (timeout, neajunsa)
    if timeout:
        assert e.mesaj == "Cererea POST /x a depasit timpul de raspuns."
    else:
        assert e.mesaj.startswith("Cererea POST /x nu a primit raspuns: ")
