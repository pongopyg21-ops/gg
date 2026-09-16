# 🍳 Cucina & Spesa

Web app per gestire ricette, dispensa, piano pasti settimanale e lista della spesa.

## Funzionalità

- **Piano settimanale** — assegna una ricetta a pranzo e cena per ogni giorno, con porzioni personalizzabili. I pasti sono definiti in `MEALS` (`app.py`) e l'interfaccia li legge da `/api/meta`, quindi aggiungerne o toglierne uno si fa in un punto solo.
- **Ricette** — nome, porzioni, tempo, difficoltà, ingredienti con quantità e unità, preparazione.
- **Dispensa** — ciò che hai già in casa, con quantità aggiornabili.
- **Spesa** — lista raggruppata per categoria merceologica, con spunta degli articoli acquistati.
- **Generazione automatica** — dal piano settimanale crea la lista della spesa: somma gli ingredienti di tutti i pasti, scala le porzioni rispetto alla ricetta base e sottrae quello che è già in dispensa.
- **Conversione automatica delle unità** — le unità compatibili vengono convertite da sole, quindi funziona mescolare `kg` e `g`, oppure `l`, `ml` e `cucchiai`.
- **Allergie e intolleranze** — alla prima apertura l'app chiede di dichiarare allergie e intolleranze. Le ricette che le contengono vengono evidenziate, sia nell'elenco sia nel piano settimanale, e possono essere nascoste con un filtro.

## Allergie e intolleranze

Alla prima apertura un onboarding chiede di dichiarare ciò che riguarda l'utente; la scelta è modificabile in ogni momento dalla scheda **Profilo**.

Si possono selezionare i 14 allergeni dell'allegato II del Regolamento UE 1169/2011 (quelli che per legge vanno evidenziati in etichetta) oppure aggiungere termini liberi come `nichel` o `fruttosio`.

Il riconoscimento (`allergens.py`) lavora sul nome dell'ingrediente, per parola intera, ignorando maiuscole e accenti. Include alcune eccezioni per evitare falsi positivi: `noce moscata` non è frutta a guscio, `latte di cocco` non è latte, `noodles di riso` non contengono glutine. Al contrario, `salsa di soia` viene marcata sia soia sia glutine, perché contiene grano.

L'app mostra:

- l'elenco degli allergeni riconosciuti in ogni ingrediente di una ricetta;
- un'etichetta di allerta sulle ricette in conflitto con le restrizioni dichiarate;
- un filtro che nasconde le ricette in conflitto, utile per scegliere cosa cucinare;
- un avviso nel piano pasti se un pasto pianificato contiene una restrizione;
- un riepilogo di tutti gli ingredienti in uso, con gli allergeni e l'evidenza di quelli che riguardano l'utente.

> **Attenzione** — è un controllo indicativo basato sui nomi: un allergene nascosto in un prodotto lavorato (dado, salsa, pasta sfoglia, surgelati) può sfuggire. Non sostituisce la lettura dell'etichetta né il parere del medico.

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
- La lista usa sempre l'unità più leggibile: 1500 g diventano 1,5 kg, mentre 400 ml restano ml. I cucchiai si mantengono solo per quantità piccole (`1 cucchiaino` di sale, `2 cucchiai` d'olio), oltre i 250 ml si passa automaticamente a ml o l.
- I nomi delle unità vengono normalizzati in ingresso: `Grammi`, `GR` e `g.` finiscono tutti in `g`.

## Ricettario di partenza

`seed.py` inserisce 18 ricette (primi, secondi, contorni e piatti unici, inclusi alcuni etnici) con ingredienti completi e categorie merceologiche già assegnate. È idempotente: le ricette già presenti vengono saltate, mentre quelle elencate in `REMOVED` vengono rimosse dal database.

```bash
python3 seed.py
```

Viene usato per avere subito contenuti da selezionare nel piano pasti. Il database (`cucina.db`) non è versionato: va creato al primo avvio o popolato con `seed.py`.

## Test

```bash
pip install pytest
python -m pytest test_cucina.py -q
```

Trentadue test coprono conversione, normalizzazione, fusione di unità compatibili nella lista della spesa, scala delle porzioni, riconoscimento degli allergeni (incluse le eccezioni) e filtro delle ricette.


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
| GET | `/api/meta` | Pasti, unità di misura, categorie, allergeni |
| GET/PUT | `/api/profile` | Profilo: nome e restrizioni dichiarate |
| GET | `/api/profile/allergens` | Allergeni riconosciuti per ogni ingrediente in uso |
| GET/POST | `/api/ingredients` | Elenco / creazione ingredienti |
| GET/POST | `/api/pantry` | Dispensa |
| PATCH/DELETE | `/api/pantry/<id>` | Modifica quantità o rimozione |
| GET/POST | `/api/recipes` | Ricette (`?full=1` include ingredienti, allergeni e conflitti; `?safe=1` esclude quelle in conflitto) |
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
allergens.py        # riconoscimento di allergeni e intolleranze
seed.py             # ricettario di partenza
schema.sql          # schema SQLite
test_cucina.py      # test
static/index.html   # interfaccia
static/style.css
static/app.js
```
