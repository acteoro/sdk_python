"""Decodare VIN, numere disponibile si poze de masini, pe clientul sincron `Acteo`."""

import json
from datetime import datetime
from typing import Any

import httpx
import pytest

from acteo import (
    Acteo,
    Cota,
    EroareLimita,
    EroareServer,
    EroareTimeoutVerificare,
    EroareValidare,
    Limite,
)
from tests.conftest import CHEIE, CeasFals, ServerFals, json_raspuns

COTA = {
    "X-RateLimit-Limit-Day": "100",
    "X-RateLimit-Remaining-Day": "99",
    "X-RateLimit-Limit-Month": "1000",
    "X-RateLimit-Remaining-Month": "999",
}
LIMITE = Limite(zi=Cota(limita=100, ramase=99), luna=Cota(limita=1000, ramase=999))

DECODARE: dict[str, Any] = {
    "vin": "WVWZZZ1KZBW000000",
    "gasit": True,
    "taxat": True,
    "marca": "Volkswagen",
    "model": "Golf",
    "anFabricatie": 2011,
    "sursaAn": "pozitia-10",
    "modelePosibile": [],
    "structura": {
        "wmi": "WVW",
        "vds": "ZZZ1KZ",
        "vis": "BW000000",
        "regiune": "Europa",
        "tara": "Germania",
        "cifraControl": "neaplicabila",
        "cifraControlAsteptata": None,
        "aniPosibili": [2011],
    },
}
NUMAR_LIBER = {"numar": "BV07ABC", "disponibil": True, "mesaj": None}
IMAGINE_GATA: dict[str, Any] = {
    "gata": True,
    "status": "gata",
    "taxat": True,
    "url": "https://example.com/golf.webp",
    "expiraLa": "2026-11-01T10:00:00.000Z",
    "unghi": "trei-sferturi",
    "umbra": True,
    "latime": 1600,
    "inaltime": 900,
    "marca": "Volkswagen",
    "model": "Golf",
    "generatie": {"eticheta": "Volkswagen Golf VII", "anDe": 2012, "anPana": 2019, "caroserie": "5-door hatchback"},
}
IMAGINE_IN_LUCRU = {**IMAGINE_GATA, "gata": False, "status": "in-lucru", "taxat": False, "generatie": None}


def client(server: ServerFals, ceas: CeasFals | None = None, http_client: httpx.Client | None = None) -> Acteo:
    return Acteo(
        api_key=CHEIE,
        http_client=http_client or server.client(),
        _ceas=ceas or CeasFals(),
        _aleator=lambda: 0.5,
    )


def corp(server: ServerFals, i: int = 0) -> object:
    return json.loads(server.cereri[i].content)


# --- auto.vin.decodeaza ---


def test_decodeaza_trimite_vin_normalizat_si_intoarce_cota() -> None:
    server = ServerFals(json_raspuns(200, DECODARE, COTA))
    d = client(server).auto.vin.decodeaza(" wvwzzz1kzbw000000 ")
    cerere = server.cereri[0]
    assert cerere.method == "POST"
    assert cerere.url.path == "/api/public/v1/decodare-vin"
    assert corp(server) == {"vin": "WVWZZZ1KZBW000000"}
    assert (d.marca, d.model, d.an_fabricatie, d.sursa_an) == ("Volkswagen", "Golf", 2011, "pozitia-10")
    assert d.structura.ani_posibili == [2011]
    assert d.structura.cifra_control == "neaplicabila"
    assert d.limite == LIMITE


def test_decodeaza_opreste_local_vin_invalid() -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare) as info:
        client(server).auto.vin.decodeaza("WVWZZZ1KZBW00000O")
    assert info.value.camp == "vin"
    assert server.cereri == []


def test_plafon_netaxat_e_eroare_limita_fara_reincercare() -> None:
    server = ServerFals(json_raspuns(429, {"error": "Plafon", "code": "PLAFON_NETAXAT"}))
    with pytest.raises(EroareLimita) as info:
        client(server).auto.vin.decodeaza(DECODARE["vin"])
    assert info.value.cod == "PLAFON_NETAXAT"
    assert len(server.cereri) == 1


# --- auto.numere.verifica ---


def test_numere_trimite_numar_normalizat_si_intoarce_verdictul() -> None:
    server = ServerFals(json_raspuns(200, NUMAR_LIBER, COTA))
    r = client(server).auto.numere.verifica("bv 07 abc")
    assert server.cereri[0].url.path == "/api/public/v1/numere-disponibile"
    assert corp(server) == {"numar": "BV07ABC"}
    assert r.disponibil is True
    assert r.limite is not None and r.limite.zi.ramase == 99


@pytest.mark.parametrize("numar", ["BV07AB", "BV07A?C", "B12*", "XX07ABC", "CD123A", "", "   "])
def test_numere_opreste_local_numerele_incomplete_sau_cu_wildcard(numar: str) -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare) as info:
        client(server).auto.numere.verifica(numar)
    assert info.value.camp == "numar"
    assert server.cereri == []


def test_numere_wildcard_are_mesaj_propriu() -> None:
    with pytest.raises(EroareValidare, match=r"`\?`"):
        client(ServerFals()).auto.numere.verifica("BV07A?C")


def test_numere_accepta_bucuresti_cu_trei_cifre() -> None:
    server = ServerFals(json_raspuns(200, {"numar": "B123ABC", "disponibil": False, "mesaj": "Inregistrat"}))
    r = client(server).auto.numere.verifica("B 123 ABC")
    assert (r.disponibil, r.mesaj) == (False, "Inregistrat")
    assert corp(server) == {"numar": "B123ABC"}


def test_numar_respins_422_e_eroare_validare() -> None:
    server = ServerFals(json_raspuns(422, {"error": "Respins", "code": "NUMAR_RESPINS"}))
    with pytest.raises(EroareValidare) as info:
        client(server).auto.numere.verifica("BV07ABC")
    assert (info.value.cod, info.value.status) == ("NUMAR_RESPINS", 422)


def test_numere_reincearca_ocupat_dupa_retry_after() -> None:
    ceas = CeasFals()
    server = ServerFals(
        json_raspuns(503, {"error": "Ocupat", "code": "OCUPAT"}, {"Retry-After": "10"}),
        json_raspuns(200, NUMAR_LIBER),
    )
    r = client(server, ceas).auto.numere.verifica("BV07ABC")
    assert r.disponibil is True
    assert len(server.cereri) == 2
    assert ceas.somnuri == [10_000]


def test_numere_nu_reincearca_ocupat_cu_retry_after_peste_plafon() -> None:
    server = ServerFals(json_raspuns(503, {"error": "Ocupat", "code": "OCUPAT"}, {"Retry-After": "60"}))
    with pytest.raises(EroareServer) as info:
        client(server).auto.numere.verifica("BV07ABC")
    assert (info.value.cod, info.value.retry_after_ms) == ("OCUPAT", 60_000)
    assert len(server.cereri) == 1


@pytest.mark.parametrize(("status", "cod"), [(504, "TIMEOUT"), (502, "EROARE_DGPCI"), (503, "INDISPONIBIL")])
def test_numere_nu_repeta_5xx_cu_cod(status: int, cod: str) -> None:
    server = ServerFals(json_raspuns(status, {"error": "x", "code": cod}))
    with pytest.raises(EroareServer) as info:
        client(server).auto.numere.verifica("BV07ABC")
    assert info.value.cod == cod
    assert len(server.cereri) == 1


def test_post_5xx_fara_cod_de_la_proxy_se_reincearca_in_continuare() -> None:
    server = ServerFals(httpx.Response(502, text="Bad Gateway"), json_raspuns(200, NUMAR_LIBER))
    assert client(server).auto.numere.verifica("BV07ABC").disponibil is True
    assert len(server.cereri) == 2


def test_numere_are_timeout_de_cel_putin_150_s() -> None:
    server = ServerFals(json_raspuns(200, NUMAR_LIBER), json_raspuns(200, DECODARE))
    acteo = client(server, http_client=httpx.Client(transport=httpx.MockTransport(server), timeout=1.0))
    acteo.auto.numere.verifica("BV07ABC")
    acteo.auto.vin.decodeaza(DECODARE["vin"])
    assert server.cereri[0].extensions["timeout"] == {"connect": 150.0, "read": 150.0, "write": 150.0, "pool": 150.0}
    # Celelalte cereri raman pe timeout-ul clientului.
    assert server.cereri[1].extensions["timeout"]["read"] == 1.0


def test_numere_pastreaza_timeout_mai_mare_al_clientului() -> None:
    server = ServerFals(json_raspuns(200, NUMAR_LIBER))
    timeout = httpx.Timeout(200.0, connect=None)
    acteo = client(server, http_client=httpx.Client(transport=httpx.MockTransport(server), timeout=timeout))
    acteo.auto.numere.verifica("BV07ABC")
    assert server.cereri[0].extensions["timeout"] == {"connect": None, "read": 200.0, "write": 200.0, "pool": 200.0}


# --- auto.imagini ---


def test_obtine_trimite_doar_campurile_date_si_decodeaza_poza() -> None:
    server = ServerFals(json_raspuns(200, IMAGINE_GATA, COTA))
    p = client(server).auto.imagini.obtine(marca=" Volkswagen ", model="Golf", an=2015, unghi="fata")
    assert server.cereri[0].url.path == "/api/public/v1/imagini-masini"
    assert corp(server) == {"marca": "Volkswagen", "model": "Golf", "an": 2015, "unghi": "fata"}
    assert isinstance(p.expira_la, datetime)
    assert p.generatie is not None and p.generatie.an_pana == 2019
    assert p.retry_after_ms is None
    assert p.limite == LIMITE


def test_obtine_trimite_umbra_cand_e_data() -> None:
    server = ServerFals(json_raspuns(200, {**IMAGINE_GATA, "umbra": False}))
    client(server).auto.imagini.obtine(marca="Dacia", model="Logan MCV", an=2020, umbra=False)
    assert corp(server) == {"marca": "Dacia", "model": "Logan MCV", "an": 2020, "umbra": False}


def test_in_lucru_expune_retry_after_ms() -> None:
    server = ServerFals(json_raspuns(200, IMAGINE_IN_LUCRU, {"Retry-After": "15"}))
    p = client(server).auto.imagini.obtine(marca="Volkswagen", model="Golf", an=2015)
    assert p.status == "in-lucru"
    assert p.retry_after_ms == 15_000


@pytest.mark.parametrize(
    ("argumente", "camp"),
    [
        ({"marca": "", "model": "Golf", "an": 2015}, "marca"),
        ({"marca": 3, "model": "Golf", "an": 2015}, "marca"),
        ({"marca": "VW", "model": "Golf<script>", "an": 2015}, "model"),
        ({"marca": "VW", "model": "G" * 67, "an": 2015}, "model"),
        ({"marca": "VW", "model": "Golf", "an": 1900}, "an"),
        ({"marca": "VW", "model": "Golf", "an": 2015.5}, "an"),
        ({"marca": "VW", "model": "Golf", "an": True}, "an"),
        ({"marca": "VW", "model": "Golf", "an": 2015, "unghi": "sus"}, "unghi"),
        ({"marca": "VW", "model": "Golf", "an": 2015, "umbra": "da"}, "umbra"),
    ],
)
def test_imagini_valideaza_local(argumente: dict[str, Any], camp: str) -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare) as info:
        client(server).auto.imagini.obtine(**argumente)
    assert info.value.camp == camp
    assert server.cereri == []


def test_imagini_accepta_litere_unicode_si_semnele_permise() -> None:
    server = ServerFals(json_raspuns(200, IMAGINE_GATA))
    client(server).auto.imagini.obtine(marca="Škoda", model="Octavia (A7) 1.6 TDI/RS+", an=2016)
    assert corp(server) == {"marca": "Škoda", "model": "Octavia (A7) 1.6 TDI/RS+", "an": 2016}


def test_imagini_mesajul_pentru_an_contine_intervalul() -> None:
    with pytest.raises(EroareValidare, match="1950"):
        client(ServerFals()).auto.imagini.obtine(marca="VW", model="Golf", an=1900)


def test_asteapta_cere_din_nou_dupa_retry_after() -> None:
    ceas = CeasFals()
    server = ServerFals(
        json_raspuns(200, IMAGINE_IN_LUCRU, {"Retry-After": "20"}),
        json_raspuns(200, IMAGINE_GATA),
    )
    p = client(server, ceas).auto.imagini.asteapta(marca="Volkswagen", model="Golf", an=2015)
    assert p.status == "gata"
    assert ceas.somnuri == [20_000]
    assert corp(server, 1) == corp(server, 0)


def test_asteapta_pauza_minima_de_10_secunde() -> None:
    ceas = CeasFals()
    server = ServerFals(json_raspuns(200, IMAGINE_IN_LUCRU), json_raspuns(200, IMAGINE_GATA))
    client(server, ceas).auto.imagini.asteapta(marca="Volkswagen", model="Golf", an=2015)
    assert ceas.somnuri == [10_000]


def test_asteapta_renunta_dupa_timeout() -> None:
    server = ServerFals(
        json_raspuns(200, IMAGINE_IN_LUCRU, {"Retry-After": "10"}),
        json_raspuns(200, IMAGINE_IN_LUCRU, {"Retry-After": "10"}),
    )
    with pytest.raises(EroareTimeoutVerificare) as info:
        client(server).auto.imagini.asteapta(marca="Volkswagen", model="Golf", an=2015, timeout_ms=15_000)
    assert info.value.cod == "TIMEOUT_IMAGINE"
    assert len(server.cereri) == 2
