# рџЌі Cucina & Spesa

Web app per gestire ricette, dispensa, piano pasti settimanale e lista della spesa.

## FunzionalitГ 

- **Piano settimanale** вЂ” assegna una ricetta a pranzo e cena per ogni giorno, con porzioni personalizzabili. I pasti sono definiti in `MEALS` (`app.py`) e l'interfaccia li legge da `/api/meta`, quindi aggiungerne o toglierne uno si fa in un punto solo.
- **Ricette** вЂ” nome, porzioni, tempo, difficoltГ , ingredienti con quantitГ  e unitГ , preparazione.
- **Dispensa** вЂ” ciГІ che hai giГ  in casa, con quantitГ  aggiornabili.
- **Spesa** вЂ” lista raggruppata per categoria merceologica, con spunta degli articoli acquistati. Ogni voce indica quanto ne ГЁ giГ  in dispensa.
- **Generazione automatica** вЂ” dal piano settimanale crea la lista della spesa: somma gli ingredienti di tutti i pasti, scala le porzioni rispetto alla ricetta base e sottrae quello che ГЁ giГ  in dispensa.
- **Conversione automatica delle unitГ ** вЂ” le unitГ  compatibili vengono convertite da sole, quindi funziona mescolare `kg` e `g`, oppure `l`, `ml` e `cucchiai`.
- **Allergie e intolleranze** вЂ” alla prima apertura l'app chiede di dichiarare allergie e intolleranze. Le ricette che le contengono vengono evidenziate, sia nell'elenco sia nel piano settimanale, e possono essere nascoste con un filtro.

## Allergie e intolleranze

Alla prima apertura un onboarding chiede di dichiarare ciГІ che riguarda l'utente; la scelta ГЁ modificabile in ogni momento dalla scheda **Profilo**.

Si possono selezionare i 14 allergeni dell'allegato II del Regolamento UE 1169/2011 (quelli che per legge vanno evidenziati in etichetta) oppure aggiungere termini liberi come `nichel` o `fruttosio`.

Il riconoscimento (`allergens.py`) lavora sul nome dell'ingrediente, per parola intera, ignorando maiuscole e accenti. Include alcune eccezioni per evitare falsi positivi: `noce moscata` non ГЁ frutta a guscio, `latte di cocco` non ГЁ latte, `noodles di riso` non contengono glutine. Al contrario, `salsa di soia` viene marcata sia soia sia glutine, perchГ© contiene grano.

L'app mostra:

- l'elenco degli allergeni riconosciuti in ogni ingrediente di una ricetta;
- un'etichetta di allerta sulle ricette in conflitto con le restrizioni dichiarate;
- un filtro che nasconde le ricette in conflitto, utile per scegliere cosa cucinare;
- un avviso nel piano pasti se un pasto pianificato contiene una restrizione;
- un riepilogo di tutti gli ingredienti in uso, con gli allergeni e l'evidenza di quelli che riguardano l'utente.

> **Attenzione** вЂ” ГЁ un controllo indicativo basato sui nomi: un allergene nascosto in un prodotto lavorato (dado, salsa, pasta sfoglia, surgelati) puГІ sfuggire. Non sostituisce la lettura dell'etichetta nГ© il parere del medico.

## UnitГ  di misura

Le unitГ  sono raggruppate in dimensioni convertibili fra loro:

| Dimensione | UnitГ  | UnitГ  base |
| --- | --- | --- |
| Massa | `g`, `kg` | `g` |
| Volume | `ml`, `l`, `cucchiaino` (5 ml), `cucchiaio` (15 ml) | `ml` |

UnitГ  come `pz`, `fetta` o `confezione` non hanno un fattore fisso e restano indipendenti: 3 uova e 1 confezione di uova vengono tenute separate, perchГ© non si puГІ sapere quante uova contenga la confezione.

Cosa comporta in pratica:

- Una ricetta con 400 g di pasta e una dispensa con 0,1 kg della stessa pasta si scalano correttamente (restano 300 g da comprare).
- Se due ricette usano lo stesso ingrediente, una in `g` e una in `kg`, la lista della spesa mostra una sola voce con il totale.
- La lista usa sempre l'unitГ  piГ№ leggibile: 1500 g diventano 1,5 kg, mentre 400 ml restano ml. I cucchiai si mantengono solo per quantitГ  piccole (`1 cucchiaino` di sale, `2 cucchiai` d'olio), oltre i 250 ml si passa automaticamente a ml o l.
- I nomi delle unitГ  vengono normalizzati in ingresso: `Grammi`, `GR` e `g.` finiscono tutti in `g`.

## Dispensa nella lista della spesa

Ogni voce della lista riporta quanto dell'ingrediente ГЁ giГ  in dispensa, convertito nell'unitГ  della voce: con 0,2 kg di farina in casa, una voce da 300 g mostra `in dispensa: 200 g`. Se le unitГ  non sono confrontabili (dispensa in pezzi contro una voce in grammi) la giacenza viene mostrata nella sua unitГ , senza tentare conversioni.

La giacenza ГЁ calcolata a ogni lettura della lista, non congelata quando si genera: aggiungendo qualcosa in dispensa il dato si aggiorna subito, senza rigenerare la spesa.

> **Nota** вЂ” la quantitГ  da comprare ГЁ giГ  al netto della dispensa, quindi l'indicazione serve a ricordare cosa c'ГЁ in casa, non a suggerire di saltare l'acquisto. Se la dispensa copre l'intero fabbisogno la voce non compare affatto in lista.

## Ricettario di partenza

`seed.py` inserisce 25 ricette (primi, secondi, contorni e piatti unici, inclusi alcuni etnici) con ingredienti completi e categorie merceologiche giГ  assegnate. Г€ idempotente: le ricette giГ  presenti vengono saltate, mentre quelle elencate in `REMOVED` vengono rimosse dal database.

```bash
python3 seed.py
```

Viene usato per avere subito contenuti da selezionare nel piano pasti. Il database (`cucina.db`) non ГЁ versionato: va creato al primo avvio o popolato con `seed.py`.

## Test

```bash
pip install pytest
python -m pytest test_cucina.py -q
```

Quarantanove test coprono conversione, normalizzazione, fusione di unità compatibili nella lista della spesa, scala delle porzioni, riconoscimento degli allergeni (incluse le eccezioni), filtro delle ricette, giacenza in dispensa nella lista e gestione della foto di una ricetta (validazione del nome file inclusa).


## Interfaccia

Lo stile è editoriale, da ricettario: fondo carta calda, inchiostro scuro e un solo accento terracotta. I titoli sono in **Fraunces** (serif variabile), l'interfaccia in **Hanken Grotesk**. Entrambi i font sono ospitati in `static/fonts/`, quindi l'app funziona anche senza connessione e non dipende da CDN esterne.

L'eleganza sta in tipografia, spaziature e linee sottili: niente ombre marcate o decorazioni. Le quantità usano cifre incolonnate (`tabular-nums`), così i numeri non ballano fra una riga e l'altra.

Per la scelta dei colori vale il contrasto WCAG AA: ogni testo resta sopra 4.5:1 sul proprio fondo, anche il grigio secondario, che sui fondi colorati tende a scendere sotto soglia.

L'app funziona anche da telefono, dove sta in una sola colonna: la barra delle schede resta agganciata in alto, i campi di input usano 16px (sotto questa soglia iOS ingrandisce la pagina al primo tocco e non torna indietro), i bersagli toccabili sono alti almeno 42px e la tabella della dispensa diventa un elenco di schede, perché quattro colonne non entrerebbero nello schermo.

## Foto delle ricette

Ogni ricetta può avere una foto, che compare in cima alla scheda in **Ricette** per invogliare a cucinarla. Le immagini stanno in `static/recipes/`, ritagliate a 3:2 e larghe 800px: circa 80 KB l'una, caricate in differita (`loading="lazy"`) così la pagina si apre subito.

Provengono da **Wikimedia Commons**, scelte con licenze libere (CC0, CC BY, CC BY-SA). Il credito con autore, licenza e link alla pagina originale è salvato nel database (`image_credit`), mostrato al passaggio del mouse sulla foto e modificabile dal form della ricetta. Le licenze CC BY e CC BY-SA richiedono l'attribuzione: se sostituisci un'immagine, aggiorna anche il credito.

Cinque foto sono **indicative**, e il credito lo dichiara: quella di un piatto simile quando non ne esisteva una adatta su Commons.

La foto si imposta dal form della ricetta (menu a tendina fra i file presenti, con anteprima) e si può togliere con un pulsante. Il campo è facoltativo: una ricetta senza foto mostra solo testo. Il nome del file è validato lato server — solo nome semplice e estensione di immagine — per evitare percorsi o traversal.

## Avvio

```bash
pip install -r requirements.txt
python app.py           # http://localhost:8000
PORT=12000 python app.py
```

Il database SQLite (`cucina.db`) viene creato automaticamente al primo avvio. Per usare un file diverso: `CUCINA_DB=/percorso/mio.db`.

### Dal telefono

Il server ascolta su `0.0.0.0`, quindi risponde anche agli altri dispositivi della stessa rete. Apri sul telefono:

```
http://<ip-del-computer>:12000
```

Per trovare l'indirizzo: `hostname -I | awk '{print $1}'` (Linux/macOS) oppure `ipconfig` (Windows). Se non si apre, quasi sempre è il firewall che blocca la porta.

Da fuori casa si può esporre la porta con un tunnel, per esempio `ssh -R 80:localhost:12000 nokey@localhost.run` oppure `cloudflared tunnel --url http://localhost:12000`: stampano un indirizzo pubblico `https://...` da aprire sul telefono, valido finché il comando resta in esecuzione.

## API

| Metodo | Endpoint | Descrizione |
| --- | --- | --- |
| GET | `/api/meta` | Pasti, unitГ  di misura, categorie, allergeni |
| GET/PUT | `/api/profile` | Profilo: nome e restrizioni dichiarate |
| GET | `/api/profile/allergens` | Allergeni riconosciuti per ogni ingrediente in uso |
| GET/POST | `/api/ingredients` | Elenco / creazione ingredienti |
| GET/POST | `/api/pantry` | Dispensa |
| PATCH/DELETE | `/api/pantry/<id>` | Modifica quantitГ  o rimozione |
| GET/POST | `/api/recipes` | Ricette (`?full=1` include ingredienti, allergeni e conflitti; `?safe=1` esclude quelle in conflitto) |
| GET/PUT/DELETE | `/api/recipes/<id>` | Dettaglio, modifica, eliminazione |
| GET | `/api/recipe-images` | Nomi dei file foto disponibili in `static/recipes/` |
| GET/POST | `/api/plan` | Piano pasti (`?start=&end=`) |
| DELETE | `/api/plan/<id>` | Rimozione pasto |
| GET/POST | `/api/shopping` | Lista della spesa; ogni voce include `pantry` con la giacenza in dispensa |
| PATCH/DELETE | `/api/shopping/<id>` | Spunta o rimozione voce |
| POST | `/api/shopping/clear-checked` | Rimuove le voci spuntate |
| POST | `/api/shopping/generate` | Genera la lista da un intervallo `{start, end}` |

## Struttura

```
app.py              # backend Flask + API REST + logica di generazione
units.py            # conversione e normalizzazione delle unitГ  di misura
allergens.py        # riconoscimento di allergeni e intolleranze
seed.py             # ricettario di partenza
schema.sql          # schema SQLite
test_cucina.py      # test
static/index.html   # interfaccia
static/style.css
static/app.js
static/recipes/     # foto delle ricette (Wikimedia Commons, licenze libere)
static/fonts/       # Fraunces e Hanken Grotesk, ospitati in locale
```
