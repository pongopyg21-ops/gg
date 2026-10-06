# Il Maggiordomo — note per gli agenti

## ⭐ SEI APPENA ARRIVATO? Leggi qui (versione V.8)

Questa è la **V.8**. Il progetto è **maturo e funzionante**: non serve riscrivere
niente, serve **continuare**. Prima di tutto:

1. Avvia: `./avvia.sh` (all'inizio di ogni conversazione il server **non** è
   attivo: il container viene ricreato, è normale). Avvia anche la sorveglianza,
   quindi non serve più lanciare `./sorveglia.sh` a parte.
2. Test: `./avvia.sh test` → attesi **662 verdi**. Se non lo sono, fermati e dillo.
3. Il branch è **`main`** (definitivo; il vecchio `gg` è stato cancellato locale e
   remoto). Push: `./avvia.sh pubblica` (si autentica da solo: chiave SSH in
   `/workspace/ssh` o `GITHUB_TOKEN`).
4. Stato dell'ultima verifica e **cosa è stato chiuso nella sessione precedente**:
   `/workspace/CONSEGNA-MAGGIORDOMO-V8.md`. Leggilo: contiene i fili aperti.
5. **Dati delicati** (non in git, non si ricostruiscono): `cucina.db`, `houses.db`,
   `case/`, `copie/`, su `/workspace`. L'unico salvataggio vero è `/api/backup`.

**La chiave Azure qui va fra i segreti della conversazione, non in `segreto.txt`.**
Il container viene ricreato dal repository a ogni conversazione, quindi i file
ignorati da git — `segreto.txt`, `segreto` — spariscono ogni volta. Chi la scrive
nel file la riscrive a ogni sessione senza capire perché sparisce: è già successo
sei volte. La via che regge è registrarla come segreto col nome esatto
`AZURE_SPEECH_KEY` (e, se serve, `AZURE_SPEECH_REGION`); il sistema la esporta a
ogni comando e `./avvia.sh` la trova. `./avvia.sh diagnosi` deve dire
`da: ambiente`. Su una macchina propria, invece, il file accanto al programma è
la via normale e non sparisce.

**Il segreto si esporta solo per i comandi che ne scrivono il nome.** L'iniezione
scatta sul **nome esatto** che compare nel testo del comando: `./avvia.sh restart`
da solo non basta, e il server riparte **senza** la chiave — l'app dice "il browser
non riesce a raggiungere il servizio di ascolto" e sembra un firewall, mentre è
solo un riavvio senza chiave. Per riavviare con la voce attiva:

    AZURE_SPEECH_KEY="$AZURE_SPEECH_KEY" AZURE_SPEECH_REGION="$AZURE_SPEECH_REGION" ./avvia.sh restart

Il segno che è andata bene: `avvia.sh` stampa `voce neurale Azure attiva`. Un
nome generico (`AZURE_SPEECH`) **non** innesca l'iniezione: va scritto il nome
registrato per intero.

**Fili aperti**: (a) la casa `Gian` è stata rimossa dal registro su richiesta
dell'utente; il file `case/case-gian.db` resta su disco (scelta voluta, vedi
`houses.elimina`), quindi se un domani servisse si può ancora registrare; (b) la
voce è confermata **da desktop**, manca il riscontro **dal telefono**; (c) il link
stabile è quello di Tailscale (`windows/dominio.bat`), perché il link del sandbox
muore con la conversazione.

## Architettura

App Flask + SQLite + SPA in JS puro. Backend in `app.py`, case separate in
`houses.py`, conversione unità in `units.py`, riconoscimento allergeni in
`allergens.py`, comandi vocali in `voice.py`, comprensione facoltativa col
modello in `comprensione.py`, dati iniziali in `seed.py`, pulizie
in `igiene.py`, informazioni utili in `faq.py`, magazzino in `magazzino.py`,
suggerimenti dalla dispensa in `dispensa.py`, video e notizie in `tv.py`,
locandine dei film in `cinema.py`,
impegni e promemoria in `calendario.py`.

L'app si apre su una **pagina iniziale** che smista verso cinque sezioni:
**Cucina**, **Igiene**, **Appunti**, **FAQ**, **TV**. Piano, ricette,
dispensa, spesa, profilo e comandi vocali stanno in **Cucina**; le pulizie stanno
in **Igiene**; **Appunti** raccoglie lavori e idee da fare ed è anche la casa del
**Calendario** degli impegni e del **Magazzino**; **FAQ** raccoglie le
informazioni utili da consultare (Wi-Fi, indirizzi, contatti, codici); **TV**
raccoglie l'intrattenimento in **cinque schede** (Intrattenimento, Notizie, Quiz,
Film, Giochi): i video della playlist di casa, le notizie dal mondo
(vedi `tv.py`), il quiz e i giochi (Snake, vedi `static/snake.js`) e le locandine
dei film del momento sulle piattaforme di streaming, una alla volta (vedi
`cinema.py`). Il **Cinema** non ha più una sezione sua:
è intrattenimento come i video e le notizie, e sta dentro la TV. Il **GYM**
resta invece una sezione a sé, perché è una cosa diversa — si guarda *per fare*,
non per passare il tempo.

## Comandi

```bash
./avvia.sh                               # avvia server + sorveglianza
./avvia.sh restart                       # ferma e riavvia tutto
./avvia.sh stop                          # ferma server e sorveglianza
./avvia.sh status                        # attivo? su quale porta? sorveglianza?
./avvia.sh sorveglianza                  # (ri)accende solo la sorveglianza
./avvia.sh log                           # ultime righe del log
./avvia.sh test                          # test nella venv del progetto
./sorveglia.sh                           # equivalgono a './avvia.sh sorveglianza'
./sorveglia.sh status                    # sorveglianza attiva? server su?
```

`MAGGIORDOMO_SENZA_SORVEGLIA=1 ./avvia.sh` avvia il solo server, senza
sorveglianza (per un debug in primo piano).

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

Il progetto definitivo e' il branch **`main`**. Fino a un certo punto il lavoro
stava su `gg` (piu' avanti, ma non definitivo) e `main` era indietro; ora `main`
**contiene tutto**, `gg` **non serve piu'** ed e' stato cancellato. Un clone
normale prende `main`, che e' la versione giusta: non c'e' nessun `git checkout`
da fare.

```
git clone https://github.com/pongopyg21-ops/gg.git
cd gg
```

Da qui `./avvia.sh` trova tutto. Non serve altro.

Il push va fatto sul branch **`main`**, e va verificato **sul server**, non in
locale: `git ls-remote origin` mostra il commit che GitHub ha davvero. `git fetch`
puo' lasciare `origin/main` vecchio, e allora un push riuscito sembra fallito (o il
contrario), con il rischio di credere pubblicato un lavoro che non c'e'.

C'e' un comando solo per questo, `./avvia.sh pubblica`: fa il push e confronta con
`ls-remote`, cosi' l'esito **dice il vero**. Si autentica **da solo**, scegliendo:

1. la **chiave SSH** in `/workspace/ssh/config` (una *deploy key* del repo con
   "Allow write access"). La chiave vive **fuori dal repository**, quindi non puo'
   finire in git. E' il modo che funziona anche quando i segreti non arrivano:
   il segreto `GITHUB_TOKEN` viene iniettato **all'avvio della conversazione**, e
   aggiungerlo a conversazione gia' avviata non lo fa comparire (verificato:
   `${#GITHUB_TOKEN}` resta 0 anche nominandolo);
2. il **token** dall'ambiente (`GITHUB_TOKEN`, o `GH_TOKEN`), come alternativa.
   Non entra nella URL ne' negli argomenti: passa da un `GIT_ASKPASS` temporaneo,
   che si cancella subito. Un errore di push puo' stampare la URL, e in un log di
   conversazione il token resterebbe.

**Attenzione al token "presente ma vuoto".** In questo ambiente `GITHUB_TOKEN` e'
sempre *definita* (il sistema dei segreti la esporta quando la si nomina), ma se
il segreto non e' registrato il valore e' la stringa vuota: `[ -n "$GITHUB_TOKEN" ]`
lo scopre, un semplice `echo` sembra che ci sia. E' il motivo per cui dei commit
sono rimasti non pubblicati credendo che il token ci fosse.

Se manca sia la chiave sia il token, `pubblica` lo dice e si ferma, invece di
fallire con un errore di git che sembra un problema di rete. Il percorso della
chiave si puo' cambiare con `MAGGIORDOMO_SSH_CONFIG`, che serve ai test per provare
il caso "nessuna credenziale" senza fare un push vero.

Per **rigenerare** la chiave, se serve: `ssh-keygen -t ed25519 -N "" -f
/workspace/ssh/deploy_key`, poi si aggiunge `/workspace/ssh/deploy_key.pub` come
deploy key su GitHub (spuntando "Allow write access"). `openssh-client` non e'
nell'immagine di base: si installa con `sudo apt-get install -y openssh-client`
(`sudo` non chiede la password).

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
in piedi entrambi: è il primo comando da provare, sempre. È cambiato proprio per
questo: dopo ogni ricreazione il link restava a 502 perché la sorveglianza andava
riaccesa a mano ed era il passo che si dimenticava. Ora `./avvia.sh` la tira su
da solo, e `./avvia.sh stop`/`restart` la fermano prima del server (se restasse
su, vedrebbe il server sparire e lo riavvierebbe subito, annullando lo `stop`).

`sorveglia.sh` copre il caso diverso, quello in cui **solo il server** cade
mentre l'ambiente resta vivo: controlla la pagina ogni 15 secondi e riavvia se
non risponde, con `flock` per non duplicare un `avvia.sh` già in corso. Quando
richiama `./avvia.sh`, questo non deve riaccendere a sua volta la sorveglianza:
lo script esporta `MAGGIORDOMO_SORVEGLIA_GIRO=1`, e `avvia_sorveglianza()` lo
vede e non fa niente. Senza quel freno si riavvierebbe all'infinito — c'è un test
manuale da fare dopo ogni modifica a questi due script: `./avvia.sh`, poi
`kill -KILL` del server, e verificare che torni su **con un solo sorvegliante**
(`pgrep -fa "sorveglia.sh --giro"` deve contarne uno). Scrive sul
log solo quando interviene, così un log non vuoto è già un'informazione.

**Se l'utente dice che l'app "prova a connettersi senza riscontro", la prima cosa
da controllare è `./avvia.sh status` o `./sorveglia.sh status`.** È il sintomo
esatto di un server morto
a metà sessione: la pagina non carica e sembra un guasto dell'app, mentre è solo
il processo che non c'è più. Non è l'app a essere lenta: la pagina iniziale pesa
~18 KB e `app.js` ~109 KB, e il server locale risponde in circa 1 ms. Qualunque
attesa di minuti non viene dall'app.

Non esiste in questa immagine un gancio di avvio automatico: niente `systemd`
(`systemctl` è presente ma `systemd` non è il PID 1), niente `cron` (`/etc/init.d/cron`
non esiste), e il processo 1 è l'agent-server di OpenHands, che non esegue script
del progetto. **Non perdere tempo a cercare dove agganciarsi**: non c'è, e la
ricreazione del container porterebbe comunque via qualsiasi cosa avviata qui.
La continuità vera (server che riparte da solo dopo un riavvio della macchina) si
ottiene solo su una macchina propria, con un servizio di sistema o
`docker run --restart unless-stopped`. Qui l'unica strategia sensata è:
all'inizio della conversazione `./avvia.sh`, che rimette su server e sorveglianza
insieme.

`cucina.db` non è versionato di proposito: a ogni ambiente nuovo va ricreato con
`seed.py` (ci pensa `avvia.sh`), e riparte l'onboarding. Non è una perdita.

**I dati veri invece non sono in git e non si rigenerano**: `cucina.db` (ricette,
dispensa, progetti di una casa) e `houses.db` (le case e le impronte delle
password) sono in `.gitignore`. Sono su `/workspace`, che è un volume montato a
parte (`/dev/nvme0n2`) e sopravvive alla ricreazione del container, ma **non**
sopravvive alla distruzione della macchina. Se l'utente ci tiene al lavoro fatto,
l'unico salvataggio è `/api/backup`, che scarica la casa collegata come file da
rimettere al suo posto senza rinominarlo. Vale la pena proporlo, non darlo per
scontato: chi ha passato giorni a riempire il ricettario non sa che il database
non è su GitHub.

## Configurazione

Tutto quello che si configura passa da variabili d'ambiente, lette **all'avvio**, non dal browser: la chiave del servizio vocale non deve mai arrivare al client.

| Variabile | A cosa serve | Valore assente |
| --- | --- | --- |
| `AZURE_SPEECH_KEY` | Chiave della risorsa Azure Speech | la voce neurale resta spenta, si usa quella del browser |
| `AZURE_SPEECH_REGION` | Area della risorsa (`westeurope`, …): determina l'indirizzo, non si può indovinare | come sopra |
| `AZURE_SPEECH_FORMAT` | Formato dell'audio richiesto | `audio-24khz-48kbitrate-mono-mp3` |
| `PORT` | Porta del server | 12000 |
| `CUCINA_DB` | Percorso del database della prima casa | `cucina.db` |
| `LLM_API_KEY` | Chiave del modello per comprendere i comandi (facoltativa) | si usa il parser a regole |
| `LLM_MODEL` | Modello da chiamare | `qwen2.5:7b-instruct` (modello di casa) |
| `LLM_BASE_URL` | Endpoint compatibile OpenAI | `http://127.0.0.1:11434/v1` (Ollama) |
| `LLM_TIMEOUT` | Secondi di attesa della risposta del modello | 60 (modello di casa) |

Le chiavi vanno messe prima di `./avvia.sh` e non finiscono mai nel repository. In alternativa si scrivono in un **file di testo** `segreto.txt` (o `segreto`, senza estensione) accanto a `app.py`, escluso da git, modello in `segreto.esempio.txt`. Forme accettate: `chiave: valore` / `chiave=valore` / `export chiave=valore` / il valore nudo su una riga — una parola tutta minuscola è l'area, il resto è la chiave, quindi l'ordine delle due righe non conta. Le etichette possono essere `chiave`/`area` (o `key`/`region`, `regione`). Restano validi anche `segreto.sh` e `segreto.bat` per chi li ha già. **L'app non le scrive**: non c'è un pannello né una rotta che salvi la chiave, perché il segreto non deve passare da una richiesta HTTP né essere riscritto da chi apre la pagina.

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

### L'area sbagliata sembra un guasto di rete

L'indirizzo del servizio contiene l'area — `<area>.tts.speech.microsoft.com` —
quindi un'area che non esiste è un nome che non si risolve: la richiesta non
parte e il messaggio è **"Servizio vocale non raggiungibile: getaddrinfo failed"**.
Parla di rete, ma è un refuso: si cerca il guasto dove non c'è.

Per questo `_controlla_area()` ferma la chiamata **prima** di provare, dove
l'errore si può spiegare: «L'area «italynorht» non esiste fra quelle Azure», con
la variabile da correggere. `AREE_VALIDE` è l'elenco delle aree Azure Speech;
`area_valida()` lo interroga. Vale sia per la sintesi sia per la trascrizione.

La stessa lezione delle voci: **si valida prima della chiamata**, perché l'errore
di Azure (o del sistema) è generico e non dice quale valore correggere.

## Accesso da ovunque

Il caso d'uso e' la cucina, ma serve anche **da fuori casa e da piu'
dispositivi**. Le vie sono due, e la differenza e' chi tiene la macchina accesa.

1. **Il computer di casa, con un tunnel HTTPS.** E' quello che fa
   `windows/dominio.bat` (Tailscale Funnel): da' un nome
   `https://<computer>.<rete>.ts.net` che **non cambia piu'** (`--bg` lo rende
   permanente) e non tocca il router. Vale finche' il computer e' acceso.
2. **Una macchina sempre accesa** (VPS, NAS, Raspberry Pi), per l'app davvero
   "da ovunque". C'e' un **`Dockerfile`**: l'immagine contiene **solo il codice**,
   i dati si montano da fuori (`-v ...:/dati`), e `--restart unless-stopped` fa da
   `sorveglia.sh`. `.dockerignore` tiene fuori database, copie e segreti, cosi'
   l'immagine si puo' anche pubblicare senza portarsi dietro niente di privato.

**`DIETRO_PROXY=1` quando c'e' un tunnel davanti.** Senza, `request.remote_addr`
e' l'indirizzo del proxy, e il **freno ai tentativi di accesso conta tutti su un
indirizzo solo**: chi sbaglia la password farebbe aspettare anche gli altri, e un
errore di distrazione diventerebbe indistinguibile da un attacco. Si attiva solo
quando il proxy c'e' davvero: fidarsi degli header senza proxy significa
lasciarli scrivere a chiunque. In cambio Flask legge `X-Forwarded-For`,
`X-Forwarded-Proto` e `X-Forwarded-Host` (`ProxyFix`).

L'app **non ha indirizzi assoluti** (nessun `url_for(_external)`, nessun
`http://` fisso nel client): per questo funziona dietro qualunque proxy senza
configurazioni. Un test lo tiene tale, perche' un link assoluto in `http://`
riporterebbe l'utente fuori dall'HTTPS — e li' il browser blocca il microfono.

**Il sandbox di sviluppo e' effimero.** Il link `work-1-...` risponde solo
finche' quella conversazione vive: se il container viene ricreato (succede, e si
riconosce da `/proc/uptime` di pochi secondi), i processi in background sono
morti e va rilanciato `./avvia.sh`. Non e' un guasto dell'app. Per un indirizzo
**stabile** non si usa il sandbox: si usa una delle due vie qui sopra.

## Windows

L'app di casa va su una macchina sempre accesa, e per l'utente questa e' Windows.
`avvia.sh` e' POSIX (bash, `venv/bin/python`, `setsid`): su Windows **non parte**, e
adattarlo con mille condizioni lo renderebbe illeggibile per entrambe le
piattaforme. Percio' `windows/` e' una traduzione, non una variante: fa le stesse
cose con gli strumenti di Windows.

- `windows\avvia.bat` — prepara l'ambiente (una venv separata, `.venv-win`, cosi'
  non si confonde con quella POSIX), installa le dipendenze, avvia il server e
  mostra i due indirizzi.
- `segreto.esempio.txt` — modello della chiave Azure in testo semplice, da copiare
  in `segreto.txt` (c'e' anche `windows\segreto.esempio.bat` per la forma a script).
- `windows\installa.bat` — registra un'**attivita' pianificata** che parte
  all'accesso e riavvia se cade.
- `windows\indirizzo.ps1` — trova l'indirizzo di rete.
- `windows\verifica-pubblico.bat` (+ `.ps1`) — controlla in una schermata se
  l'app e' raggiungibile **da fuori**: stato di Funnel, risposta su
  `127.0.0.1:12000`, e presenza di `DIETRO_PROXY=1` in `avvia.bat`. Non modifica
  niente e non tocca i segreti. Serve perche' le tre cause (tunnel, app spenta,
  proxy non dichiarato) si confondono fra loro, e il tunnel resta attivo anche
  ad app spenta.
- `windows\verifica-modello.bat` (+ `windows\modello.ps1`) — controlla se il
  modello di casa (Ollama) e' pronto: se risponde, se il modello che l'app si
  aspetta e' scaricato, e — quando tutto c'e' — che resta da accendere
  l'interruttore in **Profilo > Capire i comandi**. `avvia.bat` lo chiama a ogni
  avvio (poche righe, senza fermare la finestra). La configurazione si **chiede
  all'app** (`import comprensione`), non si riscrive nello script: due copie
  della stessa regola divergono, e allora lo stato all'avvio mente — la stessa
  scelta di `avvia.sh` per la voce Azure. Serve perche' il sintomo «il modello
  non capisce» ha tre cause (Ollama spento, modello non scaricato, interruttore
  spento) che danno lo stesso effetto, e l'interruttore spento — il piu'
  frequente, perche' parte a `0` — non produce nessun avviso.

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
- **Il repository e' pubblico, quindi la chiave Azure sta in `segreto.bat`.** Il
  codice sta su GitHub, `avvia.bat` compreso: una `set AZURE_SPEECH_KEY=...` scritta
  li' finirebbe pubblica al primo push. `windows/segreto.bat` e' in `.gitignore` e
  `avvia.bat` lo chiama con `call` se esiste, quindi la chiave resta sulla macchina
  e il comportamento senza chiave non cambia (voce del sistema).
- **Il branch e' `main`.** Un clone normale lo prende gia': non c'e' nessun
  `git checkout` da fare, e `windows/` c'e'. (Il vecchio branch di lavoro `gg` e'
  stato cancellato: non serve piu'.)
- **Il percorso principale non richiede Git: e' lo ZIP del branch.** L'utente ha
  provato `git clone` e ha ricevuto "Termine 'git' non riconosciuto" - Git non e'
  installato, e per un'app che si scarica una volta non vale la pena installarlo.
  L'indirizzo e' `https://github.com/pongopyg21-ops/gg/archive/refs/heads/main.zip`,
  e lo ZIP **non contiene i database**, quindi aggiornare l'app non tocca i dati.
  Un problema in meno e' un utente che arriva in fondo: le istruzioni partono da
  li', Git resta alternativa.
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

### Copie automatiche (`copie.py`)

Il pulsante salva solo chi si ricorda di premerlo, quindi esiste anche una copia
che non si deve chiedere: **una al giorno, le ultime sette**, in `copie/<slug>/`
dentro `DATA_DIR`. `app.avvia_copie_automatiche()` ne fa una subito all'avvio e
poi ci riprova ogni ora; `copie.fai_copie(forse=True)` salta le case la cui copia
e' gia' recente, quindi le ore passano senza produrre copie inutili.

Tre cose che sembrano dettagli e non lo sono:

- **Il primo giro parte subito.** Se la prima copia aspettasse un giorno, un
  server appena installato non avrebbe nessuna copia proprio nel momento in cui
  serve. Un test lo verifica.
- **Scrittura atomica.** La copia si fa su `<nome>.tmp` e si rinomina solo a
  lavoro finito. Un file a meta' col nome di una copia buona e' la trappola
  peggiore: la si crede valida fino al giorno in cui serve.
- **Il thread non deve far cadere il server.** `_giro_di_copie()` cattura tutto e
  scrive nel log: un disco pieno non deve diventare un errore visibile a chi
  stava solo guardando la dispensa.

`GET /api/copie` dice quante ce ne sono e quando e' l'ultima, **della sola casa
collegata**, e il Profilo lo mostra sotto il pulsante del salvataggio. Senza quella
riga l'utente vedrebbe solo il pulsante e crederebbe di non avere nessuna copia.

Nei test la cartella delle copie va isolata come il registro: `houses.DATA_DIR`
puntato al temporaneo, altrimenti i test scrivono nei dati veri dell'app. La
fixture `percorsi_dei_dati` (autouse) rimette a posto i percorsi prima di ogni
test, perche' un test ricarica `houses` e al ritorno li riporta accanto al codice.

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

### Errori: sempre in italiano, e con una traccia nel log

C'e' un gestore di errori di riserva: `app._errore_imprevisto` registra
l'eccezione con `app.logger.exception` e risponde in italiano, e
`app._errore_http` fa lo stesso per i codici previsti (404, 405, 413...). Prima
non c'era niente: l'utente vedeva la pagina di Flask **in inglese** — e
l'interfaccia e' tutta in italiano — e nel log non restava traccia di cosa fosse
successo, quindi un guasto era irripetibile.

Due regole:

- **L'API risponde JSON, la pagina risponde HTML.** Un chiamante dell'API si
  aspetta `{error: ...}`: mandargli l'HTML della pagina lo farebbe rompere con un
  errore di analisi al posto del messaggio. La distinzione e' su `request.path`.
- **Il testo e' breve e senza il nome dell'eccezione ne' la traccia.** Quella
  resta nel log; sulla pagina confonderebbe e basta.

`app._prepara_log()` manda tutto su `stderr`, che `avvia.sh` raccoglie gia' in
`server.log`: un secondo file di log sarebbe un posto in piu' da guardare. Il
logger e' `propagate = False`, altrimenti lo stesso errore comparirebbe due volte.

Nei test i fallimenti di proposito si verificano con `caplog` (`logger="app"`):
si controlla che il messaggio *arrivi nel log*, non che esista una chiamata.

### Tentativi di accesso: un freno, non un muro

Le password sono in PBKDF2 con sale, ma nulla impediva di provarle all'infinito:
il server ascolta su `0.0.0.0` per farsi raggiungere dal telefono, quindi chi e'
sulla stessa rete poteva continuare per giorni. Il freno sta in `houses.py`
(`attesa_accesso`, `segnala_fallimento`, `segnala_successo`): fino a
`TENTATIVI_LIBERI` errori non si aspetta, poi l'attesa raddoppia (1s, 2s, 4s...)
fino a `ATTESA_MASSIMA`. Dopo `DIMENTICARE_DOPO` senza errori il contatore si
azzera da solo.

Le due scelte che contano:

- **Si contano due chiavi, l'indirizzo e il nome provato.** Solo l'indirizzo non
  basta: dietro un tunnel tutti i dispositivi risultano lo stesso IP e un errore
  di uno farebbe aspettare gli altri. Solo il nome non basta: chi prova nomi
  diversi non verrebbe mai fermato. Vince l'attesa piu' lunga.
- **Nessuna attesa fa dormire il server.** Si risponde subito con `429` e il
  numero di secondi ("Troppi tentativi: riprova fra 3 secondi"), e aspetta il
  browser. Un server che dorme tiene occupato un filo, e con `waitress` a 8
  thread pochi tentativi in parallelo lo farebbero sembrare piantato.

L'accesso riuscito azzera il contatore. Attenzione: **mentre il blocco e' attivo
anche la password corretta viene respinta**, ed e' voluto — e' tutto il senso del
freno. I test lo verificano restando sotto la soglia, perche' sopra soglia non si
puo' passare.

## Case separate

Ogni **casa** ha il suo database: ricette, dispensa, piano, spesa, pulizie, FAQ,
progetti e magazzino non si vedono fra case diverse. La separazione è un **file di
database distinto** (`case/case-<slug>.db`), non una colonna `house_id`: le tabelle
sono diciassette e le query cinquanta, e una colonna dimenticata da qualche parte
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
- **Una casa nasce sempre col ricettario, anche se il file era sparito.** `get_db()`
  passa `con_ricettario=True` quando il database va creato adesso (file assente o
  vuoto). Senza, una casa registrata il cui file manca — ripristino parziale,
  copia rimessa nel posto sbagliato — si ricreava vuota, e l'utente non aveva
  nessuna ricetta da scegliere nel piano pasti. Il seme però non si rifà su un
  database esistente con zero ricette: quello è uno stato voluto da chi le ha
  cancellate, e ripopolarlo sarebbe un dispetto.
- **`migra_case()` scarta il `cucina.db` vuoto.** Un file con lo schema ma senza
  nessun dato non è il lavoro di mesi: `app.prepara_database_storico()` evita di
  crearlo dal nulla quando non c'è nessuna casa, e `migra_case()` non adotta un
  guscio vuoto (`_database_ha_dati`). Era una trappola in due tempi: primo avvio
  creava `cucina.db`, secondo avvio lo registrava come casa "Casa" senza niente
  dentro. Il controllo su "qualche dato" e non "qualche ricetta" è voluto: c'è
  chi usa l'app solo per le FAQ, e scartare il suo file lo lascerebbe senza
  accesso. `chores` è escluso dal controllo perché le voci le semina lo schema.
  Il controllo è sicuro perché lì il registro è vuoto per costruzione: per
  svuotare il database servirebbe una casa, e una casa lo renderebbe non vuoto.
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
- **Le preparazioni sono dettagliate, a passi.** Il testo di `instructions` sta in
  `RECIPES` (unica fonte: non esiste un secondo dizionario di preparazioni) ed è
  scritto su paragrafi separati da una riga vuota, perché il client lo mostra come
  elenco numerato (`passiDa` in `static/app.js` divide anche sulle frasi). Almeno
  quattro passi, con tempi e temperature espliciti: «inforna a 180°C per 40
  minuti», non «cuoci». Una preparazione di una frase sola diventa un passo unico e
  non serve a chi cucina; i test `test_ogni_ricetta_ha_una_preparazione_dettagliata`
  e `test_le_preparazioni_dettagliate_escono_come_passi` (quest'ultimo esegue
  `passiDa` vera con node) lo tengono fermo.
- **Le preparazioni arrivano anche ai database esistenti, senza cancellare il
  lavoro dell'utente.** `PREPARAZIONI_PRECEDENTI` è la fotografia dei testi com'era
  prima di essere riscritti, e `semina()` sostituisce `instructions` **solo se è
  ancora esattamente quella vecchia**: una preparazione riscritta a mano è un dato
  dell'utente e non va sovrascritta. È la stessa cautela dell'aggiornamento dei
  minuti in `igiene.py`: le stime ritoccate a mano non si riallineano mai. Senza,
  chi usa l'app da prima vedrebbe i testi nuovi solo creando una
  casa nuova, e chi ha riscritto la ricetta di famiglia se la vedrebbe cancellare.
  Aggiungendo un testo nuovo a `RECIPES`, va aggiunto il testo vecchio anche a
  `PREPARAZIONI_PRECEDENTI`, altrimenti l'aggiornamento non scatta.
- **Ogni ricetta del ricettario ha una foto**, e la foto è un file in
  `static/recipes/` registrato in `PHOTOS` (`seed.py`) con il suo credito. Il test
  `test_ogni_ricetta_ha_la_sua_foto` verifica tre cose insieme: la voce esiste, il
  file esiste davvero su disco, e il credito è completo (autore, licenza,
  `Wikimedia Commons`, indirizzo della pagina). Un nome giusto con il file assente
  è lo stesso difetto di una voce mancante: si nota solo aprendo la scheda.
  Le foto vengono da **Wikimedia Commons** e sono a licenza libera (CC0, CC BY,
  CC BY-SA, pubblico dominio): sono le uniche che si possono ridistribuire in un
  repository pubblico con l'attribuzione. La via per trovarne una **non è cercare
  il nome del piatto su Commons**: la ricerca restituisce PDF, bancarelle e
  foto di piatti diversi (una «lasagna soup» è finita su una zuppa di zucca in
  Bolivia). Il criterio che regge è l'**immagine principale della voce Wikipedia**
  di quel piatto (`prop=pageimages`): è scelta dagli editori, quindi è quasi
  sempre il piatto giusto. Quando non c'è — «lasagna soup» non ha una voce — si
  ripiega su una foto **indicativa** e lo si scrive nel credito, come già fa
  `PHOTOS` per altre voci. Non inventare un abbinamento: una foto sbagliata in
  una scheda è peggio di un riquadro vuoto. Una foto che è già di un'altra
  ricetta non si riusa (sarebbe un doppione).
- **Le ricette con la foto vengono prima nell'elenco**, quelle senza in fondo
  (`conFotoPrima` in `static/app.js`). L'ordine è del client, non dell'API, che
  resta alfabetico: `sort` in JS è stabile, quindi dentro i due gruppi l'ordine
  non cambia. Una ricetta senza foto è un dato incompleto da completare, e non
  deve stare in mezzo a quelle pronte. La tendina del piano pasti **non** segue
  questo ordine: lì resta l'ordine dell'API, perché scegliere un pasto è un'altra
  cosa dal guardare il ricettario.
- **Dal ricettario si aggiunge al piano senza cambiare scheda.** Ogni scheda ha
  un pulsante `+ Piano` (`data-plan`) e il dettaglio della ricetta ha «Aggiungi
  al piano»: entrambi aprono `openPlanPicker(ricetta)`, che chiede **giorno,
  pasto e porzioni** con la ricetta **già scelta**. È il verso opposto di
  `openMealPicker(date, meal)`, che per un pasto vuoto del Piano fa scegliere la
  ricetta da una tendina. Il motivo è la richiesta: nel Piano si sceglie una
  ricetta **senza vederne la foto**, e per una cosa che si mangia l'immagine è
  metà della scelta. Così si guarda il ricettario e si decide lì.
  Due dettagli non ovvi: (1) le porzioni proposte sono quelle della ricetta
  (`r.servings`), non un 2 fisso, perché è il numero per cui la ricetta è
  scritta; (2) alla conferma si ridisegna il Piano **solo se è la scheda
  aperta** (`#tab-plan.active`), perché `openPlanPicker` si può chiamare anche
  da dentro il dettaglio aperto dal Piano (dove serve il ridisegno) e dal
  ricettario (dove una richiesta a vuoto non serve). Dal dettaglio il pulsante
  «Aggiungi al piano» c'è **solo** quando non c'è già «Rimuovi dal piano»: le
  due azioni si escludono. `pastiDelGiorno()` è l'unica definizione dei pasti
  per il selettore, con la stessa riserva del Piano se `MEALS` non è arrivato.
- **Togliere una ricetta dal ricettario richiede due passaggi, non uno.** Va
  messa in `seed.REMOVED` **e** tolta da `RECIPES` (con `PHOTOS`,
  `PREPARAZIONI_PRECEDENTI` e il file in `static/recipes/`). Solo `REMOVED` non
  basta: in `semina()` la cancellazione avviene **prima** dell'inserimento,
  quindi una ricetta presente in entrambe le liste verrebbe tolta e subito
  rimessa. Solo toglierla da `RECIPES` non basta dall'altra parte:
  `seed.semina()` gira solo quando un database nasce, e `windows\avvia.bat` non
  lo chiama affatto, quindi chi ha già i dati se la terrebbe per sempre. Il
  passaggio che copre i database esistenti è `app._rimuovi_ricette_tolte`,
  chiamato da `migrate()` — che `get_db()` esegue a ogni richiesta su ogni casa.
  La cancellazione si fa solo se una delle ricette è davvero presente, quindi una
  richiesta normale non paga il `rebuild_shopping`.
- **`init_db()` accende le foreign key**, come `get_db()` e `seed.semina()`.
  SQLite le tiene spente per default e `executescript` non le accende: senza,
  il `ON DELETE CASCADE` non scatta e una ricetta cancellata lascia righe orfane
  in `meal_plan`, `recipe_items` e `favorites` — un danno che non si vede, perché
  il database resta «valido» e le query continuano a rispondere. Il test
  `test_le_ricette_tolte_spariscono_anche_dai_database_esistenti` verifica proprio
  che non resti niente che punti a una ricetta che non esiste più.
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
- **Suggerimenti dalla dispensa** (`dispensa.py`, `GET /api/pantry/suggerimenti`):
  sotto l'elenco compare cosa si può cucinare con quello che c'è. Il criterio è la
  **copertura**, e il punteggio è una **frazione**, non un conteggio di ingredienti
  coperti: contando gli ingredienti vincerebbe la ricetta più lunga — una da dodici
  con sette in dispensa batterebbe una da quattro con quattro, che è invece quella
  che si può fare stasera. A parità vince la spesa più corta.
  Un ingrediente coperto **in parte** conta mezzo punto: con 100 g di farina e 500 g
  richiesti la ricetta non si fa, ma non è nemmeno da comprare tutta; contarlo intero
  direbbe «hai tutto» quando non è vero.
  Le quantità si confrontano solo fra unità **convertibili** (`units.convert`): 200 g
  coprono 0,2 kg, ma una confezione non copre un pezzo, e lì non si indovina.
  Il filtro allergie sta **sul server**, non nel client: qui l'app dice «cucina
  questa», e proporre un allergene non è una svista da correggere, è un errore. Una
  ricetta senza ingredienti non è un suggerimento (non c'è niente da consumare), e
  nemmeno una che non usa niente di quello che c'è.
  La riga dei mancanti è troncata a `MAX_NOMI` ma **dice quanti ne restano**
  («e altri 3»): senza, l'elenco sembrerebbe completo e l'utente comprerebbe solo
  quelli. Nel client `renderPantry()` carica tabella **e** suggerimenti, mentre il
  filtro di ricerca (`renderPantryTable`) è locale: non deve rifare la richiesta dei
  suggerimenti, che non dipendono da cosa si sta cercando. Modificare una quantità
  dalla tabella invece li aggiorna, perché cambia cosa risulta coperto.
  Con la dispensa **vuota** il riquadro non resta muto: dice di aggiungere qualche
  ingrediente. Prima spariva e basta, e sembrava che i suggerimenti non esistessero
  — che è esattamente quello che si vede al primo avvio, quando la dispensa è vuota.
- **La scheda condivisibile della spesa** (`GET /api/shopping/condividi`) è una
  vista, non un secondo archivio: si costruisce da `_voci_spesa`, le stesse voci
  della lista, quindi non può mostrare numeri diversi da quelli a schermo. Le
  regole del periodo sono quelle della vista per giorno — un giorno porta la
  **quota** di quel giorno (`quota` nella voce), un intervallo il totale — e le
  voci già spuntate restano fuori (chi compra non ricompra il carrello), mentre
  quelle senza giorni (aggiunte a mano) restano sempre.
  L'endpoint restituisce **dati**, non HTML: la scheda grafica si compone nel
  client (`schedaSpesaHtml` per la pagina, `schedaSpesaCanvas` per il PNG), che
  conosce il tema e il carattere. Aggiungendo un campo alla scheda, si aggiorna
  `_scheda_spesa` in un punto solo; il testo (`testo`) nasce dalle stesse voci.
  I parametri (`giorno` oppure `dal`/`al`, più `nota`) si validano una volta sola:
  una data storta è un 400, non una scheda vuota che sembra «niente da comprare».
- **La scadenza in dispensa** (`pantry.expires_at`, `parse_data`). È una data
  facoltativa: vuoto significa «non lo so», che è **diverso** da «non scade». Non
  si indovina mai una data, perché una scadenza inventata farebbe buttare cibo
  buono. Nel `PATCH` ogni campo si tocca solo se presente nel corpo (`quantity`,
  `expires_at`): mandare la sola scadenza non deve azzerare la quantità, e
  cambiare la quantità non deve cancellare la scadenza; per toglierla si manda
  vuota. Aggiungendo scorte dello stesso ingrediente vince la scadenza **più
  vicina** (`_scadenza_piu_vicina`): è quella che va guardata prima, e una partita
  senza data non cancella quella che si sapeva. Nel client il colore dice
  l'urgenza (`statoScadenza`: rosso scaduto, ambra entro pochi giorni) senza
  dover leggere la data.
  I suggerimenti **tengono conto delle scadenze**: a parità di copertura sale in
  cima la ricetta che consuma una scorta in scadenza entro `GIORNI_SCADENZA` (7),
  perché è quella da cucinare adesso. La card dice quali (`sug-scade`), invece di
  lasciarlo intuire dall'ordine. `suggerimenti()` prende un `oggi` opzionale, che
  è anche l'unico posto in cui il modulo guarda la data vera — i test lo passano.
- **L'ordine della home**: categorie (le schede), poi il riepilogo «Oggi», il
  calendario, le notizie del giorno, il riquadro «Domani» e in fondo
  l'intestazione «Il Maggiordomo» (`home-hero-basso`, **centrata**:
  `text-align: center` sul blocco, con `.con-icona` a `justify-content: center`).
  Le categorie stanno subito sotto l'invito a parlare: si
  arriva in home per scegliere dove andare, e devono vedersi senza scorrere.
  Tutto il resto è da leggere, non da premere, quindi viene dopo. È un ordine
  scelto dall'utente, non un dettaglio di stile: prima le schede erano in fondo,
  ed era sbagliato. L'intestazione era invece in cima e spingeva giù le
  categorie: ora chiude la pagina (vedi `test_l_intestazione_chiude_la_home`).
  **L'ordine delle schede è: Cucina, Appunti, FAQ, TV, GYM, Igiene**
  (`test_l_ordine_delle_categorie_in_home` lo fissa). L'Igiene è in fondo perché
  è la cosa che si guarda meno spesso; l'ordine è dell'utente, non alfabetico.
  La scheda **Cucina ha un'icona sua** (`static/icons/cucina.svg`, una pentola
  sul fuoco col vapore): prima usava il logo dell'app, quindi non si
  distingueva. Il disegno era un cappello da chef ed è stato cambiato su
  richiesta dell'utente. **Il disegno è piatto e su fondo trasparente**, come le
  emoji delle altre schede (Appunti, FAQ, TV, GYM, Igiene): la prima versione
  aveva un riquadro di fondo colorato a tutta tela, e in mezzo ai simboli piatti
  sembrava il logo dell'app incollato sulla scheda — quella era l'incoerenza. Il
  colore della pentola (`#c1440e`) distingue il nuovo dal vecchio, così un
  ritorno al cappello non passa inosservato (`test_la_cucina_ha_la_sua_icona`,
  che verifica anche l'assenza del riquadro di fondo). Le altre schede tengono la
  loro emoji.
- **Le notizie del giorno in home** (`renderHomeNotizie`). In fondo, sotto il
  calendario: solo i titoli con fonte e data, e «Apri →» che porta alla TV, dove
  stanno il sommario e l'elenco completo. Si riempie da `/api/notizie`, un
  endpoint dedicato: `/api/tv` tirerebbe giù anche i video, che in home non si
  mostrano. Stessa regola dell'endpoint TV (risposta subito dalla cache, un
  filo riprova dopo — `_aggiorna_notizie_in_sottofondo`) e del riepilogo «Oggi»
  (se non c'è niente, il riquadro resta nascosto). **In home se ne mostrano al
  massimo dieci** (`slice(0, 10)`): è un assaggio, e il taglio è della home, non
  del feed — la sezione TV resta con tutte quelle della cache (`MAX_NOTIZIE`, 20,
  `test_la_home_mostra_dieci_notizie_non_tutte`).
- **Il riquadro «Domani» in home** (`renderHomeDomani`). Dopo le notizie: gli
  impegni di domani non ancora chiusi e i pasti già scelti. È una sezione a sé
  (non una riga dentro «Oggi»), perché un impegno di domani non è ancora scattato
  e i pasti di domani non sono ancora cucinati. Le fonti si chiedono **in
  parallelo** con `.catch` e, se non c'è niente, il riquadro resta nascosto —
  stessa regola di «Oggi». Si ridisegna all'avvio e al ritorno in home
  (`tornaAlleSezioni`).
- **Il riepilogo «Oggi» in home** (`renderHomeOggi`). La home non è solo un menu:
  mostra i pasti di oggi, le attività di casa da fare, gli impegni che avvisano
  adesso e cosa sta per scadere in dispensa. Gli impegni di oggi li manda
  `prossimi` (i promemoria scattati e le cose in ritardo). Le fonti si
  chiedono **in parallelo** e ognuna fallisce per conto suo (`.catch`): un errore
  sul calendario non deve far sparire i pasti. Se non c'è niente da dire il
  riquadro resta nascosto — una home con un riquadro vuoto è peggio di una home
  senza riquadro.
- **Il calendario degli impegni in fondo alla home** (`renderHomeCalendario`).
  La stessa griglia del mese della scheda Calendario, ma **in sola lettura**: qui
  si sfoglia e si vede quali giorni sono occupati, non si compila. Cliccando un
  giorno o «Apri →» si va al Calendario nei Progetti, dove si aggiunge e si
  modifica. Il mese mostrato vive in `homeCalVista`, **separato** da `calVista`:
  sfogliare in home non deve spostare il calendario dei Progetti. Se gli impegni
  non arrivano il riquadro resta nascosto (stessa regola del riepilogo «Oggi»).
  Si ridisegna all'avvio e al ritorno in home (`tornaAlleSezioni`), così un
  impegno aggiunto nei Progetti compare senza ricaricare la pagina.
- **Le porzioni si scalano nel dettaglio ricetta** (`qtaScalata`). La ricetta è
  scritta per `servings`; cambiando il numero nel dettaglio, le quantità seguono
  (frazione rispetto al numero base). Una quantità non numerica («q.b.») resta
  com'è: riscalarla non vorrebbe dire niente.
- **Tempi e costo della ricetta**: `prep_minutes` e `cook_minutes` sono due colonne
  separate perché dicono cose diverse — la cottura si può lasciare andare da sola, la
  preparazione assorbe l'attenzione — e il totale è la loro somma, calcolata nel
  client (`tempiRicetta`) così non può contraddire le due parti. `cost` è per porzione.
  `time_minutes` **resta com'è**: è il totale delle ricette salvate prima, e
  reinterpretarlo vorrebbe dire riscrivere dati inseriti a mano. Una ricetta vecchia
  mostra `time_minutes`; il campo sparisce solo quando si indicano i due tempi, perché
  allora il totale si ricava da quelli (`test_il_totale_vecchio_non_si_perde...`).
  Zero minuti non è un tempo e diventa `None`; zero **euro** invece è un costo — «non
  costa niente», tipico di una ricetta con gli avanzi — e si tiene. `parse_minutes` e
  `parse_cost` in `app.py` sono l'unico posto dove questa distinzione è scritta.
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
- **Schema e migrazioni si applicano a ogni casa, non solo alla storica.**
  `get_db()` chiama `init_db()` sul database della casa collegata a ogni richiesta
  (meno di 1 ms): una tabella o colonna nuova arriverebbe altrimenti solo al
  `cucina.db` storico, e le case create prima risponderebbero "no such table"
  proprio a chi ha più dati da perdere. Non aggiungere una cache dei file già
  migrati: mentirebbe quando si rimette al suo posto una copia dei dati.
- **Le foto del magazzino** stanno in `storage_photos` (BLOB), una riga per voce
  con `storage_id` come chiave primaria: `ON CONFLICT ... DO UPDATE` fa sì che
  ricaricare sostituisca la foto invece di accumularne una seconda. Il client le
  ridimensiona da sé (`riduciFoto` in `app.js`, canvas → JPEG) prima di mandarle
  come data URL: niente Pillow fra le dipendenze, e il server accetta solo JPEG,
  PNG e WebP. La foto sta nel database, non su disco, così `/api/backup` resta un
  file solo. `photo_url` porta un `?v=<hash>`, altrimenti il browser mostrerebbe
  la foto vecchia dopo una sostituzione (la risposta è in `Cache-Control`).
- **`GET /api/storage/<id>`** restituisce il dettaglio di una voce: senza il ramo
  esplicito su `request.method`, il `get_json(force=True)` più sotto risponde 400
  a ogni lettura, perché una GET non ha corpo.
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
  `chores`, come le ricette. La cadenza (`giornaliera`, `frazionaria`,
  `settimanale`, `mensile`, `semestrale`, `stagionale`) decide quando una voce
  rientra; le stagionali solo nel loro `month` e una volta l'anno, le
  **semestrali** ogni `CADENZE["semestrale"]` = 182 giorni. `piano()` in
  `igiene.py` è il cuore del metodo: **quotidiane, frazionarie e settimanali
  stanno nel piano di oggi, mensili e stagionali nel blocco del mese, e le
  semestrali in un blocco loro** (`piano()["semestrali"]`, con
  `semestrali_da_fare`). Se finissero tutte nel piano di oggi la giornata
  diventerebbe impraticabile e il piano verrebbe abbandonato; una cosa che tocca
  ogni sei mesi non è una cosa del mese, quindi non va mescolata al mese: è il
  motivo per cui i test `test_piano_separa_oggi_dal_mese` e
  `test_piano_mette_i_semestrali_a_parte` esistono. La voce semestrale è
  «Disinfettare il condizionatore» (area «Tutta la casa», 15 min): l'aria
  condizionata va igienizzata due volte l'anno, non è una pulizia mensile.
  `minuti_previsti` conta solo oggi, `mese_minuti` solo il mese: mescolarli
  darebbe una cifra falsa in entrambi i casi.
- La cadenza **frazionaria** («ogni giorno e mezzo», `FRAZIONARIE` — la lavatrice)
  non è un blocco tondo e per questo non entra mai nel blocco mensile: `CADENZE`
  le dà 1,5 giorni. Conta **l'ora del completamento**, non solo la data: con la
  sola data la mezza giornata si perderebbe e alle 8 di lunedì la voce sembrerebbe
  da rifare già martedì mattina, cioè un giorno. `chore_log.date` per questo è un
  istante ISO (`datetime('now')`, non `date('now')`) e `scadenza()` confronta
  istanti per questa cadenza (`giorni` può quindi essere una frazione). In `piano()`
  rientra **solo quando è davvero da rifare** (come le settimanali), non sempre:
  altrimenti gonfierebbe il «da fare» di oggi con una lavatrice non dovuta. Resta
  comunque visibile in Routine e nel catalogo.
- **La sezione Igiene è divisa in schede** (Oggi / Routine / Calendario / Attività),
  e ognuna ha il suo pannello (`.ch-panel`, `data-chp-panel`). Prima erano un'unica
  colonna: lo stesso catalogo compariva in più blocchi — le quotidiane tre volte,
  le stagionali due — e la prima schermata arrivava a ~129 righe per 60 voci.
  Le schede separano tre mestieri diversi: **cosa fare adesso**, **cosa esiste**
  (il catalogo) e **cosa tocca nell'anno**. `mostraChPanel()` in `app.js` tiene
  aperto un pannello solo; il pulsante attivo si riconosce dal colore, non solo dal
  contenuto. La scheda aperta (`chPanel`) vive in memoria e non si salva: riaprendo
  l'app si torna su «Oggi». I test `test_la_sezione_igiene_ha_le_schede_e_i_pannelli`
  e `test_il_cambio_scheda_mostra_un_pannello_solo` lo tengono fermo.
- La scheda **Oggi** si apre con un riquadro-guida (`.ch-hero`): un anello
  (`.ch-ring`, disegnato con `conic-gradient` e `--pct`) che mostra quante voci
  sono state spuntate, e i minuti che restano. Sotto, ogni voce è una riga
  (`.ch-row`) con la fascia di colore del suo ambiente (`.ch-area[data-area=…]`,
  da `areaChiave` in `app.js`), così le voci della stessa zona si riconoscono a
  colpo d'occhio senza leggerle. Prima era un'unica colonna di testo uguale.
- Nel calendario annuale **solo il mese corrente è aperto** (`<details open>`), gli
  altri chiusi: aprirli tutti faceva una pagina di quarantacinque righe che non si
  scorre. Le attività del mese corrente restano comunque visibili nel blocco «Oggi».
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
- `chore_day` in `profile` è il giorno fisso delle settimanali (0 = lunedì). **Le
  settimanali non entrano più tutte in quel giorno**: `giorni_settimanali()` le
  distribuisce dal giorno scelto a ritroso, dalla più pesante alla più leggera, una
  per giorno. Prima il sabato arrivava a cento minuti di sole settimanali più la
  routine, e il piano veniva abbandonato. Il giorno scelto resta il più pesante.
  L'ordine in `SETTIMANALI` è significativo: non riordinarle per nome.
- Una settimanale **mai fatta** non rientra subito: aspetta il suo giorno, altrimenti
  al primo uso rientrerebbero tutte insieme, che è l'ammasso che la distribuzione
  deve togliere. Una settimanale **saltata** invece rientra in ritardo, perché
  perdere il proprio giorno non deve nasconderla per una settimana.
- `RIMOSSE` in `igiene.py` mappa una voce tolta dal catalogo alla sua sostituta
  (o a `None` se va solo tolta). Serve perché il seme è idempotente e non tocca le
  righe esistenti: senza, chi usa l'app da prima terrebbe per sempre la voce doppia.
  I completamenti della voce tolta si **spostano** sulla sostituta prima del
  `DELETE`: il `CASCADE` li porterebbe via, e sono lavoro fatto davvero. I minuti
  delle voci del catalogo non si riallineano mai: sono una stima che l'utente può
  correggere, e un `UPDATE` incondizionato cancellerebbe la correzione a ogni
  richiesta.
- Quanti **bucati al giorno** fa la casa (`profile.bucati_giorno`, 0 = non
  dichiarato, da 1 a 5) decidono ogni quanto torna «Avviare la lavatrice»:
  `igiene.cadenza_lavatrice()` traduce i bucati in giorni (`max(0.5, 1/bucati)`),
  con 1,5 giorni come valore di partenza. La cadenza entra nello stato di
  `scadenza()` come `cadenza_giorni`, così l'interfaccia dice ogni quanto tocca
  davvero. Il minimo è mezza giornata: sotto la voce resterebbe sempre in cima al
  piano. Le opzioni stanno in `BUCATI_OPZIONI` e si servono da `/api/meta` e
  `/api/chores/meta`, così onboarding e Profilo non inventano i numeri.
- La routine **quotidiana** sta in `QUOTIDIANE` e deve restare sotto i venticinque
  minuti in tutto: oltre smette di essere una routine. Il test
  `test_la_routine_quotidiana_resta_breve` lo tiene fermo.
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
  dettare testo (o a registrare l'audio, vedi sotto) e a mandarlo a
  `POST /api/voice`, così la comprensione è testabile senza microfono. `parse()`
  riconosce gli intenti `pantry_add`, `shopping_add`, `storage_add`, `term_add`,
  `recipe_search`, `recipe_add` e restituisce `unknown` quando non capisce. Le unità
  si aggiungono in `_UNIT_TOKENS`, le parole di comando in `_COMMAND_VERBS`, le
  destinazioni in `_find_destination`. Una frase senza verbo, destinazione o
  quantità è rumore di fondo e deve restare `unknown`: il microfono sente anche i
  discorsi in cucina e le voci inventate in lista sono peggio di un comando non
  capito.
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
  comprensione col modello non c'e' piu': e' stato tolto dal Profilo (vedi
  «Capire i comandi»). La voce
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
  runtime produce un avviso breve (`toast`) e una riga nel registro, con la
  raffica limitata a un avviso per volta e senza nome dell'eccezione ne' traccia a
  schermo. (2) `avviaApp()` distingue i due guasti: se la **sessione** non
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

## La chiave Azure si configura prima di avviare, non dall'app

La chiave entra **solo** dall'ambiente o da un file accanto all'app
(`segreto.txt`, `segreto`, `segreto.sh`, `segreto.bat`), prima dell'avvio. Non
esiste una rotta che la salvi e nella pagina non c'e' nessun campo che la chieda:
l'app non deve poter riscrivere il proprio segreto, e la chiave non deve passare
da una richiesta HTTP. Un pannello "incolla qui la chiave" e' stato rimosso
apposta, insieme a `POST /api/voce/configura`, `voce_cloud.salva_config` e
`voce_cloud.verifica`.

Cosa resta al suo posto: `voce_cloud._leggi_file_segreto` legge i file **da
sola** quando l'ambiente non ha la chiave, e `avvia.sh` lo stato lo **chiede
all'app** (`stato_voce` chiama `voce_cloud.chiave()`/`regione()`) invece di
riparsare i file in bash. Il riconoscimento delle forme sta in un posto solo:
quando due copie divergono, lo stato all'avvio mente — ed e' proprio il caso che
`stato_voce` esiste per evitare.

`segreto.txt` vive accanto all'app, che in questo ambiente e' `/workspace/...`:
sopravvive ai riavvii ma **non e' eterno**, e quando il workspace viene ricreato
sparisce. Per questo all'avvio lo stato della voce si stampa sempre: e' la
diagnosi che evita di cercare nell'app un problema che sta in un file assente.

Il repository e' pubblico, quindi la chiave non ci entra in nessuna forma. Non si
puo' nemmeno metterla nei segreti di GitHub e rileggerla da sola: il token di
questa app non ha i permessi di Actions, e comunque un repo pubblico non e' un
posto per un segreto.

## La pagina non resta in memoria nel browser

Il server manda `Cache-Control: no-cache, no-store, must-revalidate` su tutto
tranne le risposte che scelgono da sole la loro scadenza (le foto delle voci, la
voce di conferma di un comando). Prima non lo faceva, e una modifica alla pagina
restava invisibile nel browser **per giorni**: sembrava che l'app non fosse stata
aggiornata, mentre il server serviva già la versione nuova. Si cercava un guasto
che non c'era.

Il sintomo, per riconoscerlo: la pagina è vecchia **solo** in un browser che l'ha
già aperta, e ricaricando con forza si aggiorna. Il rimedio immediato per l'utente
è aggiungere `?v=2` all'indirizzo, che per il browser è una pagina mai vista.

**Gli asset hanno la versione nell'indirizzo.** La pagina è servita da `/` (non da
`send_from_directory`) e inietta in `app.js` e `style.css` un `?v=<impronta>`:
l'impronta è un hash del contenuto, calcolato una volta e tenuto in memoria finché
mtime e dimensione non cambiano (`_versione_asset`). Così il browser può tenere
quei file **a lungo** (`max-age=31536000, immutable`) senza mai vedere una
versione vecchia: se il file cambia, cambia l'indirizzo. Le immagini dei dati non
hanno la versione e continuano a scegliere da sole la loro scadenza.

**Il service worker (`static/sw.js`, servito da `/sw.js`).** Salva la **scocca**
(pagina, CSS, JS, icone) per farla aprire anche senza rete. Quattro cose da non
rompere: (1) è servito da `/sw.js` e non da `/static/`, perché un service worker
controlla solo il percorso da cui è servito e da `/static/` non potrebbe mostrare
la pagina `/`; (2) `/sw.js` è in `ROTTE_PUBBLICHE`, perché deve partire prima del
login; (3) le **API non si salvano mai**: un dato vecchio mostrato come fresco è
peggio di un dato mancante — la dispensa di ieri non è la dispensa di oggi;
(4) **pagine e file statici vanno entrambi prima in rete**, copia solo se la rete
manca.

Il punto (4) è stato un guasto vero, non una preferenza. La versione precedente
serviva i file statici **prima dalla copia**, ragionando che tanto hanno la
versione nell'indirizzo (`?v=...`). Ma `chiave()` **toglie** la query per
riconoscere la copia salvata all'installazione: così la copia vecchia rispondeva
anche a una richiesta con versione nuova. Effetto: `index.html` (prima la rete) si
aggiornava, `app.js` restava quello dell'installazione, e la funzione nuova — il
calendario in home — non veniva mai disegnata. Si è visto in home: la sezione
c'era nell'HTML e restava vuota/invisibile. La regola che ne esce: **mentre c'è
rete, la versione servita è sempre quella nuova**; il `?v=...` esiste per
distinguere le versioni e va onorato, non aggirato con la cache. Il
`serveStatico()` corrispondente ha un test che esegue davvero la funzione con un
`fetch` finto: online vince la rete, offline regge la copia. Alzando `CACHE`
(`...-v2`) le copie vecchie vengono sfrattate al prossimo `activate`.

## Intestazioni di sicurezza e CSP

Le risposte portano `X-Content-Type-Options: nosniff`, `X-Frame-Options:
SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin`,
`Permissions-Policy: camera=(), geolocation=(), payment=()` e una
`Content-Security-Policy`. Servono a limitare cosa la pagina può caricare e
incorporare, se un giorno un contenuto esterno (un titolo di notizia, un nome di
ricetta) riuscisse a iniettare markup.

Tre cose che non sono ovvie:

- **Stanno in un `after_request` a parte**, non in quello della cache. Quello
  della cache **esce subito** per le risorse versionate (le foto, la voce di
  conferma) perché scelgono da sole la loro scadenza: mettere le intestazioni lì
  significherebbe non averle proprio su quelle risposte. Un secondo
  `after_request` le applica a tutto.
- **La CSP ha un `nonce` per pagina, non `'unsafe-inline'` per gli script.** La
  pagina ha script inline (il tema scuro nello `<head>`, la configurazione
  iniziale): `script-src 'unsafe-inline'` li autorizzerebbe, ma autorizzerebbe
  anche qualsiasi script iniettato — cioè renderebbe la CSP inutile. La rotta `/`
  genera un nonce casuale, lo mette in `g.csp_nonce` e lo inietta negli script
  inline; l'intestazione lo cita. Un nonce diverso a ogni pagina è ciò che lo
  rende una difesa e non un permesso fisso.
- **`style-src` ha `'unsafe-inline'`**, invece: il client usa stili inline
  (`style="..."` e `<style>`), e gli stili non eseguono codice. È un compromesso
  consapevole, non una dimenticanza.

I domini esterni ammessi sono quelli che l'app usa davvero: `image.tmdb.org` per
le locandine, `youtube-nocookie.com` per gli embed. `object-src 'none'` e
`base-uri 'self'` chiudono i vettori classici (plugin, dirottamento dei link
relativi). Aggiungendo un contenuto esterno nuovo, va aggiunto il suo dominio
**qui**, altrimenti resta invisibile e sembra un guasto della sezione.

## Capire i comandi con un modello (facoltativo)

> **Stato attuale: la funzione esiste sul server, ma non ha piu' un pannello.**
> L'interruttore «Capire i comandi» e' stato tolto dal Profilo su richiesta
> dell'utente: `#voice-llm`, `#voice-llm-block`, `#voice-llm-avviso`,
> `popolaLlm()` e il suo ascoltatore non esistono piu'. La rotta
> `PUT /api/voce/llm` e `comprensione.py` restano, quindi riaccendere la
> funzione e' una scelta di prodotto (un interruttore nuovo) e non un lavoro da
> rifare: il codice della comprensione e' intatto. Con `llm_prefs.abilitato` a
> `0` l'app usa il parser a regole, come sempre. Il capitolo resta perche' spiega
> come funziona la parte server.

Il parser a regole di `voice.py` capisce le frasi previste e lascia fuori le
altre: «dammi la lista della spesa», «fammi vedere la dispensa», «metti via il
vino in cantina». Non e' un difetto del riconoscimento — la trascrizione Azure e'
buona — e' che le regole sono una grammatica scritta a mano, e la lingua parlata
non ci sta dentro. `comprensione.py` fa la stessa comprensione con un modello
linguistico.

**Fallisce in modo aperto**, ed e' la proprieta' che rende sicuro accenderlo. Il
parser diventa cosi': si prova il modello, e se risponde `unknown` o non risponde
(manca la chiave, manca la rete, risposta storta) si usa il risultato di
`voice.parse`. Quindi o capisce di piu', o non cambia niente:

```
cmd = comprensione.chiama(testo)
if not cmd or cmd["intent"] == "unknown":
    cmd = voice.parse(testo)     # la rete di sicurezza di sempre
```

E' un test (`test_se_il_modello_non_capisce_si_usa_il_parser`) e non una
promessa. Il modello si preferisce **anche** quando il parser crede di aver
capito, perche' proprio li' stanno gli errori da correggere («metti via il vino
in cantina» diventava un articolo in magazzino chiamato «via il vino»).

Le tre scelte che contano:

- **Il modello non inventa intenti.** La risposta viene ripulita con
  `_ripulisci()`: un intento fuori da `INTENTI`, un'unita' fuori da `UNITA`, una
  quantita' non numerica vengono scartati. Se resta poco, il comando vale
  `unknown`. Una comprensione sbagliata deve restare una frase, non un'azione:
  meglio «non ho capito» di una voce sbagliata in dispensa per sempre.
- **Niente funziona senza che la casa l'abbia acceso.** `llm_prefs.abilitato`
  (una riga sola, nel database **della casa**) parte a `0`: nessuna chiamata a
  consumo se non la si accende dalla scheda **Profilo** («Capire i comandi»).
  E' una scelta dell'utente, non del dispositivo, per questo sta nella casa e non
  in `localStorage`.
- **L'interruttore non accende una cosa che non c'e'.** `PUT /api/voce/llm` con
  `abilitato: true` e nessun modello **raggiungibile** risponde **400** dicendo
  cosa manca: per un servizio in rete il nome della variabile (`LLM_API_KEY`),
  per un modello di casa la causa vera (Ollama spento / modello non scaricato).
  L'alternativa — accettare e non fare niente — e' peggio di un rifiuto: l'utente
  crederebbe di aver acceso qualcosa.
- **`configurato()` non e' `raggiungibile()`.** Sono due cose diverse, e
  confonderle faceva mentire il pannello: un endpoint locale c'e' **sempre** (e'
  il predefinito), quindi `configurato()` era vero anche a Ollama spento.
  `/api/voce/config` espone `llm_disponibile` (c'e' la configurazione),
  `llm_pronto` (il modello risponde **adesso**) e `llm_manca` (la causa, se
  manca). L'interruttore si mostra — e si accende — solo se `llm_pronto`, che e'
  una verifica di rete breve (`raggiungibile()`, `TIMEOUT_VERIFICA` 1.5 s) contro
  l'elenco dei modelli: `/api/tags` per Ollama (porta 11434), `/models` per un
  servizio in rete. Un guasto di rete qui non e' un errore, e' "non pronto": si
  resta sulle regole senza rompere niente.

La chiave entra **solo** dall'ambiente o da un file accanto all'app
(`_leggi_file`), prima dell'avvio, come quella di Azure: non c'e' una rotta che
la salvi, perche' l'app non deve poter riscrivere il proprio segreto. Il file e'
`segreto.txt` (o `segreto`, `segreto.sh`, `segreto.bat`), lo stesso della voce, e
accetta le etichette `chiave`, `modello`, `base_url` oltre ai nomi veri
(`LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`). A differenza della voce, che
distingue una chiave da un'area, qui una riga nuda che non sia una parola
minuscola corta vale come chiave LLM.

**Verifica di Ollama, prima di credere che sia configurato.** `configurato()` e'
vero anche a Ollama spento (l'endpoint locale e' il predefinito): la verifica
vera e' `raggiungibile()`, che interroga `/api/tags` sulla porta 11434. Con
Ollama acceso e il modello `qwen2.5:7b-instruct` scaricato
(`ollama pull qwen2.5:7b-instruct`) il percorso funziona senza chiave: una
chiamata a `comprensione.chiama("aggiungi il latte alla spesa")` restituisce
`{"intent": "shopping_add", "name": "latte", "quantity": 1.0, "unit": "pz"}`.
Se `raggiungibile()` e' falso, `messaggio_stato()` dice la causa (Ollama spento
o modello non scaricato) e l'interruttore resta spento.
**Modelli di ragionamento e modelli locali: due trappole, entrambe misurate.**

- I modelli di ragionamento spendono lo stesso budget di token prima di scrivere
  la risposta. Con un tetto stretto il JSON arriva troncato o vuoto, la chiamata
  fallisce e l'app ripiega in silenzio sulle regole: sembra che "non capisca".
  `MAX_TOKENS` (1024) lascia il margine che serve, e non costa sugli altri
  modelli, che si fermano da soli.
- Ollama in locale su CPU: risponde in 2-10 secondi, non in frazioni. Con un
  `TIMEOUT` corto la chiamata scadrebbe spesso e si ricadrebbe sulle regole.
  `LLM_TIMEOUT` regola l'attesa (`comprensione.timeout()`). **Il predefinito e'
  il modello di casa**: `LLM_BASE_URL` = `http://127.0.0.1:11434/v1`, `LLM_MODEL`
  = `qwen2.5:7b-instruct`, `LLM_TIMEOUT` = 60. Un servizio in rete si punta con
  le stesse variabili. Nota di qualita': un 7B locale sbaglia piu' spesso di un
  modello grande in rete — il parser a regole resta la rete di sicurezza, quindi
  l'errore non peggiora l'app.
- **Un endpoint locale vale anche senza chiave.** Ollama non ne usa: se
  `configurato()` pretendesse `LLM_API_KEY` resterebbe spenta proprio la
  configurazione predefinita. `_e_locale()` riconosce 127.0.0.1/localhost
  nell'indirizzo. Nei test, per simulare "nessun modello", va impostato un
  `LLM_BASE_URL` in rete e tolta la chiave; per un modello che **risponde**
  (necessario ora che l'interruttore lo richiede) si sostituisce
  `comprensione.urllib.request.urlopen` con `_ModelloFinto`, che finge sia
  `/api/tags` sia la chat.

Le variabili sono `LLM_API_KEY` (serve solo ai servizi in rete), `LLM_MODEL`
(default `qwen2.5:7b-instruct`) e `LLM_BASE_URL` (default Ollama in locale; lo
stesso codice parla con qualsiasi servizio che esponga l'API compatibile OpenAI).

**Il costo e' la ragione per cui questa funzione e' scritta cosi'.** Ogni comando
e' una chiamata breve: il modello e' il piu' economico, `temperature=0`,
`max_tokens` basso, e la risposta e' un oggetto JSON solo. Non si chiama il
modello se l'interruttore e' spento: e' la differenza fra un'app che costa a
consumo e una che costa a caso.

**La latenza si misura, non si intuisce.** Il difetto riferito («lento,
macchinoso») e' quasi tutto attese del client, non Azure: la trascrizione e'
~1,0 s e la sintesi ~0,6 s a caldo. Il pacchetto `azure-cognitiveservices-speech`
(1.52.0) e' stato **provato e scartato**: installato e misurato con
`PushAudioOutputStream`, il primo byte arriva a ~0,52 s contro ~0,59 s del REST a
caldo, per una funzione (audio incrementale) che il client non usa. Non vale una
dipendenza con binari nativi per qualche decina di millisecondi. La lentezza che
si sente e' la **partenza a freddo** (~1,3–1,8 s alla prima chiamata), e si taglia
riusando le frasi gia' sintetizzate (la cache del client), che infatti esiste.

## Il riconoscimento vocale

Il microfono **registra** e la trascrizione avviene **sul server**
(`voce_cloud.trascrivi`), non nel browser: la Web Speech API manda l'audio ai
server di Google, e in molte case quel traffico è bloccato (firewall, antivirus,
VPN), per cui Chrome risponde `network` e il microfono resta muto senza rimedio.
Il server invece esce dalla rete. Dettagli e trappole nel capitolo
«L'ascolto passa dal server» qui sopra. `voice.py` comprende il testo trascritto;
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

### L'accensione automatica: all'accesso parte subito, al ricaricamento solo se il permesso c'è già

"Hey GG" senza pulsante: l'ascolto si apre da solo, e ci sono **due strade**, con
regole diverse perché diverso è ciò che si può dare per scontato.

1. **All'accesso** (`accendiAscoltoDopoAccesso`, chiamata da `init` quando
   `appenaEntrato` è vero). Il click su "Entra" **è** il gesto che il browser
   pretende: il microfono si può chiedere e l'audio è sbloccato. Quindi qui non
   serve il permesso già concesso — serve solo che l'utente non l'abbia spento
   **esplicitamente** (`'0'`): un valore assente è una prima volta, e all'accesso
   la prima volta parte. Chi l'ha spento dal pannello non se lo ritrova acceso.
   La regola sta in `deveAccendereDopoAccesso`, pura apposta.
2. **Al ricaricamento** (`accendiAscoltoContinuoDaSolo`). Non c'è nessun gesto
   attorno, quindi vale la regola più stretta: `deveAccendereDaSolo` richiede
   preferenza `'1'`, permesso già `granted` **e** il server che sa trascrivere.

La preferenza si scrive al click del pulsante (`'1'`/`'0'`) e anche quando
l'ascolto parte all'accesso (`'1'`): senza, al ricaricamento successivo non
ripartirebbe, perché il gesto non c'è più.

Tre trappole:

- **Il permesso non si chiede senza un tocco.** Al ricaricamento, con `prompt` o
  `denied` il browser non lo dà: si aprirebbe solo un avviso bloccato. Per questo
  si legge `permissions.query` e non si tenta a fondo.
- **Un `AudioContext` nasce "suspended" finché la pagina non riceve un gesto**,
  e un contesto sospeso non riceve un campione solo: l'app direbbe "ti ascolto"
  senza sentire. Il controllo va fatto sul contesto **vero**, quello del
  registratore (`ascoltaSulServer`), non su una sonda a parte: ogni contesto ha
  il suo stato, e sbloccarne uno non sblocca l'altro. Se resta bloccato, la
  frase `{bloccato: true}` porta ad `attendeUnGesto`, che chiede un tocco sulla
  pagina e poi riparte.
- **`appenaEntrato` distingue i due casi.** È una variabile di modulo che vale
  `true` solo nel giro di `avviaApp` subito dopo il login: senza, `init`
  tratterebbe l'accesso come un ricaricamento e l'ascolto non partirebbe proprio
  quando l'utente se lo aspetta.

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

## Il tema scuro

La pagina nasce chiara (palette «mare»), e il tema **scuro e' l'opposto**: sfondo
profondo, inchiostro chiaro, accento schiarito. Si sceglie dalla **FAQ → Aspetto**,
perche' e' un'impostazione di servizio come la password della casa, non una voce
da consultare.

Tre cose che il tema ha richiesto e non sono ovvie:

- **Si applica nello `<head>`, non da `app.js`.** `app.js` arriva in fondo alla
  pagina: applicandolo li', chi ha scelto il tema scuro vedrebbe un **lampo
  bianco** all'avvio. Lo script nello `<head>` mette `data-tema="scuro"` su
  `<html>` prima del disegno. `applicaTema` serve solo al cambio dal vivo.
- **Il tema chiaro non ha una regola sua.** E' il predefinito: `applicaTema`
  **toglie** l'attributo invece di scriverlo, cosi' non esistono due regole da
  tenere allineate (`html[data-tema="scuro"]` e una per il chiaro).
- **Il tema e' del dispositivo, non della casa.** Chi entra dal telefono la sera lo
  vuole scuro e il computer di giorno no, quindi la scelta sta in `localStorage`
  come timbro e suono, non nel database.

Il colore e' passato **tutto** per le variabili CSS: prima c'erano una decina di
`#...` fuori dalla palette (il cielo di fondo, le nuvole, l'intestazione delle
tabelle, il riquadro d'errore) e sarebbero rimasti chiari in tema scuro. Un test
lo verifica in modo oggettivo (`test_il_tema_scuro_e_l_opposto_di_quello_chiaro`):
calcola la **luminanza** di `--paper` e `--ink` nelle due palette e pretende che
siano invertite.

## Le domande non sono ordini

`voice.parse` riconosce le domande **prima** di ogni altro ramo. Senza, "che cosa
c'è in dispensa" contiene un luogo ("dispensa") e un verbo ("c'è"), quindi veniva
eseguita e scriveva in dispensa una voce chiamata "che cosa c'e" — e quella voce
sbagliata resta lì per sempre. Una domanda risposta male è peggio di una domanda
senza risposta.

L'avvio è una parola interrogativa **all'inizio** (`_DOMANDA_AVVIO`): così "metti
il sale, che serve" resta un comando. "vorrei sapere se c'è il latte" e "dimmi
quante ricette ho" sono domande, quindi la regex copre anche le forme di cortesia.
La risposta si costruisce in `_rispondi_domanda` (`app.py`) e viene **letta ad
alta voce**: è una frase in italiano, non un elenco di dati.

Attenzione ai nomi delle colonne, che non sono quelli che si indovinano: `pantry`
**non ha** una colonna `name` (il nome sta in `ingredients`, unito per
`ingredient_id`), `chores` **non ha** `title`/`done`/`next_due` ma `name` e
`active`, e la scadenza si ricava con `igiene.scadenza()` come fa `/api/chores`.
Indovinarli dà un `OperationalError` a runtime, non un errore di sintassi.

## Icone degli alimenti in dispensa

`iconaAlimento()` in `app.js`: prima le parole che valgono solo da sole
(`ICONE_PAROLA_INTERA`, es. "te"), poi le parti di parola, infine la categoria.
L'ordine delle liste conta — la prima che trova vince.

Due trappole, entrambe già costate un giro di prove: **"te" sta dentro
"de-te-rsivo"** e "de-te-rgente", quindi senza il confronto sulla parola intera il
detersivo prendeva la tazza di tè; e le voci vanno dalla più specifica alla più
generica, altrimenti "olio di semi" trova "semi" prima di "olio". Il test
`test_le_icone_degli_alimenti_sono_scelte_bene` estrae le funzioni e le esegue con
node: verifica il comportamento vero, non la presenza delle stringhe.

La tabella della dispensa diventa schede sotto i 560px e le etichette di colonna
arrivano da `data-label`. L'icona non ha `data-label`, e non deve averlo: sta
**dentro** la cella dell'ingrediente, che l'etichetta ce l'ha già.

## Ricette cercate su un sito esterno

`ricette_online.py` legge le ricette da GialloZafferano, per conto dell'utente.
Sta a parte perché è l'unico pezzo che dipende da un sito che non controlliamo:
se cambia la grafica o l'indirizzo, si sostituisce questo solo modulo.

La ricetta si prende dal **dato strutturato** JSON-LD (`schema.org/Recipe`) che il
sito pubblica per i motori di ricerca: ha nome, dosi e passi già separati, quindi
non si indovina nulla dalla pagina. La foto non si scarica mai.

Tre trappole, tutte già pagate:

- **`RobotFileParser.read()` scarica con lo user agent "Python-urllib/..."**, che
  GialloZafferano respinge con un 403. Il parser legge il 403 come "vietato a
  tutti" e nessuna pagina risulta più leggibile. Il `robots.txt` va scaricato a
  mano con il nostro UA (`_apri`) e passato a `parse()`. Se il `robots.txt` non si
  legge si **procede**: non poterlo leggere non è un divieto.
- **La fonte non è il credito della foto.** Il campo `image_credit` esiste solo
  insieme a una foto (`if image else ""`): una ricetta importata non ha foto,
  quindi la provenienza spariva al salvataggio. La fonte ha una colonna sua,
  `source`, che si salva sempre.
- **Il sito vieta gli agenti AI** (GPTBot, ClaudeBot...) nel `robots.txt`.
  Leggere per conto dell'utente non li riguarda, ma è bene saperlo prima di
  allargare l'uso.

I test non toccano la rete: sostituiscono `_apri` e costruiscono pagine finte col
JSON-LD vero. Si prova l'interpretazione, che è la parte che sbaglia.


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
nomini le funzioni del gioco (vedi «I Giochi: Snake»).

### I Giochi: Snake

I **Giochi** sono una sotto-scheda della TV (`data-tvp="giochi"`, pannello
`data-tvp-panel="giochi"`). Per ora c'è un gioco solo, **Snake**, in
`static/snake.js`: un file a parte, non dentro `app.js`, perché è un pezzo a sé
che si carica con la pagina ma vive di vita propria. Non usa librerie e non usa
la rete: si disegna su un `<canvas>` e funziona **anche senza connessione**,
come il resto della sezione (sta nella scocca del service worker).

La scelta che conta: **la logica è pura e separata dal disegno**. `snakeNuovo`,
`snakePasso` e `snakeDirezione` prendono lo stato e ne restituiscono uno nuovo,
senza DOM e senza attese, e ricevono un `rand` iniettato. Così si eseguono
**davvero** con node nei test — che è l'unico modo di verificare un gioco senza
giocarlo — e il disegno (`snakeDisegna`) e i comandi restano l'unica parte che
non si può provare con un test unitario.

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

