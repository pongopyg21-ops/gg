# Cucina & Spesa — note per gli agenti

App Flask + SQLite + SPA in JS puro. Backend in `app.py`, conversione unità in
`units.py`, riconoscimento allergeni in `allergens.py`, dati iniziali in `seed.py`.

## Comandi

```bash
pip install -r requirements.txt          # flask>=3.0 e pytest, non sono preinstallati
python3 seed.py                          # popola il ricettario (idempotente)
python3 -m pytest test_cucina.py -q      # 34 test
PORT=12000 nohup python3 app.py > /tmp/server.log 2>&1 &
```

L'ambiente può essere azzerato fra una sessione e l'altra: se `import flask`
fallisce, reinstalla da `requirements.txt` prima di avviare il server.

## Convenzioni

- `MEALS` in `app.py` è l'unica fonte dei pasti; il frontend li legge da `/api/meta`.
- I test usano un DB temporaneo via `CUCINA_DB`, impostato prima di importare `app`.
  Non toccano `cucina.db`.
- `cucina.db` non è versionato: per provare l'app va creato con `seed.py`.
- `seed.py` è idempotente e rimuove le ricette elencate in `REMOVED`.
