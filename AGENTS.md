# Il Maggiordomo — note per gli agenti

App Flask + SQLite + SPA in JS puro. Backend in `app.py`, case separate in
`houses.py`, conversione unità in `units.py`, riconoscimento allergeni in
`allergens.py`, comandi vocali in `voice.py`, dati iniziali in `seed.py`, pulizie
in `igiene.py`, informazioni utili in `faq.py`, magazzino in `magazzino.py`.

L'app si apre su una **pagina iniziale** che smista verso quattro sezioni:
**Cucina**, **Igiene**, **Progetti**, **FAQ**. Piano, ricette, dispensa, spesa,
profilo e comandi vocali stanno in **Cucina**; le pulizie stanno in **Igiene**;
**Progetti** raccoglie lavori e idee da fare ed è anche la casa del **Magazzino**;
**FAQ** raccoglie le informazioni utili da consultare (Wi-Fi, indirizzi,
contatti, codici).

## Comandi

```bash
./avvia.sh                               # avvia e verifica il server
./avvia.sh restart                       # ferma e riavvia
./avvia.sh status                        # attivo? su quale porta?
./avvia.sh log                           # ultime righe del log
./avvia.sh test                          # test nella venv del progetto
./sorveglia.sh                           # riavvia il server da solo se cade
./sorveglia.sh status                    # sorveglianza attiva? server su?
```

**All'inizio di ogni conversazione il server non è attivo.** L'ambiente viene
azzerato fra una sessione e l'altra: i processi in background muoiono e i
pacchetti installati con `pip` di sistema spariscono. Il primo passo operativo è
quindi sempre `./avvia.sh`, che rimette in piedi tutto e aspetta che la **pagina
iniziale** risponda davvero (non un'API: con le case separate le API rispondono 401
finché non si è collegati, e un 401 farebbe sembrare morto un server vivo). Non
serve chiederlo all'utente: è il modo normale di ricominciare.

Le dipendenze però non si reinstallano più a ogni giro: stanno in una **venv
dentro il progetto** (`.venv`). `/workspace` è un volume che sopravvive
all'azzeramento mentre `$HOME` no, quindi la venv resta e Flask si installa solo
la prima volta. Non spostarla in `$HOME`: sparirebbe a ogni conversazione.
Da venv già pronta l'avvio è sotto il secondo; da zero (venv da creare) circa
cinque secondi. Se la venv non è creabile — `python3-venv` assente, disco pieno —
`avvia.sh` ripiega sui pacchetti di sistema senza fermarsi.

`avvia.sh` fa quello che serve per rimettere in piedi l'app: prepara l'ambiente,
crea `cucina.db` con `seed.py` se non c'è, avvia il server staccato dalla
shell e **aspetta che risponda davvero** invece di dare per scontato che sia
partito. È il modo normale di avviare l'app: evita di ripetere a mano i passi qui
sotto.

L'host pubblico inoltra sulla **porta 12000** (predefinita nello script): senza
`PORT=12000` il server si avvia su 8000 e il link esterno restituisce errore. Il
processo va staccato con `setsid`, altrimenti viene terminato alla fine del comando.

Due dettagli che riguardano solo chi modifica `avvia.sh`: un processo terminato in
questo ambiente può restare **zombie** (`ps` lo mostra in stato `Zs`), e `kill -0`
riesce comunque su uno zombie. Il controllo `vivo()` guarda lo stato reale, e la
prima lettera basta perché lo stato è `Z`, `Zs`, `Z+`… Senza questo, lo `stop`
aspetta cinque secondi e poi "forza" un processo già morto. Il riconoscimento del
processo verifica anche che giri da questa cartella (`/proc/<pid>/cwd`): `app.py` è
un nome comune e si rischierebbe di fermare quello di un altro progetto.

## Recupero e link pubblico

Il codice vive sul branch **`gg`**, allineato a **`main`**: un clone normale del
repository contiene già tutto, non serve recuperare nulla prima di `./avvia.sh`.

Il link pubblico **non** è legato alla conversazione: l'host inoltra sulla porta
12000, quindi l'indirizzo da aprire è quello della conversazione *corrente*
(`work-1-...`) e non quello di una sessione vecchia. Un link di una conversazione
chiusa risponde 404 anche se l'app era sana: significa solo che il sandbox non è
più attivo. Il rimedio è riavviare l'app in una sessione attiva, non ricostruirla.

**Bad Gateway (502) invece è il server dell'app spento**, non un problema di
rete: l'ambiente termina i processi in background anche durante una sessione,
non solo fra una e l'altra, e la porta inoltrata resta senza ascoltatore. Si
risolve con `./avvia.sh`, che riparte e aspetta che la pagina iniziale risponda.
Vale la pena ricontrollare `./avvia.sh status` prima di dare per rotto qualcosa:
una 502 non dice nulla sulla salute dell'app, dice che non c'e' nessuno in
ascolto.

**Non è successo che il processo muoia: viene ricreato il container.** È una
distinzione che cambia il rimedio. Se `cat /proc/uptime` mostra pochi secondi o
`ps -p 1` mostra un processo diverso da quello di prima, non è il server a essere
caduto: è tutto l'ambiente a essere nuovo, e allora anche `sorveglia.sh` è morto
con lui. In quel caso non serve indagare sul perché il server sia "morto" —
non è morto, non è mai stato avviato in questo container. `./avvia.sh` rimette
in piedi entrambi: è il primo comando da provare, sempre.

`sorveglia.sh` copre il caso diverso, quello in cui **solo il server** cade
mentre l'ambiente resta vivo: controlla la pagina ogni 15 secondi e riavvia se
non risponde, con `flock` per non duplicare un `avvia.sh` già in corso. Scrive sul
log solo quando interviene, così un log non vuoto è già un'informazione.

Non esiste in questa immagine un gancio di avvio automatico: niente `systemd`
(`systemctl` è presente ma `systemd` non è il PID 1), niente `cron` (`/etc/init.d/cron`
non esiste), e il processo 1 è l'agent-server di OpenHands, che non esegue script
del progetto. **Non perdere tempo a cercare dove agganciarsi**: non c'è, e la
ricreazione del container porterebbe comunque via qualsiasi cosa avviata qui.
La continuità vera (server che riparte da solo dopo un riavvio della macchina) si
ottiene solo su una macchina propria, con un servizio di sistema o
`docker run --restart unless-stopped`. Qui l'unica strategia sensata è:
all'inizio della conversazione `./avvia.sh`, poi `./sorveglia.sh`.

`cucina.db` non è versionato di proposito: a ogni ambiente nuovo va ricreato con
`seed.py` (ci pensa `avvia.sh`), e riparte l'onboarding. Non è una perdita.

## Configurazione

Tutto quello che si configura passa da variabili d'ambiente, lette **all'avvio**, non dal browser: la chiave del servizio vocale non deve mai arrivare al client.

| Variabile | A cosa serve | Valore assente |
| --- | --- | --- |
| `AZURE_SPEECH_KEY` | Chiave della risorsa Azure Speech | la voce neurale resta spenta, si usa quella del browser |
| `AZURE_SPEECH_REGION` | Area della risorsa (`westeurope`, …): determina l'indirizzo, non si può indovinare | come sopra |
| `AZURE_SPEECH_FORMAT` | Formato dell'audio richiesto | `audio-24khz-48kbitrate-mono-mp3` |
| `PORT` | Porta del server | 12000 |
| `CUCINA_DB` | Percorso del database della prima casa | `cucina.db` |

Le chiavi vanno messe prima di `./avvia.sh` e non finiscono mai nel repository: non c'è un file di configurazione da riempire, proprio per non rischiare di versionarlo.

In questo ambiente la chiave va registrata fra i **segreti della conversazione** (non scritta in un file): il sistema la esporta come variabile d'ambiente prima di ogni comando, quindi `./avvia.sh` la trova e il container la ritrova anche dopo essere stato ricreato. Il nome della variabile deve coincidere esattamente con `AZURE_SPEECH_KEY`, altrimenti il codice non la vede.

All'avvio `avvia.sh` dice se la voce neurale è attiva, e distingue il caso della variabile sola — l'errore più probabile — dal caso in cui non c'è nessuna configurazione. Un `giallo` "servono sia ... sia ..." significa che ne manca una.

### Voce neurale cloud

La voce del browser ha un tetto: dipende da quello che il sistema ha installato, quindi cambia — e peggiora — da un dispositivo all'altro. La voce neurale **non dipende dal dispositivo**: arriva da Azure, suona identica sul telefono e sul computer, ed è la differenza fra una voce che sembra una persona e un sintetizzatore.

```bash
AZURE_SPEECH_KEY="la-tua-chiave" AZURE_SPEECH_REGION="westeurope" ./avvia.sh
```

Con le due variabili presenti, il pannello vocale mostra il blocco **Voce neurale** e la conferma arriva da lì; le voci sono le ufficiali italiane (`it-IT-IsabellaNeural`, `it-IT-ElsaNeural`, `it-IT-DiegoNeural`…) incluse le più naturali **multilingua** e **HD**. Senza, resta la voce del sistema: **non c'è niente da configurare per continuare a usare l'app**.

Se la chiave c'è ma è errata, o l'area non è quella della risorsa, l'app **ripiega in silenzio** sulla voce del browser: un comando a voce resta riuscito anche quando la voce non riesce a parlare.

**La chiave resta sul server.** Il client chiede l'audio a `/api/voce/parla`, il server parla con Azure e restituisce solo l'MP3. È il motivo per cui la rotta non sta nel client: una chiave nel browser la legge chiunque apra gli strumenti di sviluppo, e da lì consuma il credito. Per lo stesso motivo le due rotte vocali **richiedono l'accesso** e senza password rispondono 401.

**Costo.** Azure fattura i caratteri sintetizzati. Le conferme sono brevi e ripetitive, e l'app ne tiene conto: le frasi **già sentite** non si richiedono di nuovo, c'è un **limite di 600 caratteri** per richiesta, e l'audio non viene salvato. Il piano gratuito di Azure Speech copre abbondantemente un uso domestico.

**Senza connessione** si sente la voce del sistema, senza messaggi d'errore: la neurale è la preferita, quella del browser è la rete di sicurezza. Su **iPhone** la primissima riproduzione può non partire perché iOS blocca l'audio finché l'utente non tocca la pagina: si sente la voce del sistema, e dal comando successivo funziona.

La sintesi è in `voce_cloud.py`, e i nomi delle voci sono un sottoinsieme verificato di quelli ufficiali Azure: un nome inventato verrebbe rifiutato con un 400, quindi la validazione avviene prima della chiamata, dove l'errore è leggibile e non costa nulla.

## Windows

L'app di casa va su una macchina sempre accesa, e per l'utente questa e' Windows.
`avvia.sh` e' POSIX (bash, `venv/bin/python`, `setsid`): su Windows **non parte**, e
adattarlo con mille condizioni lo renderebbe illeggibile per entrambe le
piattaforme. Percio' `windows/` e' una traduzione, non una variante: fa le stesse
cose con gli strumenti di Windows.

- `windows\avvia.bat` — prepara l'ambiente (una venv separata, `.venv-win`, cosi'
  non si confonde con quella POSIX), installa le dipendenze, avvia il server e
  mostra i due indirizzi.
- `windows\installa.bat` — registra un'**attivita' pianificata** che parte
  all'accesso e riavvia se cade.
- `windows\indirizzo.ps1` — trova l'indirizzo di rete.

Cose che sembrano dettagli e non lo sono:

- **L'avvio automatico e' un'attivita' pianificata, non un collegamento nella
  cartella di avvio.** Il collegamento fa partire l'app una volta; se poi cade,
  resta caduta. In un'app di casa la differenza e' che nessuno se ne accorge. Si
  e' scelto `-RestartCount 999 -RestartInterval 1 minuto`, che e' il sorvegliante
  che su Linux fa `sorveglia.sh`.
- **Il calcolo dell'indirizzo sta in un `.ps1`, non dentro il `.bat`.** In un file
  `.bat` virgolette e caratteri speciali hanno regole che si sbagliano facilmente, e
  un errore in un `for /f` non si vede: fallisce in silenzio. In un file `.ps1` quel
  codice si legge e si prova.
- **Non serve il permesso di amministratore.** L'attivita' e' dell'utente, parte al
  suo accesso. Chiedere privilegi per un'app di casa e' un ostacolo inutile.
- **`localhost` e' un indirizzo sicuro per il browser, un IP di rete no.** Sul
  computer il microfono funziona, dal telefono no: i browser pretendono una
  connessione sicura per ascoltare, e `localhost` e' considerato tale, mentre
  `192.168.x.x` no. Non e' una svista da correggere: e' il motivo per cui sul
  telefono l'app consulta e parla ma non detta, e per cui il microfono dal telefono
  richiederebbe un certificato (`waitress` non supporta HTTPS: servirebbe un proxy
  davanti).
- **Il firewall di Windows chiede il permesso la prima volta.** Se si risponde
  *Annulla*, il telefono non passa e sembra un problema dell'app: e' la prima cosa
  da controllare, ed e' scritto in `windows/LEGGIMI.md`.

## Copia dei dati

I database non sono in git (dati di casa, non codice), quindi **cambiare macchina
senza un export significa ripartire da zero**. Da qui `/api/backup`, che scarica
lo **stesso `cucina.db`/`case-*.db`** della casa collegata dentro uno ZIP con un
`LEGGIMI.txt`.

Tre vincoli, in ordine di importanza:

1. **Una casa sola.** Mai il registro (`houses.db`), che contiene nomi e password
   di tutte le case, e mai i database delle altre. Chi condivide una casa non deve
   poter scaricare i dati dell'altra: un export "di tutto" sarebbe la violazione
   piu' facile da scrivere e la piu' grave.
2. **Copia coerente.** Si usa `sqlite3.Connection.backup()`, non una lettura del
   file: copiare un database mentre e' in uso puo' dare un file corrotto, che e' il
   peggior esito possibile per un backup (sembra riuscito e non lo e'). Si esporta
   con `iterdump`, cosi' il file non porta con se' il diario di scrittura.
3. **Il percorso di ripristino sta dentro il file.** La casa storica ha il database
   accanto al codice, le altre in `case/`: il `LEGGIMI.txt` dice quello esatto,
   ricavato con `relpath` da `DATA_DIR`. Indicare la cartella sbagliata e' il modo
   piu' facile di credere di aver recuperato i dati senza averlo fatto.

Lato client il download e' un semplice `window.location.href`, non una `fetch`: il
browser deve trattarlo come file da scaricare, con il suo nome e la sua finestrella.

## Percorsi dei dati

`MAGGIORDOMO_DATA` sposta tutti i dati (registro, `case/` e database storico)
fuori dal progetto. Serve a tenere i dati fermi mentre il codice cambia, e a fare
un backup che li comprenda davvero.

L'insidia e' che i percorsi sono **tre** e sembrano indipendenti: `houses.db` e
`case/` in `houses.py`, il database storico in `app.py`. Dimenticarne uno dà
un'app che sembra funzionare ma perde una parte dei dati quando i dati stanno
altrove. Per questo `houses.db_path` cerca anche la casa storica in `DATA_DIR` e
non accanto al codice, e per questo c'e' un test che ricarica il modulo con la
variabile impostata e verifica tutti e tre.

## Server: sviluppo e produzione

Il ricaricatore di `FLASK_DEBUG` **non** va usato su una macchina sempre accesa:
tiene un processo supervisore che genera un figlio, quindi fermare "il server" ne
lascia vivo uno dei due, e un sorvegliante che riavvia trova la porta occupata da
un processo che credeva morto. In piu' riavvia il server a ogni tocco di file.
`app.avvia()` usa quindi `waitress` (multi-thread, senza ricaricatore) e ripiega
sul server di sviluppo senza ricaricatore se manca: l'app parte comunque.

`waitress` **non supporta HTTPS**: e' fatto per stare dietro a un proxy. Se un
giorno serve la voce dal telefono, davanti ci vuole qualcosa che termini TLS
(nginx, Caddy), non una modifica a questo codice.

Il log del server dice **quale** modalita' e' attiva (`Server (waitress) su ...`).
Vale la pena perche' il log finisce in un file e non in un terminale: senza
`flush=True` quell'annuncio resterebbe invisibile finche' il processo non muore,
cioe' proprio quando servirebbe leggerlo.

## Case separate

Ogni **casa** ha il suo database: ricette, dispensa, piano, spesa, pulizie, FAQ,
progetti e magazzino non si vedono fra case diverse. La separazione è un **file di
database distinto** (`case/case-<slug>.db`), non una colonna `house_id`: le tabelle
sono tredici e le query cinquanta, e una colonna dimenticata da qualche parte
mostrerebbe i dati di una casa a un'altra. `get_db()` (`app.py`) apre il file giusto
e tutte le query restano com'erano: **non aggiungere filtri per casa alle query**, la
separazione è già nel file.

Conseguenze pratiche per chi mette mano al codice:

- **Ogni rotta nuova richiede una sessione.** Il controllo sta in un unico
  `before_request` (`app.py`) con l'elenco `ROTTE_PUBBLICHE`; una rotta non elencata
  lì è protetta da sola. Aggiungendo una rotta pubblica, va aggiunta a quell'insieme
  — e deve essere una che non tocca dati di una casa.
- **`get_db()` può restituire `None`** se non c'è sessione. In pratica non succede
  mai dentro una rotta, perché `before_request` risponde 401 prima; ma un nuovo
  percorso chiamato fuori da una richiesta (uno script, un comando) non ha sessione
  e va fatto passare da un percorso esplicito, come fa `seed.semina()`.
- **Il seed di una casa nuova non passa dalle API**: una casa appena creata non ha
  sessione, quindi le API risponderebbero 401. `seed.semina(percorso)` scrive
  direttamente sul database, e `app.init_db(..., con_ricettario=True)` la chiama
  alla creazione.
- **Le password stanno in `houses.db`**, in PBKDF2-SHA256 con sale. `houses.db`
  contiene solo nomi e password: nessun dato di casa. Il file del database non si
  cancella insieme alla casa (mesi di ricette non devono sparire con un click
  sbagliato).
- **Il segreto delle sessioni è in `houses.db`** (`houses.secret_key()`), non in una
  variabile generata all'avvio: altrimenti ogni riavvio del server scollegherebbe
  tutti, e i riavvii qui sono frequenti.
- **La casa storica** (`slug` `casa`) è il `cucina.db` di prima: `houses.migra_case()`
  la registra al primo avvio e stampa la password una volta sola. Il registro tiene
  il percorso in `db_file`, vuoto per le case normali.
- **Nei test** il registro e la cartella delle case sono deviati su una cartella
  temporanea (`houses.REGISTRY_PATH`, `houses.CASE_DIR` in `test_cucina.py`), così i
  test non toccano il `houses.db` vero. La fixture `client` collega la casa di prova
  e la `anon` no: i test dell'accesso usano `anon`.

## Convenzioni

- `MEALS` in `app.py` è l'unica fonte dei pasti; il frontend li legge da `/api/meta`.
- I test usano un DB temporaneo via `CUCINA_DB`, impostato prima di importare `app`.
  Non toccano `cucina.db`.
- `cucina.db` non è versionato: per provare l'app va creato con `seed.py`.
- `seed.py` è idempotente e rimuove le ricette elencate in `REMOVED`.
- `ingredients` è un catalogo condiviso: le ricette lo popolano via `get_or_create_ingredient`, ma eliminare una ricetta non lo ripulisce (il `CASCADE` tocca `recipe_items`, non il catalogo). Ogni endpoint che rimuove un uso — ricetta, dispensa, voce di spesa — chiama `delete_orphan_ingredients`, che cancella solo gli id non referenziati da nessuna delle tre tabelle. Aggiungendo un nuovo percorso di rimozione, va chiamata anche lì.
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
  effettivo della voce, che l'utente può aver corretto a mano.
- La lista della spesa distingue le voci generate (`shopping_items.generated = 1`)
  da quelle scritte a mano (`0`). La generazione cancella e ricostruisce solo le
  prime: è una fotografia del piano, quindi una ricetta tolta dal piano porta via
  i suoi ingredienti, e rigenerare due volte non raddoppia le quantità. Se esiste
  già una voce manuale aperta per un ingrediente, la generazione la salta
  (`already_listed`) invece di duplicarla o fondersi: quella riga è dell'utente.
  Aggiungendo un nuovo percorso che crea voci dal piano, va marcato `generated`.
- La lista si ricostruisce **da sola**: `rebuild_shopping()` è chiamata da ogni
  endpoint che cambia il fabbisogno — piani, ricette e dispensa — non solo da
  `/api/shopping/generate`. Il pulsante "Vai alla spesa" nel piano è quindi solo
  una scorciatoia di navigazione: se un percorso nuovo modifica ingredienti,
  quantità o scorte e non la richiama, la lista resta indietro senza che l'utente
  abbia un modo per accorgersene. La dispensa è compresa perché quello che si
  compra e si mette via non deve restare anche in lista.
- Le ricette preferite stanno nella tabella `favorites`, non in una colonna di
  `recipes`: sono una scelta dell'utente e la FK con `ON DELETE CASCADE` evita
  preferenze orfane. In `PUT /api/profile` i campi si toccano solo se presenti
  (`favorite_ids`, `full_name`, …), così i salvataggi parziali non azzerano il resto.
- `migrate()` in `app.py` è l'unico posto dove aggiungere colonne: `CREATE TABLE IF
  NOT EXISTS` non tocca le tabelle esistenti, quindi ogni colonna nuova va aggiunta
  sia in `schema.sql` sia in `migrate()` (vedi `fav_prompted` e `chore_day`).
  Attenzione anche alle tabelle **nuove**: `_semina_pulizie` deve controllare
  `sqlite_master` prima di leggere `chores`, altrimenti la migrazione di un DB
  vecchio fallisce con "no such table: chores".
- **Progetti**: la priorità è 1–5 stelle e l'ordinamento è per priorità
  decrescente, con i conclusi in fondo. Spuntare "concluso" **non** richiede di
  rimandare titolo e date: `PUT /api/projects/<id>` tocca solo i campi presenti,
  altrimenti spuntare una casella cancellerebbe il resto della scheda.
- **Magazzino**: sta dentro Progetti, non in Cucina, perché non entra in nessuna
  ricetta e non si scala dal fabbisogno della spesa. È una tabella a parte
  (`storage`) e non un secondo elenco della dispensa: tenerli insieme
  costringerebbe la generazione della spesa a filtrarli via a ogni giro, e prima
  o poi un detergente finirebbe in una lista di ingredienti. Il test
  `test_magazzino_non_entra_nella_spesa` esiste per questo. `low` (in
  esaurimento) è calcolato dal server e non dal client, così il confronto fra
  giacenza e scorta minima resta in un posto solo.
- **Igiene**: il catalogo di partenza sta in `igiene.py` e viene seminato in
  `chores`, come le ricette. La cadenza (`giornaliera`, `settimanale`, `mensile`,
  `stagionale`) decide quando una voce rientra; le stagionali solo nel loro `month`
  e una volta l'anno. `piano()` in `igiene.py` è il cuore del metodo: **quotidiane
  e settimanali stanno nel piano di oggi, mensili e stagionali nel blocco del
  mese**. Se finissero tutte nel piano di oggi la giornata diventerebbe
  impraticabile e il piano verrebbe abbandonato: è il motivo per cui il test
  `test_piano_separa_oggi_dal_mese` esiste. `minuti_previsti` conta solo oggi,
  `mese_minuti` solo il mese: mescolarli darebbe una cifra falsa in entrambi i casi.
- Le scadenze delle pulizie **non si salvano**: si ricavano dall'ultima riga di
  `chore_log`, come i giorni della spesa dal piano. Una tabella di appoggio si
  disallineerebbe appena si registra un completamento. `scadenza()` restituisce
  anche `giorni`: **negativo se in ritardo**, 0 il giorno esatto, positivo se non
  ancora da fare.
- Una quotidiana fatta oggi ha `giorni == 1` (torna domani) e `in_scadenza == False`:
  è corretto, e non la toglie dal piano perché `piano()` include comunque le
  quotidiane. Nell'interfaccia `quandoDetto()` controlla `fatto_oggi` **prima** di
  `giorni`, altrimenti una voce appena spuntata direbbe "rifare fra 1 giorno", che
  sembra una spunta non registrata.
- `chore_day` in `profile` è il giorno fisso delle settimanali (0 = lunedì). È una
  scelta dell'utente e serve a dare costanza: nel giorno scelto le settimanali
  rientrano anche se non è ancora passata una settimana.
- Nel frontend il timer usa un **timestamp in `localStorage`** (`choreTimer`), non
  un contatore in memoria: il cronometro deve continuare se la pagina si ricarica o
  il telefono si blocca, che è esattamente ciò che succede mentre si pulisce. Il
  campo `fine` esiste solo per la regola dei 15 minuti, dove il tempo è un tetto e
  non una misura: in quel caso si registra il tempo **reale** usato, non i 15 minuti
  interi.
- Nel calendario annuale il mese corrente è evidenziato ma **chiuso**: le sue voci
  sono già elencate per intero nel blocco del mese qui sopra, e ripeterle due volte
  nella stessa schermata confonde invece di aiutare.
- I comandi vocali stanno in `voice.py` e non nel frontend: il browser si limita a
  dettare testo con la Web Speech API e a mandarlo a `POST /api/voice`, così la
  comprensione è testabile senza microfono. `parse()` riconosce gli intenti
  `pantry_add`, `shopping_add`, `storage_add`, `term_add`, `recipe_search` e
  restituisce `unknown` quando non capisce. Le unità si aggiungono in
  `_UNIT_TOKENS`, le parole di comando in `_COMMAND_VERBS`, le destinazioni in
  `_find_destination`. Una frase senza verbo, destinazione o quantità è rumore di
  fondo e deve restare `unknown`: il microfono sente anche i discorsi in cucina e
  le voci inventate in lista sono peggio di un comando non capito.
- **La dispensa non è il magazzino.** La dispensa si confronta con le ricette, il
  magazzino no: confonderli scrive un detergente in una lista di ingredienti, che è
  il motivo per cui `storage` è una tabella a parte. `_find_destination` decide in
  quest'ordine — la parola ("al magazzino", "alle scorte"), poi un luogo
  (`_LUOGO_TOKENS`: "in cantina", "in garage"), poi la parola dell'oggetto
  (`_MAGAZZINO_PAROLE`). L'ordine è una regola, non un dettaglio: una destinazione
  esplicita deve battere la parola dell'oggetto, altrimenti "il sapone in dispensa"
  finirebbe in magazzino. I verbi come "comprare" non spostano niente. Il luogo
  detto da solo vale solo se non c'è una destinazione: "in cucina" è anche il posto
  della dispensa e non basta da solo. Aggiungendo una destinazione nuova, va
  aggiunta qui e non nel ramo dell'esecuzione.
- La voce di conferma si sceglie in `TIMBRI` (`static/app.js`) per **caratteristiche**,
  non per nome: l'elenco `nomi` è una lista di preferenze, e `scegliVoce` prende la
  prima voce italiana che combacia, altrimenti la prima italiana, altrimenti quella
  predefinita. Non tornare a un nome fisso come `Alice`: su Linux e Android quella
  voce non esiste, e la conferma resterebbe muta. `aggiornaEtichetteVoci` mostra il
  nome reale accanto al timbro, così l'etichetta dice la verità su ogni piattaforma.
  `rate` e `pitch` restano vicini a 1: le voci di sistema sono sintetiche e
  allontanarsi dalla loro intonazione naturale le rende robotico, non espressivo.
  `parlaTesto` legge **una frase per volta** (`spezzaInFrasi`) e abbassa tono e
  velocità sull'ultima: è così che la sintesi chiude l'intonazione, ed è l'unica
  leva che abbiamo su voci che non controlliamo. Prima di cambiare i valori, provare
  ad ascoltare: un numero più "espressivo" di solito suona peggio.
- **La qualità della voce del browser non dipende dall'app.** `scegliVoce` preferisce le
  voci italiane **naturali** (`eVoceNaturale`, cioè con "natural"/"neural" nel nome),
  perché sono le uniche che suonano bene, e solo dopo ripiega sul timbro. Ma la
  scelta di quali voci esistano è del sistema operativo e del browser, non nostra:
  le voci naturali di Windows **non sono esposte a Chrome e Firefox**, solo a Edge.
  Quando un utente dice che la voce è pessima, la prima cosa da verificare è quali
  voci vede il suo browser — non riscrivere i valori di `rate`/`pitch`, che sono già
  al minimo intervento possibile. **La soluzione a questo limite è la voce neurale
  cloud** (`voce_cloud.py`), che non dipende da cosa ha installato il dispositivo:
  è la strada da percorrere quando la voce del browser non basta, non un ritocco ai
  timbri. `aggiornaElencoVoci` riempie la tendina "Voce di sistema" con tutte le voci
  italiane e `#voice-avviso` avvisa quando non ce n'è nessuna naturale.
- `voceScelta` (localStorage) è una voce precisa scelta a mano, indicata per
  **`voiceURI` e non per nome**: fra due voci diverse il nome può coincidere, il
  voiceURI no. Cambiare timbro la cancella, perché il timbro è una modalità
  automatica e senza questo non avrebbe effetto. Se la voce memorizzata non esiste
  più (altro browser, altro sistema) `voceEsplicita()` restituisce `null` e si
  ricade sul timbro: non si resta muti.
- L'assegnazione `u.voice = v` va sempre dentro un suo `try`. Una voce tenuta da
  parte può non essere più valida, e l'assegnazione solleva: senza la protezione
  se ne va in silenzio **tutto** il messaggio invece della sola voce. Meglio la voce
  predefinita che niente. Vale per `parlaTesto`, `anteprimaTimbro` e `anteprimaVoce`.
- Il container di questo ambiente **non ha alcun motore di sintesi installato**
  (`speechSynthesis.getVoices()` restituisce `[]`). Quindi la logica delle voci non
  è verificabile dal vivo qui: va provata simulando `speechSynthesis` con
  `Object.defineProperty` in uno script di init di Playwright. `getVoices` è di sola
  lettura e riassegnarlo direttamente non ha effetto — serve sostituire l'intero
  oggetto. Attenzione: con un oggetto JS semplice come voce Chromium **rifiuta**
  l'assegnazione e `u.voice` resta null; non è un difetto del codice, è l'artefatto
  dello stub. La verifica reale va fatta su una macchina con voci installate.
- **La voce neurale cloud non si può provare chiamando Azure nei test**: sarebbe una
  chiamata di rete che dipende da una chiave. Si prova tutto quello che sta intorno,
  che è la parte che sbaglia: costruzione dell'SSML, escape, limiti, validazione
  della voce, traduzione degli errori e stato delle rotte. Per il percorso client si
  sostituisce la `fetch` della sola rotta vocale in uno script di init, lasciando vere
  le altre: sostituendole tutte si rompe l'app e il test non misura più il fallback.
  Un accorgimento che vale per ogni intercettazione: **una richiesta ad Azure non
  deve mai comparire fra le chiamate del browser** — se compare, la chiave sta
  passando dal client, che è il difetto che tutto questo esiste per evitare. Nella
  prova il conteggio era 0, ed è la conferma che la chiave resta sul server.
- Il `<prosody>` va emesso **solo se serve**. `rate` è un moltiplicatore (1.0 neutro)
  mentre `pitch` è in percentuale (**0 è neutro**): confondere i due valori produce
  un `pitch="1%"`, che non è "quasi zero" ma un tono leggermente alterato che cambia
  la lettura. Questo è stato trovato da un test, non da un ascolto.
- I nomi delle voci in `voce_cloud.VOCI` sono un **sottoinsieme verificato** di quelli
  ufficiali Azure. Un nome inventato viene rifiutato con un 400: la validazione sta
  prima della chiamata, dove l'errore è leggibile e non costa una richiesta. Prima di
  aggiungerne uno, verificarlo sull'elenco ufficiale (`language-support?tabs=tts`),
  senza inventarlo per simmetria con le altre voci.
- La scelta della voce cloud è **per dispositivo** (`voceCloud` in localStorage), non
  per casa: sul telefono si può volere una voce diversa che sul computer. I dati sì,
  quelli sono della casa. È il motivo per cui la voce cloud, che suona identica
  ovunque, risolve il problema di un'app usata da più dispositivi.
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
- **FAQ**: le voci stanno nella tabella `faq` e si gestiscono dall'interfaccia,
  non in `seed.py` — sono informazioni dell'utente (la sua password, i suoi
  contatti), non un catalogo di partenza. Le **categorie** invece stanno in
  `faq.py`: sono la struttura della sezione, come gli ambienti per le pulizie.
  `categoria_valida()` fa ricadere una chiave ignota sulla predefinita invece di
  rifiutare la voce: un'etichetta sbagliata non deve far perdere un numero di
  telefono. L'ordine è **categoria → evidenza → titolo**: le voci in evidenza
  risalgono dentro la propria categoria, non in cima all'elenco, perché
  raggruppate per categoria saltare il gruppo le staccherebbe dalle voci affini.
  `secret` fa nascondere il valore finché non lo si apre, ma **non è una
  protezione**: il valore viaggia comunque in `/api/faq` e chi apre gli strumenti
  del browser lo vede. Serve a non tenere una password sullo schermo, e dirla
  chiara è l'unico modo perché non faccia abbassare la guardia; la nota nel form
  lo ripete all'utente. Il testo di `answer` può essere lungo (un indirizzo con
  citofono e scale), quindi nel form è un'area di testo e a schermo i ritorni a
  capo diventano `<br>`. I valori che **sono** un telefono o un'email diventano
  `tel:`/`mailto:` — solo se sono quello e non se lo contengono: un testo lungo
  con un numero dentro resta testo. La ricerca è lato client e guarda anche il
  nome della categoria, così non serve indovinare dove sta una voce.
- Nelle sezioni la barra mostra solo le schede dell'area aperta (`data-section`
  sulle schede, `SEZIONI` in `app.js` come mappa area → prima scheda): le voci delle
  aree non vanno mescolate in un'unica barra. Il pulsante vocale è una funzione
  della cucina e resta nascosto altrove.
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
- Il pulsante vocale è `position: fixed` in basso a destra, quindi `main` ha `padding-bottom` generoso: senza, il pulsante coprirebbe l'ultima voce delle liste. Lo `z-index` (40) è sotto i modali, così non galleggia sopra le finestre aperte. Il pulsante Home flottante (`.home-fab`) sta nello stesso punto ma a sinistra: se un domani si aggiunge un terzo pulsante, va tenuto conto che gli angoli bassi sono occupati.
- **Il pulsante vocale flottante è nascosto in home** (`tornaAlleSezioni` lo rimette `hidden`), perché lì non c'è una sezione da cui parlare. Al suo posto c'è `.home-mic`, dentro l'hero: chiama lo stesso `apriVoce()`. Il pannello `#voice` sta **fuori** da `#app`, quindi funziona anche a sezioni chiuse — ma i comandi che ricaricano una scheda chiamano `apreSezioneDella()`, che apre prima l'area giusta. Senza, la scheda si attiverebbe sotto un'intestazione che non le appartiene.
- `.voice-box` ha `max-height: 100%; overflow-y: auto`: su schermi bassi (telefono piccolo, tastiera aperta) scorre dentro di sé invece di spingere la ✕ fuori dallo schermo. Senza, il pannello diventa impossibile da chiudere.

## Stile

Direzione: mare. Fondo schiuma, inchiostro blu profondo, un solo accento acqua. Tutto in Helvetica (`--font-display` e `--font-ui` puntano allo stesso stack).

- **Niente `@font-face`**: Helvetica Neue (macOS/iOS), Arial (Windows) e Liberation Sans (Linux) sono già nei sistemi. Il font non si scarica, la pagina si compone alla prima visita e non c'è niente da mantenere in `static/fonts/`. La cartella è stata rimossa: se un domani serve un font che i sistemi non hanno, va rimessa e vanno ripristinati i `@font-face`.
- Lo stack è `'Helvetica Neue', Helvetica, Arial, 'Liberation Sans', sans-serif`. `sans-serif` in fondo non è decorativo: è la rete di sicurezza per i sistemi senza nessuna delle tre.
- I colori stanno tutti in `:root`. Cambiare palette significa toccare solo quelle variabili.
- `--font-display` e `--font-ui` sono uguali, ma restano due variabili: distinguono titoli e interfaccia, quindi un domani si possono separare senza toccare le regole.
- **Il peso va scelto per Helvetica, non per un serif**: a parità di `font-weight`, un sans sembra più leggero. I titoli sono a `700` e con `letter-spacing` negativo, altrimenti in Helvetica si sfaldano. Non esistono più i `font-variation-settings: 'opsz'`, che erano della variabile Fraunces: con un font statico non fanno nulla.
- `--sand` è l'unico accento caldo (stelle delle preferite e priorità dei progetti). Scurito a `#b0761c` perché il tono più chiaro scendeva a 2.88:1 sul fondo carta, sotto il minimo di 3:1 per gli elementi grafici.
- Ogni combinazione testo/fondo deve restare sopra 4.5:1 (WCAG AA). Il grigio `--muted` è scelto per passare anche sui fondi colorati come `--accent-soft`, dove un grigio più chiaro scenderebbe a 4.37.
- Le cifre delle quantità usano `tabular-nums`.

Test di verifica senza browser grafico: Chromium headless è già presente.

```bash
chromium --headless=new --no-sandbox --window-size=390,844 --screenshot=/tmp/prova.png http://localhost:12000/
```

Playwright **non** è in `requirements.txt` e va installato a parte (`./.venv/bin/pip install playwright`; Chromium c'è già, si punta con `executable_path="/usr/bin/chromium"`). Serve a controllare overflow orizzontale, aree toccabili e contrasto su viewport diversi — è utile proprio quando si tocca il CSS della home, dove un pulsante con testo può andare a capo o allargare la pagina su schermo stretto.

Attenzione quando si controlla una pagina con l'estrattore di testo: comprime gli
spazi e incolla tra loro elementi adiacenti (`IgienePulizie di casa`). Un blocco
popolato può sembrare vuoto, e `<details>` chiusi non mostrano il contenuto — che è
esattamente il comportamento voluto, non un errore. Prima di concludere che qualcosa
non è renderizzato, conviene guardare gli elementi interattivi (`browser_get_state`)
o i dati delle API: se i dati ci sono e i nodi ci sono, il problema è nell'estrattore.
