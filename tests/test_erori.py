import pickle

import pytest

from verificrca import (
    EroareAutentificare,
    EroareConfigurare,
    EroareConflict,
    EroareHttp,
    EroareInterzis,
    EroareLimita,
    EroareNegasit,
    EroarePlanInactiv,
    EroareRaspunsInvalid,
    EroareRetea,
    EroareServer,
    EroareTimeoutVerificare,
    EroareValidare,
    EroareVerificare,
    EroareWebhook,
    StatusDocument,
    StatusWebhook,
    TipVerificare,
    VerificRcaError,
)

TOATE = [
    EroareConfigurare,
    EroareValidare,
    EroareAutentificare,
    EroarePlanInactiv,
    EroareInterzis,
    EroareNegasit,
    EroareConflict,
    EroareLimita,
    EroareServer,
    EroareHttp,
    EroareRetea,
    EroareRaspunsInvalid,
    EroareVerificare,
    EroareTimeoutVerificare,
    EroareWebhook,
]


@pytest.mark.parametrize("clasa", TOATE)
def test_toate_erorile_mostenesc_baza(clasa: type[VerificRcaError]) -> None:
    e = clasa("mesaj", status=400, cod="X", hint="h", raspuns={"a": 1})
    assert isinstance(e, VerificRcaError)
    assert isinstance(e, Exception)
    assert str(e) == "mesaj"
    assert (e.mesaj, e.status, e.cod, e.hint, e.raspuns) == ("mesaj", 400, "X", "h", {"a": 1})


def test_valori_implicite() -> None:
    e = VerificRcaError("m")
    assert (e.status, e.cod, e.hint, e.raspuns) == (None, None, None, None)


def test_campuri_specifice() -> None:
    assert EroareValidare("m", acceptate=["rca"], camp="tip").acceptate == ["rca"]
    assert EroareValidare("m", camp="tip").camp == "tip"
    assert EroareInterzis("m", limita=5).limita == 5
    limita = EroareLimita("m", retry_after_ms=2000, utilizare_zi="300/300", utilizare_luna="1/10")
    assert (limita.retry_after_ms, limita.utilizare_zi, limita.utilizare_luna) == (2000, "300/300", "1/10")
    retea = EroareRetea("m", timeout=True, neajunsa=True)
    assert (retea.timeout, retea.neajunsa) == (True, True)
    assert (EroareRetea("m").timeout, EroareRetea("m").neajunsa) == (False, False)
    assert EroareVerificare("m", cod_sursa="vin_invalid").cod_sursa == "vin_invalid"
    assert EroareVerificare("m").cod_sursa is None


@pytest.mark.parametrize(
    "eroare",
    [
        EroareLimita("cota", status=429, cod="COTA_ATINSA", retry_after_ms=1000, utilizare_zi="3/3"),
        EroareRetea("retea", timeout=True, neajunsa=False),
        EroareValidare("tip", camp="tip", acceptate=["rca", "itp"]),
        EroareVerificare("refuzat", cod="VERIFICARE_ESUATA", cod_sursa="serie_talon_invalida"),
    ],
)
def test_erorile_trec_prin_pickle(eroare: VerificRcaError) -> None:
    refacuta = pickle.loads(pickle.dumps(eroare))
    assert type(refacuta) is type(eroare)
    assert refacuta.__dict__ == eroare.__dict__
    assert str(refacuta) == str(eroare)


def test_repr_arata_clasa_si_codul() -> None:
    assert (
        repr(EroareNegasit("lipsa", status=404, cod="NEGASIT")) == "EroareNegasit('lipsa', status=404, cod='NEGASIT')"
    )


def test_enumuri() -> None:
    assert [t.value for t in TipVerificare] == ["rca", "itp", "rovinieta", "arr"]
    assert [s.value for s in StatusDocument] == ["valid", "warning", "expired", "not_found"]
    assert [s.value for s in StatusWebhook] == ["valid", "warning", "expired", "not_found", "error"]
    assert TipVerificare("rca") is TipVerificare.RCA
    assert isinstance(TipVerificare.RCA, str)
