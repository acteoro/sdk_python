from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from verificrca import (
    Limite,
    StatusDocument,
    TipVerificare,
    Vehicul,
    VerificareFinala,
    VerificareInCurs,
)
from verificrca._intern.decodare import cale_eroare
from verificrca.modele import Baza

VEHICUL = {
    "id": "veh_1",
    "numarInmatriculare": "B123ABC",
    "serieSasiu": None,
    "rcaExpiraLa": "2026-11-02T00:00:00.000Z",
    "itpExpiraLa": None,
    "rovinietaExpiraLa": None,
    "arrExpiraLa": None,
    "arrMonitorizat": False,
    "activ": True,
    "createdAt": "2026-01-15T10:20:30+02:00",
    "campNou": "ignorat",
}

FINAL = {
    "tip": "rca",
    "query": "B123ABC",
    "numarInmatriculare": "B123ABC",
    "serieSasiu": None,
    "checkedAt": "2026-09-29T08:00:00Z",
    "status": "valid",
    "expiresAt": "2027-03-01T00:00:00.000Z",
}


class Lista(Baza):
    vehicule: list[Vehicul]


def test_vehicul_din_json_camel() -> None:
    v = Vehicul.model_validate(VEHICUL)
    assert v.numar_inmatriculare == "B123ABC"
    assert v.rca_expira_la == datetime(2026, 11, 2, tzinfo=timezone.utc)
    assert v.created_at.utcoffset() is not None
    assert v.activ is True
    assert not hasattr(v, "camp_nou")


def test_vehicul_serie_talon() -> None:
    v = Vehicul.model_validate({**VEHICUL, "serieTalon": "I00639603F", "serieTalonRespinsa": True})
    assert (v.serie_talon, v.serie_talon_respinsa) == ("I00639603F", True)
    # un server fara campurile noi nu strica decodarea
    vechi = Vehicul.model_validate(VEHICUL)
    assert (vechi.serie_talon, vechi.serie_talon_respinsa) == (None, False)


def test_modelele_sunt_imuabile() -> None:
    v = Vehicul.model_validate(VEHICUL)
    with pytest.raises(ValidationError):
        v.activ = False  # type: ignore[misc]


def test_data_fara_fus_orar_e_respinsa() -> None:
    with pytest.raises(ValidationError):
        Vehicul.model_validate({**VEHICUL, "createdAt": "2026-01-15T10:20:30"})


def test_enum_necunoscut_e_respins() -> None:
    with pytest.raises(ValidationError):
        VerificareFinala.model_validate({**FINAL, "status": "suspendat"})


def test_final_cu_optionale() -> None:
    f = VerificareFinala.model_validate({**FINAL, "requestId": "req_1", "hint": "Trimite si VIN-ul."})
    assert f.tip is TipVerificare.RCA
    assert f.status is StatusDocument.VALID
    assert (f.request_id, f.hint, f.limite) == ("req_1", "Trimite si VIN-ul.", None)


def test_campurile_nullabile_sunt_obligatorii() -> None:
    corp = dict(FINAL)
    del corp["expiresAt"]
    with pytest.raises(ValidationError) as info:
        VerificareFinala.model_validate(corp)
    assert cale_eroare(info.value) == "expiresAt: lipseste"


def test_cale_eroare_in_lista() -> None:
    fara_data = {k: v for k, v in VEHICUL.items() if k != "createdAt"}
    with pytest.raises(ValidationError) as info:
        Lista.model_validate({"vehicule": [VEHICUL, VEHICUL, fara_data]})
    assert cale_eroare(info.value) == "vehicule[2].createdAt: lipseste"


def test_cale_eroare_tip_gresit() -> None:
    with pytest.raises(ValidationError) as info:
        Lista.model_validate({"vehicule": [{**VEHICUL, "activ": "poate"}]})
    assert cale_eroare(info.value) == "vehicule[0].activ: valoare invalida"


def test_cale_eroare_la_radacina() -> None:
    with pytest.raises(ValidationError) as info:
        Lista.model_validate([1, 2])
    assert cale_eroare(info.value) == "valoare invalida"


def test_verificare_in_curs_trece_prin_json() -> None:
    r = VerificareInCurs(
        tip=TipVerificare.ROVINIETA,
        query="B123ABC",
        serie_sasiu="WVWZZZ1JZXW000001",
        since=1_700_000_000_000,
        request_id="req_1",
        queued_at=datetime(2026, 9, 29, 8, 0, tzinfo=timezone.utc),
        limite=Limite.model_validate({"zi": {"limita": 300, "ramase": 299}, "luna": {"limita": 9000, "ramase": 8999}}),
    )
    assert r.status == "processing"
    for text in (r.model_dump_json(), r.model_dump_json(by_alias=True)):
        assert VerificareInCurs.model_validate_json(text) == r
    assert '"serieSasiu"' in r.model_dump_json(by_alias=True)
