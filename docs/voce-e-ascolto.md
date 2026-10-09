# Voce e ascolto (dettaglio)

## Il riconoscimento vocale

Il microfono **registra** e la trascrizione avviene **sul server**
(`voce_cloud.trascrivi`), non nel browser: la Web Speech API manda l'audio ai
server di Google, e in molte case quel traffico è bloccato (firewall, antivirus,
VPN), per cui Chrome risponde `network` e il microfono resta muto senza rimedio.
Il server invece esce dalla rete. Dettagli e trappole nella voce
«L'ascolto passa dal server» più sotto (in «Convenzioni — voce e comandi»).
`voice.py` comprende il testo trascritto;
la comprensione sta sul server perché si prova con dei test, senza microfono.

La Web Speech API resta solo come **ripiego**, quando la chiave non c'è
(l'endpoint risponde 503). In quel caso il comportamento **cambia fra PC e
telefono**:

- Chrome e Firefox **non espongono** le voci neurali di Windows (solo Edge, e
  solo su PC). La voce "brutta" da PC è per lo più questo. `voce_cloud` aggira il
  problema quando la chiave Azure è configurata dalla pagina.
- `SR` può essere `undefined` (Firefox lo è sempre stato). Il controllo va fatto
  prima di costruire il riconoscimento, dicendo all'utente cosa scrivere invece.

Il primo clic su `#mic` chiama `apriVoce()` che chiama `ascolta()` **prima** che
esista un riconoscimento: lì `voce.rec` è `null`. Chiamare `stop()` su `null`
solleva un `TypeError` che non passa da nessun `onerror`, quindi il pannello si
apre ma non ascolta, in silenzio. La guardia è `if (voce.attivo && voce.rec)`
(per il percorso server la guardia analoga è `if (voce.attivo)`).

## L'ascolto continuo e la parola di sveglia

Perché a cicli e non un microfono davvero sempre aperto: l'audio breve di Azure
accetta registrazioni di poche decine di secondi, non un flusso continuo. Si
registra una frase, si manda, si guarda se conteneva la sveglia, e si riparte.

La sveglia si riconosce **sul server** (`voice.sveglia`, usata da
`/api/voce/ascolta` che restituisce `sveglia` e `resto`, e dal nuovo
`/api/voce/sveglia` che classifica **senza eseguire**). Il motivo è lo stesso
della trascrizione: una logica sola vale sia per il server sia per il ripiego
sul browser, invece di una seconda copia libera di divergere. E
`/api/voce/sveglia` non esegue perché in ascolto continuo si sentono anche le
frasi che non c'entrano: mandarle a `/api/voice` scriverebbe in dispensa ogni
discorso.

Tre trappole, tutte costate una prova:

- **La sveglia vale solo all'inizio.** "il maggiordomo prepara la cena" è una
  conversazione, non un ordine. Un "maggiordomo" a metà frase non deve far
  partire niente.
- **Il riconoscimento sbaglia i nomi propri.** Si accettano gli esordi
  ("hey/ehi/ok/ciao") e le storpiature del nome ("magiordomo"): la forma esatta
  da sola vuol dire non essere mai chiamati.
- **Mentre l'app parla, il microfono va sospeso** (`riprendiDopoLaVoce`,
  `voce.aFineParlato`). Senza, la risposta letta ad alta voce rientra dal
  microfono e l'app si risponde da sola, in un ciclo infinito. C'è anche un
  tetto di sicurezza (`TETTO_VOCE_MS = 20000`): `onend` della sintesi non arriva
  in tutti i browser, e senza il tetto l'ascolto resterebbe fermo per sempre con
  l'aria di essere acceso.

Chiudere il pannello **non** spegne l'ascolto continuo: è acceso apposta, e il
pulsante `#mic` (classe `.sempre`) e la spia `#voice-sempre-spia` sono l'unico
segno che il microfono sta ancora ascoltando.

### Dopo "Sì." il comando non ripete la sveglia

C'era un buco silenzioso proprio nel dialogo naturale: si chiama "maggiordomo",
lui risponde "Sì.", e la frase successiva è il comando — ma il ciclo
pretendeva di nuovo la sveglia, quindi il comando veniva **ignorato in
silenzio**. La trascrizione era perfetta: era la logica del ciclo a scartare la
frase.

Dopo un "Sì." si apre una finestra a tempo (`attendeComando`, 10 s) in cui
una frase senza sveglia è un comando. Non è aperta per sempre: altrimenti, una
volta chiamato l'assistente, ogni discorso di casa diventerebbe un ordine — "il
maggiordomo prepara la cena" detto a tavola scriverebbe in dispensa. La frase
deve aprirsi con un verbo d'azione o un numero (`sembraComando`, `NUMERI_A_PAROLE`
per le dosi senza verbo come "due chili di farina").

**La finestra non si consuma col primo comando, e si riarma.** Il difetto
riferito — «sembra che senza Hey GG non esegua» — aveva due cause, entrambe
dentro `sembraComando` e `valutaFrase`:

- il cancello accettava "quanto" ma non "quante/quanti/quanta", che è la forma
  più naturale ("quante ricette ho", "quanti grammi sono rimasti"): il parser del
  server le capisce (intento `domanda`), era solo il cancello a sbarrarle;
- nel ramo `esegui` si azzerava la finestra (`inAttesa = 0`), quindi dopo **un**
  comando il secondo ordine di fila richiedeva di nuovo la sveglia. Ora si chiama
  `riarmaFinestra()`, che rinnova la scadenza **solo se la finestra era già
  aperta**.

Il riarmo non apre una finestra chiusa (`riarmaFinestra` non è `attendeComando`),
altrimenti bastava un comando qualunque per far entrare il discorso di casa; e il
tempo complessivo resta limitato da un tetto fisso dall'apertura
(`TETTO_FINESTRA_MS`, 30 s), altrimenti una chiamata seguita da comandi a raffica
terrebbe la finestra aperta per sempre. La regola sta in `inAttesaComando`, che
guarda **due** limiti: la scadenza mobile e il tetto. `apriFinestra` fissa
l'ancora del tetto solo quando la finestra si apre da chiusa.

Il criterio resta una lista di parole, non una comprensione: la finestra non va
aperta a qualunque frase. Misurato, il parser del server ha falsi positivi reali
sul discorso di casa («ho trovato un lavoro nuovo» → voce in lista), quindi
lasciar passare tutto dentro la finestra scriverebbe spazzatura in dispensa. Le
parole colloquiali che il parser capisce davvero (`faro`, `sistemero`,
`riordino`…) danno `unknown` e non aggiungono niente al criterio: `quante/quanti/
quanta` sono l'unica aggiunta, perché sono l'unica che il server comprende.

La decisione sta in `decisioneContinuo`, **pura** apposta: è la regola che decide
se un comando parte, e va provata senza microfono, DOM e attese. `valutaFrase` la
applica, e la usano **entrambi** i percorsi (server e ripiego del browser): due
copie della regola sarebbero libere di divergere.

Nel ripiego del browser `onresult` e `onend` arrivano entrambi: il primo che
parla decide, l'altro non deve far ripartire un secondo ciclo, altrimenti il
microfono si apre due volte e i due giri si annullano a vicenda — restando
acceso ma sordo.

### "Hey GG": le varianti del riconoscimento si misurano, non si indovinano

Il secondo modo di chiamare è "Hey GG". La trappola è che il trascrittore
**non rende quello che si scrive**: "Hey GG" torna come "Ai giorni", "Hey Gi Gi"
come "Ai GG", "Hey Gigi" come "Gigi", "Ehi maggiordomo" come "E i, maggiordomo".
Un regex sulle forme scritte ("hey gg") non scatterebbe mai.

Le forme accettate in `voice.py` (`_SVEGLIA_GG`) sono quelle **misurate**:
si sintetizza la frase con la voce neurale e si rilegge cosa torna dal
trascrittore, con `misura_sveglia.py` accanto all'app. Se in futuro si aggiunge
una variante, va misurata allo stesso modo — indovinarla significa non essere
chiamati, o peggio, accendere l'assistente su parole di casa.

Attenzione al formato: la sintesi esce in MP3 per default, ma la trascrizione
accetta solo WAV PCM 16 kHz (`AZURE_SPEECH_FORMAT`). Con l'MP3 la trascrizione
torna **vuota** e sembra che il servizio non senta, mentre è solo il formato
sbagliato. `misura_sveglia.py` lo imposta già.

Le forme misurate, per non doverle rimisurare: "Hey GG" → "E i giorni", "Ai
giorni"; "Hey Gi Gi" → "Ai Gigi"; "Hey Gigi" → "Aigigi"; "Ehi GG" → "E i
giorni"; "Ciao GG" → "Ciao giorni".

Oltre alle forme del nome, gli esordi includono come il riconoscitore rende
"hey": anche "ai" e "e i". Restano opzionali e da soli non bastano.

### "Ehi maggiordomo" e l'articolo che il trascrittore infila in mezzo

Le forme misurate, per non doverle rimisurare, comprendono anche un **articolo**
fra l'esordio e il nome. "Ehi maggiordomo" non torna mai come scritto: Elsa rende
**"E il maggiordomo"**, Isabella e Diego **"E i, maggiordomo"**. Senza l'articolo
facoltativo (`_SVEGLIA_ARTICOLO`, opzionale ma valido **solo dopo un esordio**)
"E il maggiordomo" non svegliava, e chi chiamava l'assistente restava senza
risposta — il difetto vero visto dal telefono.

L'articolo vale solo **dopo un esordio**: "il maggiordomo prepara la cena"
comincia con l'articolo e non con un esordio, quindi resta chiacchiera. È il
confine che tiene insieme "E il maggiordomo" (chiamata) e "il maggiordomo"
(soggetto). Il test `test_la_sveglia_sente_anche_quando_il_trascrittore_mette_l_articolo`
fissa entrambi i lati.

L'ancora all'**inizio** è ciò che separa un richiamo dal discorso: "il nonno Gigi
arriva alle otto" non fa partire niente. Il prezzo onesto è che "I giorni scorsi
ho comprato il pane" farebbe partire un "Sì." una volta, senza eseguire nulla.

### La sveglia non parte più da sola

Il comando predefinito è il **push-to-talk**; "Hey GG" è un'opzione che si
accende a mano dal pannello. Non c'è dunque più un avvio automatico **all'accesso**
(con la coppia `accendiAscoltoDopoAccesso`/`deveAccendereDopoAccesso` e la
variabile `appenaEntrato`, rimosse): quello era il modo in cui la sveglia si
apriva da sola appena si entrava, senza chiedere niente.

Resta una sola strada di ripresa automatica, ed è quella prudente —
`accendiAscoltoContinuoDaSolo`, al ricaricamento. Non c'è nessun gesto attorno,
quindi vale la regola stretta: `deveAccendereDaSolo` richiede preferenza `'1'`,
permesso già `granted` **e** il server che sa trascrivere. La preferenza si
scrive al click del pulsante (`'1'`/`'0'`), così chi l'ha accesa se la ritrova.

Tre trappole:

- **Il permesso non si chiede senza un tocco.** Con `prompt` o
  `denied` il browser non lo dà: si aprirebbe solo un avviso bloccato. Per questo
  si legge `permissions.query` e non si tenta a fondo.
- **Un `AudioContext` nasce "suspended" finché la pagina non riceve un gesto**,
  e un contesto sospeso non riceve un campione solo: l'app direbbe "ti ascolto"
  senza sentire. Il controllo va fatto sul contesto **vero**, quello del
  registratore (`ascoltaSulServer`), non su una sonda a parte: ogni contesto ha
  il suo stato, e sbloccarne uno non sblocca l'altro. Se resta bloccato, la
  frase `{bloccato: true}` porta ad `attendeUnGesto`, che chiede un tocco sulla
  pagina e poi riparte.
- **La preferenza va scritta al click.** Senza, al ricaricamento successivo non
  ripartirebbe: `deveAccendereDaSolo` la rilegge da `localStorage`.

`resume()` può non risolversi **mai** senza gesto: va sempre atteso con un tetto
(`Promise.race`), altrimenti l'avvio dell'app resta appeso per sempre.

La spia `#voice-sempre-spia` distingue i tre stati: "● in ascolto", "⏸ in pausa
(sto parlando)", "⏸ tocca lo schermo una volta", così non dice "in ascolto"
quando non lo è.


### La registrazione che non finiva mai (il telefono muto)

Il sintomo era preciso: la spia diceva **"● in ascolto"** ma non si passava mai
a **"Trascrivo…"**, e non si sentiva né "Sì." né altro. L'audio del telefono era
alto: non era un problema di uscita.

La causa era la chiusura della frase. Le tre scadenze (fine del silenzio,
nessuno parla, tetto massimo) si guardavano **solo** dentro `onaudioprocess`.
Su iPhone quel callback può non arrivare mai: senza campioni nessuna condizione
veniva valutata, e la registrazione restava appesa **per sempre** — l'ascolto
acceso con l'aria di funzionare, e nessun suono perché non si arrivava mai alla
trascrizione.

Il rimedio: le scadenze sono una funzione **pura**, `fineRegistrazione`, e la
guardano da **due** punti — il callback dei campioni e un `setInterval` di
sicurezza (250 ms). Una sola regola, così i due controlli non possono divergere.
Il caso peggiore diventa "non ho sentito nulla", che almeno si sente.

Il test `test_la_registrazione_non_resta_appesa_senza_campioni` esegue
`ascoltaSulServer` **vera** con un `AudioContext` finto il cui callback non viene
mai invocato, e verifica che l'esito arrivi lo stesso: senza la correzione fallisce.
Due trappole del banco, già pagate: in Node `navigator` è un oggetto nativo e
**non si assegna** (serve `Object.defineProperty`), e il flag va messo
sull'**invocazione** del callback, non sulla sua assegnazione.


### Il cenno "Comandi.": chi parla deve sapere di essere stato sentito

Quando il comando arriva **insieme** alla sveglia ("Hey GG, metti il latte"),
l'app non risponde subito: fra la frase e l'esito passano i secondi della
trascrizione e dell'esecuzione. In quel silenzio chi ha parlato non sa se è stato
sentito, e in cucina, con le mani occupate, lo dice di nuovo — e il secondo
tentativo si somma al primo.

Il cenno chiude quel silenzio: un "Comandi." breve, subito, prima dell'esito.
Sta in `cennoDiRicevuto(azione)`, **puro**, e vale **solo** per `esegui`:

- chiamare e basta riceve già "Sì.", e due frasi per lo stesso caso
  confonderebbero;
- una frase ignorata non merita risposta: rispondere a tutto è il contrario
  dell'ascolto continuo, che deve tacere sul discorso di casa.

"Sì." per la chiamata e "Comandi." per l'ordine sono due frasi diverse per due
casi diversi: a orecchio si sente se l'assistente ha preso un ordine o ha solo
risposto.

Le due frasi vanno dette **in fila**, non insieme: `parlaEAttendi` aspetta che la
voce taccia prima di lasciar dire l'esito. `speak` da solo non basta, perché la
sintesi del browser annulla quello che sta dicendo e la voce neurale suona un
audio per volta — dette insieme, la seconda mangerebbe la prima. Anche qui c'è un
tetto (`TETTO_VOCE_MS`): se la sintesi non annuncia mai la fine, non si resta
appesi.

La frase della chiamata sta in `cennoDiChiamata()`, **pura** come
`cennoDiRicevuto`: era "Dimmi.", poi si è scelta "Sì." perché è più corta e
immediata — l'utente ha chiesto così. Il comando si dice subito dopo, nella
finestra aperta da `attendeComando`.

### La voce neurale avvisava la fine quando l'audio *cominciava*

Il difetto che faceva sembrare l'assistente "macchinoso" e che lo **bloccava dopo
il primo comando**. `Audio.play()` risolve all'**inizio** della riproduzione, non
alla fine: la promessa di `parlaCloud` si chiudeva subito, il segnale di "fine
parlato" (`avvisaFineParlato`) partiva mentre Azure stava ancora parlando, e il
microfono riprendeva **sopra** la voce. L'assistente si risentiva, si riconosceva
e il ciclo si incastrava — restando acceso con l'aria di funzionare.

Il rimedio: `parlaCloud` risolve su `'ended'` (o `'error'`), non su `play()`; e le
frasi di un messaggio lungo si dicono **in fila** con un `for await`, non con un
`forEach` che le sovrapponeva. Il test `test_la_voce_neurale_avvisa_la_fine_...`
esegue la funzione vera con un `Audio` finto ma fedele e guarda **quando** la
promessa si chiude: è l'unico modo per accorgersi di un difetto di *tempo*.

### Su iPhone la voce resta muta senza un gesto *recente*

Sintomo riferito: il microfono sente, ma l'assistente **non dice né "Sì." né
"Comandi."**. La causa è iOS: non lascia partire un elemento `Audio` creato senza
un gesto **recente**, e la voce neurale è proprio un `Audio` (`parlaCloud`).
Sbloccare l'`AudioContext` del "tin" non basta: **ogni elemento `Audio` ha il suo
sblocco**, e finora nessuno lo faceva per la voce.

Il rimedio è `sbloccaVoce()`: dentro ogni tocco sulla pagina si riproduce un WAV
**muto** (`SILENZIO_WAV`), che sblocca la riproduzione. Non si sente nulla. Va
fatto a **ogni** tocco, non una volta sola, perché il permesso di iOS vale per un
gesto recente; il "tin" invece resta una volta sola.

Attenzione al banco di prova: `--autoplay-policy=no-user-gesture-required` **maschera**
questo difetto. Nelle prove sul telefono va tolto.

### Col pannello chiuso non si vedeva niente: la riga `#voice-fuori`

Con l'ascolto continuo acceso il pannello e' **chiuso**, e la frase trascritta
(`#voice-heard`) e le conferme stanno **dentro** di esso. Chi parla col pannello
chiuso vedeva solo il pulsante colorato — e siccome l'ascolto continuo **tace**
sul discorso di casa, sembrava che l'assistente non avesse sentito, anche quando
aveva capito.

`mostraFuori()` scrive in `#voice-fuori`, una riga **fuori** dal pannello (sopra
il pulsante del microfono): "Ti ho sentito, dimmi." alla chiamata, "Ho sentito:
«…»" quando capisce, e l'istruzione sulla sveglia mancante quando serve. A
pannello **aperto** la riga si nasconde, altrimenti raddoppierebbe `#voice-heard`.

### Il comando partiva dopo la voce, e la finestra si consumava parlando

Due cause della latenza, entrambe visibili col telefono (Brave su Android).

1. **L'esecuzione aspettava la fine di "Comandi.".** `eseguiComandoContinuo` era
   `await parlaEAttendi(...)` e **poi** `eseguiComando`: il comando restava fermo
   per tutta la voce. Ora si **avvia subito** (`parla: false`, perche' l'esito lo
   dice il chiamante) e il cenno e l'esito si mettono in fila sulla voce **dopo**.
   Misurato: il comando parte 0,46 s dopo la risposta del server.
2. **La finestra dopo "Sì." si apriva prima di parlare** e si consumava mentre
   l'assistente diceva "Sì.". Con la voce neurale lenta, chi diceva il comando
   arrivava a finestra scaduta e veniva **ignorato in silenzio**. Ora la finestra
   si apre quando la voce **tace**: `parlaPoi(cennoDiChiamata(), () => { attendeComando(); riparti(); })`.

`eseguiComando` accetta `{ parla: false }` e **restituisce** la risposta (o
`null`): a chiamarlo dalla voce e' `eseguiComandoContinuo`, che parla l'esito una
volta sola. Il test `test_il_comando_parte_subito_senza_aspettare_la_voce` fissa
l'ordine: comando per primo, poi le due frasi in fila.

### I tempi del ciclo di ascolto: la reattivita' si sceglie, non si subisce

La trascrizione Azure e' veloce (~1,1 s per una frase breve): la lentezza che si
sente e' fatta di **attese del client**, e ognuna si somma. Tre tagli:

- **`ASCOLTO_FINE_MS` da 1600 a 800 ms.** E' il silenzio che chiude la frase, cioe'
  la pausa che si fa **dentro** una frase per prendere fiato: non serve lunga, e
  si aspetta prima di mandare la registrazione. Il tetto di "nessuno parla"
  (`ASCOLTO_ATTESA_MS`, 4000) resta piu' largo perche' copre anche l'inizio.
- **`SVEGLIA_RIPRESA_MS` da 700 a 250 ms e `CICLO_PAUSA_MS` = 120 ms** fra un giro
  e il successivo: quanto basta a lasciar chiudere il microfono, non un'attesa di
  comodo.
- **Le frasi fisse si preparano in anticipo** (`preriscaldaFrasiFisse`, chiamata
  da `caricaVoceCloud`): "Comandi." e "Sì." sono sempre le stesse, quindi si
  scaricano **senza riprodurle** all'avvio. Senza, ogni "Comandi." costava un giro
  di rete prima di sentirsi — il silenzio che si nota di piu' dopo aver parlato.
  L'audio di una frase si prende ora con `audioCloud` (memoria o server), separata
  da `parlaCloud` che la riproduce: il test del tempo di `parlaCloud` estrae
  entrambe.

### L'assistente inutile da telefono e da certi browser: tre rimedi

Il sintomo riferito — «l'assistente vocale e' inutile da smartphone e da vari
browser per pc» — non era il riconoscimento (Azure trascrive bene: misurato con
un round-trip sintesi→trascrizione, «aggiungi due chili di farina in dispensa»
torna identico). Era tutto intorno: **contesto sicuro**, **ripiego silenzioso** e
**interfaccia del pulsante**. Tre rimedi, scelti dall'utente.

1. **`voce.senzaMicrofono` (`apriVoce`).** Da un indirizzo non sicuro
   `getUserMedia` non arriva: l'app **non tenta a vuoto**, dice cosa manca e porta
   il cursore al campo di testo (`mostraSenzaMicrofono`). Prima apriva un
   microfono che non avrebbe mai sentito.
2. **Push-to-talk (`modoParla`, `collegaPushToTalk`, `#voice-parla`).** Si
   **tiene premuto** e si invia al rilascio, su **ogni** dispositivo: il vecchio
   interruttore col mouse è stato tolto, perché il secondo tocco per inviare a
   mani occupate non si dà. `modoParla()` restituisce sempre `'push'`.
   `collegaPushToTalk(btn, { tocco })` è l'unico punto che lega un pulsante al
   gesto (`pointerdown`/`up`/`cancel`/`leave`) e lo usano `#mic`, `#home-mic`,
   `#voice-parla` e `#voice-retry`: prima il wiring era duplicato e il microfono
   flottante apriva solo il pannello. Un tocco **breve** (`PTT_TOCCO_MS`, 300 ms)
   non è una frase: se il pulsante ha un `tocco` lo chiama (il microfono flottante
   apre il pannello), così chi voleva solo aprire non resta con un "non ho sentito
   nulla". La barra del livello dice che il microfono manda audio davvero.
   `guardaSeRilascia` tollera il dito che scorre fuori dal pulsante
   (`setPointerCapture` piu' 40 px di margine): senza, la frase si perderebbe
   proprio mentre si parla. La corsa «dito alzato prima che il microfono si apra»
   si chiude con `voce.rilasciato`, altrimenti un tocco brevissimo aprirebbe il
   microfono per 12 s. In push-to-talk **il silenzio non chiude la frase** (chiude
   il rilascio): il tetto `ASCOLTO_MAX_MS` resta come rete di sicurezza. E
   `apriVoce()` **non** apre più il microfono da solo: mostrerebbe un ascolto
   senza rilascio, che non finisce mai.
3. **«Prova il microfono» (`provaMicrofono`, `#voice-prova`).** Un pulsante che
   verifica in fila contesto sicuro, API, permesso, stato dell'`AudioContext` e
   chi trascrive, poi registra una frase e **mostra cosa ha sentito**. Il ramo
   `voce.provaMicrofono` intercetta l'esito **prima** di `eseguiComando`: chi prova
   vuole sapere se il microfono funziona, non scrivere in dispensa. `audioSbloccato`
   mette un tetto a `resume()` perche' senza gesto puo' non risolversi mai.

Le funzioni di regola (`verdettoMicrofono`, `modoParla`/`guardaSeRilascia`) sono
**pure**, quindi si provano con node senza browser. Il test
`_ascolta_senza_campioni_js` esegue `ascoltaSulServer` **vera**: il suo finto DOM
deve conoscere i nuovi helper (`aggiornaParla`, `mostraLivello`, `$` con `focus`),
altrimenti il test fallisce per un motivo che non c'entra.

**Le informazioni tecniche passive sono state tolte** su richiesta dell'utente:
la riga «chi ascolta» (`voice-stato-ascolto`), l'avviso «voce robotica / dove
mettere la chiave» (`voice-chiave-manca`), l'avviso sul contesto non sicuro
(`voice-avviso-sicurezza`) e il **registro dell'assistente** (`voice-registro` e
`registra()`). Erano diagnostica dello sviluppatore in faccia a chi usa l'app: chi
parla vuole parlare, non sapere se trascrive Azure o il browser. Restano solo i
messaggi *attivi* — cosa fare quando il microfono non c'e' (il campo di testo) e
la conferma del comando. Il test
`test_il_pannello_non_riporta_informazioni_tecniche_su_ascolto_e_voce` li tiene
fuori.

Resta il limite che **nessuna di queste modifiche risolve**: il telefono ha bisogno
di HTTPS per il microfono, e questo si ottiene solo con il Funnel Tailscale sul PC
di casa (`windows\dominio.bat`) o un proxy TLS. E' la strada A, e va fatta sulla
macchina sempre accesa, non nell'app.

## Convenzioni — voce e comandi

- I comandi vocali stanno in `voice.py` e non nel frontend: il browser si limita a
  dettare testo (o a registrare l'audio, vedi sotto) e a mandarlo a
  `POST /api/voice`, così la comprensione è testabile senza microfono. `parse()`
  riconosce gli intenti `pantry_add`, `shopping_add`, `storage_add`, `term_add`,
  `event_add`, `recipe_search`, `recipe_add` e restituisce `unknown` quando non
  capisce. Le unità
  si aggiungono in `_UNIT_TOKENS`, le parole di comando in `_COMMAND_VERBS`, le
  destinazioni in `_find_destination`. Una frase senza verbo, destinazione o
  quantità è rumore di fondo e deve restare `unknown`: il microfono sente anche i
  discorsi in cucina e le voci inventate in lista sono peggio di un comando non
  capito.
- **Gli impegni si programmano a voce** (`event_add`). "ricordami il dentista
  domani alle 15" crea un impegno nel Calendario, con data, ora, categoria e
  promemoria: è l'unica capacità vocale che *scrive* nel calendario, ed è nata
  perché programmare un promemoria è esattamente il momento in cui si hanno le
  mani occupate. La comprensione sta in `voice.py`; l'esecuzione in
  `app._esegui_impegno`, che riusa `calendario` (categoria che ricade, ora
  tollerante, `promemoria_giorni`) e risponde con "domani/fra N giorni" e se
  avvisa. Tre guardie, tutte per non trasformare chiacchiera in appuntamenti:
  serve **una data vera oppure un'ora** (senza, non c'è niente da programmare);
  i verbi di promemoria si dividono in **forti** (`ricordami`, `fissami`,
  `programma`) e **deboli** (`segnami`, `segna`, che valgono solo con una data o
  con la parola "impegno"); e i verbi di comando della spesa/dispensa vincono
  ("metti il latte domani" resta una voce di lista). I verbi forti vanno tolti
  dal controllo generico `_COMMAND_VERBS`, altrimenti "ricordami il dentista
  domani" resterebbe una spesa. Le date dette si leggono in `_data_detta`
  ("domani"/"dopodomani", giorno della settimana, "25 dicembre", `12/03`), le ore
  in `_ora_detta` ("alle 18", "di sera"), il promemoria in `_promemoria_detto`
  ("una settimana prima"). Nel percorso col modello, `comprensione._ripulisci`
  **valida la data ISO**: una data inventata scarta l'impegno invece di
  programmarlo nel giorno sbagliato. Nel client i verbi forti sono in
  `VERBI_COMANDO` (la finestra dopo "Sì." li accetta) e `reload: ["calendario"]`
  apre la scheda del Calendario, dove `renderCalendario()` lo mostra.
- **Le parole di comando non sono alimenti.** Lo stesso guasto delle domande, per
  un'altra strada: "fammi la spesa" non dice *cosa* comprare, e senza guardia il
  verbo "fammi" finiva in lista come articolo. I verbi (`fai`, `fammi`, `vedere`,
  `dammi`...) stanno in `_STOPWORDS`, e **ogni parola della destinazione** viene
  saltata (`_DEST_TOKENS`), non solo "magazzino" come prima: "aggiungi il latte
  alla spesa" è "latte", non "latte spesa". Aggiungendo un verbo a `_COMMAND_VERBS`
  va aggiunto anche qui, altrimenti diventa un alimento.
- **`fai` e `fammi` sono verbi di creazione ricetta**, come `crea` e `prepara`: è
  così che si chiede una ricetta parlando ("fai una ricetta di lasagne"). Ma
  "fammi **vedere**" non crea niente: `_RICETTA_GUARDA` tiene fuori i verbi di
  consultazione, altrimenti una richiesta di lettura aprirebbe il modulo di una
  ricetta nuova.
- **L'ascolto passa dal server, non più dal browser.** La Web Speech API manda
  l'audio ai server di Google, e in molte case quel traffico è bloccato (firewall,
  antivirus, VPN): Chrome risponde `network` e il microfono resta muto senza
  rimedio, perché il problema non è nell'app. Il server invece esce, quindi il
  browser **registra** con `getUserMedia` e manda i byte a `POST /api/voce/ascolta`;
  a trascrivere è `voce_cloud.trascrivi`, con la stessa chiave della sintesi. La
  Web Speech API resta come **ripiego**, per quando la chiave non c'è: l'endpoint
  risponde 503 e il client passa al browser senza mostrare un errore. Il flag
  `ascolto` in `GET /api/voce/config` decide la strada, e sbagliarlo riporta il
  microfono al guasto che si vuole evitare. Non "sistemare" la trascrizione nel
  browser: è il browser che non può, non la sua configurazione.
- **L'audio breve di Azure accetta due soli formati**: WAV PCM 16 kHz mono, oppure
  OGG Opus. Il browser produce di suo un webm/opus, che non è fra questi, quindi
  `wavDaCampioni` (`static/app.js`) scrive l'intestazione WAV a mano — poche righe,
  nessuna libreria — e `aSediciKhz` porta i campioni a 16 kHz (il microfono non
  consegna sempre la stessa frequenza). L'endpoint riceve il WAV **grezzo** nel
  corpo, non in JSON: in base64 crescerebbe di un terzo per nulla. Il test
  dell'intestazione esegue la funzione vera con node e legge i byte: un test sulle
  stringhe non accorgerebbe di un byte sbagliato, che il servizio rifiuterebbe con
  un 400 indistinguibile da un guasto.
- L'ascolto si ferma **da solo**: dopo ~1,6 s di silenzio, o dopo un tetto di 15 s.
  Senza, il microfono resterebbe aperto finché non lo si chiude a mano, e la frase
  non partirebbe mai. La soglia di voce (`ampiezza`) è un **picco**, non una media:
  una media su blocchi quasi muti resta a zero anche parlando.
- Un audio senza parlato non è un errore: `trascrivi` restituisce stringa vuota e
  il client dice "non ho sentito nulla". Solo i guasti veri (chiave, area, rete)
  sollevano `ErroreAscolto`, altrimenti il ripiego sul browser scatterebbe anche
  quando non serve. Sotto `MIN_AUDIO_BYTE` non si chiama nemmeno Azure: un
  microfono aperto per sbaglio non deve costare una chiamata.
- `recipe_add` è l'unico intento che **non scrive niente**: risponde con
  `open_recipe_form` e il client apre il modulo della ricetta col nome già dentro.
  Una ricetta creata a voce senza ingredienti né preparazione sarebbe una scheda
  vuota da ripulire, quindi la voce fa il lavoro noioso — aprire il modulo e
  scrivere il nome — e il resto resta all'utente. Perché scatti servono **sia** la
  parola "ricetta" **sia** un verbo di novità (`_RECIPE_VERBS`): "aggiungi" da solo
  è una spesa, "ricetta" da sola è una ricerca. Una destinazione esplicita vince
  sempre ("nel carrello"), e "ricetta" non può restare nel nome di un ingrediente:
  senza queste due guardie "aggiungi la ricetta carbonara" diventa una voce di
  lista chiamata "ricetta carbonara", che è il motivo per cui l'intento esiste.
  Il nome si ripulisce in `_nome_ricetta`, che toglie i riempitivi ovunque ma
  articoli e preposizioni solo ai bordi: dentro il nome sono parte di esso
  ("pasta al forno", "risotto ai funghi"), fuori sono avanzi di discorso.
- **Chi detta una ricetta detta anche gli ingredienti, e le dosi non sono il
  titolo.** "crea la ricetta pasta al forno con 500 grammi di pasta" senza la
  separazione diventava una ricetta **chiamata** "pasta al forno con 500 grammi di
  pasta": la voce sembrava aver capito, mentre l'unica cosa utile — gli
  ingredienti — finiva nel nome e andava persa. `_nome_da_ingredienti` decide dove
  finisce il nome e `_ingredienti_da_dettato` legge le dosi, che il client
  precompila nelle righe del modulo. Il segnale è **il numero con l'unità** oppure
  "con" + un numero: il solo numero non basta, altrimenti "crea la ricetta torta 7
  vasetti" diventerebbe una ricetta chiamata "torta". La virgola che si scriverebbe
  dettando ("guanciale, 4 uova") **non arriva** dal riconoscimento vocale, quindi
  un numero che apre dopo un ingrediente già completo vale come ingrediente nuovo.
  Cercando online gli ingredienti dettati non si usano: arrivano dal sito e
  sostituirebbero quelli.
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
- **La scheda «Voce» delle FAQ e' stata rimossa**: timbro, voce di sistema, voce
  neurale e suono non hanno piu' un pannello. Le preferenze restano in
  `localStorage` col loro comportamento predefinito, e il codice che le legge e'
  null-safe o centralizzato (`confermaVoce()`). Anche l'interruttore della
  comprensione col modello non c'e' piu': e' stato tolto dal Profilo e la
  comprensione e' ora **sempre attiva** (vedi «Capire i comandi»). La voce
  naturale Azure resta attiva quando il server ha la chiave (`cloudAttivo()` =
  `voceCloud.disponibile`): si spegne togliendo la chiave, non da una casella.
  **Attenzione alle chiamate che restano.** Togliendo la scheda era stata rimossa
  la funzione `caricaVoci`, ma due chiamate erano rimaste in `init()`: il
  ReferenceError scatta **dopo** che il login e' riuscito, quindi finisce nel
  `catch` di `avviaApp` e l'utente, appena entra, resta sulla schermata di accesso
  ("l'app si blocca e si chiude"). Un test che non esegue `init()` intera non lo
  vede; ora `test_app_js_non_chiama_funzioni_che_non_esiste` scandisce `app.js` e
  pretende che ogni funzione chiamata esista. Rimuovendo una funzione, cercarne
  **tutte** le chiamate.
  **Due reti chiudono quel buco.** (1) `erroreNonGestito` e' legato a
  `window.onerror` e `unhandledrejection` in cima ad `app.js` (l'ascolto e' a
  livello di modulo, quindi copre anche `avviaApp()` in fondo): un errore a
  runtime produce un avviso breve (`toast`), con la raffica limitata a un avviso
  per volta e senza nome dell'eccezione ne' traccia a schermo. (2) `avviaApp()` distingue i due guasti: se la **sessione** non
  risponde si mostra l'accesso (non si sa chi e' collegato), ma se la sessione
  c'e' e `init()` fallisce l'utente **resta dentro** con l'avviso `#errore-app` e
  "Ricarica" — rimandarlo all'accesso gli farebbe credere di aver sbagliato la
  password. Il banner sta fuori da `#app` (si vede anche con la home aperta) e
  sotto i modali (`z-index` 45).
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
