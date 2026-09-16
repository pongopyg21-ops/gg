# Cucina & Spesa — note per gli agenti

App Flask + SQLite + SPA in JS puro. Backend in `app.py`, conversione unità in
`units.py`, riconoscimento allergeni in `allergens.py`, dati iniziali in `seed.py`.

## Comandi

```bash
pip install -r requirements.txt          # flask>=3.0, non è preinstallato
python3 seed.py                          # popola il ricettario (idempotente)
python3 -m pytest test_cucina.py -q      # 41 test
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

## Interfaccia mobile

Il layout sotto i 560px è una sola colonna. Tre vincoli da non rompere quando si tocca il CSS:

- Gli input del telefono usano `font-size: 16px`: sotto questa soglia iOS ingrandisce la pagina al primo tocco e non torna indietro.
- La dispensa è una tabella che diventa elenco di schede. Le etichette di colonna arrivano da `data-label` sulle celle, generato in `renderPantry`, e sono mostrate via `::before`: aggiungendo una colonna va aggiunto anche il `data-label`.
- I bersagli toccabili hanno `min-height: 42px`.

Per verificare il layout senza indovinare si può usare Chromium headless, già presente:

```bash
chromium --headless=new --no-sandbox --window-size=390,844 --screenshot=/tmp/prova.png http://localhost:12000/
```

Playwright con `executable_path="/usr/bin/chromium"` permette di controllare overflow orizzontale e misure delle aree toccabili su viewport diversi.
