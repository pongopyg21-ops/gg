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
