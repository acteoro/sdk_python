"""Clientul `Acteo`: adresa si cheia implicite, identificatorii fiecarui document, polling, flota, webhook-uri."""

import json

import httpx
import pytest

from acteo import (
    Acteo,
    ActeoError,
    EroareConfigurare,
    EroareRaspunsInvalid,
    EroareValidare,
    RezultatItp,
    RezultatRca,
    StatusDocument,
    StatusWebhook,
    TipVerificare,
    VerificareFinala,
    VerificareInCurs,
    VerificareInCursItp,
    VerificRca,
    VerificRcaError,
)
from tests.conftest import CHEIE, CeasFals, ServerFals, json_raspuns

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


def client(server: ServerFals, ceas: CeasFals | None = None, **kw: object) -> Acteo:
    return Acteo(
        api_key=CHEIE,
        http_client=server.client(),
        _ceas=ceas or CeasFals(),
        _aleator=lambda: 0.5,
        **kw,  # type: ignore[arg-type]
    )


def corp(server: ServerFals, i: int = 0) -> object:
    return json.loads(server.cereri[i].content)


# --- configurare ---


def test_adresa_implicita_si_user_agent() -> None:
    server = ServerFals(json_raspuns(200, FINAL))
    client(server).auto.rca.verifica("B123ABC")
    cerere = server.cereri[0]
    assert str(cerere.url) == "https://api.acteo.ro/api/public/v1/verificare"
    assert cerere.headers["user-agent"].startswith("acteo-sdk-python/")


def test_cheia_din_acteo_api_key_apoi_din_verificrca_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ACTEO_API_KEY", "  ")
    monkeypatch.setenv("VERIFICRCA_API_KEY", CHEIE)
    server = ServerFals(json_raspuns(200, {"vehicule": []}))
    Acteo(http_client=server.client()).auto.flota.lista()
    assert server.cereri[0].headers["authorization"] == f"Bearer {CHEIE}"

    monkeypatch.setenv("ACTEO_API_KEY", "acteo_cheie_0123456789abcdef")
    server2 = ServerFals(json_raspuns(200, {"vehicule": []}))
    Acteo(http_client=server2.client()).auto.flota.lista()
    assert server2.cereri[0].headers["authorization"] == "Bearer acteo_cheie_0123456789abcdef"


def test_fara_cheie_eroarea_numeste_acteo_api_key() -> None:
    with pytest.raises(EroareConfigurare) as info:
        Acteo()
    assert "ACTEO_API_KEY" in info.value.mesaj
    assert info.value.hint == "Cheia se genereaza din https://app.acteo.ro/api/chei"


def test_clientul_legacy_ramane_neschimbat(monkeypatch: pytest.MonkeyPatch) -> None:
    server = ServerFals(json_raspuns(200, {"vehicule": []}))
    VerificRca(api_key=CHEIE, http_client=server.client()).vehicule.lista()
    assert str(server.cereri[0].url).startswith("https://www.verificrca.ro/")
    assert server.cereri[0].headers["user-agent"].startswith("verificrca-sdk-python/")
    # Legacy citeste doar VERIFICRCA_API_KEY.
    monkeypatch.setenv("ACTEO_API_KEY", CHEIE)
    with pytest.raises(EroareConfigurare, match="VERIFICRCA_API_KEY") as info:
        VerificRca()
    assert info.value.hint == "Cheia se genereaza din https://www.verificrca.ro/dashboard/api"


def test_acteo_error_e_aceeasi_clasa() -> None:
    assert ActeoError is VerificRcaError
    assert issubclass(EroareValidare, ActeoError)


# --- documente ---


def test_rca_cu_numar_trimite_numarul_normalizat() -> None:
    server = ServerFals(json_raspuns(200, FINAL))
    r = client(server).auto.rca.verifica("b-123 abc")
    assert corp(server) == {"tip": "rca", "query": "B123ABC"}
    assert isinstance(r, RezultatRca)
    assert isinstance(r, VerificareFinala)
    assert r.tip is TipVerificare.RCA
    assert r.status is StatusDocument.VALID


def test_rca_text_de_17_caractere_e_vin() -> None:
    server = ServerFals(json_raspuns(200, FINAL_VIN))
    client(server).auto.rca.verifica(VIN.lower())
    assert corp(server) == {"tip": "rca", "query": VIN}


def test_rca_cu_numar_si_vin_trimite_vin_in_serie_sasiu() -> None:
    server = ServerFals(json_raspuns(200, FINAL_VIN))
    client(server).auto.rca.verifica(numar="B123ABC", vin=VIN)
    assert corp(server) == {"tip": "rca", "query": "B123ABC", "serieSasiu": VIN}


def test_rca_fara_identificator_respins_local_fara_cerere() -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare) as info:
        client(server).auto.rca.verifica()
    assert info.value.cod == "VALIDARE_LOCALA"
    with pytest.raises(EroareValidare):
        client(server).auto.rca.verifica(numar="", vin="  ")
    assert server.cereri == []


def test_rca_text_si_cuvinte_cheie_impreuna_respins() -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare):
        client(server).auto.rca.verifica("B123ABC", vin=VIN)
    assert server.cereri == []


def test_itp_cere_vin_numarul_e_respins_local() -> None:
    server = ServerFals(json_raspuns(200, {**FINAL_VIN, "tip": "itp"}))
    r = client(server).auto.itp.verifica(VIN)
    assert corp(server) == {"tip": "itp", "query": VIN}
    assert isinstance(r, RezultatItp)
    gol = ServerFals()
    with pytest.raises(EroareValidare):
        client(gol).auto.itp.verifica("B123ABC")
    assert gol.cereri == []


def test_arr_trimite_numarul() -> None:
    server = ServerFals(json_raspuns(200, {**FINAL, "tip": "arr"}))
    r = client(server).auto.arr.verifica("B123ABC")
    assert corp(server) == {"tip": "arr", "query": "B123ABC"}
    assert r.tip is TipVerificare.ARR


def test_rovinieta_trimite_numarul_vin_si_talonul() -> None:
    server = ServerFals(json_raspuns(200, {**FINAL, "tip": "rovinieta", "serieSasiu": VIN}))
    r = client(server).auto.rovinieta.verifica(numar="B123ABC", vin=VIN, serie_talon=TALON)
    assert corp(server) == {"tip": "rovinieta", "query": "B123ABC", "serieSasiu": VIN, "serieTalon": TALON}
    assert r.tip is TipVerificare.ROVINIETA


def test_rovinieta_fara_talon_respinsa_local() -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare) as info:
        client(server).auto.rovinieta.verifica(numar="B123ABC", vin=VIN, serie_talon="")
    assert info.value.camp == "serie_talon"
    assert server.cereri == []


def test_raspuns_cu_alt_tip_e_raspuns_invalid() -> None:
    server = ServerFals(json_raspuns(200, FINAL))
    with pytest.raises(EroareRaspunsInvalid):
        client(server).auto.arr.verifica("B123ABC")


# --- porneste, rezultat, asteapta ---


def test_porneste_trimite_callback_url_si_intoarce_in_curs() -> None:
    poll = f"GET /api/public/v1/verificare?tip=itp&query={VIN}&since=9"
    server = ServerFals(json_raspuns(202, {**IN_CURS_ITP, "requestId": "req_1", "pollUrl": poll}))
    r = client(server).auto.itp.porneste(VIN, callback_url="https://example.com/hook")
    assert corp(server) == {"tip": "itp", "query": VIN, "callbackUrl": "https://example.com/hook"}
    assert isinstance(r, VerificareInCursItp)
    assert (r.status, r.tip, r.since, r.request_id) == ("processing", TipVerificare.ITP, 9, "req_1")


def test_asteapta_primeste_verificarea_in_curs_si_pastreaza_since() -> None:
    poll = f"GET /api/public/v1/verificare?tip=itp&query={VIN}&since=5"
    server = ServerFals(
        json_raspuns(202, {**IN_CURS_ITP, "pollUrl": poll}),
        json_raspuns(200, IN_CURS_ITP),
        json_raspuns(200, {**FINAL_VIN, "tip": "itp"}),
    )
    acteo = client(server)
    pornit = acteo.auto.itp.porneste(VIN)
    assert isinstance(pornit, VerificareInCurs)
    r = acteo.auto.itp.asteapta(pornit)
    assert r.status is StatusDocument.VALID
    assert [c.url.params.get("since") for c in server.cereri[1:]] == ["5", "5"]


def test_verifica_cu_polling() -> None:
    ceas = CeasFals()
    server = ServerFals(json_raspuns(202, IN_CURS_ITP), json_raspuns(200, {**FINAL_VIN, "tip": "itp"}))
    r = client(server, ceas).auto.itp.verifica(VIN)
    assert isinstance(r, RezultatItp)
    assert [c.method for c in server.cereri] == ["POST", "GET"]
    assert ceas.somnuri == [3000]


def test_rezultat_dupa_identificator_rca_cu_vin_interogheaza_dupa_vin() -> None:
    server = ServerFals(json_raspuns(200, FINAL_VIN))
    client(server).auto.rca.rezultat(numar="B123ABC", vin=VIN)
    cerere = server.cereri[0]
    assert cerere.method == "GET"
    assert dict(cerere.url.params) == {"tip": "rca", "query": VIN}


def test_rezultat_rca_dupa_text() -> None:
    server = ServerFals(json_raspuns(200, FINAL))
    client(server).auto.rca.rezultat("b 123 abc")
    assert dict(server.cereri[0].url.params) == {"tip": "rca", "query": "B123ABC"}


def test_rezultat_rovinieta_trimite_serie_sasiu_nu_talonul() -> None:
    server = ServerFals(json_raspuns(200, {**FINAL, "tip": "rovinieta", "serieSasiu": VIN}))
    client(server).auto.rovinieta.rezultat(numar="b123abc", vin=VIN, serie_talon=TALON)
    params = dict(server.cereri[0].url.params)
    assert params == {"tip": "rovinieta", "query": "B123ABC", "serieSasiu": VIN}


def test_rezultat_respinge_verificarea_altui_document() -> None:
    server = ServerFals()
    in_curs = VerificareInCurs(tip=TipVerificare.ITP, query=VIN, since=1)
    with pytest.raises(EroareValidare):
        client(server).auto.rca.rezultat(in_curs)
    assert server.cereri == []


def test_rezultat_itp_dupa_numar_respins_local() -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare):
        client(server).auto.itp.rezultat("B123ABC")
    assert server.cereri == []


def test_porneste_nu_repeta_post_la_500() -> None:
    server = ServerFals(json_raspuns(500, {"error": "x"}))
    with pytest.raises(ActeoError):
        client(server).auto.arr.porneste("B123ABC")
    assert len(server.cereri) == 1


# --- flota si webhook-uri ---


def test_flota_foloseste_endpointul_de_vehicule() -> None:
    server = ServerFals(json_raspuns(200, {"vehicule": []}))
    assert client(server).auto.flota.lista() == []
    assert server.cereri[0].url.path == "/api/public/v1/vehicule"


def test_webhooks_parseaza_rezultat() -> None:
    corp_webhook = {
        "requestId": "req_1",
        "tip": "rca",
        "query": "B123ABC",
        "serieSasiu": None,
        "status": "valid",
        "result": FINAL,
        "checkedAt": FINAL["checkedAt"],
    }
    w = client(ServerFals()).webhooks.parseaza_rezultat(json.dumps(corp_webhook))
    assert (w.request_id, w.status) == ("req_1", StatusWebhook.VALID)


def test_webhooks_verifica_notificare() -> None:
    corp_test = {"event": "webhook.test", "id": "t1", "mesaj": "ok", "trimisLa": "2026-09-29T07:00:00.000Z"}
    ev = client(ServerFals()).webhooks.verifica_notificare(
        json.dumps(corp_test), httpx.Headers({"x-verificrca-key": "whsec_0123456789"}), "whsec_0123456789"
    )
    assert ev.id == "t1"


def test_context_manager() -> None:
    with Acteo(api_key=CHEIE) as acteo:
        assert acteo.auto.rca is not None
