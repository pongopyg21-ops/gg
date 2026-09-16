# 🍳 Cucina & Spesa

Web app per gestire ricette, dispensa, piano pasti settimanale e lista della spesa.

## Funzionalità

- **Piano settimanale** — assegna una ricetta a colazione/pranzo/cena/spuntino per ogni giorno, con porzioni personalizzabili.
- **Ricette** — nome, porzioni, tempo, difficoltà, ingredienti con quantità e unità, preparazione.
- **Dispensa** — ciò che hai già in casa, con quantità aggiornabili.
- **Spesa** — lista raggruppata per categoria merceologica, con spunta degli articoli acquistati.
- **Generazione automatica** — dal piano settimanale crea la lista della spesa: somma gli ingredienti di tutti i pasti, scala le porzioni rispetto alla ricetta base e sottrae quello che è già in dispensa.
- **Conversione automatica delle unità** — le unità compatibili vengono convertite da sole, quindi funziona mescolare `kg` e `g`, oppure `l`, `ml` e `cucchiai`.

## Unità di misura

Le unità sono raggruppate in dimensioni convertibili fra loro:

| Dimensione | Unità | Unità base |
| --- | --- | --- |
| Massa | `g`, `kg` | `g` |
| Volume | `ml`, `l`, `cucchiaino` (5 ml), `cucchiaio` (15 ml) | `ml` |

Unità come `pz`, `fetta` o `confezione` non hanno un fattore fisso e restano indipendenti: 3 uova e 1 confezione di uova vengono tenute separate, perché non si può sapere quante uova contenga la confezione.

Cosa comporta in pratica:

- Una ricetta con 400 g di pasta e una dispensa con 0,1 kg della stessa pasta si scalano correttamente (restano 300 g da comprare).
- Se due ricette usano lo stesso ingrediente, una in `g` e una in `kg`, la lista della spesa mostra una sola voce con il totale.
- La lista usa sempre l'unità più leggibile: 1500 g diventano 1,5 kg, mentre 400 ml restano ml. I cucchiai non entrano in questa scelta automatica, altrimenti 400 ml diventerebbero "26,67 cucchiai".
- I nomi delle unità vengono normalizzati in ingresso: `Grammi`, `GR` e `g.` finiscono tutti in `g`.

## Test

```bash
pip install pytest
python -m pytest test_cucina.py -q
```

Venti test coprono conversione, normalizzazione, fusione di unità compatibili nella lista della spesa, scala delle porzioni e casi limite.


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
units.py            # conversione e normalizzazione delle unità di misura
schema.sql          # schema SQLite
test_cucina.py      # test
static/index.html   # interfaccia
static/style.css
static/app.js
```
