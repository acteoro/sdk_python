"""Ruleaza secvential (acelasi cont). O verificare reala poate dura minute."""

from __future__ import annotations

from datetime import datetime

import pytest

from acteo import (
    AsyncActeo,
    EroareAutentificare,
    EroareConflict,
    EroareNegasit,
    StatusDocument,
    TipVerificare,
    VerificareFinala,
    VerificareInCurs,
    normalizeaza,
)
from e2e.conftest import BASE_URL, CHEIE, CU_FLOTA, CU_VERIFICARI, NUMAR, VIN, client

fara_cheie = pytest.mark.skipif(not CHEIE, reason="lipseste ACTEO_API_KEY in .env.e2e")


def verifica_final(r: VerificareFinala) -> None:
    assert isinstance(r.status, StatusDocument)
    assert isinstance(r.checked_at, datetime)
    assert r.expires_at is None or isinstance(r.expires_at, datetime)


def test_cheie_inexistenta_primeste_eroare_autentificare() -> None:
    with client("e2e_cheie_inexistenta_00000") as acteo, pytest.raises(EroareAutentificare) as info:
        acteo.auto.flota.lista()
    assert info.value.status == 401


@fara_cheie
def test_lista_vehicule_gratuita() -> None:
    with client() as acteo:
        for v in acteo.auto.flota.lista():
            assert isinstance(v.activ, bool)
            assert isinstance(v.created_at, datetime)


@fara_cheie
@pytest.mark.anyio
async def test_lista_vehicule_async() -> None:
    async with AsyncActeo(base_url=BASE_URL, user_agent="e2e") as acteo:
        assert isinstance(await acteo.auto.flota.lista(), list)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.skipif(not (CHEIE and CU_FLOTA and NUMAR), reason="cere ACTEO_E2E_FLOTA=1 si NUMAR")
def test_flota_adauga_lista_sterge() -> None:
    assert NUMAR is not None
    with client() as acteo:
        try:
            adaugat = acteo.auto.flota.adauga(numar_inmatriculare=NUMAR, serie_sasiu=VIN)
        except EroareConflict as e:
            # Vehiculul e deja in cont: nu il atingem, validam doar raspunsul 409.
            assert e.status == 409
            return
        try:
            assert adaugat.numar_inmatriculare == normalizeaza(NUMAR)
            assert any(v.id == adaugat.id for v in acteo.auto.flota.lista())
        finally:
            acteo.auto.flota.sterge(adaugat.id)
        assert all(v.id != adaugat.id for v in acteo.auto.flota.lista())
        with pytest.raises(EroareNegasit):
            acteo.auto.flota.sterge(adaugat.id)


@pytest.mark.skipif(not (CHEIE and CU_VERIFICARI and NUMAR), reason="cere ACTEO_E2E_VERIFICARI=1 si NUMAR")
def test_rca_porneste_asteapta_reciteste() -> None:
    assert NUMAR is not None
    with client() as acteo:
        pornit = acteo.auto.rca.porneste(numar=NUMAR, vin=VIN)
        assert pornit.limite is not None and pornit.limite.zi.limita > 0
        final = acteo.auto.rca.asteapta(pornit, timeout_ms=600_000) if isinstance(pornit, VerificareInCurs) else pornit
        verifica_final(final)
        # GET-ul nu consuma din cota si trebuie sa dea acelasi rezultat.
        recitit = acteo.auto.rca.rezultat(final.query)
        assert recitit.status == final.status


@pytest.mark.skipif(not (CHEIE and CU_VERIFICARI and VIN), reason="cere ACTEO_E2E_VERIFICARI=1 si VIN")
def test_itp_dupa_vin() -> None:
    assert VIN is not None
    with client() as acteo:
        itp = acteo.auto.itp.verifica(VIN, timeout_ms=600_000)
    verifica_final(itp)
    assert itp.tip is TipVerificare.ITP
