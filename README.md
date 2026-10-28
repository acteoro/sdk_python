# acteo: API verificare RCA, ITP, rovinietă și ARR pentru Python

[![PyPI](https://img.shields.io/pypi/v/acteo.svg)](https://pypi.org/project/acteo/)
[![Python](https://img.shields.io/pypi/pyversions/acteo.svg)](https://pypi.org/project/acteo/)
[![licență MIT](https://img.shields.io/pypi/l/acteo.svg)](./LICENSE)

SDK-ul oficial Python pentru [API-ul Acteo](https://acteo.ro/api-acces). Cu el verifici din cod dacă o mașină are RCA valabil, ITP la zi, rovinietă plătită sau copie conformă ARR, după numărul de înmatriculare sau seria de șasiu (VIN). Datele vin din sursele oficiale: baza AIDA pentru asigurarea RCA, RAR pentru inspecția tehnică periodică, CNAIR pentru rovinietă și ARR pentru transportul rutier.

Pe lângă verificările la cerere, SDK-ul gestionează vehiculele monitorizate din cont și citește webhook-urile trimise când un document se apropie de expirare. Are client sincron (Django, Flask, scripturi, Celery) și asincron (FastAPI, asyncio), cu tipuri complete. Dacă ai o firmă de leasing, rent-a-car sau curierat, un service auto ori pur și simplu o flotă, afli din timp ce RCA, ITP sau rovinietă expiră, înainte să vină amenda.

> Ai nevoie de o cheie API. O generezi din [contul tău Acteo](https://app.acteo.ro/api/chei), după ce alegi un plan de pe [pagina API](https://acteo.ro/api-acces).

```python
from acteo import Acteo

with Acteo() as acteo:  # cheia din ACTEO_API_KEY
    rca = acteo.auto.rca.verifica("B123ABC")
    print(rca.status.value, rca.expires_at)  # valid 2027-03-01 00:00:00+00:00
```

Apelurile sunt grupate pe domeniu și pe document, deci citești din cod ce verifici: `acteo.auto.rca`, `acteo.auto.itp`, `acteo.auto.rovinieta`, `acteo.auto.arr`, plus `acteo.auto.flota` pentru vehiculele din cont și `acteo.webhooks` pentru notificări.

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
- [Vii de la verificrca?](#vii-de-la-verificrca)
- [Întrebări frecvente](#întrebări-frecvente)

## Ce face SDK-ul

| Funcție | Apel | Ce primești |
|---|---|---|
| Verificare RCA după număr sau VIN | `acteo.auto.rca.verifica()` | Starea poliței RCA și data expirării, din baza AIDA |
| Verificare ITP după VIN | `acteo.auto.itp.verifica()` | Data până la care e valabilă inspecția tehnică, din RAR |
| Verificare rovinietă | `acteo.auto.rovinieta.verifica()` | Dacă rovinieta e plătită și până când, din CNAIR |
| Verificare copie conformă ARR | `acteo.auto.arr.verifica()` | Valabilitatea copiei conforme pentru transportatori |
| Gestionare flotă | `acteo.auto.flota` | Adaugi, listezi și ștergi vehiculele monitorizate automat |
| Webhook-uri | `acteo.webhooks` | Rezultatul verificării la URL-ul tău, alerte `document.expira` la 30, 14 și 3 zile |
| Validare locală | | Numărul de înmatriculare, VIN-ul și numărul talonului sunt verificate înainte de cerere, deci o greșeală de tastare nu consumă din cotă |
| Excepții tipate | | O clasă de excepție pentru fiecare situație, cu mesaj în română și `hint` de rezolvare |
| Reîncercări sigure | | Backoff exponențial cu jitter, `Retry-After` respectat, niciun POST taxat de două ori |
| Sync și async | | `Acteo` pentru cod sincron, `AsyncActeo` pentru asyncio și FastAPI, cu aceleași metode |
| Tipuri complete | | Modele Pydantic imuabile, `py.typed`, verificat cu mypy în mod strict |

## Instalare

```bash
pip install acteo
# sau
uv add acteo
poetry add acteo
```

SDK-ul cere Python 3.10 sau mai nou și folosește [httpx](https://www.python-httpx.org/) pentru cereri și [Pydantic](https://docs.pydantic.dev/) pentru modele.

Cheia API o poți da direct în constructor (`Acteo(api_key="...")`) sau prin variabila de mediu `ACTEO_API_KEY`:

```bash
export ACTEO_API_KEY=cheia_ta_api
```

Nu pune cheia în cod care ajunge într-un repo public sau într-o aplicație instalată pe telefonul clienților. Cheia dă acces la cota contului tău și la vehiculele din el, deci o folosești doar pe server.

## Pornire rapidă

### Verificare RCA după număr de înmatriculare

```python
from acteo import Acteo, StatusDocument

with Acteo() as acteo:  # citește ACTEO_API_KEY
    rca = acteo.auto.rca.verifica("B 123 ABC")

if rca.status is StatusDocument.EXPIRED:
    print("Mașina nu are RCA valabil.")
elif rca.status is StatusDocument.WARNING and rca.expires_at:
    print(f"RCA-ul expiră curând, pe {rca.expires_at:%d.%m.%Y}")
```

Un text de 17 caractere fără literele I, O și Q e tratat ca VIN, orice altceva ca număr de înmatriculare. Pentru RCA îți recomandăm să trimiți ambele. Baza AIDA găsește polița mai sigur după seria de șasiu, iar uneori o poliță emisă pe VIN nu apare la căutarea după număr:

```python
rca = acteo.auto.rca.verifica(numar="B123ABC", vin="WVWZZZ1JZXW000001")
```

### Verificare ITP după serie de șasiu

```python
itp = acteo.auto.itp.verifica("WVWZZZ1JZXW000001")
print(f"ITP valabil până la {itp.expires_at:%d.%m.%Y}" if itp.expires_at else itp.status.value)
```

### Verificare rovinietă

Rovinieta cere trei date: numărul de înmatriculare, seria de șasiu (VIN) și numărul certificatului de înmatriculare (`serie_talon`), tipărit jos pe talon. Sursa oficială le validează pe toate trei împreună, așa că fără numărul talonului SDK-ul oprește cererea înainte să plece și nu consumă din cotă.

```python
rovinieta = acteo.auto.rovinieta.verifica(
    numar="B123ABC",
    vin="WVWZZZ1JZXW000001",
    serie_talon="I00639603F",
)
print(rovinieta.status.value, rovinieta.expires_at)
```

Dacă sursa respinge datele (de exemplu, numărul talonului nu corespunde mașinii), primești `EroareVerificare` cu `cod_sursa` `"serie_talon_invalida"`. O reîncercare cu aceleași date nu ajută; corectează întâi câmpul indicat:

```python
from acteo import EroareVerificare

try:
    acteo.auto.rovinieta.verifica(numar="B123ABC", vin=vin, serie_talon=talon)
except EroareVerificare as e:
    if e.cod_sursa == "serie_talon_invalida":
        cere_utilizatorului_numarul_talonului()
    else:
        raise
```

Vezi și [unde găsești numărul certificatului de înmatriculare](#unde-găsesc-numărul-certificatului-de-înmatriculare).

### Verificare copie conformă ARR

```python
arr = acteo.auto.arr.verifica("CJ45XYZ")
```

## Client async

`AsyncActeo` are aceleași metode, aceleași argumente și aceleași excepții, doar că le apelezi cu `await`. E potrivit pentru FastAPI, Starlette, aiohttp sau orice cod asyncio, și îți permite să rulezi mai multe verificări în paralel:

```python
import asyncio

from acteo import ActeoError, AsyncActeo


async def main() -> None:
    numere = ["B123ABC", "CJ45XYZ", "B12XYZ"]
    async with AsyncActeo() as acteo:
        rezultate = await asyncio.gather(
            *(acteo.auto.rca.verifica(n) for n in numere),
            return_exceptions=True,
        )
    for numar, r in zip(numere, rezultate):
        if isinstance(r, ActeoError):
            print(f"{numar}: {r.mesaj}")
        elif not isinstance(r, BaseException):
            print(f"{numar}: {r.status.value}")


asyncio.run(main())
```

Pauzele dintre interogări folosesc `anyio.sleep`, deci nu blochează event loop-ul.

## Ce identificator cere fiecare verificare

Fiecare sursă oficială caută după alt identificator, așa că fiecare document își cere exact datele lui. SDK-ul aplică aceleași reguli ca API-ul și te oprește înainte de cerere dacă lipsește ceva.

| Apel | Ce primește | Sursa |
|---|---|---|
| `auto.rca.verifica(x)` | număr de înmatriculare **sau** VIN, ori `numar=..., vin=...` (recomandat) | AIDA / BAAR |
| `auto.itp.verifica(vin)` | VIN (17 caractere) | RAR |
| `auto.rovinieta.verifica(numar=..., vin=..., serie_talon=...)` | toate trei, **obligatorii** | CNAIR |
| `auto.arr.verifica(numar)` | număr de înmatriculare | ARR |

Formatele de număr acceptate: București (`B123ABC`, `B12ABC`), județe (`CJ45XYZ`, `IS08BCD`), corp diplomatic (`CD123A`) și numere temporare (`TC1234AB`). Spațiile și cratimele sunt eliminate automat, deci `b-123 abc` devine `B123ABC`. VIN-ul trebuie să aibă exact 17 caractere, fără literele I, O și Q (standardul ISO 3779).

`serie_talon` este numărul certificatului de înmatriculare, de forma `I00639603F`. SDK-ul păstrează doar literele și cifrele, cu majuscule, și cere între 6 și 20 de caractere, cu cel puțin o cifră. Doar sursa oficială poate confirma că numărul aparține mașinii.

## Cum decurge o verificare

1. **Cerere** (`porneste`). Dacă există un rezultat recent pentru mașina respectivă, îl primești imediat. Altfel verificarea intră în coadă și primești un obiect `VerificareInCurs` (`status == "processing"`).
2. **Interogarea sursei.** Sursa oficială e consultată în fundal. Dacă nu răspunde, verificarea se încheie cu eroare.
3. **Rezultatul** ajunge la tine pe una din trei căi:
   - `verifica()` face tot drumul și întoarce direct rezultatul final;
   - `rezultat()` sau `asteapta()` fac polling, fără să consume din cotă;
   - webhook: dacă trimiți `callback_url` la `porneste()`, API-ul face POST cu rezultatul la adresa ta.

O verificare consumă din cota planului doar când sursa oficială a răspuns, inclusiv atunci când refuză datele trimise. Dacă sursa nu răspunde, nu consumi nimic. Interogările de rezultat sunt gratuite.

### Statusuri

Rezultatul final are `status` de tip `StatusDocument`:

| `status` | Înseamnă | `expires_at` |
|---|---|---|
| `StatusDocument.VALID` (`"valid"`) | Document valabil | data expirării |
| `StatusDocument.WARNING` (`"warning"`) | Expiră curând: RCA în 14 zile, ITP în 30, rovinietă în 7, ARR în 14 | data expirării |
| `StatusDocument.EXPIRED` (`"expired"`) | Expirat sau inexistent, confirmat de sursă | data expirării sau `None` |
| `StatusDocument.NOT_FOUND` (`"not_found"`) | Sursa nu a găsit vehiculul | `None` |

O verificare încă în curs e un obiect `VerificareInCurs`, nu un rezultat. Le deosebești cu `isinstance()`.

Când verificarea se încheie cu eroare, SDK-ul aruncă `EroareVerificare` (`cod` e mereu `VERIFICARE_ESUATA`). Dacă sursa oficială doar nu a răspuns, `cod_sursa` e `None` și poți relua cererea. Dacă sursa a refuzat datele trimise, `cod_sursa` spune ce e greșit și reîncercarea nu ajută până nu corectezi câmpul:

| `cod_sursa` | Câmpul de corectat |
|---|---|
| `serie_talon_invalida` | `serie_talon`, numărul certificatului de înmatriculare |
| `vin_invalid` | `vin` |
| `numar_invalid` | numărul de înmatriculare |

## Referință API

### `Acteo(...)` și `AsyncActeo(...)`

Constructorul primește doar argumente numite, toate opționale:

| Argument | Tip | Implicit | Descriere |
|---|---|---|---|
| `api_key` | `str \| None` | variabila `ACTEO_API_KEY`, apoi `VERIFICRCA_API_KEY` | Cheia API |
| `base_url` | `str \| None` | `https://api.acteo.ro` | Adresa API-ului |
| `timeout_ms` | `float` | `30000` | Timeout pe fiecare cerere HTTP, aplicat clientului construit de SDK |
| `retry` | `SetariRetry \| dict \| bool` | `SetariRetry(incercari=3, intarziere_initiala_ms=500, intarziere_maxima_ms=10000)` | Politica de reîncercare; `False` o oprește |
| `http_client` | `httpx.Client` / `httpx.AsyncClient` | construit de SDK | Client propriu (proxy, certificate, teste) |
| `user_agent` | `str \| None` | | Adăugat la `User-Agent`, util în loguri |

Constructorul nu face nicio cerere pe rețea. Aruncă `EroareConfigurare` dacă lipsește cheia sau dacă o opțiune e invalidă.

Folosește clientul cu `with` (sau `async with`), ori apelează `close()` / `await aclose()` la final, ca să închizi conexiunile. Un `http_client` dat de tine își păstrează propriul timeout și nu e închis de SDK. Redirecturile nu sunt urmate: un răspuns 3xx devine `EroareHttp`.

### `auto.<document>.verifica(identificator, *, interval_ms=3000, timeout_ms=300000)`

Disponibil pe `auto.rca`, `auto.itp`, `auto.rovinieta` și `auto.arr`. Pornește verificarea și așteaptă rezultatul final. E calea cea mai simplă pentru scripturi și joburi cron. `interval_ms` are minimum 2000, iar `timeout_ms` e implicit 5 minute. La depășire aruncă `EroareTimeoutVerificare`.

Rezultatul are tipul documentului: `auto.rca.verifica()` întoarce un `RezultatRca` (cu `tip` mereu `TipVerificare.RCA`), `auto.itp.verifica()` un `RezultatItp` și așa mai departe. Toate sunt subclase ale `VerificareFinala`, deci codul scris pe `VerificareFinala` merge neschimbat.

### `auto.<document>.porneste(identificator, *, callback_url=None)`

Pornește verificarea fără să aștepte și **consumă din cotă**. Întoarce fie rezultatul final (dacă există unul recent), fie un obiect `VerificareInCurs` pe care îl dai mai departe la `rezultat()` sau `asteapta()`.

```python
from acteo import VerificareInCurs

r = acteo.auto.itp.porneste(
    "WVWZZZ1JZXW000001",
    callback_url="https://example.com/webhooks/acteo/9f3k2",  # opțional
)

if isinstance(r, VerificareInCurs):
    print("În coadă, request_id:", r.request_id)
    final = acteo.auto.itp.asteapta(r)
```

### `auto.<document>.rezultat(referinta)`

Interoghează o singură dată. Nu consumă din cotă. Primește obiectul `VerificareInCurs` întors de `porneste()` sau direct identificatorul documentului:

```python
acteo.auto.rca.rezultat("B123ABC")
acteo.auto.rca.rezultat(numar="B123ABC", vin="WVWZZZ1JZXW000001")  # caută după VIN
acteo.auto.itp.rezultat("WVWZZZ1JZXW000001")
acteo.auto.rovinieta.rezultat(numar="B123ABC", vin="WVWZZZ1JZXW000001")
```

La RCA cu VIN, API-ul caută doar după VIN, deci și interogarea merge după VIN. La rovinietă interogarea folosește numărul și VIN-ul; `serie_talon` e acceptat, ca să poți trimite aceleași argumente ca la `verifica()`, dar nu e necesar.

### `auto.<document>.asteapta(referinta, *, interval_ms=3000, timeout_ms=300000)`

Face polling până la rezultatul final, cu aceleași argumente ca `rezultat()` și aceleași opțiuni ca `verifica()`. Nu consumă din cotă. Reîncercările se opresc la termen, așa că doar o cerere HTTP deja pornită îl poate depăși, cu cel mult timeout-ul ei.

### `auto.flota.lista()`

Toate vehiculele din cont, cu datele de expirare `rca_expira_la`, `itp_expira_la`, `rovinieta_expira_la` și `arr_expira_la` (ca `datetime` sau `None`). Câmpul `activ` e `True` cât timp vehiculul e verificat automat și primește notificări de expirare. `serie_talon` e numărul certificatului de înmatriculare salvat pentru vehicul (sau `None`), iar `serie_talon_respinsa` devine `True` când sursa oficială l-a respins: rovinieta nu se mai verifică până când îl corectezi. Vehiculele din cont sunt verificate automat și periodic, deci lista îți dă o imagine la zi a flotei fără să consume din cota de verificări.

```python
for v in acteo.auto.flota.lista():
    rca = f"{v.rca_expira_la:%d.%m.%Y}" if v.rca_expira_la else "-"
    print(v.numar_inmatriculare, "RCA:", rca)
```

### `auto.flota.adauga(*, numar_inmatriculare=None, serie_sasiu=None, serie_talon=None, arr_monitorizat=None)`

Adaugă un vehicul în monitorizare. Trimite cel puțin un identificator (`numar_inmatriculare`, `serie_sasiu`); opționale sunt `serie_talon` și `arr_monitorizat`. ITP-ul se monitorizează doar cu VIN, iar rovinieta cere numărul, VIN-ul și numărul talonului.

```python
v = acteo.auto.flota.adauga(
    numar_inmatriculare="B123ABC",
    serie_sasiu="WVWZZZ1JZXW000001",
    serie_talon="I00639603F",
)
```

Poți primi `EroareInterzis` cu `cod` `LIMIT_ATINS` când ai atins numărul de mașini din plan, sau `EroareConflict` când vehiculul există deja.

### `auto.flota.sterge(id)`

Scoate vehiculul din cont. Aruncă `EroareNegasit` dacă ID-ul nu există în contul cheii.

Operațiile pe flotă nu consumă din cota de verificări, dar cer un plan activ.

### Utilitare de validare

```python
from acteo import (
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
| `URL_IMPLICIT` | `"https://api.acteo.ro"` |
| `VERSIUNE_SDK` | versiunea pachetului, trimisă în `User-Agent` |

### Documentația tipurilor

Rezultatele sunt modele Pydantic imuabile, cu câmpuri în snake_case (`expires_at`, `checked_at`, `numar_inmatriculare`) și datele ca `datetime` cu fus orar. Pe fir, API-ul folosește camelCase; `model_dump_json(by_alias=True)` îți dă exact forma din API. Pachetul are `py.typed` și docstring-uri pe fiecare metodă, deci IDE-ul (VS Code cu Pylance, PyCharm) și mypy văd toate tipurile, inclusiv documentul fiecărui rezultat.

## Webhook-uri

API-ul trimite două feluri de webhook. SDK-ul le validează strict și îți dă modele tipate, cu datele ca `datetime`. Corpul poate fi `bytes`, `str` sau un `dict` deja parsat. `acteo.webhooks` nu face cereri pe rețea, deci îl folosești la fel din cod sincron și async.

### Rezultatul unei verificări (`callback_url`)

Când trimiți `callback_url` la `porneste()`, primești un POST cu rezultatul imediat ce e gata. Dacă sursa nu răspunde, primești `status` `StatusWebhook.ERROR`.

```python
from fastapi import FastAPI, Request

from acteo import Acteo, StatusWebhook

app = FastAPI()
acteo = Acteo()


@app.post("/webhooks/acteo/rezultat/9f3k2x")
async def rezultat(request: Request) -> dict[str, bool]:
    r = acteo.webhooks.parseaza_rezultat(await request.body())
    if r.status is not StatusWebhook.ERROR and r.result:
        salveaza(r.request_id, r.result.expires_at)
    return {"ok": True}
```

Pune un segment greu de ghicit în URL, păstrează-l pe HTTPS și verifică dacă `request_id`-ul primit corespunde celui întors de `porneste()` înainte să te bazezi pe conținut.

### Notificări de expirare (`document.expira`)

Pe planurile care includ webhook-uri, configurezi un URL în dashboard și primești câte un eveniment când un document al unui vehicul monitorizat intră într-un prag de expirare. Pentru RCA, ITP și rovinietă pragurile sunt 30, 14 și 3 zile, iar pentru ARR 60, 50 și 45 de zile. Fiecare cerere vine cu cheia contului în headerul `X-Verificrca-Key`. SDK-ul o compară în timp constant, ca să nu dezvăluie nimic prin durata comparației.

`acteo.webhooks.verifica_notificare(corp, headere, cheie)` primește headerele în forma în care ți le dă framework-ul: `request.headers` din FastAPI, Starlette, Flask sau Django, `request.META` din Django ori un simplu `dict`.

**FastAPI:**

```python
import os

from fastapi import FastAPI, HTTPException, Request

from acteo import Acteo, EroareWebhook, WebhookDocumentExpira

app = FastAPI()
acteo = Acteo()
CHEIE_WEBHOOK = os.environ["ACTEO_WEBHOOK_KEY"]


@app.post("/webhooks/acteo")
async def notificare(request: Request) -> dict[str, bool]:
    try:
        ev = acteo.webhooks.verifica_notificare(await request.body(), request.headers, CHEIE_WEBHOOK)
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

from acteo import Acteo, EroareWebhook, WebhookDocumentExpira

acteo = Acteo()


@csrf_exempt
@require_POST
def notificare(request: HttpRequest) -> HttpResponse:
    try:
        ev = acteo.webhooks.verifica_notificare(request.body, request.headers, os.environ["ACTEO_WEBHOOK_KEY"])
    except EroareWebhook as e:
        return JsonResponse({"error": e.cod}, status=400)
    if isinstance(ev, WebhookDocumentExpira):
        trimite_alerta.delay(ev.vehicul.id, ev.document.value, ev.zile_ramase)
    return JsonResponse({"ok": True})
```

**Flask:**

```python
@app.post("/webhooks/acteo")
def notificare():
    try:
        ev = acteo.webhooks.verifica_notificare(request.get_data(), request.headers, os.environ["ACTEO_WEBHOOK_KEY"])
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
from acteo import Acteo, VerificareInCurs


@app.task
def verifica_rca(numar: str) -> None:
    with Acteo() as acteo:
        pornita = acteo.auto.rca.porneste(numar)
    if isinstance(pornita, VerificareInCurs):
        citeste_rezultat.apply_async(args=[pornita.model_dump_json()], countdown=10)


@app.task
def citeste_rezultat(date: str) -> None:
    with Acteo() as acteo:
        rezultat = acteo.auto.rca.asteapta(VerificareInCurs.model_validate_json(date))
    salveaza(rezultat)
```

Excepțiile SDK-ului trec prin `pickle` cu toate atributele, deci apar corect și în rezultatele joburilor eșuate.

## Erori

Toate excepțiile moștenesc `ActeoError`, care moștenește `Exception`. Fiecare are `mesaj` (în română, la fel ca `str(e)`), plus atributele `status`, `cod`, `hint` și `raspuns` când vin de la API. Eroarea originală (de rețea, de decodare) e în `__cause__`.

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
from acteo import ActeoError, EroareLimita, EroareValidare

try:
    acteo.auto.rca.porneste(numar)
except EroareValidare as e:
    return arata_utilizatorului(e.mesaj)
except EroareLimita as e:
    if e.cod == "COTA_ATINSA":
        return amana_pana_maine()
    raise
except ActeoError as e:
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
from acteo import Acteo, SetariRetry

acteo = Acteo(
    timeout_ms=15_000,
    retry=SetariRetry(incercari=5, intarziere_initiala_ms=250, intarziere_maxima_ms=8_000),
)
# sau: retry={"incercari": 5}, ori retry=False ca să le oprești
```

## Cotă și limite

Fiecare verificare consumă o unitate din cota zilnică și lunară a planului, dar numai când sursa oficială a răspuns, inclusiv atunci când refuză datele trimise. Dacă mașina a fost verificată de curând, primești imediat rezultatul existent, iar cererea consumă din cotă. Dacă sursa nu răspunde, nu consumi nimic. Verificările încă în curs ocupă cota până la răspuns, ca să nu treci de limită cu cereri trimise în paralel.

Rezultatele au câmpul `limite`, completat din headerele `X-RateLimit-*`:

```python
r = acteo.auto.rca.porneste("B123ABC")
if r.limite:
    print(r.limite.zi.ramase)  # 287
    print(r.limite.luna.limita)  # 10000
```

Cota zilnică se resetează la miezul nopții, ora României. Limitele fiecărui plan le găsești pe [pagina API](https://acteo.ro/api-acces).

## Exemple

Folderul [`examples/`](./examples) conține scripturi gata de rulat:

- [`verificare_rca.py`](./examples/verificare_rca.py): verificare RCA după număr (și VIN, opțional), cu tratarea erorilor;
- [`flota.py`](./examples/flota.py): adaugă vehicule și afișează ce RCA, ITP, rovinietă sau ARR expiră în 30 de zile;
- [`async_verificari.py`](./examples/async_verificari.py): mai multe verificări în paralel cu clientul async;
- [`webhook_fastapi.py`](./examples/webhook_fastapi.py), [`webhook_django.py`](./examples/webhook_django.py), [`webhook_flask.py`](./examples/webhook_flask.py): primirea webhook-urilor.

### Verificare în masă

```python
from acteo import Acteo, ActeoError

with Acteo() as acteo:
    for numar in ["B123ABC", "CJ45XYZ", "IS08BCD"]:
        try:
            r = acteo.auto.rca.verifica(numar)
            print(numar, r.status.value)
        except ActeoError as e:
            print(numar, e.mesaj)
```

Pentru liste mari, adaugă vehiculele în cont cu `auto.flota.adauga()`. Sunt monitorizate automat și primești notificările de expirare, fără să consumi din cota de verificări.

## Vii de la verificrca?

Pachetul `verificrca` s-a mutat la `acteo`. Instalezi pachetul nou și schimbi apelurile:

| Înainte | Acum |
|---|---|
| `pip install verificrca` | `pip install acteo` |
| `import verificrca` / `from verificrca import ...` | `import acteo` / `from acteo import ...` |
| `VerificRca()` / `AsyncVerificRca()` | `Acteo()` / `AsyncActeo()` |
| `VERIFICRCA_API_KEY` | `ACTEO_API_KEY` (cea veche e citită în continuare, dacă lipsește cea nouă) |
| `verificari.verifica_si_asteapta(tip="rca", query=q)` | `auto.rca.verifica(q)` |
| `verificari.verifica_si_asteapta(tip="rca", query=numar, serie_sasiu=vin)` | `auto.rca.verifica(numar=numar, vin=vin)` |
| `verificari.verifica_si_asteapta(tip="itp", query=vin)` | `auto.itp.verifica(vin)` |
| `verificari.verifica_si_asteapta(tip="rovinieta", query=numar, serie_sasiu=vin, serie_talon=talon)` | `auto.rovinieta.verifica(numar=numar, vin=vin, serie_talon=talon)` |
| `verificari.verifica_si_asteapta(tip="arr", query=numar)` | `auto.arr.verifica(numar)` |
| `verificari.porneste(...)` / `rezultat(...)` / `asteapta(...)` | `auto.<document>.porneste` / `rezultat` / `asteapta` |
| `vehicule.lista()` / `adauga()` / `sterge()` | `auto.flota.lista()` / `adauga()` / `sterge()` |
| `parseaza_webhook_rezultat()` / `verifica_webhook_notificare()` | `webhooks.parseaza_rezultat()` / `webhooks.verifica_notificare()` |
| `VerificRcaError` | `ActeoError` |

Pachetul `acteo` include și modulul `verificrca`, deci `import verificrca` și codul scris pe clientul vechi merg în continuare după `pip install acteo`, cu aceleași obiecte. Excepțiile, modelele și utilitarele de validare au rămas aceleași.

## Întrebări frecvente

### Cum verific RCA-ul unei mașini din Python?

Instalezi pachetul cu `pip install acteo`, creezi un client cu cheia API și apelezi `acteo.auto.rca.verifica("B123ABC")`. Primești statusul poliței și data expirării, din baza de date AIDA. Pentru o verificare manuală, fără cod, folosește pagina [verificare RCA](https://acteo.ro/verificare-rca).

### Pot verifica ITP-ul după numărul de înmatriculare?

Nu. RAR caută inspecția tehnică periodică doar după seria de șasiu (VIN), așa că SDK-ul respinge cererea înainte să plece, fără să consume din cotă. VIN-ul îl găsești în talon, la rubrica E.

### Unde găsesc numărul certificatului de înmatriculare?

E tipărit jos pe talon (certificatul de înmatriculare), la „Numărul certificatului”, și arată ca `I00639603F`. Nu îl confunda cu seria de șasiu (VIN), care e la rubrica E și are 17 caractere. Îl trimiți în `serie_talon` la verificarea rovinietei sau la `auto.flota.adauga()`. Spațiile și cratimele sunt eliminate automat. Dacă sursa oficială îl respinge, primești `EroareVerificare` cu `cod_sursa` `serie_talon_invalida`, iar la vehiculele din flotă `serie_talon_respinsa` devine `True`.

### Cum verific rovinieta unei mașini din Python?

Apelezi `acteo.auto.rovinieta.verifica(numar="B123ABC", vin="WVWZZZ1JZXW000001", serie_talon="I00639603F")`. Primești statusul și data până la care e plătită rovinieta, din CNAIR. Sursa oficială validează împreună cele trei date, așa că fără numărul talonului cererea e oprită înainte să plece. Pentru o verificare manuală, folosește pagina [verificare rovinietă](https://acteo.ro/verificare-rovinieta).

### De unde vin datele?

Din sursele oficiale: AIDA (baza de date a asigurărilor RCA administrată de BAAR), Registrul Auto Român pentru ITP, CNAIR pentru rovinietă și Autoritatea Rutieră Română pentru copia conformă. Nu estimăm nimic: fiecare rezultat e exact ce a răspuns sursa.

### De ce o poliță RCA nouă apare ca expirată?

Asigurătorul are nevoie de timp ca să înregistreze polița nouă în AIDA, de obicei între 1 și 7 zile. În acest interval verificarea poate arăta polița veche. Detalii despre [amenzile pentru RCA expirat](https://acteo.ro/amenzi/rca).

### Merge cu Django, Flask sau FastAPI?

Da. SDK-ul nu depinde de niciun framework. În Django și Flask folosești `Acteo`, în FastAPI și alte aplicații asyncio `AsyncActeo`. Webhook-urile acceptă direct `request.headers` din oricare dintre ele. Cheia API rămâne pe server.

### Pot folosi SDK-ul în Celery sau alte joburi de coadă?

Da. `VerificareInCurs` se serializează în JSON, așa că pornești verificarea într-un job și citești rezultatul în altul (exemplul din [Verificarea în joburi de coadă](#verificarea-în-joburi-de-coadă)). Excepțiile trec prin `pickle` fără să-și piardă atributele.

### Există SDK pentru Node.js sau PHP?

Da, cu aceleași apeluri: [`@acteo/api`](https://github.com/acteoro/sdk_javascript) pentru Node.js și TypeScript și [`acteo/api`](https://github.com/acteoro/sdk_php) pentru PHP. [Documentația API](https://acteo.ro/api-acces) are și exemple pentru cURL.

## Linkuri utile

- [Documentația API Acteo](https://acteo.ro/api-acces)
- [Verificare RCA online](https://acteo.ro/verificare-rca)
- [Verificare ITP online](https://acteo.ro/verificare-itp)
- [Verificare rovinietă online](https://acteo.ro/verificare-rovinieta)
- [Verificare copie conformă ARR](https://acteo.ro/verificare-arr)
- [Monitorizare flote auto](https://acteo.ro/flote)
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

Fără cheie rulează doar testul de autentificare. Cu `ACTEO_API_KEY` se adaugă listarea vehiculelor, care e gratuită. Verificările reale (`ACTEO_E2E_VERIFICARI=1`) consumă din cotă, iar testul de flotă (`ACTEO_E2E_FLOTA=1`) adaugă și șterge un vehicul. Amândouă pornesc doar dacă le activezi explicit.

## Licență

[MIT](./LICENSE), © Acteo.ro
