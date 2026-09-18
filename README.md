# 🍳 Il Cliente

Web app per gestire la cucina — ricette, dispensa, piano pasti settimanale e lista
della spesa — insieme alle altre aree di casa.

## Sezioni

L'app si apre su una **pagina iniziale** con tre aree:

- **🍳 Cucina** — tutto quello che l'app sa fare oggi: piano pasti, ricette,
  dispensa, lista della spesa, profilo e comandi vocali.
- **🧽 Igiene** — pulizie di casa e della cucina. Sezione predisposta, ancora senza
  funzioni.
- **📋 Progetti** — lavori in corso e idee. Sezione predisposta, ancora senza funzioni.

Aprendo un'area la barra mostra solo le schede di quell'area, così le voci non si
mescolano; il pulsante vocale, che serve in cucina, resta nascosto altrove.

## Funzionalità

- **Piano settimanale** — assegna una ricetta ai pasti di ogni giorno, con porzioni personalizzabili. Quanti pasti al giorno si sceglie all'inizio (da 1 a 5) e si cambia quando si vuole dal Profilo: i nomi dei pasti stanno in `MEAL_SETS` (`app.py`), l'interfaccia li legge da `/api/meta`, quindi aggiungerne o toglierne uno si fa in un punto solo.
- **Ricette** — nome, porzioni, tempo, difficoltà, ingredienti con quantità e unità, preparazione. Cliccando una ricetta si apre la finestra con ingredienti e passi numerati.
- **Dispensa** — ciò che hai già in casa, con quantità aggiornabili.
- **Spesa** — lista raggruppata per categoria merceologica, con spunta degli articoli acquistati. Ogni voce indica quanto ne è già in dispensa.
- **Filtro per giorno** — ogni voce dice quando serve e la lista si può restringere a un singolo giorno. Così i freschi si comprano vicino al pasto in cui servono, invece di fare tutta la spesa il lunedì per la domenica.
- **Generazione automatica** — dal piano settimanale crea la lista della spesa: somma gli ingredienti di tutti i pasti, scala le porzioni rispetto alla ricetta base e sottrae quello che è già in dispensa.
- **Conversione automatica delle unità** — le unità compatibili vengono convertite da sole, quindi funziona mescolare `kg` e `g`, oppure `l`, `ml` e `cucchiai`.
- **Allergie e intolleranze** — alla prima apertura l'app chiede di dichiarare allergie e intolleranze. Le ricette che le contengono vengono evidenziate, sia nell'elenco sia nel piano settimanale, e possono essere nascoste con un filtro.
- **Ricette preferite** — sempre in fase di profilazione si scelgono le ricette preferite, ritrovabili con il filtro **Solo preferite** e contrassegnate da una stella. La scelta si cambia dalla scheda Profilo o dalla stella su ogni ricetta.
- **Comandi vocali** — un pulsante 🎙 in basso a destra apre la dettatura: si può chiedere di aggiungere qualcosa alla dispensa o alla spesa, dichiarare un'allergia o cercare una ricetta, senza toccare la tastiera. Utile proprio quando le mani sono occupate o sporche, in cucina. La voce di conferma si può scegliere fra tre timbri, e un breve suono di apertura accompagna l'ingresso nell'app.

## Allergie e intolleranze

Alla prima apertura un onboarding in tre passi chiede quanti pasti al giorno si
vogliono gestire, poi di dichiarare allergie e intolleranze, infine le ricette
preferite; tutte le scelte sono modificabili in ogni momento dalla scheda
**Profilo**. Le domande compaiono entrando in **Cucina**, non sulla pagina iniziale:
riguardano la cucina e non hanno senso per chi sta andando altrove.

Il passo delle allergie si può saltare, e il primo passo salva comunque prima di passare al secondo: chi chiude a metà ritrova quanto aveva già dichiarato. A chi si era profilato prima che esistesse la scelta delle preferite il secondo passo viene riproposto una volta sola, all'avvio successivo, e può essere rimandato con **Più tardi**.

Si possono selezionare i 14 allergeni dell'allegato II del Regolamento UE 1169/2011 (quelli che per legge vanno evidenziati in etichetta) oppure aggiungere termini liberi come `nichel` o `fruttosio`.

Il riconoscimento (`allergens.py`) lavora sul nome dell'ingrediente, per parola intera, ignorando maiuscole e accenti. Include alcune eccezioni per evitare falsi positivi: `noce moscata` non è frutta a guscio, `latte di cocco` non è latte, `noodles di riso` non contengono glutine. Al contrario, `salsa di soia` viene marcata sia soia sia glutine, perché contiene grano.

L'app mostra:

- l'elenco degli allergeni riconosciuti in ogni ingrediente di una ricetta;
- un'etichetta di allerta sulle ricette in conflitto con le restrizioni dichiarate;
- un filtro che nasconde le ricette in conflitto, utile per scegliere cosa cucinare;
- un avviso nel piano pasti se un pasto pianificato contiene una restrizione;
- un riepilogo di tutti gli ingredienti in uso, con gli allergeni e l'evidenza di quelli che riguardano l'utente.

> **Attenzione** — è un controllo indicativo basato sui nomi: un allergene nascosto in un prodotto lavorato (dado, salsa, pasta sfoglia, surgelati) può sfuggire. Non sostituisce la lettura dell'etichetta né il parere del medico.

## Ricette preferite

Le preferite si scelgono nel secondo passo dell'onboarding, con una ricerca fra le ricette, e si possono cambiare in qualsiasi momento dalla scheda **Profilo** o dalla stella **☆ Preferita** su ogni scheda della scheda Ricette.

Nella scheda Ricette le preferite hanno una stella accanto al nome e il filtro **Solo preferite** restringe l'elenco a quelle scelte.

Le preferite stanno in una tabella dedicata (`favorites`), non in una colonna di `recipes`: sono una scelta dell'utente, non un dato della ricetta. La chiave esterna con `ON DELETE CASCADE` fa sì che eliminando una ricetta sparisca anche la sua preferenza, senza voci orfane. In `PUT /api/profile` il campo `favorite_ids` si tocca solo se presente, così un salvataggio parziale (per esempio solo il nome) non azzera la scelta; gli id inesistenti vengono ignorati.

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

## Dispensa nella lista della spesa

Ogni voce della lista riporta quanto dell'ingrediente è già in dispensa, convertito nell'unità della voce: con 0,2 kg di farina in casa, una voce da 300 g mostra `in dispensa: 200 g`. Se le unità non sono confrontabili (dispensa in pezzi contro una voce in grammi) la giacenza viene mostrata nella sua unità, senza tentare conversioni.

La giacenza è calcolata a ogni lettura della lista, non congelata quando si genera: aggiungendo qualcosa in dispensa il dato si aggiorna subito, senza rigenerare la spesa.

> **Nota** — la quantità da comprare è già al netto della dispensa, quindi l'indicazione serve a ricordare cosa c'è in casa, non a suggerire di saltare l'acquisto. Se la dispensa copre l'intero fabbisogno la voce non compare affatto in lista.

## Spesa per giorno

Fare tutta la spesa il lunedì per i pasti della domenica non ha senso per quello che deperisce: il pesce del giovedì e la verdura del sabato comprati con una settimana di anticipo perdono qualità. Le voci della lista riportano quindi quando servono — `serve mar 15`, oppure `serve lun 14 +3` quando l'ingrediente ricorre in più giorni, con l'elenco completo nel suggerimento del mouse — e un filtro in cima restringe la lista a un singolo giorno, mostrando per ogni voce la quota di quel giorno e non il totale.

La ripartizione è calcolata a ogni lettura dal piano pasti, non salvata: il piano è già la fonte di verità di quando serve un ingrediente, e una copia si disallineerebbe appena si modifica un pasto.

Due dettagli che rendono i numeri affidabili:

- la somma delle quote giornaliere è esattamente il totale della voce, quindi la vista per giorno non contraddice quella completa;
- la dispensa viene scalata a partire dai giorni più vicini, perché quello che si ha in casa serve naturalmente ai primi pasti. Con 400 g di riso in dispensa e due pasti da 400 g, il giorno più vicino risulta già coperto e resta da comprare solo quello lontano.

Quando la quantità in lista non corrisponde al fabbisogno del piano — perché la lista si accumula a ogni generazione o perché è stata corretta a mano — le quote vengono riscalate sul valore effettivo della voce, così i due numeri continuano a coincidere.

Le categorie che deperiscono (Frutta e Verdura, Carne e Pesce, Latticini) sono segnalate con un avviso, che invita a comprarle vicino al giorno in cui servono.

## Ricettario di partenza

`seed.py` inserisce 45 ricette (primi, secondi, contorni e piatti unici, inclusi alcuni etnici) con ingredienti completi e categorie merceologiche già assegnate. È idempotente: le ricette già presenti vengono saltate, mentre quelle elencate in `REMOVED` vengono rimosse dal database.

Fra queste, 20 sono state scelte fra i piatti entrati in voga negli ultimi anni: la classifica dei primi più popolari per hashtag Instagram e ricerche Google (Pasta Day 2024) e le ricerche più alte su Google nel 2024-2025. Ci sono classici regionali tornati in auge come **Pasta alla Norma** (2ª in classifica), **Cacio e pepe**, **Spaghetti all'assassina**, **Casoncelli alla bergamasca** e **Malloreddus alla campidanese**, e piatti nati o rilanciati dai social come **Marry me chicken** e **Lasagna soup**, accanto a **Poke bowl**, **Ramen**, **Paella** e **Chicken tikka masala**.

```bash
python3 seed.py
```

Viene usato per avere subito contenuti da selezionare nel piano pasti. Il database (`cucina.db`) non è versionato: va creato al primo avvio o popolato con `seed.py`.

## Comandi vocali

Il pulsante 🎙 in basso a destra apre la dettatura e resta raggiungibile da ogni scheda. Il riconoscimento avviene nel browser con la **Web Speech API** (`it-IT`), quindi nessun audio lascia il dispositivo: al server arriva solo il testo, come se fosse scritto a mano.

La comprensione della frase sta invece in `voice.py`, non nel browser, così è verificabile con i test. `POST /api/voice` restituisce l'intento riconosciuto e lo esegue:

| Cosa si può dire | Intento | Effetto |
| --- | --- | --- |
| «aggiungi due chili di farina in dispensa» | `pantry_add` | aggiunge in dispensa |
| «metti mezzo litro di latte nella spesa» | `shopping_add` | aggiunge alla lista |
| «sono allergico al nichel» | `term_add` | aggiunge alle restrizioni del profilo |
| «cerca la carbonara» | `recipe_search` | filtra le ricette |

Senza indicazioni la destinazione predefinita è la lista della spesa, perché è la scelta più frequente e la meno rischiosa: una voce di troppo in lista si cancella con un tocco, una giacenza sbagliata in dispensa falsa i calcoli.

Il parser riconosce quantità in cifre e a parole, anche composte (`venticinque`, `duecento`), le frazioni (`mezzo`, `un quarto`, `un chilo e mezzo`) e le unità comuni. Gli **etti** vengono convertiti subito in grammi, così in dispensa le quantità restano confrontabili. Articoli, preposizioni e verbi di comando vengono tolti dal nome, ma solo ai bordi: all'interno restano, altrimenti `passata di pomodoro` diventerebbe `passata pomodoro`. Le unità sono elencate in `_UNIT_TOKENS`, le parole di comando in `_COMMAND_VERBS`.

Una frase senza verbo di comando, senza destinazione e senza quantità è considerata rumore di fondo e non scrive nulla: durante la cottura il microfono sente anche conversazioni e rumori, e una lista piena di voci inventate è peggio di un comando non capito. Il pannello mostra sempre la frase sentita e chiede conferma; c'è anche un campo per scrivere o correggere il comando a mano, così la funzione resta utilizzabile dove il riconoscimento vocale non c'è.

### La voce che risponde

La conferma a voce usa la sintesi del sistema operativo e si può cambiare dal pannello con il selettore **Voce**: tre timbri fra cui scegliere, con anteprima immediata al momento della scelta. Il timbro preferito resta memorizzato, come la possibilità di spegnere del tutto la conferma parlata.

Il timbro è una *preferenza*, non un nome fisso: la voce concreta cambia fra Windows, macOS, Android e Chrome, quindi l'app cerca la voce italiana più vicina e mostra accanto al timbro il nome che sta usando davvero. La ricerca è per genere e lingua, con una lista di nomi noti in ordine di preferenza (`alice`, `elsa`, `paola`… per il timbro femminile) e, se nessuna voce italiana esiste, si ripiega su quella predefinita invece di restare muta.

### Il suono all'apertura

Il jingle breve, due note in salita, è sintetizzato al volo con la **Web Audio API**: non c'è nessun file audio da scaricare e la pagina resta usabile anche senza rete.

> **Perché non suona da solo all'apertura** — i browser bloccano l'audio finché l'utente non tocca la pagina. Non è una scelta dell'app: è una protezione loro contro i suoni automatici. Il jingle parte quindi in un modo che aggira il problema senza violarlo: se il contesto audio è già attivo suona subito, altrimenti scatta **al primo tocco o tasto** — la prima occasione in cui il browser lo permette. Suona una volta sola per visita e si può disattivare con la casella **Suono all'avvio**, scelta che viene ricordata.

## Test

```bash
pip install pytest
python -m pytest test_cucina.py -q
```

Novantacinque test coprono conversione, normalizzazione, fusione di unità compatibili nella lista della spesa, scala delle porzioni, riconoscimento degli allergeni (incluse le eccezioni e le forme di pasta del ricettario), filtro delle ricette, giacenza in dispensa nella lista, ripartizione della spesa per giorno (incluso il caso della dispensa che copre i giorni più vicini), dettaglio di una ricetta con la sua preparazione, gestione della foto (validazione del nome file inclusa), ricette preferite (persistenza, cascata all'eliminazione della ricetta, salvataggi parziali), coerenza del ricettario di partenza, migrazione delle colonne `fav_prompted` e `meals_per_day` su un database esistente i comandi vocali (quantità a parole e in cifre, etti, frazioni, numeri composti, pulizia del nome, allergie dette a voce, ricerca, rumore di fondo ignorato, esecuzione reale degli intenti via `/api/voice`) e la scelta dei pasti al giorno (numero valido, effetto sui pasti ammessi, pasti tolti che non pesano più sulla spesa).


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

## Preparazione di una ricetta

Cliccando una ricetta — la scheda in **Ricette**, il pulsante *Preparazione*, o un pasto nel **Piano** — si apre una finestra con foto, porzioni, tempo, difficoltà, ingredienti e preparazione.

La preparazione viene scritta come testo unico e spezzata in **passi numerati** sulle fine di frase (`passiDa` in `static/app.js`). La suddivisione richiede una maiuscola dopo il punto, così non tronca le abbreviazioni seguite da minuscola come `es. la farina`; gli a capo nel testo restano separatori validi, quindi si possono scrivere i passi uno per riga.

Dal **Piano** la finestra ha in più il pulsante *Rimuovi dal piano*, perché cliccare il pasto serve prima di tutto a sapere come si cucina: la rimozione è diventata un'azione esplicita invece di una conferma che compariva al primo clic. Una ricetta senza preparazione resta leggibile e invita ad aggiungerla dal pulsante *Modifica*.

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
| GET | `/api/meta` | Pasti e numero di pasti al giorno, unità di misura, categorie, allergeni |
| GET/PUT | `/api/profile` | Profilo: nome, `meals_per_day`, restrizioni dichiarate, `favorite_ids` (preferite) e `fav_prompted` |
| GET | `/api/profile/allergens` | Allergeni riconosciuti per ogni ingrediente in uso |
| GET/POST | `/api/ingredients` | Elenco / creazione ingredienti |
| GET/POST | `/api/pantry` | Dispensa |
| PATCH/DELETE | `/api/pantry/<id>` | Modifica quantità o rimozione |
| GET/POST | `/api/recipes` | Ricette (`?full=1` include ingredienti, allergeni e conflitti; `?safe=1` esclude quelle in conflitto) |
| GET/PUT/DELETE | `/api/recipes/<id>` | Dettaglio, modifica, eliminazione |
| GET | `/api/recipe-images` | Nomi dei file foto disponibili in `static/recipes/` |
| GET/POST | `/api/plan` | Piano pasti (`?start=&end=`) |
| DELETE | `/api/plan/<id>` | Rimozione pasto |
| GET/POST | `/api/shopping` | Lista della spesa; ogni voce include `pantry` con la giacenza in dispensa, `days` con i giorni in cui serve e `perishable` per le categorie deperibili |
| PATCH/DELETE | `/api/shopping/<id>` | Spunta o rimozione voce |
| POST | `/api/shopping/clear-checked` | Rimuove le voci spuntate |
| POST | `/api/shopping/generate` | Genera la lista da un intervallo `{start, end}` |
| POST | `/api/voice` | Interpreta un comando dettato `{text}` (`voice.py`) e lo esegue: `pantry_add`, `shopping_add`, `term_add`, `recipe_search`. Risponde 422 se la frase non è un comando |

## Struttura

```
app.py              # backend Flask + API REST + logica di generazione
units.py            # conversione e normalizzazione delle unità di misura
voice.py            # comprensione dei comandi vocali
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
