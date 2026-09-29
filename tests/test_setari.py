import pytest

from tests.conftest import CHEIE, setari_test
from verificrca import VERSIUNE_SDK, EroareConfigurare, SetariRetry


def test_implicite() -> None:
    s = setari_test(retry=None)
    assert s.api_key == CHEIE
    assert s.retry == SetariRetry(3, 500, 10_000)
    assert s.user_agent == f"verificrca-sdk-python/{VERSIUNE_SDK}"


def test_cheia_din_mediu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERIFICRCA_API_KEY", f"  {CHEIE}  ")
    assert setari_test(api_key=None).api_key == CHEIE


def test_cheie_lipsa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VERIFICRCA_API_KEY", raising=False)
    with pytest.raises(EroareConfigurare) as info:
        setari_test(api_key=None)
    assert info.value.mesaj == (
        "Lipseste cheia API. Trimite `api_key` sau seteaza variabila de mediu VERIFICRCA_API_KEY."
    )
    assert info.value.hint == "Cheia se genereaza din https://www.verificrca.ro/dashboard/api"


@pytest.mark.parametrize("cheie", ["scurta", "x" * 129])
def test_cheie_lungime(cheie: str) -> None:
    with pytest.raises(EroareConfigurare, match="intre 16 si 128"):
        setari_test(api_key=cheie)


@pytest.mark.parametrize("cheie", ["vrca_test 0123456789", "vrca_test\n0123456789", "vrca_test_0123456789\u0103"])
def test_cheie_cu_caractere_neacceptate(cheie: str) -> None:
    with pytest.raises(EroareConfigurare) as info:
        setari_test(api_key=cheie)
    assert info.value.mesaj == "Cheia API contine caractere neacceptate (spatii sau caractere non-ASCII)."


def test_base_url() -> None:
    assert setari_test(base_url="https://api.example.com/").base_url == "https://api.example.com"
    assert setari_test(base_url="http://example.com:8443").base_url == "http://example.com:8443"


@pytest.mark.parametrize("url", ["nu-e-url", "ftp://example.com", "https://", "//example.com"])
def test_base_url_invalid(url: str) -> None:
    with pytest.raises(EroareConfigurare, match="`base_url` invalid"):
        setari_test(base_url=url)


@pytest.mark.parametrize("timeout", [0, -1, True, "30"])
def test_timeout_invalid(timeout: object) -> None:
    with pytest.raises(EroareConfigurare) as info:
        setari_test(timeout_ms=timeout)
    assert info.value.mesaj == "`timeout_ms` trebuie sa fie pozitiv."


def test_retry_variante() -> None:
    assert setari_test(retry=False).retry is None
    assert setari_test(retry=True).retry == SetariRetry()
    assert setari_test(retry={"incercari": 5}).retry == SetariRetry(incercari=5)
    assert setari_test(retry=SetariRetry(1, 100, 200)).retry == SetariRetry(1, 100, 200)


def test_retry_cheie_necunoscuta() -> None:
    with pytest.raises(EroareConfigurare) as info:
        setari_test(retry={"incercari": 1, "pauza": 3})
    assert info.value.mesaj == "Optiuni `retry` necunoscute: pauza."


@pytest.mark.parametrize("valoare", [-1, 1.5, True, "3"])
def test_retry_valoare_invalida(valoare: object) -> None:
    with pytest.raises(EroareConfigurare) as info:
        setari_test(retry={"incercari": valoare})
    assert info.value.mesaj == "`retry.incercari` trebuie sa fie un numar intreg pozitiv sau zero."


def test_retry_tip_invalid() -> None:
    with pytest.raises(EroareConfigurare, match="`retry` trebuie sa fie"):
        setari_test(retry="da")


def test_user_agent_propriu() -> None:
    assert setari_test(user_agent="flota-mea/2.1").user_agent.endswith(" flota-mea/2.1")


@pytest.mark.parametrize("agent", ["flota-mea/ă", "flota\nX-Injectat: 1", "tab\tagent"])
def test_user_agent_cu_caractere_neacceptate(agent: str) -> None:
    with pytest.raises(EroareConfigurare) as info:
        setari_test(user_agent=agent)
    assert info.value.mesaj == "`user_agent` contine caractere neacceptate (doar ASCII tiparibil)."
