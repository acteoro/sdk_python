# verificrca: API verificare RCA, ITP, rovinietă și ARR pentru Python

[![PyPI](https://img.shields.io/pypi/v/verificrca.svg)](https://pypi.org/project/verificrca/)
[![Python](https://img.shields.io/pypi/pyversions/verificrca.svg)](https://pypi.org/project/verificrca/)
[![licență MIT](https://img.shields.io/pypi/l/verificrca.svg)](./LICENSE)

SDK-ul oficial Python pentru [API-ul verificrca.ro](https://www.verificrca.ro/api-acces). Cu el verifici din cod dacă o mașină are RCA valabil, ITP la zi, rovinietă plătită sau copie conformă ARR, după numărul de înmatriculare sau seria de șasiu (VIN). Datele vin din sursele oficiale: baza AIDA pentru asigurarea RCA, RAR pentru inspecția tehnică periodică, CNAIR pentru rovinietă și ARR pentru transportul rutier.

Pe lângă verificările la cerere, SDK-ul gestionează vehiculele monitorizate din cont și citește webhook-urile trimise când un document se apropie de expirare. Are client sincron (Django, Flask, scripturi, Celery) și asincron (FastAPI, asyncio), cu tipuri complete. Dacă ai o firmă de leasing, rent-a-car sau curierat, un service auto ori pur și simplu o flotă, afli din timp ce RCA, ITP sau rovinietă expiră, înainte să vină amenda.

> Ai nevoie de o cheie API (`vrca_...`). O generezi din [contul tău verificrca.ro](https://www.verificrca.ro/dashboard/api), după ce alegi un plan de pe [pagina API](https://www.verificrca.ro/api-acces).

```python
from verificrca import VerificRca

with VerificRca() as vrca:  # cheia din VERIFICRCA_API_KEY
    rca = vrca.verificari.verifica_si_asteapta(tip="rca", query="B123ABC")
    print(rca.status.value, rca.expires_at)  # valid 2027-03-01 00:00:00+00:00
```

## Cuprins

- [Ce face SDK-ul](#ce-face-sdk-ul)
- [Instalare](#instalare)
- [Pornire rapidă](#pornire-rapidă)
- [Client async](#client-async)
- [Ce identificator cere fiecare verificare](#ce-identificator-cere-fiecare-verificare)
- [Cum decurge o verificare](#cum-decurge-o-verificare)
- [Referință API](#referință-api)
- [Webhook-uri](#webhook-uri)
- [Erori](#erori)
- [Reîncercări, backoff și timeout](#reîncercări-backoff-și-timeout)
- [Cotă și limite](#cotă-și-limite)
- [Exemple](#exemple)
- [Întrebări frecvente](#întrebări-frecvente)

## Ce face SDK-ul

| Funcție | Ce primești |
|---|---|
| Verificare RCA după număr sau VIN | Starea poliței RCA și data expirării, din baza AIDA |
| Verificare ITP după VIN | Data până la care e valabilă inspecția tehnică, din RAR |
| Verificare rovinietă | Dacă rovinieta e plătită și până când, din CNAIR |
| Verificare copie conformă ARR | Valabilitatea copiei conforme pentru transportatori |
| Gestionare flotă | Adaugi, listezi și ștergi vehiculele monitorizate automat |
| Webhook-uri | Rezultatul verificării la URL-ul tău, alerte `document.expira` la 30, 14 și 3 zile |
| Validare locală | Numărul de înmatriculare, VIN-ul și numărul talonului sunt verificate înainte de cerere, deci o greșeală de tastare nu consumă din cotă |
| Excepții tipate | O clasă de excepție pentru fiecare situație, cu mesaj în română și `hint` de rezolvare |
| Reîncercări sigure | Backoff exponențial cu jitter, `Retry-After` respectat, niciun POST taxat de două ori |
| Sync și async | `VerificRca` pentru cod sincron, `AsyncVerificRca` pentru asyncio și FastAPI, cu aceleași metode |
| Tipuri complete | Modele Pydantic imuabile, `py.typed`, verificat cu mypy în mod strict |

## Instalare

```bash
pip install verificrca
# sau
uv add verificrca
poetry add verificrca
```

SDK-ul cere Python 3.10 sau mai nou și folosește [httpx](https://www.python-httpx.org/) pentru cereri și [Pydantic](https://docs.pydantic.dev/) pentru modele.

Cheia API o poți da direct în constructor (`VerificRca(api_key="vrca_...")`) sau prin variabila de mediu `VERIFICRCA_API_KEY`:

```bash
export VERIFICRCA_API_KEY=vrca_xxxxxxxxxxxxxxxx
```

Nu pune cheia în cod care ajunge într-un repo public sau într-o aplicație instalată pe telefonul clienților. Cheia dă acces la cota contului tău și la vehiculele din el.

## Pornire rapidă

### Verificare RCA după număr de înmatriculare

```python
from verificrca import StatusDocument, VerificRca

with VerificRca() as vrca:  # citește VERIFICRCA_API_KEY
    rca = vrca.verificari.verifica_si_asteapta(tip="rca", query="B 123 ABC")

if rca.status is StatusDocument.EXPIRED:
    print("Mașina nu are RCA valabil.")
elif rca.status is StatusDocument.WARNING and rca.expires_at:
    print(f"RCA-ul expiră curând, pe {rca.expires_at:%d.%m.%Y}")
```

Pentru RCA îți recomandăm să trimiți și VIN-ul. Baza AIDA găsește polița mai sigur după seria de șasiu, iar uneori o poliță emisă pe VIN nu apare la căutarea după număr:

```python
rca = vrca.verificari.verifica_si_asteapta(tip="rca", query="B123ABC", serie_sasiu="WVWZZZ1JZXW000001")
```

### Verificare ITP după serie de șasiu

```python
itp = vrca.verificari.verifica_si_asteapta(tip="itp", query="WVWZZZ1JZXW000001")
print(f"ITP valabil până la {itp.expires_at:%d.%m.%Y}" if itp.expires_at else itp.status.value)
```

### Verificare rovinietă

```python
rovinieta = vrca.verificari.verifica_si_asteapta(
    tip="rovinieta",
    query="B123ABC",
    serie_sasiu="WVWZZZ1JZXW000001",
    serie_talon="I00639603F",
)
```

Rovinieta cere trei identificatori: numărul de înmatriculare, seria de șasiu și numărul certificatului de înmatriculare (`serie_talon`), tipărit jos pe talon. Sursa oficială le verifică împreună, așa că fără numărul talonului SDK-ul oprește cererea înainte să plece și nu consumă din cotă. Vezi [unde găsești numărul certificatului de înmatriculare](#unde-găsesc-numărul-certificatului-de-înmatriculare).

### Verificare copie conformă ARR

```python
arr = vrca.verificari.verifica_si_asteapta(tip="arr", query="CJ45XYZ")
```

`tip` poate fi text (`"rca"`, `"itp"`, `"rovinieta"`, `"arr"`, indiferent de majuscule), de exemplu direct din valoarea trimisă de un formular, sau enum-ul `TipVerificare.RCA`.

## Client async

`AsyncVerificRca` are aceleași metode, aceleași argumente și aceleași excepții, doar că le apelezi cu `await`. E potrivit pentru FastAPI, Starlette, aiohttp sau orice cod asyncio, și îți permite să rulezi mai multe verificări în paralel:

```python
import asyncio

from verificrca import AsyncVerificRca, VerificRcaError


async def main() -> None:
    numere = ["B123ABC", "CJ45XYZ", "B12XYZ"]
    async with AsyncVerificRca() as vrca:
        rezultate = await asyncio.gather(
            *(vrca.verificari.verifica_si_asteapta(tip="rca", query=n) for n in numere),
            return_exceptions=True,
        )
    for numar, r in zip(numere, rezultate):
        if isinstance(r, VerificRcaError):
            print(f"{numar}: {r.mesaj}")
        elif not isinstance(r, BaseException):
            print(f"{numar}: {r.status.value}")


asyncio.run(main())
```

Pauzele dintre interogări folosesc `anyio.sleep`, deci nu blochează event loop-ul.

## Ce identificator cere fiecare verificare

Fiecare sursă oficială caută după alt identificator. SDK-ul aplică aceleași reguli ca API-ul și te oprește înainte de cerere dacă lipsește ceva.

| `tip` | `query` | `serie_sasiu` | `serie_talon` | Sursa |
|---|---|---|---|---|
| `rca` | număr de înmatriculare **sau** VIN | opțional, recomandat | nu | AIDA / BAAR |
| `itp` | VIN (17 caractere) | nu | nu | RAR |
| `rovinieta` | număr de înmatriculare | **obligatoriu** | **obligatoriu** | CNAIR |
| `arr` | număr de înmatriculare | nu | nu | ARR |

Formatele de număr acceptate: București (`B123ABC`, `B12ABC`), județe (`CJ45XYZ`, `IS08BCD`), corp diplomatic (`CD123A`) și numere temporare (`TC1234AB`). Spațiile și cratimele sunt eliminate automat, deci `b-123 abc` devine `B123ABC`. VIN-ul trebuie să aibă exact 17 caractere, fără literele I, O și Q (standardul ISO 3779). Numărul certificatului de înmatriculare (`serie_talon`, de forma `I00639603F`) e păstrat doar cu litere și cifre, cu majuscule, și trebuie să aibă între 6 și 20 de caractere, dintre care cel puțin o cifră. La celelalte tipuri de verificare `serie_talon` e ignorat și nu se trimite.

## Cum decurge o verificare

1. **Cerere** (`porneste`). Dacă există un rezultat recent pentru mașina respectivă, îl primești imediat. Altfel verificarea intră în coadă și primești un obiect `VerificareInCurs`.
2. **Interogarea sursei.** Sursa oficială e consultată în fundal. Dacă nu răspunde, verificarea se încheie cu eroare.
3. **Rezultatul** ajunge la tine pe una din trei căi:
   - `verifica_si_asteapta()` face tot drumul și întoarce direct rezultatul final;
   - `rezultat()` sau `asteapta()` fac polling, fără să consume din cotă;
   - webhook: dacă trimiți `callback_url`, API-ul face POST cu rezultatul la adresa ta.

Doar pasul 1 consumă din cota planului. Interogările de rezultat sunt gratuite.

### Statusuri

Rezultatul final (`VerificareFinala`) are `status` de tip `StatusDocument`:

| `status` | Înseamnă | `expires_at` |
|---|---|---|
| `StatusDocument.VALID` (`"valid"`) | Document valabil | data expirării |
| `StatusDocument.WARNING` (`"warning"`) | Expiră curând: RCA în 14 zile, ITP în 30, rovinietă în 7, ARR în 14 | data expirării |
| `StatusDocument.EXPIRED` (`"expired"`) | Expirat sau inexistent, confirmat de sursă | data expirării sau `None` |
| `StatusDocument.NOT_FOUND` (`"not_found"`) | Sursa nu a găsit vehiculul | `None` |

O verificare încă în curs e un obiect `VerificareInCurs`, nu un rezultat. Le deosebești cu `isinstance()`. Când sursa oficială nu răspunde, SDK-ul aruncă `EroareVerificare` cu `cod` `VERIFICARE_ESUATA` și poți relua cererea. Când sursa refuză datele trimise, `cod` rămâne `VERIFICARE_ESUATA`, iar atributul `cod_sursa` spune care câmp e greșit: `serie_talon_invalida`, `vin_invalid` sau `numar_invalid`. În cazul ăsta o reluare cu aceleași date nu ajută, corectează întâi câmpul.

## Referință API

### `VerificRca(...)` și `AsyncVerificRca(...)`

Constructorul primește doar argumente numite, toate opționale:

| Argument | Tip | Implicit | Descriere |
|---|---|---|---|
| `api_key` | `str \| None` | variabila `VERIFICRCA_API_KEY` | Cheia API `vrca_...` |
| `base_url` | `str` | `https://www.verificrca.ro` | Adresa API-ului |
| `timeout_ms` | `float` | `30000` | Timeout pe fiecare cerere HTTP, aplicat clientului construit de SDK |
| `retry` | `SetariRetry \| dict \| bool` | `SetariRetry(incercari=3, intarziere_initiala_ms=500, intarziere_maxima_ms=10000)` | Politica de reîncercare; `False` o oprește |
| `http_client` | `httpx.Client` / `httpx.AsyncClient` | construit de SDK | Client propriu (proxy, certificate, teste) |
| `user_agent` | `str \| None` | | Adăugat la `User-Agent`, util în loguri |

Constructorul nu face nicio cerere pe rețea. Aruncă `EroareConfigurare` dacă lipsește cheia sau dacă o opțiune e invalidă.

Folosește clientul cu `with` (sau `async with`), ori apelează `close()` / `await aclose()` la final, ca să închizi conexiunile. Un `http_client` dat de tine își păstrează propriul timeout și nu e închis de SDK. Redirecturile nu sunt urmate: un răspuns 3xx devine `EroareHttp`.

### `verificari.porneste(*, tip, query, serie_sasiu=None, serie_talon=None, callback_url=None)`

Pornește o verificare și **consumă o unitate din cotă**. Întoarce fie rezultatul final (`VerificareFinala`, dacă există unul recent), fie un obiect `VerificareInCurs` pe care îl poți da mai departe la `rezultat()` sau `asteapta()`.

```python
from verificrca import VerificareInCurs

r = vrca.verificari.porneste(
    tip="itp",
    query="WVWZZZ1JZXW000001",
    callback_url="https://example.com/webhooks/verificrca/9f3k2",  # opțional
)

if isinstance(r, VerificareInCurs):
    print("În coadă, request_id:", r.request_id)
    final = vrca.verificari.asteapta(r)
```

### `verificari.rezultat(ref)`

Interoghează o singură dată. Nu consumă din cotă. Primește obiectul `VerificareInCurs` întors de `porneste()` sau un `ReferintaVerificare` construit de tine.

```python
from verificrca import ReferintaVerificare, VerificareInCurs

r = vrca.verificari.rezultat(ReferintaVerificare(tip="rca", query="B123ABC"))
if isinstance(r, VerificareInCurs):
    r = vrca.verificari.asteapta(r, interval_ms=5000, timeout_ms=120_000)
```

### `verificari.asteapta(ref, *, interval_ms=3000, timeout_ms=300000)`

Face polling până la rezultatul final. `interval_ms` are minimum 2000, iar `timeout_ms` e implicit 5 minute. La depășire aruncă `EroareTimeoutVerificare`. Reîncercările se opresc la termen, așa că doar o cerere HTTP deja pornită îl poate depăși, cu cel mult timeout-ul ei.

### `verificari.verifica_si_asteapta(*, tip, query, serie_sasiu=None, serie_talon=None, callback_url=None, interval_ms=3000, timeout_ms=300000)`

`porneste()` urmat de `asteapta()`, într-un singur apel. E calea cea mai simplă pentru scripturi și joburi cron.

### `vehicule.lista()`

Toate vehiculele din cont, cu datele de expirare `rca_expira_la`, `itp_expira_la`, `rovinieta_expira_la` și `arr_expira_la` (ca `datetime` sau `None`). Câmpul `activ` e `True` cât timp vehiculul e verificat automat și primește notificări de expirare. `serie_talon` e numărul certificatului de înmatriculare salvat pentru vehicul (sau `None`), iar `serie_talon_respinsa` devine `True` când sursa oficială l-a respins: rovinieta nu se mai verifică până când îl corectezi. Vehiculele din cont sunt verificate automat și periodic, deci lista îți dă o imagine la zi a flotei fără să consume din cota de verificări.

```python
for v in vrca.vehicule.lista():
    rca = f"{v.rca_expira_la:%d.%m.%Y}" if v.rca_expira_la else "-"
    print(v.numar_inmatriculare, "RCA:", rca)

v = vrca.vehicule.adauga(
    numar_inmatriculare="B123ABC",
    serie_sasiu="WVWZZZ1JZXW000001",
    serie_talon="I00639603F",
)
vrca.vehicule.sterge(v.id)
```

### `vehicule.adauga(*, numar_inmatriculare=None, serie_sasiu=None, serie_talon=None, arr_monitorizat=None)`

Adaugă un vehicul în monitorizare. Trimite cel puțin un identificator (`numar_inmatriculare`, `serie_sasiu`); opționale sunt `serie_talon` și `arr_monitorizat`. Rovinieta unui vehicul din flotă se verifică doar când are număr, VIN și numărul talonului. Poți primi `EroareInterzis` cu `cod` `LIMIT_ATINS` când ai atins numărul de mașini din plan, sau `EroareConflict` când vehiculul există deja.

### `vehicule.sterge(id)`

Scoate vehiculul din cont. Aruncă `EroareNegasit` dacă ID-ul nu există în contul cheii.

Operațiile pe vehicule nu consumă din cota de verificări, dar cer un plan activ.

### Utilitare de validare

```python
from verificrca import (
    este_numar_inmatriculare_valid,
    este_serie_talon_valida,
    este_vin_valid,
    normalizeaza,
    normalizeaza_serie_talon,
)

este_numar_inmatriculare_valid("CJ 45 XYZ")  # True
este_vin_valid("WVWZZZ1JZXW00000I")  # False: litera I nu e permisă în VIN
normalizeaza(" b-123 abc ")  # "B123ABC"
este_serie_talon_valida("I00639603F")  # True
normalizeaza_serie_talon(" i 00639603-f ")  # "I00639603F"
```

Le poți folosi în formularele tale (de exemplu într-un validator Django sau Pydantic), ca să verifici datele înainte să ajungă la server.

### Constante

| Constantă | Valoare |
|---|---|
| `TIPURI_VERIFICARE` | `TipVerificare.RCA`, `ITP`, `ROVINIETA`, `ARR`, util pentru dropdown-uri și validare |
| `HEADER_CHEIE` | `"x-verificrca-key"`, headerul cu cheia de webhook |
| `HEADER_EVENIMENT` | `"x-verificrca-event"`, headerul cu numele evenimentului |
| `URL_IMPLICIT` | `"https://www.verificrca.ro"` |
| `VERSIUNE_SDK` | versiunea pachetului, trimisă în `User-Agent` |

### Documentația tipurilor

Rezultatele sunt modele Pydantic imuabile, cu câmpuri în snake_case (`expires_at`, `checked_at`, `numar_inmatriculare`) și datele ca `datetime` cu fus orar. Pe fir, API-ul folosește camelCase; `model_dump_json(by_alias=True)` îți dă exact forma din API. Pachetul are `py.typed` și docstring-uri pe fiecare metodă, deci IDE-ul (VS Code cu Pylance, PyCharm) și mypy văd toate tipurile.

## Webhook-uri

API-ul trimite două feluri de webhook. SDK-ul le validează strict și îți dă modele tipate, cu datele ca `datetime`. Corpul poate fi `bytes`, `str` sau un `dict` deja parsat.

### Rezultatul unei verificări (`callback_url`)

Când trimiți `callback_url` la `porneste()`, primești un POST cu rezultatul imediat ce e gata. Dacă sursa nu răspunde, primești `status` `StatusWebhook.ERROR`.

```python
from fastapi import FastAPI, Request

from verificrca import StatusWebhook, parseaza_webhook_rezultat

app = FastAPI()


@app.post("/webhooks/verificrca/rezultat/9f3k2x")
async def rezultat(request: Request) -> dict[str, bool]:
    r = parseaza_webhook_rezultat(await request.body())
    if r.status is not StatusWebhook.ERROR and r.result:
        salveaza(r.request_id, r.result.expires_at)
    return {"ok": True}
```

Pune un segment greu de ghicit în URL, păstrează-l pe HTTPS și verifică dacă `request_id`-ul primit corespunde celui întors de `porneste()` înainte să te bazezi pe conținut.

### Notificări de expirare (`document.expira`)

Pe planurile care includ webhook-uri, configurezi un URL în dashboard și primești câte un eveniment când un document al unui vehicul monitorizat intră într-un prag de expirare. Pentru RCA, ITP și rovinietă pragurile sunt 30, 14 și 3 zile, iar pentru ARR 60, 50 și 45 de zile. Fiecare cerere vine cu cheia contului în headerul `X-Verificrca-Key`. SDK-ul o compară în timp constant, ca să nu dezvăluie nimic prin durata comparației.

`verifica_webhook_notificare(corp, headere, cheie)` primește headerele în forma în care ți le dă framework-ul: `request.headers` din FastAPI, Starlette, Flask sau Django, `request.META` din Django ori un simplu `dict`.

**FastAPI:**

```python
import os

from fastapi import FastAPI, HTTPException, Request

from verificrca import EroareWebhook, WebhookDocumentExpira, verifica_webhook_notificare

app = FastAPI()
CHEIE_WEBHOOK = os.environ["VERIFICRCA_WEBHOOK_KEY"]


@app.post("/webhooks/verificrca")
async def notificare(request: Request) -> dict[str, bool]:
    try:
        ev = verifica_webhook_notificare(await request.body(), request.headers, CHEIE_WEBHOOK)
    except EroareWebhook as e:
        raise HTTPException(status_code=401 if e.cod in ("CHEIE_INVALIDA", "CHEIE_NECONFIGURATA") else 400) from e
    if isinstance(ev, WebhookDocumentExpira):
        print(f"{ev.vehicul.numar_inmatriculare}: {ev.document.value} expiră în {ev.zile_ramase} zile")
    return {"ok": True}
```

**Django** (exclude view-ul din protecția CSRF):

```python
import os

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from verificrca import EroareWebhook, WebhookDocumentExpira, verifica_webhook_notificare


@csrf_exempt
@require_POST
def notificare(request: HttpRequest) -> HttpResponse:
    try:
        ev = verifica_webhook_notificare(request.body, request.headers, os.environ["VERIFICRCA_WEBHOOK_KEY"])
    except EroareWebhook as e:
        return JsonResponse({"error": e.cod}, status=400)
    if isinstance(ev, WebhookDocumentExpira):
        trimite_alerta.delay(ev.vehicul.id, ev.document.value, ev.zile_ramase)
    return JsonResponse({"ok": True})
```

**Flask:**

```python
@app.post("/webhooks/verificrca")
def notificare():
    try:
        ev = verifica_webhook_notificare(request.get_data(), request.headers, os.environ["VERIFICRCA_WEBHOOK_KEY"])
    except EroareWebhook as e:
        return jsonify(error=e.cod), 400
    return jsonify(ok=True)
```

Codurile `EroareWebhook`:

| `cod` | Când |
|---|---|
| `CHEIE_NECONFIGURATA` | Ai trimis o cheie goală (de obicei lipsește variabila de mediu) |
| `CHEIE_INVALIDA` | Headerul `X-Verificrca-Key` lipsește sau nu se potrivește |
| `JSON_INVALID` | Corpul nu e JSON |
| `PAYLOAD_INVALID` | Evenimentul nu are forma așteptată |

Folosește `ev.id` pentru deduplicare. Un eveniment poate ajunge de mai multe ori dacă serverul tău nu răspunde cu 2xx. Butonul de test din dashboard trimite un `WebhookTest` (`event` `webhook.test`).

### Verificarea în joburi de coadă

`VerificareInCurs` se salvează cu `model_dump_json()` și se reface cu `VerificareInCurs.model_validate_json()`. Așa pornești verificarea într-un proces și citești rezultatul în altul, de exemplu cu Celery:

```python
from verificrca import VerificareInCurs, VerificRca


@app.task
def verifica_rca(numar: str) -> None:
    with VerificRca() as vrca:
        pornita = vrca.verificari.porneste(tip="rca", query=numar)
    if isinstance(pornita, VerificareInCurs):
        citeste_rezultat.apply_async(args=[pornita.model_dump_json()], countdown=10)


@app.task
def citeste_rezultat(date: str) -> None:
    with VerificRca() as vrca:
        rezultat = vrca.verificari.asteapta(VerificareInCurs.model_validate_json(date))
    salveaza(rezultat)
```

Excepțiile SDK-ului trec prin `pickle` cu toate atributele, deci apar corect și în rezultatele joburilor eșuate.

## Erori

Toate excepțiile moștenesc `VerificRcaError`, care moștenește `Exception`. Fiecare are `mesaj` (în română, la fel ca `str(e)`), plus atributele `status`, `cod`, `hint` și `raspuns` când vin de la API. Eroarea originală (de rețea, de decodare) e în `__cause__`.

| Clasă | Când apare | Câmpuri utile |
|---|---|---|
| `EroareConfigurare` | Cheie lipsă sau opțiuni invalide | `hint` |
| `EroareValidare` | Date greșite, local sau HTTP 400 | `camp`, `acceptate` |
| `EroareAutentificare` | 401: cheie invalidă sau dezactivată | `hint` |
| `EroarePlanInactiv` | 402: fără abonament activ | `hint` |
| `EroareInterzis` | 403: `LIMIT_ATINS`, `ARR_NECESITA_PLAN` | `cod`, `limita` |
| `EroareNegasit` | 404: vehicul inexistent în cont | |
| `EroareConflict` | 409: `VEHICUL_EXISTENT` | |
| `EroareLimita` | 429: cotă, plafon de flotă sau polling prea des | `cod`, `retry_after_ms`, `utilizare_zi`, `utilizare_luna` |
| `EroareServer` | 5xx | `status` |
| `EroareHttp` | Alt status HTTP neașteptat, inclusiv redirecturi | `status` |
| `EroareRetea` | Fără răspuns sau timeout | `timeout`, `neajunsa` |
| `EroareRaspunsInvalid` | Răspuns cu formă neașteptată | `raspuns` |
| `EroareVerificare` | Sursa nu a răspuns sau a refuzat datele trimise; `cod` e mereu `VERIFICARE_ESUATA` | `cod_sursa`: `serie_talon_invalida`, `vin_invalid`, `numar_invalid` sau `None` |
| `EroareTimeoutVerificare` | `asteapta()` a depășit `timeout_ms` | |
| `EroareWebhook` | Cheie greșită sau payload invalid | `cod` |

```python
from verificrca import EroareLimita, EroareValidare, VerificRcaError

try:
    vrca.verificari.porneste(tip="rca", query=numar)
except EroareValidare as e:
    return arata_utilizatorului(e.mesaj)
except EroareLimita as e:
    if e.cod == "COTA_ATINSA":
        return amana_pana_maine()
    raise
except VerificRcaError as e:
    logger.error(e.mesaj, extra={"cod": e.cod, "hint": e.hint})
    raise
```

## Reîncercări, backoff și timeout

Erorile trecătoare sunt reîncercate automat, cu backoff exponențial (x2) și jitter, plafonat la `intarziere_maxima_ms`. Când serverul trimite `Retry-After`, pauza nu coboară sub valoarea cerută.

SDK-ul nu trimite niciodată de două ori o verificare taxată.

| Situație | GET / DELETE | POST |
|---|---|---|
| Rețea căzută, timeout la citirea răspunsului | se reîncearcă | nu (cererea poate să fi ajuns) |
| Redirect (3xx) | nu, `EroareHttp` | nu |
| DNS, conexiune refuzată, eroare TLS, timeout la conectare | se reîncearcă | se reîncearcă (sigur nu a ajuns) |
| 502, 503, 504 | se reîncearcă | se reîncearcă (proxy, nu aplicația) |
| 500 | se reîncearcă | nu |
| 429 la polling | se reîncearcă după `Retry-After`, dacă acesta nu depășește `intarziere_maxima_ms` | |
| 429 cotă sau plafon flotă | nu | nu |
| 4xx | nu | nu |

```python
from verificrca import SetariRetry, VerificRca

vrca = VerificRca(
    timeout_ms=15_000,
    retry=SetariRetry(incercari=5, intarziere_initiala_ms=250, intarziere_maxima_ms=8_000),
)
# sau: retry={"incercari": 5}, ori retry=False ca să le oprești
```

## Cotă și limite

Fiecare `porneste()` consumă o unitate din cota zilnică și lunară a planului. Dacă mașina a fost verificată de curând, primești imediat rezultatul existent. Cererea tot consumă din cotă.

Rezultatele au câmpul `limite`, completat din headerele `X-RateLimit-*`:

```python
r = vrca.verificari.porneste(tip="rca", query="B123ABC")
if r.limite:
    print(r.limite.zi.ramase)  # 287
    print(r.limite.luna.limita)  # 10000
```

Cota zilnică se resetează la miezul nopții. Limitele fiecărui plan le găsești pe [pagina API](https://www.verificrca.ro/api-acces).

## Exemple

Folderul [`examples/`](./examples) conține scripturi gata de rulat:

- [`verificare_rca.py`](./examples/verificare_rca.py): verificare RCA după număr, cu tratarea erorilor;
- [`flota.py`](./examples/flota.py): adaugă vehicule și afișează ce RCA, ITP sau rovinietă expiră în 30 de zile;
- [`async_verificari.py`](./examples/async_verificari.py): mai multe verificări în paralel cu clientul async;
- [`webhook_fastapi.py`](./examples/webhook_fastapi.py), [`webhook_django.py`](./examples/webhook_django.py), [`webhook_flask.py`](./examples/webhook_flask.py): primirea webhook-urilor.

### Verificare în masă

```python
from verificrca import VerificRca, VerificRcaError

with VerificRca() as vrca:
    for numar in ["B123ABC", "CJ45XYZ", "IS08BCD"]:
        try:
            r = vrca.verificari.verifica_si_asteapta(tip="rca", query=numar)
            print(numar, r.status.value)
        except VerificRcaError as e:
            print(numar, e.mesaj)
```

Pentru liste mari, adaugă vehiculele în cont cu `vehicule.adauga()`. Sunt monitorizate automat și primești notificările de expirare, fără să consumi din cota de verificări.

## Întrebări frecvente

### Cum verific RCA-ul unei mașini din Python?

Instalezi pachetul cu `pip install verificrca`, creezi un client cu cheia API și apelezi `vrca.verificari.verifica_si_asteapta(tip="rca", query="B123ABC")`. Primești statusul poliței și data expirării, din baza de date AIDA.

### Pot verifica ITP-ul după numărul de înmatriculare?

Nu. RAR caută inspecția tehnică periodică doar după seria de șasiu (VIN), așa că SDK-ul respinge cererea înainte să plece, fără să consume din cotă. VIN-ul îl găsești în talon, la rubrica E.

### Unde găsesc numărul certificatului de înmatriculare?

E tipărit jos pe talon (certificatul de înmatriculare), la „Numărul certificatului”, și arată ca `I00639603F`. Îl trimiți în `serie_talon` la verificarea rovinietei sau la `vehicule.adauga()`. Spațiile și cratimele sunt eliminate automat. Dacă sursa oficială îl respinge, primești `EroareVerificare` cu `cod_sursa` `serie_talon_invalida`, iar la vehiculele din flotă `serie_talon_respinsa` devine `True`.

### Cum verific rovinieta unei mașini din Python?

Apelezi `vrca.verificari.verifica_si_asteapta(tip="rovinieta", query="B123ABC", serie_sasiu="WVWZZZ1JZXW000001", serie_talon="I00639603F")`. Primești statusul și data până la care e plătită rovinieta, din CNAIR. Pentru o verificare manuală, fără cod, folosește pagina [verificare rovinietă](https://www.verificrca.ro/verificare-rovinieta).

### De unde vin datele?

Din sursele oficiale: AIDA (baza de date a asigurărilor RCA administrată de BAAR), Registrul Auto Român pentru ITP, CNAIR pentru rovinietă și Autoritatea Rutieră Română pentru copia conformă. Nu estimăm nimic: fiecare rezultat e exact ce a răspuns sursa.

### De ce o poliță RCA nouă apare ca expirată?

Asigurătorul are nevoie de timp ca să înregistreze polița nouă în AIDA, de obicei între 1 și 7 zile. În acest interval verificarea poate arăta polița veche. Detalii în articolul despre [amenzile pentru RCA expirat](https://www.verificrca.ro/postari/amenzi-rca-expirat-2026).

### Merge cu Django, Flask sau FastAPI?

Da. SDK-ul nu depinde de niciun framework. În Django și Flask folosești `VerificRca`, în FastAPI și alte aplicații asyncio `AsyncVerificRca`. Webhook-urile acceptă direct `request.headers` din oricare dintre ele. Cheia API rămâne pe server.

### Pot folosi SDK-ul în Celery sau alte joburi de coadă?

Da. `VerificareInCurs` se serializează în JSON, așa că pornești verificarea într-un job și citești rezultatul în altul (exemplul din [Verificarea în joburi de coadă](#verificarea-în-joburi-de-coadă)). Excepțiile trec prin `pickle` fără să-și piardă atributele.

### Există SDK și pentru alte limbaje?

Da. Pentru Node.js și TypeScript: [`@verificrca/sdk`](https://github.com/verificrca/sdk_javascript). Pentru PHP: [`verificrca/sdk`](https://github.com/verificrca/sdk_php). Toate au aceleași metode și aceleași nume.

## Linkuri utile

- [Documentația API verificrca.ro](https://www.verificrca.ro/api-acces)
- [Verificare RCA online](https://www.verificrca.ro/verificare-rca)
- [Verificare ITP online](https://www.verificrca.ro/verificare-itp)
- [Verificare rovinietă online](https://www.verificrca.ro/verificare-rovinieta)
- [Verificare copie conformă ARR](https://www.verificrca.ro/verificare-arr)
- [Monitorizare flote auto](https://www.verificrca.ro/flote)
- [Changelog](./CHANGELOG.md)

## Dezvoltare

```bash
uv sync
uv run pytest                                   # teste unitare, fără rețea
uv run mypy                                     # tipuri, mod strict
uv run ruff check && uv run ruff format --check # stil
uv run pytest e2e                               # teste pe API-ul real
```

Testele e2e citesc configurarea din `.env.e2e`, fișier ignorat de git. Pornești de la șablon:

```bash
cp .env.e2e.example .env.e2e
```

Fără cheie rulează doar testul de autentificare. Cu `VERIFICRCA_API_KEY` se adaugă listarea vehiculelor, care e gratuită. Verificările reale (`VERIFICRCA_E2E_VERIFICARI=1`) consumă din cotă, iar testul de flotă (`VERIFICRCA_E2E_FLOTA=1`) adaugă și șterge un vehicul. Amândouă pornesc doar dacă le activezi explicit.

## Licență

[MIT](./LICENSE), © verificrca.ro
