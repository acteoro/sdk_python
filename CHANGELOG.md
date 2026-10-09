# Changelog

Toate schimbările importante ale pachetului `verificrca` sunt notate aici.

## [0.2.0] - 2026-10-09

- Verificarea rovinietei cere și numărul certificatului de înmatriculare (talon), în noul argument `serie_talon` al metodelor `porneste` și `verifica_si_asteapta`. Lipsa lui sau o formă invalidă (6-20 litere și cifre, cel puțin o cifră) oprește cererea local, fără să consume din cotă. La celelalte verificări `serie_talon` e ignorat.
- `vehicule.adauga` acceptă opțional `serie_talon`.
- `Vehicul` are câmpurile noi `serie_talon` și `serie_talon_respinsa`.
- `EroareVerificare.cod` spune de ce s-a încheiat verificarea cu eroare: `VERIFICARE_ESUATA` când sursa nu a răspuns, sau `serie_talon_invalida`, `vin_invalid`, `numar_invalid` când sursa a refuzat datele trimise.
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
