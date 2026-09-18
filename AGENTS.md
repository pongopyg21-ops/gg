# Il Cliente — note per gli agenti

App Flask + SQLite + SPA in JS puro. Backend in `app.py`, conversione unità in
`units.py`, riconoscimento allergeni in `allergens.py`, comandi vocali in
`voice.py`, dati iniziali in `seed.py`.

L'app si apre su una **pagina iniziale** che smista verso tre sezioni: **Cucina**,
**Igiene**, **Progetti**. Tutte le funzioni attuali (piano, ricette, dispensa,
spesa, profilo, comandi vocali) stanno in **Cucina**; Igiene e Progetti hanno una
pagina dedicata ma ancora senza funzioni.

## Comandi

```bash
pip install -r requirements.txt          # flask>=3.0, non è preinstallato
python3 seed.py                          # popola il ricettario (idempotente)
python3 -m pytest test_cucina.py -q      # 95 test
PORT=12000 setsid nohup python3 app.py > /tmp/server.log 2>&1 < /dev/null &
```

L'ambiente può essere azzerato fra una sessione e l'altra: `cucina.db` sopravvive,
ma i pacchetti installati no. Se `import flask` fallisce, reinstalla da
`requirements.txt` prima di avviare il server.

L'host pubblico inoltra sulla **porta 12000**: senza `PORT=12000` il server si
avvia su 8000 e il link esterno restituisce errore. Usa `setsid` per staccare il
processo dalla shell, altrimenti viene terminato alla fine del comando.

## Convenzioni

- `MEALS` in `app.py` è l'unica fonte dei pasti; il frontend li legge da `/api/meta`.
- I test usano un DB temporaneo via `CUCINA_DB`, impostato prima di importare `app`.
  Non toccano `cucina.db`.
- `cucina.db` non è versionato: per provare l'app va creato con `seed.py`.
- `seed.py` è idempotente e rimuove le ricette elencate in `REMOVED`.
- Aggiungendo una ricetta al seed si usa una delle costanti di categoria (`FRUTTA`,
  `CARNE`, …): se manca il valore, va aggiunta in cima a `seed.py`, altrimenti la
  categoria finisce nel DB come stringa sbagliata. Ogni formato di pasta nuovo va
  aggiunto alle regole del glutine in `allergens.py`, altrimenti la ricetta sfugge
  al filtro allergie. Il test `test_ricettario_di_partenza_e_coerente` verifica
  categorie, unità e quantità di tutto il ricettario.
- I giorni in cui serve una voce della spesa (`days` in `/api/shopping`) si calcolano
  a ogni lettura dal piano con `_need_by_day`/`_day_breakdown`, non si salvano: una
  tabella di appoggio si disallineerebbe appena si modifica un pasto. L'invariante
  `sum(days) == quantity` va mantenuta, e le quote vanno riscalate sul totale
  effettivo della voce perché la lista si accumula a ogni generazione.
- Le ricette preferite stanno nella tabella `favorites`, non in una colonna di
  `recipes`: sono una scelta dell'utente e la FK con `ON DELETE CASCADE` evita
  preferenze orfane. In `PUT /api/profile` i campi si toccano solo se presenti
  (`favorite_ids`, `full_name`, …), così i salvataggi parziali non azzerano il resto.
- `migrate()` in `app.py` è l'unico posto dove aggiungere colonne: `CREATE TABLE IF
  NOT EXISTS` non tocca le tabelle esistenti, quindi ogni colonna nuova va aggiunta
  sia in `schema.sql` sia in `migrate()` (vedi `fav_prompted`).
- I comandi vocali stanno in `voice.py` e non nel frontend: il browser si limita a
  dettare testo con la Web Speech API e a mandarlo a `POST /api/voice`, così la
  comprensione è testabile senza microfono. `parse()` riconosce gli intenti
  `pantry_add`, `shopping_add`, `term_add`, `recipe_search` e restituisce `unknown`
  quando non capisce. Le unità si aggiungono in `_UNIT_TOKENS`, le parole di comando
  in `_COMMAND_VERBS`, le preposizioni di destinazione in `_find_destination`. Una
  frase senza verbo, destinazione o quantità è rumore di fondo e deve restare
  `unknown`: il microfono sente anche i discorsi in cucina e le voci inventate in
  lista sono peggio di un comando non capito.
- La voce di conferma si sceglie in `TIMBRI` (`static/app.js`) per **caratteristiche**,
  non per nome: l'elenco `nomi` è una lista di preferenze, e `scegliVoce` prende la
  prima voce italiana che combacia, altrimenti la prima italiana, altrimenti quella
  predefinita. Non tornare a un nome fisso come `Alice`: su Linux e Android quella
  voce non esiste, e la conferma resterebbe muta. `aggiornaEtichetteVoci` mostra il
  nome reale accanto al timbro, così l'etichetta dice la verità su ogni piattaforma.
- Il jingle di apertura (`suonoApertura`) è sintetizzato con la Web Audio API, senza
  file audio. **Non può partire da solo**: i browser tengono l'`AudioContext`
  sospeso finché l'utente non interagisce. `tentaSuonoApertura` è legato ai primi
  `pointerdown`/`keydown` con `once: true`, e la guardia `tingsuonato` impedisce che
  risuoni; non "semplificarlo" in una chiamata diretta all'avvio, verrebbe ignorato
  dai browser e il suono non si sentirebbe mai. Le preferenze di voce e suono stanno
  in `localStorage` (`voceTimbro`, `voceSuono`), non nel profilo sul server: sono
  scelte del dispositivo, non dell'utente.
- Quanti pasti al giorno è una scelta dell'utente (1-5) salvata in
  `profile.meals_per_day`, non una costante: i nomi dei pasti stanno in `MEAL_SETS`
  (`app.py`) e il frontend li mostra da `/api/meta`. `valid_meals(db)` e
  `meal_clause(db)` sono l'unico modo per sapere quali pasti contano: riducendo i
  pasti restano righe vecchie in `meal_plan`, e senza quel filtro continuerebbero a
  pesare sulla lista della spesa pur non essendo più visibili.
- Nelle sezioni la barra mostra solo le schede dell'area aperta (`data-section`
  sulle schede, `SEZIONI` in `app.js` come mappa area → prima scheda): le voci di
  cucina, igiene e progetti non vanno mescolate in un'unica barra. Il pulsante
  vocale è una funzione della cucina e resta nascosto altrove.
- L'onboarding ha tre passi (`passoPasti` dentro `openOnboarding` e
  `openFavoritesStep`): prima quanti pasti, poi allergie, poi preferite.
  `fav_prompted` distingue chi non ha mai visto la scelta delle preferite, così il
  terzo passo viene riproposto a chi si era profilato prima. Lo stato dei passi vive
  in una `bozza` condivisa, perché "Indietro" non salva. Le domande iniziali si
  aprono entrando in Cucina (`avviaProfiloSeServe`), non sulla pagina iniziale: chi
  sta andando in Igiene non deve vedersi chiedere cose di cucina.

## Interfaccia mobile

Il layout sotto i 560px è una sola colonna. Tre vincoli da non rompere quando si tocca il CSS:

- Gli input del telefono usano `font-size: 16px`: sotto questa soglia iOS ingrandisce la pagina al primo tocco e non torna indietro.
- La dispensa è una tabella che diventa elenco di schede. Le etichette di colonna arrivano da `data-label` sulle celle, generato in `renderPantry`, e sono mostrate via `::before`: aggiungendo una colonna va aggiunto anche il `data-label`.
- I bersagli toccabili hanno `min-height: 42px`.
- Il pulsante vocale è `position: fixed` in basso a destra, quindi `main` ha `padding-bottom` generoso: senza, il pulsante coprirebbe l'ultima voce delle liste. Lo `z-index` (40) è sotto i modali, così non galleggia sopra le finestre aperte.
- `.voice-box` ha `max-height: 100%; overflow-y: auto`: su schermi bassi (telefono piccolo, tastiera aperta) scorre dentro di sé invece di spingere la ✕ fuori dallo schermo. Senza, il pannello diventa impossibile da chiudere.

## Stile

Direzione: editoriale da ricettario. Fondo carta calda, inchiostro scuro, un solo accento terracotta. Titoli in Fraunces (`--font-display`), interfaccia in Hanken Grotesk (`--font-ui`).

- I font sono in `static/fonts/` e serviti da Flask, non da una CDN: l'app resta usabile senza internet.
- I colori stanno tutti in `:root`. Cambiare palette significa toccare solo quelle variabili.
- Ogni combinazione testo/fondo deve restare sopra 4.5:1 (WCAG AA). Il grigio `--muted` è scelto per passare anche sui fondi colorati come `--accent-soft`, dove un grigio più chiaro scenderebbe a 4.37.
- Le cifre delle quantità usano `tabular-nums`.

Test di verifica senza browser grafico: Chromium headless è già presente.

```bash
chromium --headless=new --no-sandbox --window-size=390,844 --screenshot=/tmp/prova.png http://localhost:12000/
```

Playwright con `executable_path="/usr/bin/chromium"` permette di controllare overflow orizzontale, aree toccabili, caricamento dei font e contrasto su viewport diversi.
