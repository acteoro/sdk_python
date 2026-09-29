import pytest

from verificrca import (
    TIPURI_VERIFICARE,
    EroareValidare,
    TipVerificare,
    este_numar_inmatriculare_valid,
    este_vin_valid,
    normalizeaza,
)
from verificrca.validare import TintaVerificare, valideaza_cerere_verificare, valideaza_vehicul_nou

VIN = "WVWZZZ1JZXW000001"


def eroare(**kw: object) -> EroareValidare:
    with pytest.raises(EroareValidare) as info:
        valideaza_cerere_verificare(**kw)  # type: ignore[arg-type]
    assert info.value.cod == "VALIDARE_LOCALA"
    return info.value


def test_normalizeaza() -> None:
    assert normalizeaza(" b-123 abc ") == "B123ABC"
    assert normalizeaza("cj_45_xyz") == "CJ45XYZ"


@pytest.mark.parametrize("numar", ["B123ABC", "B12ABC", "b 123 abc", "CJ45XYZ", "CJ-45-XYZ", "CD123A", "TC1234AB"])
def test_numere_valide(numar: str) -> None:
    assert este_numar_inmatriculare_valid(numar)


@pytest.mark.parametrize(
    "numar",
    ["XX12ABC", "B1ABC", "CJ4XYZ", "B123ABCD", "", "B\u0661\u0662\u0663ABC", "CJ45XY\u017d", "B123ABC!"],
)
def test_numere_invalide(numar: str) -> None:
    assert not este_numar_inmatriculare_valid(numar)


def test_vin() -> None:
    assert este_vin_valid(VIN)
    assert este_vin_valid("wvwzzz1jzxw000001")
    assert not este_vin_valid("WVWZZZ1JZXW00000I")
    assert not este_vin_valid("WVWZZZ1JZXW00001")
    assert not este_vin_valid("WVWZZZ1JZXW00000\u0661")


def test_tipuri() -> None:
    assert [t.value for t in TIPURI_VERIFICARE] == ["rca", "itp", "rovinieta", "arr"]


def test_tip_invalid() -> None:
    e = eroare(tip="casco", query="B123ABC")
    assert (e.camp, e.acceptate, e.mesaj) == ("tip", ["rca", "itp", "rovinieta", "arr"], "`tip` invalid.")


def test_tip_accepta_majuscule_si_enum() -> None:
    assert valideaza_cerere_verificare("RCA", "b 123 abc").tip is TipVerificare.RCA
    assert valideaza_cerere_verificare(TipVerificare.ARR, "B123ABC").tip is TipVerificare.ARR


def test_query_lipsa() -> None:
    e = eroare(tip="rca", query="  ")
    assert e.camp == "query"
    assert e.mesaj == "Lipseste `query` (numar de inmatriculare sau serie de sasiu)."


def test_rca_dupa_numar() -> None:
    assert valideaza_cerere_verificare("rca", "b-123 abc") == TintaVerificare(TipVerificare.RCA, "B123ABC", None, None)


def test_rca_dupa_numar_cu_vin() -> None:
    t = valideaza_cerere_verificare("rca", "B123ABC", serie_sasiu=VIN.lower())
    assert t.serie_sasiu == VIN


def test_rca_cu_vin_invalid_in_serie() -> None:
    e = eroare(tip="rca", query="B123ABC", serie_sasiu="ABC")
    assert e.camp == "serie_sasiu"
    assert e.mesaj == "`serie_sasiu` invalid. Seria de sasiu are 3 caractere, sunt necesare exact 17."


def test_rca_dupa_vin() -> None:
    assert valideaza_cerere_verificare("rca", VIN).query == VIN


def test_rca_query_invalid() -> None:
    e = eroare(tip="rca", query="XX12ABC")
    assert e.camp == "query"
    assert e.mesaj.startswith("`query` invalid: se accepta un numar de inmatriculare romanesc (ex: B123ABC)")


def test_itp_cere_vin() -> None:
    e = eroare(tip="itp", query="B123ABC")
    assert e.camp == "query"
    assert "RAR nu cauta dupa numarul de inmatriculare" in e.mesaj
    assert "Seria de sasiu are 7 caractere, sunt necesare exact 17." in e.mesaj


def test_itp_cu_vin_in_serie() -> None:
    t = valideaza_cerere_verificare("itp", "B123ABC", serie_sasiu=VIN)
    assert (t.query, t.serie_sasiu) == ("B123ABC", VIN)


def test_itp_vin_cu_litera_interzisa() -> None:
    e = eroare(tip="itp", query="WVWZZZ1JZXW00000O")
    assert "Standardul ISO 3779 exclude literele I, O si Q." in e.mesaj


def test_arr_cere_numar() -> None:
    e = eroare(tip="arr", query=VIN)
    assert e.mesaj == "Verificarea ARR cere numarul de inmatriculare in `query` (ex: B123ABC). ARR nu cauta dupa VIN."


def test_rovinieta() -> None:
    t = valideaza_cerere_verificare("rovinieta", "B123ABC", serie_sasiu=VIN)
    assert (t.query, t.serie_sasiu) == ("B123ABC", VIN)
    e = eroare(tip="rovinieta", query="B123ABC")
    assert e.camp == "serie_sasiu"
    assert e.mesaj.startswith("Verificarea rovinietei cere si seria de sasiu in `serie_sasiu`.")
    e = eroare(tip="rovinieta", query=VIN, serie_sasiu=VIN)
    assert e.mesaj == "Verificarea rovinietei cere numarul de inmatriculare in `query` (ex: B123ABC)."


@pytest.mark.parametrize(
    ("url", "mesaj"),
    [
        ("/relativ", "`callback_url` trebuie sa fie un URL absolut http(s)."),
        ("ftp://example.com/x", "`callback_url` trebuie sa foloseasca http sau https."),
        ("mailto:ana@example.com", "`callback_url` trebuie sa foloseasca http sau https."),
        ("https://", "`callback_url` trebuie sa fie un URL absolut http(s)."),
        ("https://[::1", "`callback_url` trebuie sa fie un URL absolut http(s)."),
        ("https://example.com/" + "a" * 2000, "`callback_url` e prea lung (maxim 2000 de caractere)."),
    ],
)
def test_callback_invalid(url: str, mesaj: str) -> None:
    e = eroare(tip="rca", query="B123ABC", callback_url=url)
    assert (e.camp, e.mesaj) == ("callback_url", mesaj)


def test_callback_valid_si_gol() -> None:
    t = valideaza_cerere_verificare("rca", "B123ABC", callback_url=" https://example.com/wh/9f3k ")
    assert t.callback_url == "https://example.com/wh/9f3k"
    assert valideaza_cerere_verificare("rca", "B123ABC", callback_url="  ").callback_url is None


def test_identificatorii_se_valideaza_inaintea_callback_url() -> None:
    assert eroare(tip="rca", query="XX", callback_url="ftp://x").camp == "query"


def test_vehicul_nou() -> None:
    assert valideaza_vehicul_nou(" b-123 abc ", None, None) == {"numarInmatriculare": "B123ABC"}
    assert valideaza_vehicul_nou(None, " wvwzzz1jzxw000001 ", True) == {
        "serieSasiu": "WVWZZZ1JZXW000001",
        "arrMonitorizat": True,
    }
    assert valideaza_vehicul_nou("B123ABC", VIN, False)["arrMonitorizat"] is False


@pytest.mark.parametrize(
    ("numar", "serie", "camp", "mesaj"),
    [
        (None, None, "numar_inmatriculare", "Trimite numarul de inmatriculare sau seria de sasiu."),
        ("  ", "", "numar_inmatriculare", "Trimite numarul de inmatriculare sau seria de sasiu."),
        (
            "B123ABC!",
            None,
            "numar_inmatriculare",
            "`numar_inmatriculare` poate contine doar litere, cifre, spatii si cratime (maxim 20).",
        ),
        ("A" * 21, None, "numar_inmatriculare", None),
        ("B\u0661\u0662\u0663ABC", None, "numar_inmatriculare", None),
        (None, "WVW-ZZZ", "serie_sasiu", "`serie_sasiu` poate contine doar litere si cifre (maxim 50)."),
        (None, "A" * 51, "serie_sasiu", None),
    ],
)
def test_vehicul_nou_invalid(numar: str | None, serie: str | None, camp: str, mesaj: str | None) -> None:
    with pytest.raises(EroareValidare) as info:
        valideaza_vehicul_nou(numar, serie, None)
    assert (info.value.camp, info.value.cod) == (camp, "VALIDARE_LOCALA")
    if mesaj is not None:
        assert info.value.mesaj == mesaj
