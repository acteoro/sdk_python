# Changelog

Toate schimbările importante ale pachetului `verificrca` sunt notate aici.

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
