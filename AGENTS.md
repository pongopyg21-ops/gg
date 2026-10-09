# Il Maggiordomo — note per gli agenti

## ⭐ SEI APPENA ARRIVATO? Leggi qui (versione V.8)

Questa è la **V.8**. Il progetto è **maturo e funzionante**: non serve riscrivere
niente, serve **continuare**. Prima di tutto:

1. Avvia: `./avvia.sh` (all'inizio di ogni conversazione il server **non** è
   attivo: il container viene ricreato, è normale). Avvia anche la sorveglianza,
   quindi non serve più lanciare `./sorveglia.sh` a parte.
2. Test: `./avvia.sh test` → attesi **836 verdi**. Se non lo sono, fermati e dillo.
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
(vedi `tv.py`), il quiz e i giochi (Snake e Memory, vedi `static/snake.js` e `static/memory.js`) e le locandine
dei film del momento sulle piattaforme di streaming, una alla volta (vedi
`cinema.py`). Il **Cinema** non ha più una sezione sua:
è intrattenimento come i video e le notizie, e sta dentro la TV. Il **GYM**
resta invece una sezione a sé, perché è una cosa diversa — si guarda *per fare*,
non per passare il tempo.

Il **dettaglio** di ciascun sottosistema (formato dei feed, trappole della voce,
regole del calendario, convenzioni di un'area) **non è più qui**: sta in `docs/`,
vedi «Approfondimenti (caricati su richiesta)». Apri il documento dell'area che
stai toccando **prima** di modificarla; questo file tiene l'avvio, l'architettura e
le invarianti trasversali.

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
   conversazione il token resterebbe. **Come per `AZURE_SPEECH_KEY`, il segreto
   si inietta solo se il suo nome compare nel testo del comando**: `./avvia.sh
   pubblica` da solo non basta, e `pubblica` dice "GitHub non ha accettato le
   credenziali" mentre il token c'e' — e' quello che e' successo. Si scrive
   `GITHUB_TOKEN="$GITHUB_TOKEN" ./avvia.sh pubblica`.

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
  modello di casa (Ollama) e' pronto: se risponde e se il modello che l'app si
  aspetta e' scaricato. `avvia.bat` lo chiama a ogni avvio (poche righe, senza
  fermare la finestra). La configurazione si **chiede all'app**
  (`import comprensione`), non si riscrive nello script: due copie
  della stessa regola divergono, e allora lo stato all'avvio mente — la stessa
  scelta di `avvia.sh` per la voce Azure. Serve perche' il sintomo «il modello
  non capisce» ha due cause (Ollama spento, modello non scaricato) che danno lo
  stesso effetto. L'interruttore in Profilo non esiste piu': la comprensione col
  modello e' sempre attiva, quindi non e' piu' una causa del sintomo.

Cose che sembrano dettagli e non lo sono:

- **Lo stato del modello si legge dalla cartella dell'app, non da `windows\`.**
  `avvia.bat` fa `cd /d "%~dp0"` (entra in `windows\`) e poi chiama
  `modello.ps1`, che esegue `python -c "import comprensione"`. Il processo python
  eredita la cartella corrente, e da `windows\` i moduli non si trovano:
  l'import falliva e lo stato diceva «Modello: non riesco a leggere la
  configurazione dell'app. Avvia l'app una volta con avvia.bat e riprova» —
  proprio mentre l'utente **stava** usando `avvia.bat` e tutto era a posto. Il
  rimedio e' `Push-Location $App` intorno alla chiamata. Il difetto e' di
  **percorso**, quindi non si vede leggendo il codice: il test
  `test_lo_stato_del_modello_si_legge_anche_da_windows` esegue il comando vero
  dalla cartella dell'app e pretende che risponda.
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
  temporanea (`houses.REGISTRY_PATH`, `houses.CASE_DIR` in `conftest.py`), così i
  test non toccano il `houses.db` vero. La fixture `client` collega la casa di prova
  e la `anon` no: i test dell'accesso usano `anon`.
- **I test sono spezzati per modulo**: un tempo erano un solo `test_cucina.py` da
  quasi 12.000 righe, ora sono `test_*.py` (uno per area: `test_cinema.py`,
  `test_voce.py`, `test_igiene.py`…). Le **fixture** (percorsi dei dati, `client`,
  `casa_test`, `anon`) stanno in `conftest.py`, dove pytest le scopre da sola;
  gli **helper** e le costanti condivise in `test_comuni.py`, che ogni file importa
  con `from test_comuni import *`. Aggiungendo un test si usa il file dell'area;
  aggiungendo un helper condiviso, `test_comuni.py`. `./avvia.sh test` esegue
  `pytest -q` (tutta la cartella), non un file: i file sono più d'uno.

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

**Il resto delle convenzioni è diviso per argomento** (il blocco era ~54 KB, metà
di questo file): ricette/ricettario, spesa, home, igiene, dispensa, magazzino,
progetti, voce, FAQ e cassaforte. Prima di toccare uno di questi sottosistemi,
apri il documento corrispondente in `docs/` (vedi «Approfondimenti»).

## Interfaccia mobile

Il layout sotto i 560px è una sola colonna. Tre vincoli da non rompere quando si tocca il CSS:

- Gli input del telefono usano `font-size: 16px`: sotto questa soglia iOS ingrandisce la pagina al primo tocco e non torna indietro.
- La dispensa è una tabella che diventa elenco di schede. Le etichette di colonna arrivano da `data-label` sulle celle, generato in `renderPantry`, e sono mostrate via `::before`: aggiungendo una colonna va aggiunto anche il `data-label`.
- I bersagli toccabili hanno `min-height: 42px`.
- Il pulsante vocale è `position: fixed` in basso a destra, quindi `main` ha `padding-bottom` generoso: senza, il pulsante coprirebbe l'ultima voce delle liste. Lo `z-index` (40) è sotto i modali, così non galleggia sopra le finestre aperte. Il pulsante Home flottante (`.home-fab`) sta nello stesso punto ma a sinistra: se un domani si aggiunge un terzo pulsante, va tenuto conto che gli angoli bassi sono occupati.
- **Il pulsante vocale flottante è nascosto in home** (`tornaAlleSezioni` lo rimette `hidden`), perché lì non c'è una sezione da cui parlare. Al suo posto c'è `.home-mic`, dentro l'hero: è push-to-talk come il flottante (si tiene premuto e si parla), e un tocco breve apre il pannello. Il pannello `#voice` sta **fuori** da `#app`, quindi funziona anche a sezioni chiuse — ma i comandi che ricaricano una scheda chiamano `apreSezioneDella()`, che apre prima l'area giusta. Senza, la scheda si attiverebbe sotto un'intestazione che non le appartiene.
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
- **Un colore d'accento non è un colore da testo.** `--sand` (#b0761c) basta a una stella o a un bordo — elementi grafici, soglia 3:1 — ma su fondo chiaro si ferma a 3,4:1 e non regge una parola (4,5:1). Da qui `--sand-testo` (#8a5a12, 5,2:1), usata dalle scadenze «vicino» e dall'etichetta dell'ambiente *soggiorno*. La lezione vale in generale: **quando un colore serve a scrivere, serve una variabile sua**, non la si riusa da un accento decorativo.
- **Un fondo chiaro fisso è una trappola nel tema scuro.** L'etichetta dell'ambiente *soggiorno* aveva fondo sabbia `#f6efe3` scritto a mano e testo `var(--sand)`, che di notte diventa chiaro: testo dorato su fondo dorato, **1,85:1**, illeggibile. I fondi tenui delle zone della casa sono ora variabili con il **testo accanto** (`--zona-soggiorno` / `--zona-soggiorno-testo`, e così bagno, cucina, camere), così il tema scuro li scurisce e schiarisce insieme. La regola: un fondo che non è `--paper`/`--surface` e non cambia col tema è un difetto latente.
- Il test `test_i_testi_colorati_restano_leggibili_nei_due_temi` calcola il contrasto WCAG vero (luminanza relativa) delle coppie testo/fondo **in entrambi i temi** e pretende ≥4,5:1: un colore fissato a mano fuori dalla palette non si vede leggendo il codice, e torna a ogni cambio di tema. Verificato che **fallisce** se si rimette il fondo chiaro sotto il testo chiaro (1,85:1), quindi non è un test vacuo.
- Le cifre delle quantità usano `tabular-nums`.
- **Lo sfondo della home respira, ma è discreto** (`.home::before`, `home-respira`): tre aloni del mare dietro le schede, in movimento lentissimo (30 s) e di pochi punti percentuali. È la sola pagina dove il fondo si muove — le aree sono di lavoro e restano piatte. Sta su un `::before` con `z-index: -1`, quindi i riquadri (opachi) restano leggibili e il testo non ci finisce mai sopra. I colori sono **trasparenze** del tema (`--home-alone-1/2/3`, ~10%): non coprono niente, e il tema scuro si schiarisce da solo invece di restare a macchie. Chi ha chiesto meno movimento non vede niente animarsi (la regola globale `prefers-reduced-motion` spegne anche questo). Il test `test_lo_sfondo_della_home_e_dinamico_ma_discreto` fissa trasparenze, lentezza, `z-index` e i colori in entrambi i temi.
- **Un velo diagonale attraversa la home** (`.home::after`, `home-gradiente`, 46 s). È lo stesso «fondo che vive» degli aloni, ma con un movimento **di passaggio** invece che di respiro: un gradiente che scorre da un bordo all'altro, così l'occhio lo coglie appena. **Non introduce nessun colore nuovo** — si costruisce solo con `--home-alone-1/2` del tema, quindi cambia il disegno, non la tavolozza. **Resta dentro la sezione** (`inset: 0`): il movimento lo danno `background-size` e `background-position`. Un `inset` negativo lo farebbe sporgere oltre l'ultimo riquadro e la home scorrerebbe oltre l'intestazione «Il Maggiordomo» — è il difetto visto dall'utente, e il test lo tiene fuori. `test_lo_sfondo_della_home_e_dinamico_ma_discreto`: pretende `.home::after`, le tinte del tema, nessun `#...` fisso, `z-index: -1`, `pointer-events: none`, `inset: 0` e un'animazione ≥ 30 s.
- **Le figure geometriche della home** (`#doodle-aq-*` nello sprite `<svg class="sprite-doodle">`, `.home-doodle` per il fondo e `.home-card-figura` **dentro ogni scheda**). Sono **forme mid-century** da poster di scuola Bauhaus — cerchi pieni, semicerchi (cupole), archi annidati, barre, falci e quarti di cerchio — non disegni di oggetti: niente pesci, onde o macchie informi. Il riferimento è un poster astratto tipo «Berlin Shapes» (cerchi neri, semicerchi beige, archi). Sono **campiture nette**: nessun filtro di sfocatura (prima c'era `#acquerello` con `feGaussianBlur`, rimosso). Il colore viene dal tema con `--sh-ink/--sh-ochre/--sh-clay/--sh-beige` (di notte diventano contorni di gesso su fondo profondo), quindi la palette non è fissa. Stanno **dietro** al contenuto (`z-index: -1`) e con `pointer-events: none`: non coprono mai un testo né rubano un tocco. Le posizioni del fondo stanno solo nelle **fasce libere** della home — la fascia alta, ai lati del blocco vocale, e quella bassa dopo le schede — non in mezzo, dove «Oggi», il calendario e le notizie cambiano altezza e una figura dietro un pannello opaco sarebbe invisibile. **Su ogni scheda** la figura è lo sfondo a tutta larghezza (`.home-card-figura`, `slice`), coperta da un **velo di carta** (`--surface-velo`: di giorno quasi bianco, di notte un velo scuro) perché sotto c'è del testo: la filigrana resta bassa e il contrasto lo verifica un test (l'inchiostro del testo sotto il velo resta sopra 4.5:1).
- **`position` non si applica ai figli di un SVG.** Il primo tentativo era un unico SVG con dentro delle `<use>` posizionate in assoluto: restavano **in flow**, tutte in una fascia, e le figure non comparivano dove previsto. Un elemento `<use>` (o `<path>`, `<rect>`…) è un *graphics element*, non una scatola CSS: non è posizionabile. Nel **fondo** ogni figura è quindi un **`<svg>` a sé** che richiama il suo `<symbol>` (l'SVG esterno è un elemento rimpiazzato e accetta `position: absolute`). **Nelle schede** è invece il contenitore `.home-card-figura` a fare da scatola (`position: absolute; inset: 0`), con dentro un solo `<svg>` che riempie: lì una `<use>` va bene, perché a posizionarsi è il contenitore. Il test `test_le_illustrazioni_della_home_sono_forme_geometriche` pretende `<svg>` (non `<use>`) nel livello del fondo, l'assenza di sfocatura, le forme nei symbol, lo sfondo su tutte e sei le schede, il velo, e verifica con un calcolo di luminanza che il velo non scenda sotto 4.5:1.

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


## Approfondimenti (caricati su richiesta)

Questo file tiene l'avvio, l'architettura e le invarianti; i capitoli lunghi di
dettaglio stanno in `docs/` e si aprono **solo quando servono**, così l'agente non
si porta dietro ~50k token di contesto a ogni turno.

| Quando ti serve… | Apri |
| --- | --- |
| Voce: comandi, push-to-talk (il default), "Hey GG"/sveglia, microfono, voce neurale | `docs/voce-e-ascolto.md` |
| Capire i comandi col modello (LLM/Ollama) | `docs/comprensione-llm.md` |
| TV, notizie, quiz, arte, Giochi, GYM, Cinema | `docs/tv-cinema-giochi.md` |
| Calendario degli impegni e promemoria | `docs/calendario.md` |
| Convenzioni: ricette, spesa, dispensa, home | `docs/convenzioni-cucina.md` |
| Convenzioni: migrazioni, magazzino, progetti, igiene | `docs/convenzioni-dati-igiene.md` |
| Convenzioni: pasti, FAQ, cassaforte, biometria, profili | `docs/convenzioni-faq-profili.md` |

L'architettura di base resta qui sotto; i moduli elencati in "Architettura" hanno
il loro capitolo di dettaglio in `docs/` quando esiste.


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



## Il Calendario: gli impegni con un promemoria

Sta in **Progetti**, in una scheda a parte. Modulo `calendario.py`, tabella
`appointments`. Dettaglio completo (date, promemoria, categorie, rotte):
`docs/calendario.md`.
