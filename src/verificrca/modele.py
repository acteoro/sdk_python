"""Modelele publice ale SDK-ului.

Campurile sunt snake_case in Python si camelCase pe fir, exact ca in contractul API-ului.
Datele devin `datetime` cu fus orar. Campurile noi adaugate de server sunt ignorate, deci o
versiune mai veche a SDK-ului nu se strica atunci cand API-ul creste.
"""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from .tipuri import StatusDocument, StatusWebhook, TipVerificare


class Baza(BaseModel):
    """Configuratia comuna: imuabil, alias camelCase, campuri necunoscute ignorate."""

    model_config = ConfigDict(frozen=True, alias_generator=to_camel, populate_by_name=True, extra="ignore")


class Cota(Baza):
    """O cota a planului: cate verificari permite si cate au ramas dupa aceasta cerere."""

    limita: int
    ramase: int


class Limite(Baza):
    """Cat mai ai din cota planului, din headerele `X-RateLimit-*`."""

    zi: Cota
    """Cota zilnica; se reseteaza la miezul noptii."""
    luna: Cota
    """Cota lunara."""


class VerificareFinala(Baza):
    """Rezultatul final al unei verificari."""

    tip: TipVerificare
    query: str
    """Identificatorul dupa care s-a cautat (la RCA cu VIN, acesta e VIN-ul)."""
    numar_inmatriculare: str | None
    """Numarul verificat, `None` cand cautarea s-a facut doar dupa VIN."""
    serie_sasiu: str | None
    """VIN-ul verificat, `None` cand cautarea s-a facut doar dupa numar."""
    checked_at: AwareDatetime
    """Cand a fost interogata sursa oficiala."""
    status: StatusDocument
    expires_at: AwareDatetime | None
    """Data expirarii documentului, `None` daca nu exista document valabil."""
    request_id: str | None = None
    """Prezent doar cand ai trimis `callback_url`. Apare si in webhook."""
    hint: str | None = None
    """Recomandarea API-ului, ex: la RCA cerut doar dupa numar, sa trimiti si VIN-ul."""
    limite: Limite | None = None
    """Cota ramasa dupa aceasta cerere, cand API-ul o trimite."""


class VerificareInCurs(Baza):
    """Verificare pusa in coada: sursa oficiala e interogata acum.

    Paseaz-o la `rezultat()` sau `asteapta()`. Se poate salva cu `model_dump_json()` si reface cu
    `VerificareInCurs.model_validate_json()`, de exemplu intr-un job de coada.
    """

    status: Literal["processing"] = "processing"
    tip: TipVerificare
    query: str
    """Identificatorul dupa care se face pollingul."""
    serie_sasiu: str | None = None
    """Seria de sasiu trimisa la polling; completata doar la rovinieta."""
    since: int
    """Momentul (ms epoch) de la care un rezultat e considerat nou."""
    request_id: str | None = None
    queued_at: AwareDatetime | None = None
    hint: str | None = None
    limite: Limite | None = None


class ReferintaVerificare(Baza):
    """Ce trebuie ca sa interoghezi rezultatul unei verificari fara obiectul `VerificareInCurs`."""

    tip: TipVerificare
    query: str
    """Identificatorul dupa care se face pollingul (la RCA cu VIN, VIN-ul)."""
    serie_sasiu: str | None = None
    """Doar la rovinieta."""
    since: int | None = None
    """Momentul (ms epoch) al cererii POST. Fara el, e acceptat orice rezultat recent."""


class Vehicul(Baza):
    """Un vehicul monitorizat din cont, cu datele de expirare ale documentelor."""

    id: str
    numar_inmatriculare: str | None
    serie_sasiu: str | None
    serie_talon: str | None = None
    """Numarul certificatului de inmatriculare (talon). Fara el rovinieta nu se verifica."""
    serie_talon_respinsa: bool = False
    """Sursa a respins numarul talonului; rovinieta nu se mai verifica pana la corectarea lui."""
    rca_expira_la: AwareDatetime | None
    itp_expira_la: AwareDatetime | None
    """`None` pana la primul rezultat (ITP-ul cere VIN)."""
    rovinieta_expira_la: AwareDatetime | None
    """`None` pana la primul rezultat (rovinieta cere numar, VIN si numarul talonului)."""
    arr_expira_la: AwareDatetime | None
    """Completata doar cand `arr_monitorizat` e adevarat."""
    arr_monitorizat: bool
    activ: bool
    """Vehiculul e verificat automat si primeste notificari de expirare."""
    created_at: AwareDatetime


class VehiculWebhook(Baza):
    """Vehiculul din notificarea `document.expira`."""

    id: str
    numar_inmatriculare: str | None
    serie_sasiu: str | None


class WebhookRezultat(Baza):
    """Payloadul POST trimis la `callback_url` cand o verificare se termina."""

    request_id: str
    tip: TipVerificare
    query: str
    serie_sasiu: str | None
    status: StatusWebhook
    result: VerificareFinala | None
    """Rezultatul complet, `None` la `status == "error"`."""
    checked_at: AwareDatetime | None
    error: str | None = None


class WebhookDocumentExpira(Baza):
    """Evenimentul `document.expira`: un document a intrat intr-un prag de expirare."""

    event: Literal["document.expira"]
    id: str
    """ID unic al livrarii. Foloseste-l pentru deduplicare."""
    vehicul: VehiculWebhook
    document: TipVerificare
    expira_la: AwareDatetime
    zile_ramase: int
    prag: int
    """Pragul atins, in zile (RCA/ITP/rovinieta: 30, 14, 3; ARR: 60, 50, 45)."""
    trimis_la: AwareDatetime


class WebhookTest(Baza):
    """Evenimentul `webhook.test`, trimis din butonul de test din dashboard."""

    event: Literal["webhook.test"]
    id: str
    mesaj: str
    trimis_la: AwareDatetime
