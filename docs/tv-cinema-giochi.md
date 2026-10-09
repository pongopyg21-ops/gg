# TV, Cinema e Giochi

## La sezione TV: video, notizie, quiz, arte e giochi

`tv.py` tiene insieme cose che non sono dati dell'app — la playlist YouTube
della casa, le notizie dal mondo (ANSA), il quiz (Open Trivia DB) con un
suggerimento di cosa fare (Bored API) e le opere d'arte del Metropolitan Museum
— perché vivono nella stessa sezione e hanno lo stesso problema: **la rete**. Un
feed si sposta, un sito cambia, e la casa può restare senza connessione. La
regola è una e vale per tutte: quello che si è già scaricato **resta**, e un
guasto di rete non deve svuotare la sezione. Si mostra l'ultima copia buona e si
riprova più tardi.

Nessuna dipendenza nuova: `urllib.request` per scaricare, `ElementTree` per i
due formati dei feed (Atom per la playlist, RSS per le notizie) e `json` per il
resto (quiz, suggerimento, opere). Sono formati semplici, e una libreria in più
sarebbe una cosa da aggiornare per leggere cinque campi.

**Il quiz è tradotto in italiano sul server.** Open Trivia DB **non ha contenuti
in italiano** (ignora `lang=it` e risponde comunque in inglese), quindi le
domande si traducono con un servizio pubblico senza chiave (MyMemory,
`TRADUZIONE_URL`, sostituibile con `TV_TRADUZIONE`, e spegnibile con un valore
vuoto). La traduzione è un di più: se non riesce, le domande restano in inglese e
la sezione funziona lo stesso — `_traduci` non solleva mai, ritorna vuoto e chi
chiama tiene l'originale.

Tre trappole, tutte già pagate:

- **La traduzione è per domanda, non per l'intero elenco.** Il servizio tronca i
  testi lunghi: un blocco unico perderebbe le domande in fondo, e quelle
  resterebbero in inglese senza un motivo visibile.
- **Le righe devono restare allineate.** Si manda un blocco di righe (domanda,
  poi le risposte, poi la categoria) e il servizio conserva i ritorni a capo.
  `_traduci_domande` controlla comunque che il numero di righe torni: se il
  servizio le accorpasse, allineare per posizione metterebbe la «giusta» su una
  risposta sbagliata, quindi in quel caso si tiene l'inglese. Meglio una domanda
  in inglese che una risposta falsa.
- **La difficoltà non si traduce.** È una parola sola (`easy`/`medium`/`hard`) e
  si mappa con `DIFFICOLTA_IT`: non costa una richiesta e non dipende dal
  servizio.

Open Trivia DB mette la risposta giusta in un campo a parte e le risposte
arrivano **mescolate** (`_mescola_risposte`): senza, quella giusta sarebbe
sempre la prima e il quiz si indovinerebbe senza sapere. Il testo passa da
`html.unescape`, perché Open Trivia DB manda `&quot;` e `&#039;`. Il quiz si
risponde **toccando** la risposta (verde/rossa). Il quiz si
rinnova ogni `ORE_EXTRA` (6 ore), più spesso delle notizie, perché è un
contenuto leggero; sta nella cache **della casa** (`tv_cache`, chiave `quiz`),
come video e notizie.

**Indovinando, la domanda esce e ne arriva una nuova** (`tv.rispondi`, `POST
/api/quiz/rispondi`). È la richiesta dell'utente: senza, le stesse dieci domande
si rivedevano a ogni giro e il gioco stufava. La domanda indovinata si **toglie**
dalla copia (non si rivede) e se ne accoda una **nuova**, scaricata al volo dal
servizio, così il quiz resta lungo uguale. Tre scelte:

- **La nuova domanda si scarica al momento, non da una riserva.** Una coda di
  riserva sarebbe un secondo elenco da tenere fresco; una domanda in più è un di
  più, e `_domanda_nuova` cattura `NonDisponibile` ritornando `[]`.
- **Senza rete la domanda indovinata esce lo stesso.** Ripetere una domanda a cui
  si è appena risposto è peggio di averne una in meno: la copia perde una voce,
  non si blocca.
- **Rispondendo male il quiz non cambia.** Il client chiama la rotta **solo**
  quando si indovina (`if (!giusta) return;` prima della chiamata): altrimenti la
  risposta giusta non si potrebbe mai leggere. Un test fissa l'ordine.

La scrittura è sulla cache (contenuto scaricato, non un dato dell'utente), quindi
non c'è nulla da sincronizzare: il quiz è **della casa**, come la cache, e resta
uguale su tutti i dispositivi.

**Open Trivia DB limita a una richiesta ogni cinque secondi per indirizzo.**
All'avvio il giro su tutte le case aspetta fra una casa e l'altra
(`_giro_su_tutte_le_case(..., ritardo=True)`): senza, il quiz arriverebbe solo
alla prima casa e le altre resterebbero vuote fino al giro dopo, con l'aria che
il quiz non funzioni.

### Il suggerimento di cosa fare (Bored API)

Sotto le domande, un'idea di cosa fare quando ci si annoia, dalla **Bored API**
(`bored-api.appbrewery.com`, pubblica e senza chiave). Sta nella cache della
casa (`tv_cache`, chiave `suggerimento`), si rinnova ogni `ORE_BORED` (1 ora) e
si mostra tradotto (stessa traduzione delle domande: se non riesce, resta in
inglese). Il riquadro `#tv-suggerimento` **resta nascosto** se non c'è niente,
come i riquadri della home.

La scelta che conta: **si chiede `/filter?type=` e non `/random`.** `/random`
non accetta un filtro per tipo e restituisce spesso un tipo che non si vuole
mostrare (busywork, education, charity…): con `/random` metà dei tentativi
andrebbe buttata e il riquadro resterebbe vuoto anche quando la fonte risponde.
`/filter` restituisce solo il tipo chiesto (`BORED_TIPI` = recreational, social,
music), quindi ogni risposta è buona; si sceglie una voce a caso fra quelle. Se
un tipo non risponde si passa al successivo, e se nessuno risponde la copia
vecchia resta (`NonDisponibile`).

I campi numerici (`participants`, `price`) si convertono con `_intero`/
`_decimale`: un valore non numerico non deve sollevare, perché l'aggiornamento
gira anche in un filo di sottofondo dove un'eccezione non la vedrebbe nessuno.
La risposta esatta del quiz rinnova **anche** il suggerimento
(`POST /api/quiz/rispondi`), così si aggiorna giocando.

### Le opere d'arte del Metropolitan (Met Museum)

Nella scheda **Intrattenimento**, accanto ai video di casa, una striscia di
dipinti della collezione pubblica del **Metropolitan Museum**
(`collectionapi.metmuseum.org`, pubblico e senza chiave). Sono una pausa di
gusto fra un video e l'altro, non un catalogo: si scorrono in orizzontale, e il
riquadro resta nascosto se non c'è niente. Cache `tv_cache` chiave `arte`,
rinnovata ogni `ORE_ARTE` (24 ore).

**La trappola è il cambio di versione: la ricerca è su `v1.1`, il dettaglio su
`v1`.** Il 2026-10-01 il museo ha ritirato `/v1/search` (risponde 410 con
l'indicazione di usare `/v1.1/search`, paginata con `offset`/`limit`), ma il
dettaglio dell'opera è rimasto su `/v1/objects/{id}`: sono due versioni diverse
dello stesso servizio, e usarne una sola per tutto non funziona. Un test lo
fissa (`test_la_ricerca_del_met_usa_v1_1_e_il_dipartimento`).

Si tengono solo le opere di **pubblico dominio con una foto**: un'immagine
ancora coperta da diritto d'autore non si ridistribuisce, e un'opera senza foto
in una striscia di immagini non si può mostrare. Si scartano in silenzio, e se
nessuna è mostrabile si solleva `NonDisponibile` (la copia vecchia resta).

`departmentId=11` è il dipartimento **European Paintings**: senza, `q=painting`
pesca anche un manuale a stampa e le pitture murali di Pompei — bei pezzi, ma un
libro in una striscia di quadri non c'entra. Il dettaglio si chiede solo finché
non si sono riempite le opere tenute (`MET_QUANTE`), con un tetto ai dettagli
(`MET_MAX_DETTAGLI`): la ricerca elenca centinaia di id, e chiederli tutti
sarebbe centinaia di richieste per mostrarne dodici.

**Le opere si scelgono a caso, e il tetto ai dettagli è più largo di quelle
tenute.** Il gruppo si pesca a caso fra i candidati (`_gruppo`, `random.shuffle`),
e `MET_MAX_DETTAGLI` (60) è più largo di `MET_QUANTE` (12): è quello che rende
possibile il pulsante **«Altre opere»** (`altre_arte`, `POST /api/tv/arte/altre`).
Il pulsante passa gli id già mostrati come `escludi` e genera un gruppo **nuovo**,
che **sostituisce** la copia: ricaricando la pagina si rivedono le stesse opere,
non quelle di prima. Non passa da `_aggiorna` (che salta lo scaricamento se la
copia è fresca): qui l'utente ha *chiesto* opere nuove, quindi si scarica subito.
Se il filtro svuota i candidati si ripiega su tutti (meglio ripetere un'opera che
non darne nessuna), e se il Met non risponde la copia vecchia **resta** con
`nuove: false`: un giro a vuoto non svuota il riquadro e non sembra riuscito.

**L'ingrandimento è dentro l'app.** Ogni opera porta anche la foto **originale**
(`primaryImage`, `foto_grande`), oltre alla `web-large` (~600 px) della striscia:
toccando un dipinto si apre `#tv-arte-grande`, una finestra a schermo intero
**dentro** l'app (✕, tocco sullo sfondo o Esc per chiudere), non una scheda nuova
— così non si perde il posto. L'originale pesa qualche MB e si carica **solo al
clic**: scaricarlo per dodici schede da 190 px sarebbe sprecato. La finestra
chiude staccando `img.src`, altrimenti l'originale resta in memoria.

Il retry di `renderTv` guarda **anche** le opere (`d.arte`), non solo video e
notizie: una casa nuova le riceve in sottofondo come i video, e senza guardarle
il riquadro resterebbe vuoto finché non si riapre la sezione.

**La CSP deve permettere `https://images.metmuseum.org` in `img-src`**, come già
fa per TMDB: senza, il browser blocca le foto in silenzio e la striscia resta
vuota. C'è un test che lo verifica.

**Le barzellette (JokeAPI) sono state tolte** su richiesta dell'utente: JokeAPI
non ha contenuti in italiano e le battute in inglese non avevano senso in una
sezione italiana. Restano nella storia (`git log`) se un giorno servissero, ma
non nel codice.

Le notizie sono **max venti**, dalle sezioni ANSA, mescolate fra loro, e si
rinnovano **una volta al giorno**; i video una volta al giorno anche loro. Si
mostra titolo, sommario breve e rimando alla fonte, non l'articolo: il testo è di
chi lo scrive.

Gli **argomenti** delle notizie si scelgono dal Profilo (e dall'onboarding) e
stanno in `profile.news_topics`, come testo separato da virgole. `feed_urls(db)`
li legge e restringe i feed alle sezioni scelte: nessun argomento vuol dire
**tutti**, così chi non ha ancora scelto non si trova una sezione vuota.
`argomenti_scelti()` tiene solo le chiavi note (`FEED_PER_TEMA`), perché un refuso
non deve svuotare l'elenco. Le etichette stanno in `ARGOMENTI` e si servono da
`/api/meta`. Cambiare argomenti **azzera la copia** delle notizie in `tv_cache`:
la copia vecchia è di altri argomenti, e tenerla mostrerebbe la scelta precedente
fino al giro dopo.

Le scelte che contano:

- **La copia sta nel database della casa** (`tv_cache`, tre righe: `video`,
  `notizie` e `gym`), non in memoria: un riavvio del server non deve costringere a
  riscaricare, e soprattutto la sezione non deve restare vuota se in quel
  momento la rete non c'è. È la stessa idea delle copie automatiche.
- **`GET /api/tv` non aspetta la rete.** Serve la cache e, se è vecchia, riprova
  in un filo **dopo** aver risposto. Una pagina che aspetta il feed di un sito
  altrui si pianta quando quel sito è lento, ed è proprio il momento in cui
  l'utente pensa che l'app sia rotta. Il pulsante **Aggiorna** (`POST
  /api/tv/aggiorna`) invece aspetta, perché è l'utente a chiederlo, e riporta
  l'esito: un aggiornamento che non ha portato niente di nuovo non deve sembrare
  riuscito.
- **Lo scaricamento fallito non svuota la cache.** `_aggiorna` cattura
  `NonDisponibile` e lascia la copia vecchia: è l'unica cosa che non si deve
  perdere, perché è quella che fa funzionare la sezione senza rete. Una playlist
  senza voci (privata, cancellata) è `NonDisponibile`, non una lista vuota, per
  lo stesso motivo.
- **Un lucchetto per chiave** (`_lucchetto`): il giro di avvio, la richiesta
  della pagina e il pulsante possono chiedere lo stesso scaricamento insieme, e
  senza questo partirebbero due volte per la stessa cosa.
- **All'avvio si aggiornano tutte le case** (`avvia_tv`, come
  `avvia_copie_automatiche`), non solo quella che si sta guardando: la sezione
  deve essere pronta quando si entra.
- **Il player è `youtube-nocookie`**: la pagina della casa non deve consegnare a
  YouTube i cookie di chi la apre per il solo fatto di mostrare un video. Gli
  iframe sono `loading="lazy"`: quindici player caricati insieme sono quindici
  volte il lavoro di uno.
- **La fonte si legge dal nome, non dal titolo del feed.** Il titolo di un feed
  è per un lettore di feed — "RSS di Mondo  - ANSA.it" — e accanto a una notizia
  ci vuole "ANSA.it": `_nome_fonte` prende l'ultimo pezzo dopo il trattino.
- **Il namespace si passa a `find`.** Nel feed Atom di YouTube l'id è `yt:videoId`:
  senza la mappa dei namespace `find` cerca il tag letterale, non trova niente, e
  la playlist sembra senza video. È un difetto che non si vede leggendo il codice
  e che è già costato un giro: per questo c'è un test sui campi, non solo sul
  numero di voci.

- **Le notizie vengono dalle sezioni ANSA.** `FEED_PREDEFINITI` raccoglie mondo,
  cronaca, politica ed economia: il solo «mondo» lascia fuori quello che succede
  in Italia, che è la prima cosa che si guarda. Sono argomenti, non fonti diverse.
  RaiNews è stato **tolto** dalle testate: era l'unica seconda testata, e il suo
  feed generalista non si vuole più in elenco (vedi
  `test_i_feed_predefiniti_non_includono_rainews`).
- **Un feed generalista non occupa tutto l'elenco.** Un feed che pubblica decine
  di voci senza un tetto per feed (`MAX_PER_FEED`) riempirebbe da solo le notizie
  e le altre sezioni sparirebbero. Le fonti si mescolano, non si sostituiscono.
- **Le testate si alternano e si tagliano per testata.** Il solo ordinamento per
  data non basta: una testata con più sezioni (ANSA ne ha quattro) porta voci
  recenti più numerose e occuperebbe tutto l'elenco. Due rimedi:
  `_mescola_per_fonte` prende a turno la più recente di ogni testata, e la fetta
  per testata è **proporzionale al numero di testate** (`MAX_NOTIZIE // n`), così
  con una sola fonte non si taglia niente e con due si fa metà per uno. Dentro
  ogni testata l'ordine resta per data.
- **I quasi-doppioni si riconoscono dal titolo.** Lo stesso fatto esce in più
  sezioni con lo stesso link (deduplica sul link) ma anche con titoli che
  differiscono per un apostrofo o una virgola e con link diversi: `_chiave_titolo`
  riduce il titolo a lettere minuscole e spazi, senza punteggiatura, e il
  doppione non occupa il posto di un'altra notizia.
- **Una sezione ferma non svuota le altre.** `notizie_dal_feed` legge ogni feed
  per conto suo e salta quelli che non rispondono; solo se **nessuno** risponde
  solleva `NonDisponibile`, così la cache buona non viene sovrascritta con il
  vuoto.

Il feed e la playlist si possono sostituire dall'ambiente (`TV_FEED`,
`TV_PLAYLIST`) senza toccare il modulo, come le chiavi dei servizi. `TV_FEED`
accetta **più indirizzi** separati da virgola o a capo (con un tetto `MAX_FEED`),
così una casa sceglie le proprie sezioni. I predefiniti sono la playlist
**GIAGIA-Max** (`https://www.youtube.com/playlist?list=PLQKkPe_OTLJygIqIViE5cqnWjxM1Cou0R`,
il feed Atom vuole il solo `list=...`) e le notizie dalle sezioni ANSA **mondo,
cronaca, politica, economia**. I test non toccano la rete:
sostituiscono `tv._apri` con risposte preparate e provano l'interpretazione e la
tenuta della cache, che sono le parti che sbagliano.

### La playlist è della casa, non del modulo

La playlist è una **preferenza dell'utente**, quindi sta nel database della casa
(`tv_prefs`, riga singola) e non in una costante né in `localStorage`: due case
sullo stesso server non devono vedersi i video l'una dell'altra, e la scelta è
della casa, non del dispositivo da cui la si guarda. Alla variabile d'ambiente
`TV_PLAYLIST` resta il ruolo di **predefinita** per chi non ha ancora scelto,
così un'installazione esistente continua a funzionare senza toccare niente.

L'ordine con cui `playlist_id(db)` risolve la playlist è: scelta della casa,
poi `TV_PLAYLIST`, poi `PLAYLIST_PREDEFINITA`. La casa viene prima dell'ambiente
perché è la volontà dell'utente; l'ambiente è il punto di partenza.

La playlist si chiede **alla creazione della casa** (campo `playlist`, facoltativo
in `POST /api/houses`) e si può cambiare dopo con `PUT /api/tv/playlist`, dalla
sezione TV. In entrambi i casi l'id si **valida prima di salvarlo**: si accetta
l'indirizzo incollato dalla barra del browser (`normalizza_playlist` ne estrae
il `list=`) o l'id nudo, e un video o un canale vengono rifiutati con un errore
chiaro. Alla creazione la validazione viene **prima** di registrare la casa, così
una playlist storta non lascia una casa a metà; al cambio, prima di salvare, così
non si resta con una sezione vuota che non si capisce da dove venga.

Cambiare playlist **azzera la copia dei video** (`DELETE FROM tv_cache`): i video
di prima sono di un'altra playlist, e `aggiorna` li salterebbe perché la copia è
ancora fresca. Poi `aggiorna_video(db, forse=False)` scarica subito, come il
pulsante «Aggiorna»: è l'utente che l'ha chiesto.

I test dell'endpoint usano `_niente_rete(monkeypatch)`, che spegne sia `tv._apri`
sia `_aggiorna_tv_in_sottofondo`. Il filo di sottofondo di `/api/tv` sopravvive
alla richiesta e, quando `monkeypatch` ha già rimesso a posto `_apri`, scarica
davvero tenendo aperto il database di prova: la fixture lo cancella sotto e il
test dopo fallisce con «disk I/O error». È un difetto del test, non dell'app.

### Le schede della sezione TV

La TV è una sezione con **cinque sotto-schede** — Intrattenimento (video di
casa), Notizie, Quiz, Film, Giochi — sulla stessa forma delle schede dell'Igiene:
`.ch-nav` con `data-tvp` / `data-tvp-panel`, un pannello solo aperto
(`mostraTvPanel` in `app.js`). Prima erano in un'unica colonna, e per arrivare ai
film si scorreva oltre quindici video: separarle è la stessa scelta fatta per
l'Igiene.

Due cose che sembrano dettagli e non lo sono:

- **Le schede non riscaricano.** I dati li riempie già `renderTv`/`renderCinema`
  aprendo l'area (una richiesta per fonte, come prima); cambiare sotto-scheda
  mostra e nasconde, non richiama il server. `mostraTvPanel` non e' un
  `renderTv`.
- **I selettori dell'Igiene vanno scopati per sezione.** `mostraChPanel` e il
  suo gestore usano `#tab-igiene .ch-nav-btn` e `#tab-igiene [data-chp-panel]`:
  con due `.ch-nav` nel documento, un selettore globale farebbe spegnere la
  scheda sbagliata (o accendere due pannelli). Le classi sono condivise apposta
  — la forma è la stessa — ma la ricerca è per contenitore.

Il **gioco** (Giochi) non è più una voce della barra in basso: è una sotto-scheda
della TV. Siccome non c'è più un clic sulla barra da ascoltare, `snake.js` si
aggancia **osservando le classi** (`MutationObserver`) del proprio pannello e
della sezione TV, con una regola sola (`snakeSincronizza`, idempotente): gli
inneschi sono più d'uno — l'osservatore, il pulsante Home, `visibilitychange` — e
una funzione unica evita che divergano. Un test verifica che `app.js` **non**
nomini le funzioni del gioco (vedi «I Giochi: Snake e Memory»).

### I Giochi: Snake e Memory

I **Giochi** sono una sotto-scheda della TV (`data-tvp="giochi"`, pannello
`data-tvp-panel="giochi"`). Ci sono **due** giochi, scelti da una riga di
pulsanti (`data-gioco="snake"`/`"memory"`, pannelli `data-gioco-panel`):
**Snake** in `static/snake.js` e **Memory** in `static/memory.js`, file a parte,
non dentro `app.js`, perché sono pezzi a sé che si caricano con la pagina ma
vivono di vita propria. Non usano librerie e non usano la rete: funzionano
**anche senza connessione**, come il resto della sezione (stanno nella scocca
del service worker).

La scelta che conta: **la logica è pura e separata dal disegno**. `snakeNuovo`,
`snakePasso` e `snakeDirezione` (Snake) e `memoryNuovo`, `memoryGira`,
`memoryNascondi`, `memoryAspetta` (Memory) prendono lo stato e ne restituiscono
uno nuovo, senza DOM e senza attese, e il mescolamento riceve un `rand`
iniettato. Così si eseguono **davvero** con node nei test — che è l'unico modo di
verificare un gioco senza giocarlo — e disegno e comandi restano l'unica parte
che non si può provare con un test unitario.

Il **Memory** (otto coppie, `MEMORY_COPPIE`) ha una regola in più che nella
logica di Snake non c'è: due carte girate vanno **tenute scoperte** finché
l'utente le vede, poi ricoperte se sbagliate. La decisione (uguali o diverse) sta
nella funzione pura `memoryGira`; il **quando** ricoprirle è un fatto di tempo,
non di regola, quindi è `memoryNascondi` chiamata dall'interfaccia dopo
`MEMORY_NASCONDI_MS`. Nel frattempo `memoryGira` **ignora una terza carta**: se
non lo facesse si scoprirebbero tre carte e il Memory perderebbe il senso. Alla
seconda carta uguale le due diventano `trovata` e la partita finisce quando
**tutte** lo sono. Il record è il **minor** numero di mosse con cui si vince
(`memoryRecord`, `localStorage`) — è un dato del dispositivo, come per Snake.

Tre trappole, tutte nel cuore del gioco:

- **La coda in movimento non è un muro.** Le collisioni si controllano **dopo**
  aver mosso la testa, e sul corpo senza l'ultimo tratto quando non si mangia:
  la cella che la coda sta lasciando libera si può occupare. Senza, il serpente
  morirebbe inseguendo la propria coda, che è un movimento normale.
- **Il contrario si ignora, non si applica.** Premendo «indietro» la testa
  entrerebbe nel collo e morirebbe: `snakeDirezione` tiene la direzione attuale
  se la richiesta è quella opposta.
- **Il ciclo parte solo a scheda aperta e si ferma uscendo.** Un
  `requestAnimationFrame` sempre acceso consuma batteria per un gioco che nessuno
  guarda: si accende aprendo la scheda «Giochi» e si spegne uscendo dall'area
  (home) o quando la pagina va in secondo piano (`visibilitychange`, che mette in
  pausa **senza azzerare** la partita).

**Il gioco si aggancia da solo: `app.js` non lo chiama.** Non è un vezzo — un
test scandisce `app.js` e pretende che ogni funzione chiamata esista **in quel
file**, e le funzioni del gioco vivono in `snake.js`: nominandole di là il test
le vedrebbe come orfane, che è il difetto vero (`ReferenceError` all'accesso) che
quel test esiste per cogliere. Quindi `snake.js` osserva da sé le classi del
proprio pannello (e della sezione TV) con un `MutationObserver`, e decide con una
regola sola (`snakeSincronizza`). C'è un test che verifica che `app.js` **non**
nomini le funzioni del gioco.

I due file sono script classici e **condividono lo scope**: `snake.js` può
chiamare `suonoAttivo`, definita in `app.js`, perché quando il gioco gira l'altro
file è già caricato. Il test delle funzioni orfane controlla l'**unione** dei
due file, non `snake.js` da solo.

Comandi: frecce/WASD sul computer, swipe o croce direzionale sul telefono (ogni
bersaglio 42px, come il resto dell'app). L'audio usa la preferenza «suono» già
esistente (`suonoAttivo`) e crea l'`AudioContext` al primo bip — cioè dopo un
tocco — perché un contesto creato senza gesto nasce sospeso. Il record sta in
`localStorage` (`snakeRecord`): è una preferenza del dispositivo, come tema e
voce, non un dato della casa.

### La sezione GYM

Il **GYM** è una sezione a sé (`tab-gym`, scheda in home `data-section="gym"`):
la playlist degli esercizi, incorporata come i video della TV. Non è una scheda
della TV perché è una cosa diversa — si guarda **per fare**, non per passare il
tempo — e perché così cambiare i video di casa non tocca l'allenamento.

Riusa la stessa lettura e la stessa cache della TV, con due soli pezzi nuovi:

- **`_video_di(playlist)`** è il pezzo comune: `video_playlist` (TV) e
  `video_gym` (GYM) sono lo stesso codice con un id diverso. Il messaggio di
  `NonDisponibile` dice l'id, così un feed storto si riconosce dal log.
- **Cache separata** (`tv_cache` chiave `gym`, distinta da `video`): aggiornare
  il GYM non deve toccare la TV, né viceversa. `aggiorna`/`quando_aggiornate`
  includono la chiave `gym`; `_aggiorna_tv_in_sottofondo` la controlla insieme
  alle altre.
- **La playlist GYM è indipendente** da quella della TV: `gym_playlist_id(db)`
  risolve scelta della casa → `GYM_PLAYLIST` → `PLAYLIST_GYM_PREDEFINITA`. La
  scelta della casa sta in una **colonna sua** (`tv_prefs.gym_playlist`, distinta
  da `playlist`), quindi cambiare la TV non tocca l'allenamento né viceversa. Si
  cambia dalla sezione (`PUT /api/gym/playlist`, campo `#gym-playlist`), con la
  stessa regola della TV: id validato prima di salvarlo, cache `gym` azzerata.
  La predefinita è **Ginniko Style**
  (`https://www.youtube.com/playlist?list=PLQKkPe_OTLJzyy8sW19hxUvVgnk1GuYFo`).
- **`GET /api/gym`** serve la cache e riprova in sottofondo, come `/api/tv`;
  **`POST /api/gym/aggiorna`** è il pulsante «Aggiorna» e aspetta la rete. Le
  notizie non c'entrano con gli esercizi: l'aggiornamento del GYM non le tocca.

### Il Cinema, dentro la sezione TV

Il **Cinema** non è più una sezione a sé: è **dentro la TV** (`tab-intrattenimento`),
perché è intrattenimento come i video e le notizie. Aprendo la scheda TV
`renderTv()` e `renderCinema()` partono insieme, con due richieste separate:
le fonti sono diverse (playlist/notizie e TMDB) e un guasto di una non deve
fermare l'altra. Restano la riga di stato e il pulsante «Aggiorna» del Cinema,
perché la fonte si aggiorna a parte. Non c'è più la scheda in home
`data-section="cinema"`, né il tab, né la voce in `SEZIONI`: una scheda in più
per la stessa cosa era un doppione. Il **GYM** invece resta una sezione a sé
(`tab-gym`), perché è una cosa diversa — si guarda *per fare*, non per passare
il tempo.

Le locandine sono i film del momento compresi sulle piattaforme di streaming,
**una alla volta**, da sfogliare da destra a sinistra. Serve a ispirare la
serata, non a elencare un catalogo: per questo il carosello mostra un film per
schermata, con la locandina grande, e non una griglia.

`cinema.py` è il modulo, e ricalca `tv.py` di proposito — stessa cache, stesso
lucchetto, stessa regola «quello che si è scaricato resta». Le differenze:

- **La fonte è TMDB** (`/discover/movie`), non un feed. I film sono ordinati per
  popolarità fra i **più votati** (`vote_count.gte`, `vote_average.gte`) e
  filtrati su `watch_region` + `with_watch_monetization_types=flatrate`: solo
  ciò che è compreso in un **abbonamento**. È la richiesta — «presente sulle
  piattaforme di streaming», non al cinema né a noleggio.
- **Serve una chiave** (`TMDB_API_KEY`). Senza, la sezione non è un guasto: è
  una cosa da accendere, e `messaggio_stato()` dice come. La chiave si legge
  dall'ambiente o da un file `segreto.*` accanto all'app (stessa regola di
  `voce_cloud` e `comprensione`, con l'etichetta `tmdb:`), **non si salva mai
  dall'app** e non compare nella risposta.
  **La stessa trappola dei segreti della voce vale qui.** Il sistema inietta il
  segreto solo per i comandi in cui compare il **nome esatto** `TMDB_API_KEY`:
  `./avvia.sh` da solo non basta e il server riparte **senza** la chiave — la
  sezione dice «Cinema non ancora acceso», che sembra un guasto mentre è una
  variabile non passata. Per riavviare con i film attivi:
  `TMDB_API_KEY="$TMDB_API_KEY" ./avvia.sh restart`. Il segno che è andata bene:
  `avvia.sh` stampa `cinema: chiave TMDB attiva` (`stato_cinema()`, accanto a
  `stato_voce()`). Verificato su tutte le case (2026-10-05): con la chiave
  nominata nel comando, `cinema.configurato()` è `True` e le case si riempiono.
- **La regione** (`CINEMA_REGION`, predefinita `IT`) decide **quali** piattaforme
  compaiono: il catalogo Netflix italiano non è quello americano.
- **La copia vive in `tv_cache`**, chiave `cinema`, non in una tabella a parte:
  la forma è identica (un elenco intero, letto sempre tutto) e cambia solo la
  fonte e la scadenza (**mezza giornata**, `ORE_CINEMA`, contro l'ora della TV).
- **`GET /api/cinema`** serve la cache e riprova in sottofondo
  (`_aggiorna_cinema_in_sottofondo`, che non parte senza chiave);
  **`POST /api/cinema/aggiorna`** è il pulsante «Aggiorna» e aspetta la rete.
  All'avvio `avvia_cinema()` riempie tutte le case, come `avvia_tv()`.

Lato browser (`renderCinema`, `disegnaCinema`, `disegnaFilm`, `cinemaVai`) il
carosello si sfoglia in **quattro modi**, perché su un telefono non c'è mouse e
su un desktop non tutti usano le frecce: frecce, tastiera (frecce ← →), rotellina
e dito (`touchstart`/`touchend`, col gesto orizzontale). Lo scorrimento è
**ciclico** (dopo l'ultimo si torna al primo) e i puntini sotto saltano a un film
preciso. Un film **senza locandina si scarta** nel modulo: è una sezione di
immagini, e una senza immagine non ispira niente.

**La scheda del film è affiancata, non in colonna.** Locandina a sinistra e testo
a destra (`.cinema-scheda` è una grid a due colonne, max 720px): così la locandina
resta grande e titolo, trama e piattaforme si leggono senza scorrere, mentre in
colonna il testo finiva sotto la piega. Sotto i 560px torna in colonna
(`grid-template-columns: 1fr`) con la locandina più piccola (180px). Il **voto è
un timbro sulla locandina** (`.cinema-voto`, pillola ambra in alto a destra), non
una riga di testo: si legge guardando l'immagine. Sta **dentro** il bordo perché
il carosello ha `overflow: hidden` e un timbro sporgente verrebbe tagliato. La
trama lunga è limitata in altezza (`max-height`, `overflow: hidden`) per non
spingere giù le frecce.

Tre scelte recenti, tutte deliberate:

- **Azione, film per bambini/ragazzi e Marvel restano fuori** (`GENERI_ESCLUSI`,
  `GENERI_BAMBINI`, `CASE_ESCLUSE`): azione e cinecomic sono i più popolari e da
  soli riempirebbero il carosello coprendo tutto il resto, mentre i film per
  bambini non sono quello che si cerca per una serata. Si escludono per **genere**
  (28 = Azione, 16 = Animazione, 10751 = Famiglia) e per **casa** (420 = Marvel
  Studios, 7505 = Marvel Entertainment), non per titolo: così un film nuovo non
  va aggiunto a mano. `without_genres` accetta più generi separati da virgola, in
  OR, quindi stanno in un unico parametro; da solo non basta per i cinecomic: un
  film Marvel è anche Avventura/SF, e non tutti sono marcati Azione.
  **Verificato con la chiave vera** (2026-10-05): con `sort_by=revenue.desc`
  senza filtri la prima pagina apriva con Avengers: Endgame, Avatar, Spider-Man:
  No Way Home, Avengers: Infinity War, Star Wars (tutti col genere 28); con
  `_escludi` i film d'azione passavano da **12 a 0**. La scoperta Marvel
  (`with_companies=420`) dà 20 film, **tutti** marcati Azione — quindi in questo
  momento `without_companies` è una cintura in più rispetto a `without_genres`,
  ma resta perché copre il film Marvel d'animazione o per famiglie che Azione
  non marca (è la ragione scritta sopra).
- **Si esclude per genere, non per certificazione d'età.** La certificazione di
  TMDB non è affidabile per questo scopo, ed è stato verificato con la chiave
  vera: gli operatori `certification.lte`/`.gte` vengono **ignorati** (tre
  soglie diverse restituiscono sempre lo stesso totale, 1839), i valori esatti
  (`certification=18+`) coprono pochissimi film (47), e molti — Harry Potter,
  Interstellar (certificato «T», tutti) — non hanno alcuna certificazione
  italiana. Il genere invece c'è sempre. Il prezzo è che restano fuori anche i
  film d'animazione «per tutti» (Ghibli, anime) e che un fantasy per ragazzi come
  Harry Potter, marcato Avventura/Fantasia e non Famiglia, **resta**: è il limite
  di una regola che non sbaglia per eccesso. Il test
  `test_la_scoperta_esclude_azione_e_marvel` verifica i generi richiesti.
- **Non commerciale: un tetto ai voti, non una lista di titoli.** Il segno che
  un film «l'ha visto tutti» non è il voto — i film di cassetta hanno voto alto —
  ma **quanti** voti ha: i blockbuster viaggiano a decine di migliaia
  (Interstellar 41k, Blade Runner 2049 16k, Il padrino 24k, Pulp Fiction 31k),
  un film che si scopre no. La scoperta principale ha quindi una **finestra sui
  voti** (`VOTI_MIN` 50, `VOTI_MAX` 3000, `VOTO_MIN` 6.5): il minimo toglie i
  film senza pubblico (che non è la stessa cosa di un film di nicchia), il
  **tetto** toglie i titoli da grande distribuzione che restano popolari per
  anni. È una regola sui numeri, non sui titoli: un film nuovo che sfonda esce
  da solo, e non c'è niente da aggiornare a mano. Verificato con la chiave vera:
  prima il carosello apriva con Interstellar, Blade Runner, Il padrino, Dune,
  Pulp Fiction, Fight Club, Harry Potter; dopo, con le novità e i film fuori dal
  giro. Un limite onesto: con un tetto stretto passa anche il film «normale»
  poco votato (una commedia recente con 200 voti), che non è di nicchia ma non è
  nemmeno commerciale. Il test `test_la_scoperta_mette_un_tetto_ai_voti` lo
  fissa.
- **I film di nicchia** (`_nicchia`) sono una seconda scoperta, per **tag**
  (`PAROLE_NICCHIA`, le keyword di TMDB): cinema indipendente, d'autore, cult,
  commedia nera, surrealismo, stop motion, realismo magico. Si cercano per tag e
  non per titolo, così un film nuovo che porta quel tag entra da solo, come per
  generi e case. Hanno lo **stesso tetto ai voti** dei film del momento: un
  «cult» visto da tutti non è quello che si cerca. Si ordinano per voto (non per
  popolarità), si accodano ai film del momento senza doppioni, e non rubano il
  posto ai film nuovi. Se la chiamata non riesce, non è un guasto: la sezione ha
  già i film del momento. Con la chiave vera la coda porta cinema d'autore vero
  (Nuovo Cinema Paradiso, Apocalypse Now, Va' e vedi, Il dottor Stranamore, Lo
  specchio). Il test `test_i_film_di_nicchia_si_cercano_per_tag_e_si_accodano`
  verifica tag, ordine, tetto e deduplica.
  **Perché i tag e non le case di produzione.** Provata anche la via «solo case
  indipendenti» (A24, Film4, Arte France Cinéma…): funziona ma è fragile, perché
  gli id delle case cambiano e vanno verificati a mano, e taglia fuori il cinema
  italiano e molto altro. I tag sono assegnati per opera e coprono anche il
  cinema europeo e di repertorio, che è quello che si cerca. Un tag inventato
  viene ignorato in silenzio da TMDB: gli id vanno verificati con
  `/search/keyword`, non indovinati.
- **I preferiti sono un elenco a sé** (`cinema_preferiti`): la stella salva la
  **scheda intera** (JSON), non solo l'id, perché il preferito deve restare
  anche quando il film esce dal giro dei film del momento. Senza la scheda
  salvata si vedrebbe una locandina vuota. Lato frontend due viste («Del
  momento» / «★ Preferiti») con `cinemaCambiaVista`; `POST
  /api/cinema/preferiti` segna o toglie (rifiuta un film non mostrato, che
  sarebbe un preferito senza scheda).
- **La vista Preferiti era invisibile per un id duplicato.** Il pulsante e il
  contenitore della vista avevano lo stesso `id="cinema-vista-preferiti"`:
  `$()` prende il primo (il pulsante), quindi
  `classList.toggle('hidden', ora)` finiva sul pulsante e il contenitore restava
  `hidden`. La griglia si costruiva (i `<figure>` c'erano) ma misurava 0x0, e il
  pulsante «Togli» non era cliccabile: sembrava che i preferiti «non
  funzionassero», mentre il difetto era di layout. Il contenitore ha ora un id
  suo (`cinema-pannello-preferiti`), e due test lo tengono fermo:
  `test_il_cinema_vive_dentro_la_sezione_tv` e `test_la_vista_preferiti_ha_id_distinti`
  pretendono che gli id di `index.html` siano **unici**. È la lezione generale:
  un id duplicato non dà errore, dà un elemento che non si vede.
- **Solo film che hanno una versione italiana.** La sezione serve una serata in
  casa, quindi un film che non è mai arrivato qui non serve. Il segnale è la
  presenza di una **traduzione `it`** in `movie/{id}/translations` (titolo e
  trama localizzati), non la lingua originale: `with_original_language=it`
  toglierebbe anche i film stranieri doppiati — che sono la maggioranza di quelli
  che si guardano (Match Point, Il padrino, i film francesi di Dupieux) — e
  `region=IT` colpisce i film *usciti* in Italia, non quelli che hanno una
  versione italiana. Non è il doppiaggio in senso stretto (TMDB non espone le
  tracce audio), ma è la cosa più vicina: senza traduzione il film non è
  distribuito qui in nessuna forma. Verificato con la chiave vera: i due film
  che il filtro ha tolto (Strung, un romance russo) **non** hanno la traduzione
  `it`; i film di repertorio che restano (Amarcord, Fargo, L'angelo
  sterminatore) ce l'hanno tutti. Il taglio avviene **prima** di riempire i
  posti, così restano i film previsti e non un elenco bucato. Il test
  `test_i_film_senza_versione_italiana_si_scartano` lo fissa.
  **Traduzioni e piattaforme in una chiamata sola** (`_dettagli`, con
  `append_to_response=translations,watch/providers`): i film sono qualche
  decina, e chiederli a parte raddoppiava la rete. Se il dettaglio non risponde
  il film si **tiene** (`italiano` vero): scartare un film buono per un dubbio è
  peggio che mostrarne uno in più. Era `_fornitori`; il test che lo verifica si
  chiama ora `test_un_film_resta_anche_se_i_dettagli_non_rispondono`.
- **I film "sulla scia"** (`_scia`) sono una terza coda, dalle
  **raccomandazioni** di TMDB (`/movie/{id}/recommendations`) dei capisaldi in
  `SCIA` (id di TMDB, non titoli: un titolo cambia, un id no). Sono i film che
  piacciono alla casa — Il divo, Match Point, Dio esiste e vive a Bruxelles,
  Ferie d'agosto, Yannick — e da lì TMDB propone i titoli affini. Si scartano
  azione, bambini, **documentari e musicali** (`GENERI_SCIA_VIETATI`), e si
  tiene la stessa finestra sui voti dei film del momento, così la scia non
  riporta dentro i blockbuster. Si ordina per voto (qui conta la qualità
  riconosciuta). Un film nuovo che assomiglia ai capisaldi entra da solo: non
  c'è una lista di titoli da aggiornare. Il test
  `test_i_film_sulla_scia_dei_capisaldi_si_accodano` lo verifica.
  **Perché non le "simili" o le keyword.** Le `/similar` sono quasi identiche
  alle raccomandazioni ma meno curate; le keyword darebbero film che condividono
  un tema ma non il tono. Le raccomandazioni sono il segnale costruito sul
  comportamento di chi guarda, ed è quello che serve per "sulla scia de".
  **Ogni sorgente ha i suoi posti, e gli avanzi si riprendono.** Le tre code
  (momento, nicchia, scia) si accodano con una quota (`QUANTI`, `QUANTI_NICCHIA`,
  `QUANTI_SCIA`) e non in un unico concatenamento. Difetto vero, misurato con la
  chiave: i film del momento (20) più la nicchia (fino a 20) riempivano da soli
  il tetto, e la scia — ultima in coda — non entrava **mai**; la coda sembrava
  tutta nicchia e nessun film "sulla scia" si vedeva, pur essendo la funzione
  appena scritta. Le quote sono la correzione; l'avanzo (una sorgente con pochi
  film, o film tolti dal filtro italiano) si riprende in coda dalle altre, così
  l'elenco non resta bucato. Il test `test_la_nicchia_non_soffoca_la_scia` fissa
  il caso che in produzione falliva (nicchia piena + scia piena), e
  `test_la_scia_riempie_i_posti_lasciati_liberi` il riempimento. È la lezione
  generale: **un accodamento senza quote è un tetto dato alla prima sorgente**,
  e la sorgente che si accoda per ultima sparisce senza un errore.
- **I film eliminati** (`cinema_nascosti`): l'utente può togliere un titolo che
  non gradisce. Non si cancella dalla copia (`tv_cache`) — quella è la fotografia
  di TMDB, cancellarla la lascerebbe sbagliata — e non si salva la scheda intera
  come per i preferiti: basta l'id. L'eliminazione è **reversibile**: `film()` la
  applica a ogni lettura, quindi eliminare un titolo lo fa sparire all'istante e
  ripristinarlo lo fa tornare, senza riscaricare. `POST /api/cinema/nascondi`
  (rifiuta un film non mostrato) e `POST /api/cinema/ripristina` (un id o tutti,
  col corpo vuoto). Lato client il pulsante **Elimina** sta accanto alla stella,
  e la riga `#cinema-nascosti` dice che l'eliminazione non è definitiva e offre
  il ripristino — senza, nessuno oserebbe toccare niente. `cinema_nascosti` è una
  tabella nuova, quindi la crea lo schema che `get_db()` applica a **ogni** casa;
  `_nascosti` legge in modo tollerante (una tabella assente si comporta come
  «nessuno escluso»), così `_scarica` funziona anche su una connessione nuda.
  I test `test_i_film_eliminati_spariscono_e_si_ripristinano` e
  `test_la_tabella_dei_film_eliminati_arriva_anche_a_un_db_vecchio` lo tengono
  fermo.
- **Eliminando un titolo se ne accoda subito uno nuovo** (`cinema.sostituisci`,
  chiamata da `POST /api/cinema/nascondi`): la sezione non deve accorciarsi a
  ogni titolo rifiutato. Si pesca da una pagina di `discover` **diversa** da
  quella della copia (`_candidati(pagina)`, che senza il parametro serve
  `_scarica`), si saltano i già nascosti e quelli già in elenco, e si filtra
  l'italiano come `_scarica`. La copia **cresce** invece di essere riscritta, e
  il film appena eliminato resta nei nascosti, quindi non torna. Due dettagli
  che sembrano tali: la nicchia e la scia si chiedono **solo** per la prima
  pagina (sono elenchi fissi, ripeterli sarebbe lavoro sprecato), e c'è un tetto
  alle pagine (`RIMPIAZZI_MASSIMI`) perché ogni pagina sono più chiamate di
  dettaglio. Il rimpiazzo **non solleva mai**: se la rete manca l'eliminazione è
  riuscita lo stesso e la copia resta com'è. Il messaggio del client dice il
  titolo aggiunto (`«X» eliminato · aggiunto «Y»`). I test
  `test_eliminare_un_film_ne_carica_subito_uno_nuovo`,
  `test_il_rimpiazzo_non_ripesca_i_gia_mostrati`,
  `test_senza_rete_l_eliminazione_riesce_lo_stesso` e
  `test_il_rimpiazzo_non_esce_dal_tetto_delle_pagine` lo fissano. Nota:
  `sostituisci` prende lo **stesso lucchetto** di `aggiorna` (`tv._lucchetto`),
  quindi il rimpiazzo e il giro di sottofondo non si sovrappongono.



