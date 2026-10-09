# Convenzioni — pasti, FAQ, cassaforte, biometria, profili

- Quanti pasti al giorno è una scelta dell'utente (1-5) salvata in
  `profile.meals_per_day`, non una costante: i nomi dei pasti stanno in `MEAL_SETS`
  (`app.py`) e il frontend li mostra da `/api/meta`. `valid_meals(db)` e
  `meal_clause(db)` sono l'unico modo per sapere quali pasti contano: riducendo i
  pasti restano righe vecchie in `meal_plan`, e senza quel filtro continuerebbero a
  pesare sulla lista della spesa pur non essendo più visibili.
- **FAQ**: le voci vivono **cifrate** nella cassaforte (vedi sotto), non più in
  chiaro nella tabella `faq`. La tabella `faq` resta in `schema.sql` solo per la
  **migrazione**: le voci in chiaro che ci fossero vengono importate nel blob
  cifrato alla prima lettura e poi cancellate (`_faq_importa_vecchie`). Le
  **categorie** stanno in `faq.py`: sono la struttura della sezione, come gli
  ambienti per le pulizie.
  `categoria_valida()` fa ricadere una chiave ignota sulla predefinita invece di
  rifiutare la voce: un'etichetta sbagliata non deve far perdere un numero di
  telefono. L'ordine è **categoria → evidenza → titolo**: le voci in evidenza
  risalgono dentro la propria categoria, non in cima all'elenco, perché
  raggruppate per categoria saltare il gruppo le staccherebbe dalle voci affini.
  Il testo di `answer` può essere lungo (un indirizzo con citofono e scale),
  quindi nel form è un'area di testo e a schermo i ritorni a capo diventano
  `<br>`. I valori che **sono** un telefono o un'email diventano `tel:`/`mailto:`
  — solo se sono quello e non se lo contengono: un testo lungo con un numero
  dentro resta testo. La ricerca è lato client e guarda anche il nome della
  categoria, così non serve indovinare dove sta una voce.
- **La sezione FAQ non ha due viste.** L'utente non le vuole: c'è **una sola
  lista**, e sopra il riquadro che apre o chiude il modulo
  (`cass-stato`/`cass-blocco`/`cass-contenuto`). I test
  `test_faq_non_ha_una_seconda_voce_di_menu` e quelli della cassaforte tengono
  ferma la cosa.
- **Niente password della cassaforte: si apre col controllo biometrico.** Una
  password diversa da quella della casa era una cosa in più da ricordare e da
  spiegare, e chi la dimenticava perdeva le voci — l'utente ha chiesto di
  toglierla. Ora il modulo si apre col **sensore** (`POST
  /api/faq/apri-biometria`) e si richiude da solo dopo `chiusura_minuti`. Non
  esiste una password di riserva: se il dispositivo non ha un sensore, le FAQ
  restano chiuse (`test_senza_chiave_non_si_apre`). Sono sparite le rotte
  `POST /api/cassaforte/crea` e `POST /api/cassaforte/apri`, la verifica
  `cassaforte.password_giusta`/`impronta`, e i campi password del client.
- **La cassaforte** (`cassaforte.py`) custodisce **tutte le voci delle FAQ**,
  cifrate con la **chiave della casa** (`houses.secret_key`, in `houses.db`).
  Tre scelte che contano:
  - **Il testo in chiaro non lascia mai il server a modulo chiuso.** Non è un
    nascondiglio nel client: `/api/faq` (e l'alias `/api/cassaforte/voci`)
    **non contengono il valore** finché non si è aperto, e si scrive solo a
    modulo aperto (401 altrimenti). Dire «cifrato» e poi mandare il valore al
    client sarebbe la peggiore delle due cose. Un test guarda il **file `.db`
    grezzo** (`test_il_valore_non_e_in_chiaro_nel_database`), non l'API: è
    l'unica prova che il requisito è rispettato.
  - **La chiave di cifratura è quella della casa, non una password scelta.**
    Vive in `houses.db`, che il server ha sempre: senza la casa (cioè senza la
    password d'accesso) il blob resta illeggibile. La cifratura protegge il
    **file** (un database copiato, una copia di backup), **non** un server
    compromesso — e il sensore protegge l'**accesso**. È la stessa scelta della
    firma delle sessioni. La vecchia impronta PBKDF2 nel registro
    (`cassaforte_registro.impronta`) non si usa più: la colonna resta solo per
    non rompere i registri esistenti.
  - **Cifratura autenticata, scritta a mano sulla stdlib.** `cifra`/`decifra`
    usano PBKDF2-HMAC-SHA256 (200000 iterazioni, sale nuovo a ogni scrittura) per
    la chiave, un flusso HMAC-SHA256 come keystream e un **HMAC di firma**
    (Encrypt-then-MAC): una chiave sbagliata o un byte manomesso non producono
    un errore oscuro ma `CassaforteErrore`. La firma copre **anche** iterazioni e
    sale, così abbassarle per indovinare la chiave invalida il file
    (`test_cassaforte_una_firma_non_si_riusa_su_altre_iterazioni`). Niente
    `cryptography`/`pyca`: una dipendenza in più con binari nativi per un
    requisito di casa non vale il costo.
  - **La chiusura automatica vive nel processo, non nel biscotto.** L'apertura
    ha una **scadenza** (`chiusura_minuti`, default 15): entrare nell'app **non**
    apre il modulo, e dopo il tempo scelto `_faq_aperta` lo lascia cadere. `_faq_*`
    in `app.py`; la mappa è per casa (`_FAQ_APERTE`). Nei test l'aprirebbe un
    test e resterebbe aperta a quello dopo: la fixture autouse `percorsi_dei_dati`
    chiama `_faq_dimentica()` prima di ogni test.
  - **Coerente con le case separate.** I dati stanno nel database della casa
    (`cassaforte`, riga id=1 col blob); il promemoria e la chiusura nel registro
    (`cassaforte_registro`, una riga per casa). Eliminando una casa,
    `houses.elimina()` ne cancella anche la riga. La tabella è nell'elenco delle
    tabelle di `/api/backup` (`_ha_dati`).
- **Biometria: il sensore apre la scatola, la chiave del dispositivo la
  autorizza.** L'impronta digitale **non è un segreto**: è un permesso. Il
  sensore dice "sei tu", non produce nessuna chiave. La chiave del dispositivo
  (`bio`, generata dal **client** con `bioNuovaChiave`) è quella che il server
  custodisce e verifica; **alla prima apertura si deposita da sola** (non c'è
  più niente da configurare), dalle volte successive la stessa chiave deve
  aprire il timbro, altrimenti un altro dispositivo non passa. Il timbro è
  **cifrato con se stesso** (`cassaforte.cifra(chiave, chiave)`), quindi non è in
  chiaro nel database. La chiave la custodisce il **client**: sul web in
  `localStorage`, e va detto onestamente che **non è più sicura** di una password
  ricordata — è più comoda; su un'app nativa starebbe nel Portachiavi dietro Face
  ID e lì la differenza sarebbe vera. Il sensore si chiama con
  `navigator.credentials.create` di una credenziale `platform` (`bioVerifica`);
  **`rp.id` è il nome host**, e `localhost` è un RP ID valido mentre `127.0.0.1`
  no. Nel sandbox si prova con l'**autenticatore virtuale** di Chromium
  (`WebAuthn.addVirtualAuthenticator` via CDP) su `http://localhost:12000/`; la
  colonna `bio` va aggiunta a mano in `migrate()` per i database esistenti.
- Nelle sezioni la barra mostra solo le schede dell'area aperta (`data-section`
  sulle schede, `SEZIONI` in `app.js` come mappa area → prima scheda): le voci delle
  aree non vanno mescolate in un'unica barra. Il pulsante vocale è una funzione
  della cucina e resta nascosto altrove.
- **Il Profilo si raggiunge anche dalle FAQ.** La scheda «⚠️ Profilo» ha
  `data-section="faq"` **e** una gemella con `data-section="cucina"`: è la stessa
  scheda in due aree, perché `data-section` filtra la barra e `data-tab` sceglie
  il pannello. Nessun codice nuovo: `#tabs button[data-tab="profile"]` chiama
  `renderProfile()` come prima. Sta anche nelle FAQ perché lì vive la stessa
  specie di cose — password della casa, tema — cioè impostazioni di servizio che
  si cambiano, non voci da consultare. Il pannello `#tab-profile` resta **uno
  solo** (un id duplicato, come per i preferiti del Cinema, darebbe un elemento
  che non si vede).
- L'onboarding ha cinque passi (`passoPasti`, `passoBucati`, `passoNotizie` dentro
  `openOnboarding`, più `openFavoritesStep`): quanti pasti, allergie, bucati al
  giorno, argomenti delle notizie, preferite. Il numero nell'intestazione («Passo N
  di 5») si conta da solo, così non può mentire. `fav_prompted` distingue chi non ha
  mai visto la scelta delle preferite, così l'ultimo passo viene riproposto a chi si
  era profilato prima. Lo stato dei passi vive in una `bozza` condivisa, perché
  "Indietro" non salva. Le domande iniziali si aprono entrando in Cucina
  (`avviaProfiloSeServe`), non sulla pagina iniziale: chi sta andando in Igiene non
  deve vedersi chiedere cose di cucina. Al primo accesso di una casa appena creata
  si apre anche il **menù di benvenuto** (`mostraBenvenuto`, `#wb-skip` /
  `#wb-inizia`): un elenco di cosa sa fare l'app, saltabile, per chi non sa da dove
  cominciare.

