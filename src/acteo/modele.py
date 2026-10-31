"""Modelele publice ale SDK-ului.

Campurile sunt snake_case in Python si camelCase pe fir, exact ca in contractul API-ului.
Datele devin `datetime` cu fus orar. Campurile noi adaugate de server sunt ignorate, deci o
versiune mai veche a SDK-ului nu se strica atunci cand API-ul creste.
"""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from .tipuri import StatusDocument, StatusImagine, StatusWebhook, TipVerificare, UnghiImagine


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


# Rezultatele clientului `Acteo`, cu `tip` ingustat pe document. Sunt subclase ale
# `VerificareFinala` si `VerificareInCurs`, deci codul scris pe acelea merge neschimbat.


class RezultatRca(VerificareFinala):
    """Rezultatul final al unei verificari RCA."""

    tip: Literal[TipVerificare.RCA]


class RezultatItp(VerificareFinala):
    """Rezultatul final al unei verificari ITP."""

    tip: Literal[TipVerificare.ITP]


class RezultatRovinieta(VerificareFinala):
    """Rezultatul final al unei verificari de rovinieta."""

    tip: Literal[TipVerificare.ROVINIETA]


class RezultatArr(VerificareFinala):
    """Rezultatul final al unei verificari ARR."""

    tip: Literal[TipVerificare.ARR]


class VerificareInCursRca(VerificareInCurs):
    """Verificare RCA in curs."""

    tip: Literal[TipVerificare.RCA]


class VerificareInCursItp(VerificareInCurs):
    """Verificare ITP in curs."""

    tip: Literal[TipVerificare.ITP]


class VerificareInCursRovinieta(VerificareInCurs):
    """Verificare de rovinieta in curs."""

    tip: Literal[TipVerificare.ROVINIETA]


class VerificareInCursArr(VerificareInCurs):
    """Verificare ARR in curs."""

    tip: Literal[TipVerificare.ARR]


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


# Evenimentele celorlalte servicii (add-on-ul Webhook). `id` e unic per livrare si ramane
# acelasi la reincercari. Datele cu ora devin `datetime`; cele `yyyy-mm-dd` raman text.


class DosarWebhook(Baza):
    """Dosarul monitorizat din `dosar.eveniment` si `dosar.termen`."""

    id: str
    """ID-ul dosarului in cont."""
    numar: str
    """Numarul dosarului la instanta, ex: `1234/3/2024`."""
    eticheta: str | None
    """Eticheta pusa de tine in cont."""


class EvenimentDosar(Baza):
    """Ce s-a intamplat intr-un dosar monitorizat."""

    tip: Literal["termen_nou", "solutie", "cale_atac", "stadiu", "instanta_noua", "incheiat_auto"]
    """`termen_nou` (sedinta noua), `solutie`, `cale_atac` (apel, recurs), `stadiu`, `instanta_noua`
    sau `incheiat_auto` (180 de zile fara noutati: dosarul nu mai e monitorizat)."""
    descriere: str
    """Textul alertei, ca in email."""
    institutie: str | None
    """Instanta, cand e cunoscuta."""


class WebhookDosarEveniment(Baza):
    """Evenimentul `dosar.eveniment`: noutate intr-un dosar monitorizat."""

    event: Literal["dosar.eveniment"]
    id: str
    """ID unic al livrarii. Foloseste-l pentru deduplicare."""
    trimis_la: AwareDatetime
    dosar: DosarWebhook
    eveniment: EvenimentDosar


class SedintaDosar(Baza):
    """Sedinta care se apropie."""

    data: AwareDatetime
    ora: str | None
    """Ora sedintei, cand e cunoscuta."""
    institutie: str | None
    complet: str | None
    """Completul de judecata."""


class WebhookDosarTermen(Baza):
    """Evenimentul `dosar.termen`: se apropie o sedinta intr-un dosar monitorizat."""

    event: Literal["dosar.termen"]
    id: str
    """ID unic al livrarii. Foloseste-l pentru deduplicare."""
    trimis_la: AwareDatetime
    dosar: DosarWebhook
    sedinta: SedintaDosar
    zile_ramase: Literal[1, 3]
    """Reminder cu 3 zile si cu o zi inainte de sedinta."""


class FirmaWebhook(Baza):
    """Firma monitorizata din `firma.schimbare` si `firma.dosar`."""

    id: str
    """ID-ul firmei in cont."""
    denumire: str


class SchimbareFirma(Baza):
    """Un camp schimbat la ANAF."""

    camp: Literal[
        "radiata", "inactiv", "platitor_tva", "tva_la_incasare", "split_tva", "e_factura", "denumire", "adresa", "caen"
    ]
    valoare_veche: str | None
    """Valoarea dinainte (`"da"` / `"nu"` sau textul ANAF); `None` cand nu e cunoscuta."""
    valoare_noua: str
    data_efect: str | None
    """Data (`yyyy-mm-dd`) de la care se aplica, cand ANAF o da."""


class WebhookFirmaSchimbare(Baza):
    """Evenimentul `firma.schimbare`: ANAF a schimbat starea unei firme monitorizate."""

    event: Literal["firma.schimbare"]
    id: str
    """ID unic al livrarii. Foloseste-l pentru deduplicare."""
    trimis_la: AwareDatetime
    firma: FirmaWebhook
    schimbari: list[SchimbareFirma]


class DosarFirma(Baza):
    """Dosarul nou in instanta pe numele unei firme monitorizate."""

    numar: str
    institutie: str
    calitate_parte: str | None
    """Calitatea firmei in dosar."""
    obiect: str | None
    categorie: str | None
    """Categoria de pe portalul instantelor (ex: Faliment)."""
    insolventa: Literal["debitor", "creditor", "alta"] | None
    """Dosar de insolventa: `debitor` (firma e in procedura), `creditor` (are de recuperat bani in
    procedura altcuiva), `alta`; `None` pentru alt fel de dosar."""


class WebhookFirmaDosar(Baza):
    """Evenimentul `firma.dosar`: dosar nou in instanta pe numele unei firme monitorizate."""

    event: Literal["firma.dosar"]
    id: str
    """ID unic al livrarii. Foloseste-l pentru deduplicare."""
    trimis_la: AwareDatetime
    firma: FirmaWebhook
    dosar: DosarFirma


class MarcaWebhook(Baza):
    """Marca urmarita din `marca.schimbare` si `marca.expira`."""

    id: str
    """ID-ul marcii in cont."""
    st13: str
    """ID-ul marcii in TMview (oficiul + numarul)."""
    nume: str
    oficiu: Literal["RO", "EM"]
    """`RO` = OSIM, `EM` = EUIPO (marca a Uniunii Europene)."""
    numar_depozit: str


class WebhookMarcaSchimbare(Baza):
    """Evenimentul `marca.schimbare`: s-a schimbat ceva la o marca urmarita (OSIM sau EUIPO)."""

    event: Literal["marca.schimbare"]
    id: str
    """ID unic al livrarii. Foloseste-l pentru deduplicare."""
    trimis_la: AwareDatetime
    marca: MarcaWebhook
    schimbare: Literal["inregistrata", "reinnoita", "expirata", "anulata", "respinsa", "retrasa", "opozitie"]
    """Ce s-a schimbat; `inregistrata` = cererea in curs a devenit marca inregistrata."""
    valoare_veche: str
    """La `reinnoita`: vechea data de expirare (`yyyy-mm-dd`); la `opozitie`: numarul vechi de
    opozitii; altfel statusul vechi."""
    valoare_noua: str
    """Ca `valoare_veche`, valoarea de acum."""


class WebhookMarcaExpira(Baza):
    """Evenimentul `marca.expira`: o marca urmarita intra intr-un prag de expirare."""

    event: Literal["marca.expira"]
    id: str
    """ID unic al livrarii. Foloseste-l pentru deduplicare."""
    trimis_la: AwareDatetime
    marca: MarcaWebhook
    expira_la: str
    """Data expirarii, `yyyy-mm-dd`."""
    prag: Literal["6l", "3l", "1l", "7z", "gratie"]
    """`6l`, `3l`, `1l` (luni), `7z` (zile) inainte; `gratie` = a expirat, se mai poate reinnoi cu taxa."""
    reinnoire_pana_la: str | None
    """La `gratie`: ultima zi (`yyyy-mm-dd`) in care se mai poate reinnoi; altfel `None`."""


class PersoanaWebhook(Baza):
    """Persoana monitorizata din `asigurare.schimbare`."""

    id: str
    """ID-ul persoanei in cont."""
    nume: str


class WebhookAsigurareSchimbare(Baza):
    """Evenimentul `asigurare.schimbare`: s-a schimbat statutul de asigurat la CNAS."""

    event: Literal["asigurare.schimbare"]
    id: str
    """ID unic al livrarii. Foloseste-l pentru deduplicare."""
    trimis_la: AwareDatetime
    persoana: PersoanaWebhook
    statut: Literal["asigurat", "neasigurat", "necunoscut"]
    are_card: bool | None
    """Cardul de sanatate e emis; `None` cand CNAS nu spune."""
    verificat_la: AwareDatetime
    """Cand a fost interogat CNAS."""


class TermenWebhook(Baza):
    """Termenul din cont din `termen.expira`."""

    id: str
    """ID-ul termenului in cont."""
    categorie: str
    """`auto`, `personale`, `sanatate`, `afaceri` sau `casa`."""
    tip: str
    eticheta: str
    """Numele termenului, ex: Pasaport sau numele dat de tine."""
    al: str | None
    """Al cui e termenul: numarul masinii, firma sau persoana."""
    expira_la: str
    """Data scadentei, `yyyy-mm-dd`."""


class WebhookTermenExpira(Baza):
    """Evenimentul `termen.expira`: un termen din cont intra in pragul de 30 sau de 3 zile."""

    event: Literal["termen.expira"]
    id: str
    """ID unic al livrarii. Foloseste-l pentru deduplicare."""
    trimis_la: AwareDatetime
    termen: TermenWebhook
    zile_ramase: int
    """Zile intregi ramase pana la scadenta."""
    prag: Literal[30, 3]
    """Pragul atins, in zile."""


WebhookNotificare = (
    WebhookDocumentExpira
    | WebhookDosarEveniment
    | WebhookDosarTermen
    | WebhookFirmaSchimbare
    | WebhookFirmaDosar
    | WebhookMarcaSchimbare
    | WebhookMarcaExpira
    | WebhookAsigurareSchimbare
    | WebhookTermenExpira
    | WebhookTest
)
"""Orice notificare trimisa la URL-ul de webhook al contului. Distinge-le dupa `event`."""


# Produsele cu raspuns sincron: decodare VIN, numere disponibile, poze de masini.


class StructuraVin(Baza):
    """Structura VIN-ului, calculata doar din cele 17 caractere."""

    wmi: str
    """Pozitiile 1-3: producatorul."""
    vds: str
    """Pozitiile 4-9: descrierea vehiculului."""
    vis: str
    """Pozitiile 10-17: exemplarul."""
    regiune: str | None
    tara: str | None
    cifra_control: Literal["ok", "gresita", "neaplicabila"]
    """Cifra de control (pozitia 9)."""
    cifra_control_asteptata: str | None
    """Cifra de control asteptata, cand se aplica."""
    ani_posibili: list[int]
    """Anii de fabricatie posibili dupa pozitia 10."""


class DecodareVin(Baza):
    """Rezultatul decodarii unui VIN."""

    vin: str
    """VIN-ul normalizat."""
    gasit: bool
    """Marca e cunoscuta."""
    taxat: bool
    """S-a consumat o cerere din plan: doar cand marca si modelul sunt gasite."""
    marca: str | None
    model: str | None
    an_fabricatie: int | None
    sursa_an: Literal["pozitia-10", "generatie", "anunturi"] | None
    """De unde vine anul: `pozitia-10` confirmata, startul `generatie` sau `anunturi`."""
    modele_posibile: list[str]
    """Modelele posibile, cand sursele nu cad de acord. Mereu gol cand `taxat` e fals."""
    structura: StructuraVin
    limite: Limite | None = None
    """Cota ramasa dupa aceasta cerere, cand API-ul o trimite."""


class NumarDisponibil(Baza):
    """Raspunsul DGPCI pentru un numar de inmatriculare."""

    numar: str
    """Numarul normalizat."""
    disponibil: bool
    """Numarul e liber la DGPCI si poate fi rezervat."""
    mesaj: str | None
    """Textul intors de DGPCI, cand exista."""
    limite: Limite | None = None
    """Cota ramasa dupa aceasta cerere, cand API-ul o trimite."""


class GeneratieMasina(Baza):
    """Generatia aleasa dupa an."""

    eticheta: str
    """Numele generatiei, ex: `Volkswagen Golf VII`."""
    an_de: int
    """Primul an al generatiei."""
    an_pana: int | None
    """Ultimul an; `None` = inca in productie."""
    caroserie: str
    """Caroseria, ex: `5-door hatchback`."""


class ImagineMasina(Baza):
    """Poza de studio a unei masini, sau poza generica (masina sub husa)."""

    gata: bool
    """Poza e a masinii cerute; fals = poza generica."""
    status: StatusImagine
    taxat: bool
    """S-a consumat o cerere din plan: doar cand `status` e `gata`."""
    url: str | None
    """Link semnat spre poza (WebP transparent), valabil pana la `expira_la`. `None` doar daca nici
    poza generica nu e disponibila."""
    expira_la: AwareDatetime | None
    """Cand expira `url`. `None` cand `url` e `None`."""
    unghi: UnghiImagine
    umbra: bool
    """Poza are umbra sub masina."""
    latime: int
    """Latimea pozei, in pixeli."""
    inaltime: int
    """Inaltimea pozei, in pixeli."""
    marca: str
    """Marca canonica, sau cea trimisa daca inca nu e cunoscuta."""
    model: str
    """Modelul canonic, sau cel trimis daca inca nu e cunoscut."""
    generatie: GeneratieMasina | None
    """Generatia aleasa dupa an; `None` cand nu e aleasa inca."""
    limite: Limite | None = None
    """Cota ramasa dupa aceasta cerere, cand API-ul o trimite."""
    retry_after_ms: int | None = None
    """La `status == "in-lucru"`: dupa cat timp sa ceri din nou poza, din `Retry-After`."""
