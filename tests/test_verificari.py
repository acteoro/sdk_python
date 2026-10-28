import json

import httpx
import pytest

from acteo import (
    EroareRaspunsInvalid,
    EroareServer,
    EroareTimeoutVerificare,
    EroareValidare,
    EroareVerificare,
    ReferintaVerificare,
    StatusDocument,
    TipVerificare,
    VerificareFinala,
    VerificareInCurs,
    VerificRca,
)
from acteo._intern.raspunsuri import Raspuns
from acteo._intern.verificari import interpreteaza, limite_din, since_din_poll_url
from tests.conftest import CHEIE, CeasFals, ServerFals, json_raspuns

VIN = "WVWZZZ1JZXW000001"
ACUM = 1_700_000_000_000
FINAL = {
    "tip": "rca",
    "query": "B123ABC",
    "numarInmatriculare": "B123ABC",
    "serieSasiu": None,
    "checkedAt": "2026-09-29T08:00:00.000Z",
    "status": "valid",
    "expiresAt": "2027-03-01T00:00:00.000Z",
}
IN_CURS = {"tip": "rca", "query": "B123ABC", "status": "processing", "requestId": "req_1"}
LIMITE = {
    "X-RateLimit-Limit-Day": "300",
    "X-RateLimit-Remaining-Day": "299",
    "X-RateLimit-Limit-Month": "9000",
    "X-RateLimit-Remaining-Month": "8999",
}


def client(server: ServerFals, ceas: CeasFals | None = None) -> VerificRca:
    return VerificRca(
        api_key=CHEIE,
        base_url="https://api.example.com",
        http_client=server.client(),
        _ceas=ceas or CeasFals(),
        _aleator=lambda: 0.5,
    )


def raspuns(corp: object, headere: dict[str, str] | None = None) -> Raspuns:
    return Raspuns(200, {k.lower(): v for k, v in (headere or {}).items()}, corp)


# --- nucleu ---


def test_interpreteaza_final_cu_limite() -> None:
    r = interpreteaza(raspuns(FINAL, LIMITE), None, None, ACUM)
    assert isinstance(r, VerificareFinala)
    assert r.status is StatusDocument.VALID
    assert r.limite is not None
    assert (r.limite.zi.limita, r.limite.zi.ramase, r.limite.luna.ramase) == (300, 299, 8999)


def test_limite_lipsesc_daca_un_header_lipseste_sau_nu_e_numar() -> None:
    assert limite_din(raspuns(FINAL, {**LIMITE, "X-RateLimit-Remaining-Month": "multe"})) is None
    headere = dict(LIMITE)
    del headere["X-RateLimit-Limit-Day"]
    assert limite_din(raspuns(FINAL, headere)) is None


def test_since_din_poll_url() -> None:
    assert since_din_poll_url("/api/public/v1/verificare?tip=rca&query=B123ABC&since=1700000000123") == 1700000000123
    assert since_din_poll_url("/x?since=0") is None
    assert since_din_poll_url("/x?since=abc") is None
    assert since_din_poll_url("/x?since=\u0661\u0662") is None
    assert since_din_poll_url("/x") is None
    assert since_din_poll_url(None) is None


def test_interpreteaza_in_curs() -> None:
    corp = {**IN_CURS, "pollUrl": "/api/public/v1/verificare?since=1700000000999", "queuedAt": "2026-09-29T08:00:00Z"}
    r = interpreteaza(raspuns(corp), VIN, 5, ACUM)
    assert isinstance(r, VerificareInCurs)
    assert (r.since, r.request_id, r.serie_sasiu) == (1700000000999, "req_1", None)
    assert r.queued_at is not None


def test_since_implicit_apoi_acum() -> None:
    r1 = interpreteaza(raspuns(IN_CURS), None, 42, ACUM)
    r2 = interpreteaza(raspuns(IN_CURS), None, None, ACUM)
    assert isinstance(r1, VerificareInCurs) and isinstance(r2, VerificareInCurs)
    assert (r1.since, r2.since) == (42, ACUM)


def test_serie_sasiu_pastrata_doar_la_rovinieta() -> None:
    r = interpreteaza(raspuns({**IN_CURS, "tip": "rovinieta"}), VIN, 1, ACUM)
    assert isinstance(r, VerificareInCurs)
    assert r.serie_sasiu == VIN


def test_status_error() -> None:
    corp = {"tip": "itp", "query": VIN, "status": "error", "error": "RAR nu raspunde.", "hint": "Reincearca."}
    with pytest.raises(EroareVerificare) as info:
        interpreteaza(raspuns(corp), None, None, ACUM)
    assert (info.value.mesaj, info.value.cod, info.value.hint, info.value.raspuns) == (
        "RAR nu raspunde.",
        "VERIFICARE_ESUATA",
        "Reincearca.",
        corp,
    )
    assert info.value.cod_sursa is None


@pytest.mark.parametrize("cod", ["serie_talon_invalida", "vin_invalid", "numar_invalid"])
def test_status_error_cu_cod_de_date_respinse(cod: str) -> None:
    corp = {
        "tip": "rovinieta",
        "query": "B123ABC",
        "status": "error",
        "error": "Sursa a respins datele trimise.",
        "cod": cod,
    }
    with pytest.raises(EroareVerificare) as info:
        interpreteaza(raspuns(corp), VIN, None, ACUM)
    assert (info.value.cod, info.value.cod_sursa) == ("VERIFICARE_ESUATA", cod)


@pytest.mark.parametrize("corp", [[1], "text", None, {"status": "processing", "tip": "casco", "query": "x"}])
def test_forma_invalida(corp: object) -> None:
    with pytest.raises(EroareRaspunsInvalid):
        interpreteaza(raspuns(corp), None, None, ACUM)


# --- client ---


def test_porneste_trimite_post_normalizat() -> None:
    server = ServerFals(json_raspuns(202, IN_CURS, LIMITE))
    ceas = CeasFals()
    r = client(server, ceas).verificari.porneste(
        tip="RCA", query="b-123 abc", serie_sasiu=VIN.lower(), callback_url="https://example.com/wh/9f3k"
    )
    assert isinstance(r, VerificareInCurs)
    assert r.since == ceas.acum_ms()
    assert r.limite is not None
    c = server.cereri[0]
    assert (c.method, c.url.path) == ("POST", "/api/public/v1/verificare")
    assert json.loads(c.content) == {
        "tip": "rca",
        "query": "B123ABC",
        "serieSasiu": VIN,
        "callbackUrl": "https://example.com/wh/9f3k",
    }


def test_porneste_rovinieta_trimite_serie_talon() -> None:
    server = ServerFals(json_raspuns(202, {**IN_CURS, "tip": "rovinieta"}))
    r = client(server).verificari.porneste(
        tip="rovinieta", query="B123ABC", serie_sasiu=VIN, serie_talon="i 00639603 f"
    )
    assert isinstance(r, VerificareInCurs)
    assert json.loads(server.cereri[0].content) == {
        "tip": "rovinieta",
        "query": "B123ABC",
        "serieSasiu": VIN,
        "serieTalon": "I00639603F",
    }


def test_porneste_rovinieta_fara_serie_talon_nu_trimite_cerere() -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare) as info:
        client(server).verificari.porneste(tip="rovinieta", query="B123ABC", serie_sasiu=VIN)
    assert info.value.camp == "serie_talon"
    assert server.cereri == []


def test_porneste_serie_talon_netrimisa_la_rca() -> None:
    server = ServerFals(json_raspuns(200, FINAL))
    client(server).verificari.porneste(tip="rca", query="B123ABC", serie_talon="I00639603F")
    assert "serieTalon" not in json.loads(server.cereri[0].content)


def test_porneste_validare_locala_fara_cerere() -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare):
        client(server).verificari.porneste(tip="itp", query="B123ABC")
    assert server.cereri == []


def test_porneste_nu_repeta_post_la_500() -> None:
    server = ServerFals(json_raspuns(500, {"error": "x"}))
    with pytest.raises(EroareServer):
        client(server).verificari.porneste(tip="rca", query="B123ABC")
    assert len(server.cereri) == 1


def test_rezultat_get_cu_since_si_serie_doar_la_rovinieta() -> None:
    server = ServerFals(json_raspuns(200, FINAL), json_raspuns(200, {**FINAL, "tip": "rovinieta"}))
    vrca = client(server)
    vrca.verificari.rezultat(ReferintaVerificare(tip="rca", query="B123ABC", serie_sasiu=VIN, since=7))
    vrca.verificari.rezultat(ReferintaVerificare(tip=TipVerificare.ROVINIETA, query="B123ABC", serie_sasiu=VIN))
    assert dict(server.cereri[0].url.params) == {"tip": "rca", "query": "B123ABC", "since": "7"}
    assert dict(server.cereri[1].url.params) == {"tip": "rovinieta", "query": "B123ABC", "serieSasiu": VIN}


def test_asteapta_pana_la_final() -> None:
    ceas = CeasFals()
    server = ServerFals(json_raspuns(200, IN_CURS), json_raspuns(200, FINAL))
    ref = VerificareInCurs(tip=TipVerificare.RCA, query="B123ABC", since=11)
    r = client(server, ceas).verificari.asteapta(ref)
    assert r.status is StatusDocument.VALID
    assert ceas.somnuri == [3000, 3000]
    assert all(c.url.params["since"] == "11" for c in server.cereri)


def test_asteapta_interval_minim() -> None:
    ceas = CeasFals()
    server = ServerFals(json_raspuns(200, FINAL))
    client(server, ceas).verificari.asteapta(ReferintaVerificare(tip="rca", query="B123ABC"), interval_ms=10)
    assert ceas.somnuri == [2000]


def test_asteapta_depaseste_timpul() -> None:
    ceas = CeasFals()
    server = ServerFals(*[json_raspuns(200, IN_CURS) for _ in range(3)])
    with pytest.raises(EroareTimeoutVerificare) as info:
        client(server, ceas).verificari.asteapta(
            ReferintaVerificare(tip="rca", query="B123ABC"), interval_ms=3000, timeout_ms=7000
        )
    assert info.value.cod == "TIMEOUT_VERIFICARE"
    assert info.value.mesaj == "Verificarea rca pentru B123ABC nu s-a finalizat in 7 secunde."
    assert ceas.somnuri == [3000, 3000, 1000]
    assert len(server.cereri) == 2


def test_asteapta_termenul_opreste_si_reincercarile() -> None:
    ceas = CeasFals()
    server = ServerFals(json_raspuns(503, {}), json_raspuns(503, {}), json_raspuns(503, {}))
    with pytest.raises(EroareTimeoutVerificare) as info:
        client(server, ceas).verificari.asteapta(ReferintaVerificare(tip="rca", query="B123ABC"), timeout_ms=4000)
    assert info.value.mesaj == "Verificarea rca pentru B123ABC nu s-a finalizat in 4 secunde."
    assert isinstance(info.value.__cause__, EroareTimeoutVerificare)
    assert ceas.monoton_ms() <= 4000


def test_verifica_si_asteapta_final_direct() -> None:
    ceas = CeasFals()
    server = ServerFals(json_raspuns(200, FINAL))
    r = client(server, ceas).verificari.verifica_si_asteapta(tip="rca", query="B123ABC")
    assert r.query == "B123ABC"
    assert (len(server.cereri), ceas.somnuri) == (1, [])


def test_verifica_si_asteapta_cu_polling() -> None:
    server = ServerFals(json_raspuns(202, IN_CURS), json_raspuns(200, FINAL))
    r = client(server).verificari.verifica_si_asteapta(tip="rca", query="B123ABC")
    assert r.status is StatusDocument.VALID
    assert [c.method for c in server.cereri] == ["POST", "GET"]


def test_verificare_in_curs_salvata_si_reluata() -> None:
    server = ServerFals(json_raspuns(202, IN_CURS), json_raspuns(200, FINAL))
    vrca = client(server)
    pornita = vrca.verificari.porneste(tip="rca", query="B123ABC")
    assert isinstance(pornita, VerificareInCurs)
    refacuta = VerificareInCurs.model_validate_json(pornita.model_dump_json())
    assert isinstance(vrca.verificari.rezultat(refacuta), VerificareFinala)


def test_context_manager_inchide_doar_clientul_propriu() -> None:
    injectat = httpx.Client()
    with VerificRca(api_key=CHEIE, http_client=injectat):
        pass
    assert not injectat.is_closed
    injectat.close()
    with VerificRca(api_key=CHEIE) as vrca:
        propriu = vrca._client
    assert propriu.is_closed


@pytest.mark.parametrize("valoare", [float("nan"), "30", True])
def test_asteapta_timeout_invalid_nu_intra_in_bucla(valoare: object) -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare) as info:
        client(server).verificari.asteapta(
            ReferintaVerificare(tip="rca", query="B123ABC"),
            timeout_ms=valoare,  # type: ignore[arg-type]
        )
    assert (info.value.camp, info.value.cod) == ("timeout_ms", "VALIDARE_LOCALA")
    assert server.cereri == []


def test_asteapta_interval_nan_foloseste_minimul() -> None:
    ceas = CeasFals()
    server = ServerFals(json_raspuns(200, FINAL))
    client(server, ceas).verificari.asteapta(ReferintaVerificare(tip="rca", query="B123ABC"), interval_ms=float("nan"))
    assert ceas.somnuri == [2000]
