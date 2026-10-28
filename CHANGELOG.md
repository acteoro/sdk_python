# Changelog

Toate schimbările importante ale pachetului `acteo` (fost `verificrca`) sunt notate aici.

## acteo 0.3.0 (2026-10-29)

Pachetul `verificrca` continuă sub numele `acteo` (`pip install acteo`, `import acteo`), cu apelurile grupate pe domeniu și pe document. Vezi secțiunea „Vii de la verificrca?” din README.

- Clienți noi `Acteo` (sincron) și `AsyncActeo` (asyncio): `acteo.auto.rca`, `acteo.auto.itp`, `acteo.auto.rovinieta` și `acteo.auto.arr`, fiecare cu `verifica`, `porneste`, `rezultat` și `asteapta`. Fiecare document își cere exact identificatorii lui, iar rezultatul are tipul documentului (`RezultatRca`, `VerificareInCursRca` etc., subclase ale `VerificareFinala` și `VerificareInCurs`).
- La RCA, un text de 17 caractere fără I, O și Q e tratat ca VIN. Cu ambele date: `verifica(numar=..., vin=...)`.
- `rezultat` și `asteapta` primesc verificarea în curs întoarsă de `porneste` sau direct identificatorul documentului.
- `acteo.auto.flota` pentru vehiculele din cont și `acteo.webhooks` pentru webhook-uri.
- Adresa implicită este `https://api.acteo.ro`. Cheia se citește din `ACTEO_API_KEY`, apoi din `VERIFICRCA_API_KEY`.
- `ActeoError`, clasa de bază a excepțiilor (aceeași cu `VerificRcaError`).
- `import verificrca` și clienții `VerificRca` și `AsyncVerificRca` funcționează în continuare, cu aceleași obiecte și aceeași adresă implicită.

## [0.2.0] - 2026-10-09

- Verificarea rovinietei cere și numărul certificatului de înmatriculare (talon), în noul argument `serie_talon` al metodelor `porneste` și `verifica_si_asteapta`. Lipsa lui sau o formă invalidă (6-20 litere și cifre, cel puțin o cifră) oprește cererea local, fără să consume din cotă. La celelalte verificări `serie_talon` e ignorat.
- `vehicule.adauga` acceptă opțional `serie_talon`.
- `Vehicul` are câmpurile noi `serie_talon` și `serie_talon_respinsa`.
- `EroareVerificare` are atributul nou `cod_sursa`: `serie_talon_invalida`, `vin_invalid` sau `numar_invalid` când sursa a refuzat datele trimise, `None` când sursa nu a răspuns. `cod` rămâne `VERIFICARE_ESUATA`, ca înainte.
- Utilitare noi: `este_serie_talon_valida` și `normalizeaza_serie_talon`.

## [0.1.0] - 2026-09-29

Prima versiune.

- Clienți `VerificRca` (sincron) și `AsyncVerificRca` (asyncio), cu aceleași metode.
- Verificări RCA, ITP, rovinietă și ARR: `porneste`, `rezultat`, `asteapta`, `verifica_si_asteapta`.
- Gestionarea flotei: `vehicule.lista`, `vehicule.adauga`, `vehicule.sterge`.
- Webhook-uri: `parseaza_webhook_rezultat` și `verifica_webhook_notificare`, cu cheia comparată în timp constant.
- Validare locală a numărului de înmatriculare și a VIN-ului, înainte de orice cerere.
- Modele Pydantic imuabile, cu date `datetime` cu fus orar.
- Excepții tipate, cu mesaje în română.
- Reîncercări cu backoff exponențial și jitter, `Retry-After` respectat, fără POST-uri taxate repetate.
