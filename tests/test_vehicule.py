import json

import pytest

from tests.conftest import CHEIE, CeasFals, CeasFalsAsync, ServerFals, json_raspuns
from verificrca import (
    AsyncVerificRca,
    EroareConflict,
    EroareInterzis,
    EroareNegasit,
    EroareRaspunsInvalid,
    EroareServer,
    EroareValidare,
    VerificRca,
)

VEHICUL = {
    "id": "veh_1",
    "numarInmatriculare": "B123ABC",
    "serieSasiu": "WVWZZZ1JZXW000001",
    "rcaExpiraLa": "2026-11-02T00:00:00.000Z",
    "itpExpiraLa": None,
    "rovinietaExpiraLa": None,
    "arrExpiraLa": None,
    "arrMonitorizat": False,
    "activ": True,
    "createdAt": "2026-01-15T10:20:30.000Z",
}


def client(server: ServerFals) -> VerificRca:
    return VerificRca(api_key=CHEIE, http_client=server.client(), _ceas=CeasFals(), _aleator=lambda: 0.5)


def test_lista() -> None:
    server = ServerFals(json_raspuns(200, {"vehicule": [VEHICUL, {**VEHICUL, "id": "veh_2"}]}))
    vehicule = client(server).vehicule.lista()
    assert [v.id for v in vehicule] == ["veh_1", "veh_2"]
    assert (server.cereri[0].method, server.cereri[0].url.path) == ("GET", "/api/public/v1/vehicule")


def test_lista_cu_forma_gresita() -> None:
    fara = {k: v for k, v in VEHICUL.items() if k != "activ"}
    server = ServerFals(json_raspuns(200, {"vehicule": [VEHICUL, fara]}))
    with pytest.raises(EroareRaspunsInvalid) as info:
        client(server).vehicule.lista()
    assert info.value.mesaj == "Raspunsul API-ului nu are forma asteptata: vehicule[1].activ: lipseste"


def test_adauga_normalizeaza_si_trimite_camel() -> None:
    server = ServerFals(json_raspuns(201, {"vehicul": VEHICUL}))
    v = client(server).vehicule.adauga(
        numar_inmatriculare=" b-123 abc ", serie_sasiu="wvwzzz1jzxw000001", arr_monitorizat=False
    )
    assert v.id == "veh_1"
    c = server.cereri[0]
    assert (c.method, c.url.path) == ("POST", "/api/public/v1/vehicule")
    assert json.loads(c.content) == {
        "numarInmatriculare": "B123ABC",
        "serieSasiu": "WVWZZZ1JZXW000001",
        "arrMonitorizat": False,
    }


def test_adauga_cu_serie_talon() -> None:
    server = ServerFals(
        json_raspuns(201, {"vehicul": {**VEHICUL, "serieTalon": "I00639603F", "serieTalonRespinsa": False}})
    )
    v = client(server).vehicule.adauga(
        numar_inmatriculare="B123ABC", serie_sasiu="WVWZZZ1JZXW000001", serie_talon="i00639603f"
    )
    assert (v.serie_talon, v.serie_talon_respinsa) == ("I00639603F", False)
    assert json.loads(server.cereri[0].content)["serieTalon"] == "I00639603F"


def test_adauga_serie_talon_invalida_fara_cerere() -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare) as info:
        client(server).vehicule.adauga(numar_inmatriculare="B123ABC", serie_talon="ABCDEF")
    assert info.value.camp == "serie_talon"
    assert server.cereri == []


def test_adauga_validare_locala() -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare):
        client(server).vehicule.adauga()
    assert server.cereri == []


def test_adauga_conflict_si_limita_plan() -> None:
    server = ServerFals(
        json_raspuns(409, {"error": "Vehiculul exista deja.", "code": "VEHICUL_EXISTENT"}),
        json_raspuns(403, {"error": "Limita planului.", "code": "LIMIT_ATINS", "limita": 5}),
    )
    vrca = client(server)
    with pytest.raises(EroareConflict):
        vrca.vehicule.adauga(numar_inmatriculare="B123ABC")
    with pytest.raises(EroareInterzis) as info:
        vrca.vehicule.adauga(numar_inmatriculare="B123ABC")
    assert info.value.limita == 5


def test_adauga_nu_se_repeta_la_500() -> None:
    server = ServerFals(json_raspuns(500, {"error": "x"}))
    with pytest.raises(EroareServer):
        client(server).vehicule.adauga(numar_inmatriculare="B123ABC")
    assert len(server.cereri) == 1


def test_sterge_codeaza_id() -> None:
    server = ServerFals(json_raspuns(200, {"success": True}))
    client(server).vehicule.sterge(" veh/1 ")
    c = server.cereri[0]
    assert c.method == "DELETE"
    assert c.url.raw_path == b"/api/public/v1/vehicule/veh%2F1"


def test_sterge_id_gol() -> None:
    server = ServerFals()
    with pytest.raises(EroareValidare) as info:
        client(server).vehicule.sterge("  ")
    assert (info.value.mesaj, info.value.camp) == ("Lipseste ID-ul vehiculului.", "id")
    assert server.cereri == []


def test_sterge_negasit_si_raspuns_neasteptat() -> None:
    server = ServerFals(json_raspuns(404, {"error": "Vehicul negasit."}), json_raspuns(200, {"success": False}))
    vrca = client(server)
    with pytest.raises(EroareNegasit):
        vrca.vehicule.sterge("veh_x")
    with pytest.raises(EroareRaspunsInvalid):
        vrca.vehicule.sterge("veh_x")


@pytest.mark.anyio
async def test_async_lista_adauga_sterge() -> None:
    server = ServerFals(
        json_raspuns(200, {"vehicule": [VEHICUL]}),
        json_raspuns(201, {"vehicul": VEHICUL}),
        json_raspuns(200, {"success": True}),
    )
    vrca = AsyncVerificRca(api_key=CHEIE, http_client=server.client_async(), _ceas=CeasFalsAsync())
    assert len(await vrca.vehicule.lista()) == 1
    assert (await vrca.vehicule.adauga(numar_inmatriculare="B123ABC")).id == "veh_1"
    await vrca.vehicule.sterge("veh_1")
    assert [c.method for c in server.cereri] == ["GET", "POST", "DELETE"]
