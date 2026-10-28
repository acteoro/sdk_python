"""`import verificrca` ramane functional: aceleasi obiecte ca in `acteo`."""

import acteo
import verificrca
import verificrca.erori
import verificrca.modele
from verificrca import EroareLimita, VerificareFinala, VerificRca, VerificRcaError


def test_numele_legacy_sunt_aceleasi_obiecte() -> None:
    for nume in verificrca.__all__:
        if nume == "URL_IMPLICIT":
            continue
        assert getattr(verificrca, nume) is getattr(acteo, nume), nume


def test_numele_vechi_exista_toate() -> None:
    assert len(verificrca.__all__) == 49
    assert VerificRca is acteo.VerificRca
    assert issubclass(EroareLimita, VerificRcaError)
    assert VerificareFinala is acteo.VerificareFinala


def test_url_implicit_legacy() -> None:
    assert verificrca.URL_IMPLICIT == "https://www.verificrca.ro"
    assert acteo.URL_IMPLICIT == "https://api.acteo.ro"
    assert acteo.URL_IMPLICIT_LEGACY == verificrca.URL_IMPLICIT


def test_submodulele_vechi() -> None:
    assert verificrca.modele.Vehicul is acteo.Vehicul
    assert verificrca.erori.EroareConflict is acteo.EroareConflict


def test_except_prinde_pe_oricare_nume() -> None:
    try:
        raise acteo.EroareValidare("x")
    except verificrca.VerificRcaError as e:
        assert isinstance(e, acteo.ActeoError)
