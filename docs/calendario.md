# Il Calendario degli impegni

## Il Calendario: gli impegni con un promemoria

`calendario.py` tiene gli impegni — appuntamenti, scadenze, ricorrenze — dentro
**Progetti**, in una scheda a parte. Perché non è una colonna dei progetti: un
progetto ha un **periodo** (inizio e fine) e una priorità, un impegno ha un
**giorno preciso** e un'ora. Sono due forme diverse — un progetto può durare un
mese, un impegno no — e tenerli nella stessa tabella costringerebbe metà delle
righe ad avere campi vuoti che non significano niente. È la stessa scelta del
magazzino: sta in Progetti perché è una cosa da fare, ma in una tabella sua.

La logica delle date sta nel modulo e non nelle rotte: la griglia del mese, i
giorni di distanza e il promemoria sono **funzioni pure**, e si provano senza
browser. Le rotte aggiungono solo persistenza, validazione e stato calcolato.

Tre scelte deliberate, tutte con un motivo:

- **Il promemoria è quanti giorni prima** (`reminder_days`), non una data di
  avviso. Spostando l'impegno si sposta anche il promemoria, invece di lasciarlo
  indietro: una data di avviso salvata a parte si disallinea al primo rinvio, ed è
  proprio il caso in cui il promemoria smette di servire. Zero è "il giorno
  stesso", una scelta legittima, non "nessun promemoria".
- **`when_date` non si chiama `date`.** `date` è una funzione di SQLite (come
  `time` e `datetime`): il nome funziona finché non lo si usa in un'espressione,
  e allora l'errore arriva nel posto meno aspettato. Vale anche per la colonna
  `time`, che convive con la funzione `time()`.
- **Il colore è una categoria, non una decorazione.** Lavoro, casa, salute,
  famiglia, altro: serve a leggere il mese a colpo d'occhio. La categoria è
  **testo libero con suggerimenti**, e una chiave sconosciuta **ricade** sulla
  predefinita invece di far perdere l'appuntamento — la stessa scelta fatta per
  le FAQ. Il colore è un **nome di variabile CSS** (`--cat-lavoro`), non un
  esadecimale: così il tema scuro la schiarisce da sola.

Lo stato non si salva: si ricava dalla data a ogni lettura, come le scadenze
delle pulizie e i giorni della spesa. Una colonna di appoggio si disallineerebbe
al primo cambio d'ora. `stato_impegno` segue la **stessa convenzione di
`igiene.scadenza`** — `giorni` negativo se è passato, 0 oggi, positivo se deve
venire — così chi legge i due moduli non deve ricordarsi due regole diverse. E
distingue due cose che sembrano una:

- **`avvisa`** è il promemoria scattato: da `reminder_days` giorni prima fino al
  giorno stesso. Dopo non avvisa più, perché un promemoria per una cosa già
  successa non è un promemoria.
- **`in_ritardo`** è la cosa passata e non chiusa: resta negli avvisi finché non
  si spunta. Altrimenti un impegno mancato sparisce in silenzio, che è il modo
  peggiore di fallire un promemoria.

Gli avvisi in cima alla scheda (`prossimi`) **non sono "tutti i prossimi
impegni"**: sono solo quelli scattati o in ritardo. Un promemoria per una cosa
fra sei mesi non è un promemoria, e mostrarlo toglierebbe valore a quelli veri.

Nella griglia del mese le **settimane sono intere**: si includono i giorni fuori
dal mese (le code del precedente e del successivo), perché una riga che comincia
a metà confonde più di quanto aiuti. `nel_mese` distingue quelli veri, così le
code si mostrano spente. La griglia è **sette colonne fisse** anche su telefono —
è un calendario, e un mese che comincia a metà riga deve lasciare il vuoto.

`GET /api/appointments` serve il mese corrente, o quello chiesto con `?mese=`,
o un giorno con `?giorno=`. La griglia si costruisce **sempre**, anche quando si
chiede un giorno solo: il client disegna calendario ed elenco insieme, e senza
griglia non saprebbe dove mettere il giorno scelto. Questo è stato trovato da un
test, non leggendo il codice: il ramo `?giorno=` rispondeva senza `mese`, e il
client andava in `KeyError`.

`done` si tocca da solo, come per i progetti: spuntare un impegno non deve
richiedere di rimandare titolo, data, categoria e promemoria. Un'ora scritta male
si scarta (`_ora`), non fa rifiutare l'impegno: l'ora è facoltativa e l'impegno è
la parte che conta.

I test coprono la griglia (settimane intere, weekend, primo e ultimo giorno), i
giorni di distanza, il promemoria, il ritardo, le frasi di quando, la categoria
che ricade, i limiti del promemoria e l'ora tollerante — tutte funzioni pure — e
poi le rotte per ciò che aggiungono: persistenza, validazione, `done` isolato,
gli avvisi che sono solo i promemoria scattati, il 401 senza accesso e la tabella
`appointments` che arriva anche a un database vecchio.

**Gli impegni si possono dettare a voce** (`event_add`, vedi la sezione sui
comandi vocali): "ricordami il dentista domani alle 15" crea la riga in
`appointments` senza toccare lo schermo. È l'unica capacità vocale che scrive nel
calendario, e l'esecuzione (`app._esegui_impegno`) riusa `calendario` — categoria
che ricade, ora tollerante, `promemoria_giorni` — così una frase detta e una
scheda compilata a mano danno lo stesso risultato.

### I promemoria del sistema (Notification API)

Il calendario calcola da solo i promemoria scattati, ma finché restano dentro
l'app li si vede solo aprendola. Con il pulsante **🔔 Attiva i promemoria**, in
cima alla scheda Calendario, l'avviso arriva come **notifica del sistema**: anche
a pagina chiusa o in secondo piano, che è il momento in cui un promemoria serve.
Il client è in `app.js` (`notificheAttive`, `controllaPromemoria`,
`avviaPromemoria`, `mostraPulsanteNotifiche`); non c'è codice nuovo sul server,
si riusa `GET /api/appointments?giorno=<oggi>` e i suoi `prossimi`.

Quattro scelte, tutte con un motivo:

- **Il permesso si chiede da un tocco**, mai da soli: un browser che vede una
  richiesta senza un gesto la blocca, e il permesso negato non si riprende più.
  Per questo c'è un **pulsante** e non una richiesta all'avvio; il pulsante
  compare solo se il browser sa fare le notifiche (`typeof Notification`).
- **Un avviso per impegno, una volta al giorno.** La memoria di cosa è già stato
  avvisato sta in `localStorage` (del **dispositivo**, non della casa) sotto
  `promemoriaAvvisati`, col giorno dentro la chiave: così il controllo periodico
  non ripete lo stesso avviso e il cambio di data azzera da solo la memoria. La
  chiave è `id|when_date`, non il solo id: un impegno spostato è un impegno nuovo
  e deve poter riavvisare.
- **Il controllo è leggero e periodico**: ogni mezz'ora (`setInterval`) e al
  ritorno sulla pagina (`visibilitychange`), non un filo sempre acceso. La casa
  non ha bisogno di un servizio di notifiche.
- **Se il permesso manca non si chiama nemmeno il server** (`notificheAttive`
  esce prima della `fetch`): senza, ogni mezz'ora partirebbe una richiesta per
  non fare niente.

`mostraPulsanteNotifiche` è l'unico posto che decide se il pulsante si vede
(nascosto se il browser non supporta le notifiche o se il permesso è già
concesso): due regole in due posti divergono, e il pulsante resterebbe a chiedere
un permesso già dato.

I test eseguono `controllaPromemoria` **vera** con node, con `Notification` e
`localStorage` finti: con permesso concesso e un impegno che avvisa parte **una**
notifica e richiamandola non ne parte una seconda; senza permesso non parte
niente e il server non viene chiamato. Il controllo delle funzioni non definite
(`test_app_js_non_chiama_funzioni_che_non_esiste`) ha in elenco anche
`Notification`, `localStorage`, `sessionStorage`, `navigator`, `document` e
`window`, altrimenti li scambierebbe per funzioni mancanti.


