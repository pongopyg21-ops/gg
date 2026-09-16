# 🍳 Cucina & Spesa

Web app per gestire ricette, dispensa, piano pasti settimanale e lista della spesa.

## Funzionalità

- **Piano settimanale** — assegna una ricetta a colazione/pranzo/cena/spuntino per ogni giorno, con porzioni personalizzabili.
- **Ricette** — nome, porzioni, tempo, difficoltà, ingredienti con quantità e unità, preparazione.
- **Dispensa** — ciò che hai già in casa, con quantità aggiornabili.
- **Spesa** — lista raggruppata per categoria merceologica, con spunta degli articoli acquistati.
- **Generazione automatica** — dal piano settimanale crea la lista della spesa: somma gli ingredienti di tutti i pasti, scala le porzioni rispetto alla ricetta base e sottrae quello che è già in dispensa.

## Avvio

```bash
pip install -r requirements.txt
python app.py           # http://localhost:8000
PORT=12000 python app.py
```

Il database SQLite (`cucina.db`) viene creato automaticamente al primo avvio. Per usare un file diverso: `CUCINA_DB=/percorso/mio.db`.

## API

| Metodo | Endpoint | Descrizione |
| --- | --- | --- |
| GET | `/api/meta` | Pasti, unità di misura, categorie |
| GET/POST | `/api/ingredients` | Elenco / creazione ingredienti |
| GET/POST | `/api/pantry` | Dispensa |
| PATCH/DELETE | `/api/pantry/<id>` | Modifica quantità o rimozione |
| GET/POST | `/api/recipes` | Ricette (`?full=1` include gli ingredienti) |
| GET/PUT/DELETE | `/api/recipes/<id>` | Dettaglio, modifica, eliminazione |
| GET/POST | `/api/plan` | Piano pasti (`?start=&end=`) |
| DELETE | `/api/plan/<id>` | Rimozione pasto |
| GET/POST | `/api/shopping` | Lista della spesa |
| PATCH/DELETE | `/api/shopping/<id>` | Spunta o rimozione voce |
| POST | `/api/shopping/clear-checked` | Rimuove le voci spuntate |
| POST | `/api/shopping/generate` | Genera la lista da un intervallo `{start, end}` |

## Struttura

```
app.py              # backend Flask + API REST + logica di generazione
schema.sql          # schema SQLite
static/index.html   # interfaccia
static/style.css
static/app.js
```

## Note

La generazione della spesa confronta le quantità solo a parità di unità: se una ricetta usa `kg` e la dispensa ha `g`, non vengono scalate. Conviene usare unità coerenti per lo stesso ingrediente.
