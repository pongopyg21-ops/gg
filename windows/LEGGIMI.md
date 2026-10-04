# Il Maggiordomo su Windows

Questa cartella serve a far girare l'app su un computer di casa, sempre accesa,
così il telefono e gli altri dispositivi la trovano sempre allo stesso indirizzo.

I file di questa cartella sono questi:

| File | A cosa serve |
| --- | --- |
| `avvia.bat` | Avvia l'app. La prima volta prepara tutto da solo |
| `installa.bat` | Fa partire l'app da sola a ogni accesso a Windows |
| `indirizzo.ps1` | Usato da `avvia.bat`, non serve toccarlo |
| `dominio.bat` | Attiva l'indirizzo pubblico con HTTPS (vedi *Un indirizzo da fuori casa*) |
| `dominio.ps1` | Usato da `dominio.bat`, non serve toccarlo |
| `verifica-pubblico.bat` | Controlla se l'app è raggiungibile da fuori (vedi *Controllare in un colpo solo*) |
| `verifica-pubblico.ps1` | Usato da `verifica-pubblico.bat`, non serve toccarlo |
| `verifica-modello.bat` | Controlla se il modello di casa (Ollama) è pronto (vedi *Il modello in casa*) |
| `modello.ps1` | Usato da `avvia.bat` e `verifica-modello.bat`, non serve toccarlo |
| `voce.bat` | Imposta chiave e area della voce neurale Azure |
| `ripara-voce.bat` | Corregge solo l'area della voce, senza toccare la chiave |

Sono due passi, nell'ordine scritto. Servono all'incirca dieci minuti, più il tempo
dei download, che sono due: **Python** (installazione, circa 30 MB) e **l'app**
(un file ZIP, circa 2 MB). **Git non serve.**

`dominio.bat` è la parte facoltativa: serve solo se vuoi usare l'app **da fuori
casa** o **dettare a voce dal telefono**. Per usarla in casa basta `avvia.bat`.

---

## Passo 1 — Porta l'app sul computer

Sono due clic, e si fa prima di installare Python: è più facile quando si è già
visto dove finiscono i file.

1. Apri questo indirizzo nel browser:
   <https://github.com/pongopyg21-ops/gg/archive/refs/heads/main.zip>
   Il download parte da solo (circa 2 MB).
2. Vai nella cartella **Download**, clic destro sul file `gg-main.zip` → **Estrai
   tutto** → **Estrai**.
3. Ottieni una cartella dal nome strano, **`gg-main`**. Va benissimo così: il nome
   della cartella non conta, puoi anche rinominarla in `Maggiordomo` se preferisci.
   Spostala dove vuoi tenere l'app (per esempio in `C:\`), e **dentro quella
   cartella** troverai la sottocartella `windows`.

   **Non metterla dentro `C:\Windows`, né dentro `C:\Programmi` / `C:\Program
   Files`.** Sono cartelle protette: Windows impedisce all'app di creare lì il
   proprio ambiente, e l'avvio si ferma con `WinError 5 Accesso negato`. Se ti
   succede, non è rotto niente: sposta la cartella in `C:\`, o in *Documenti*, o
   sul Desktop, e riapri `avvia.bat`. Una posizione comoda e sicura è `C:\gg-main`.

Da qui in avanti, quando queste istruzioni dicono `windows\avvia.bat`, significa:
dentro la cartella `gg-main` (o come l'hai chiamata), la sottocartella `windows`, il
file `avvia.bat`.

**Se un giorno ti serve aggiornare l'app**, riscarica lo ZIP e sostituisci i file
del codice: i tuoi dati (i file `.db`) non sono nello ZIP, quindi restano al loro
posto. In alternativa `MAGGIORDOMO_DATA` (vedi in fondo) tiene i dati
completamente separati dal codice.

### Alternativa: con Git (serve installare Git)

Se hai già Git, o se vuoi poter aggiornare con un comando solo:

```powershell
git clone https://github.com/pongopyg21-ops/gg.git
cd gg
```

Il branch **`main`** e' il progetto definitivo e contiene tutto, `windows\`
compreso: dopo il clone l'app e' pronta, senza altri comandi.

Git si scarica da <https://git-scm.com/download/win>. Nell'installazione lascia
le opzioni proposte: mettono Git nel PATH, ed è quello che serve perché il comando
`git` funzioni. Se hai già provato `git` e hai visto *"Termine 'git' non
riconosciuto"*, Git non è installato: o lo installi, o usi lo ZIP qui sopra, che
non richiede nulla.

## Passo 2 — Installa Python

L'app ha bisogno di Python. Se ce l'hai già, salta al passo 3.

1. Vai su <https://www.python.org/downloads/windows/> e scarica **Python 3**.
2. Apri il file scaricato.
3. **Importante:** nella prima schermata spunta **Add python.exe to PATH**
   (è in fondo, in piccolo, e se non lo spunti l'app non parte).
4. Clicca *Install Now* e aspetta.

## Passo 3 — Avvia una volta a mano

Doppio clic su **`windows\avvia.bat`**.

La prima volta prepara l'ambiente e installa le dipendenze: ci mette un minuto.
Poi mostra qualcosa così:

```
  Sul computer:   http://localhost:12000
  Dal telefono:   http://192.168.1.50:12000
```

Apri `http://localhost:12000` sul computer. **La primissima volta l'app è vuota:**
ti chiederà di creare una casa. È il momento di rimettere i tuoi dati (passo 4),
altrimenti riparti dalle ricette di esempio.

Lascia quella finestra aperta: **chiuderla significa fermare l'app.**

## Passo 4 — Rimetti i tuoi dati

L'app nuova non ha i tuoi dati: ricette, dispensa, pulizie, progetti, ecc.
Per portarli:

1. Apri l'app **vecchia** (il link che ti ho dato), vai su **Cucina → Profilo**,
   in fondo, e clicca **Scarica una copia dei dati**.
2. Ottieni un file `.zip`. Dentro c'è il database e un file `LEGGIMI.txt` che
   spiega dove metterlo.
3. In pratica: apri lo `.zip`, prendi il file `.db` che trovi, e copialo nella
   cartella `case\` dell'app nuova (se nella vecchia non c'era la voce
   `case\`, copialo nella cartella principale, accanto a `app.py`).
4. Riavvia l'app (chiudi la finestra e riapri `avvia.bat`).

Ora la casa nuova contiene tutto il lavoro fatto.

## Passo 5 — Fallo partire da solo

Doppio clic su **`installa.bat`**.

Da adesso l'app parte da sola quando accendi il computer e accedi a Windows, e se
si ferma riparte entro un minuto. La finestra resta ridotta a icona.

Per toglierlo, se un giorno non ti serve più:

```powershell
windows\installa.bat rimuovi
```

**Sul computer usa `http://localhost:12000`.** Non è un dettaglio: il browser
considera `localhost` un indirizzo sicuro, quindi sul computer funziona **anche la
voce** (il microfono, per parlare all'app). Da un indirizzo di rete il browser
blocca il microfono, perché non è una connessione sicura.

## Passo 6 — Dal telefono

Sul telefono apri `http://192.168.1.50:12000` (l'indirizzo che mostra `avvia.bat`).
Funziona tutto **tranne il microfono**: il browser pretende una connessione sicura
per ascoltare, e un indirizzo di rete non lo è.

Al momento il telefono serve quindi a **leggere e consultare** — piano pasti,
ricette, lista della spesa, FAQ, pulizie — e a **far leggere all'app** ad alta
voce. Per dettare i comandi a voce dal telefono serve ancora un passaggio, che
posso preparare se ti serve.

---

## L'indirizzo fisso (perché il telefono trovi sempre l'app)

Il router assegna l'indirizzo al computer quando si accende, e può cambiarlo: è il
motivo per cui un giorno il telefono si collega e il giorno dopo no. Si risolve una
volta sola, **nel router**, dicendogli di dare sempre lo stesso indirizzo a questo
computer. Da lì in poi l'indirizzo mostrato da `avvia.bat` non cambia più.

Serve l'indirizzo **MAC** del computer, che è come il router lo riconosce.

1. Apri il **Prompt dei comandi** (cerca "cmd" nel menu Start) e scrivi:
   `ipconfig /all`
   Scorri fino alla scheda di rete attiva (quella con "Gateway predefinito"
   compilato) e cerca **Indirizzo fisico**: è una serie di coppie tipo
   `A1-B2-C3-D4-E5-F6`. Quello è il MAC. Lo stesso indirizzo si vede anche
   nell'elenco dei dispositivi collegati del router.

2. Entra nelle impostazioni del router: apri il browser su `http://192.168.1.1`
   (o `192.168.0.1`; se nessuno dei due risponde, l'indirizzo esatto è il
   "Gateway predefinito" letto al punto 1) e accedi con le credenziali del router.
   Se non le hai, sono spesso scritte su un'etichetta sotto il router stesso.

3. Cerca la voce **Prenotazione DHCP** o **DHCP statico** (a volte si chiama
   "Riserva indirizzo IP", "IP statico locale", "Assegna IP fisso"). Cambia fra i
   router, ma si trova sempre sotto le impostazioni della rete o del DHCP.

4. Aggiungi una prenotazione usando il MAC del punto 1 e scegli un indirizzo
   **fuori dall'intervallo** che il router distribuisce da solo, per esempio
   `192.168.1.50`. Salva.

5. Riavvia il computer (o disattiva e riattiva il Wi-Fi), poi riapri `avvia.bat`:
   l'indirizzo mostrato è quello prenotato, e da adesso è sempre lo stesso.

**Due avvertenze.** La prima: la prenotazione va fatta **nel router**, non
impostando un indirizzo fisso dentro Windows. Impostarlo in Windows è più
complicato e, se l'indirizzo scelto rientra in quelli che il router distribuisce,
due dispositivi possono ritrovarsi lo stesso indirizzo e nessuno dei due funziona.
La seconda: dopo la prenotazione conviene togliere l'impostazione manuale, se in
Windows ne era stata messa una.

**La prima volta che il telefono si collega**, Windows chiede il permesso di
accettare connessioni: va concesso, altrimenti il telefono non passa. Il rimedio,
se la richiesta è stata annullata, è nella sezione *Se qualcosa non va* qui sopra.

Anche con l'indirizzo fisso **restano fuori due cose, ed è il browser a
pretenderlo, non l'app**: dal telefono e da qualunque indirizzo di rete **il
microfono non funziona** (serve una connessione sicura, e `localhost` è sicuro
mentre un indirizzo di rete no), e **l'app non è raggiungibile da fuori casa**.
Per avere tutte e due serve un dominio con HTTPS davanti al computer.

---

## Un indirizzo da fuori casa (con HTTPS)

Servono due cose, e conviene saperle prima di cominciare, perché **Google ha una
regola che un indirizzo gratuito non soddisfa**:

1. **L'app raggiungibile da fuori casa, con HTTPS.** Si fa con Tailscale: gratuito,
   e **non tocca il router**.
2. **L'accesso con Google** richiede invece un **dominio tuo e verificato**: Google
   non accetta un indirizzo gratuito (`ts.net`, e nemmeno i tunnel gratuiti in
   genere) come indirizzo di reingresso. Non è una limitazione di questo progetto,
   è una regola di Google.

Quindi: il passo qui sotto ti dà l'app **da fuori casa e col microfono dal
telefono** — che è già la parte più utile. L'accesso con Google resta fuori portata
finché non c'è un dominio tuo.

### Attivare l'indirizzo

1. **Avvia l'app** (`avvia.bat`) e lasciala in esecuzione: l'indirizzo pubblico
   inoltra su di essa. Senza l'app, l'indirizzo risponde con un errore.
2. **Installa Tailscale** da <https://tailscale.com/download/windows> e accedi con
   un account (Google, Microsoft o GitHub vanno bene). È gratuito per un uso
   personale: non serve pagare.
3. **Doppio clic su `dominio.bat`.** La prima volta si apre il browser per
   un'approvazione: va concessa una volta sola. Poi il file stampa l'indirizzo.
   Se dice che manca il permesso, l'approvazione si fa anche a mano dalla pagina
   **Access controls** del pannello Tailscale (`Add Funnel to policy`).
4. Apri quell'indirizzo dal telefono, **anche in un'altra rete** (dati mobili):
   funziona, ed è HTTPS, quindi **anche il microfono funziona**.

L'indirizzo ha la forma `https://<nome-computer>.<nome-rete>.ts.net` e **non cambia
più**, anche riavviando il computer: viene attivato in modo permanente, non solo per
la sessione corrente.

**Fai partire `avvia.bat` *prima* di `dominio.bat`.** L'indirizzo inoltra su
`127.0.0.1:12000`: se l'app non c'è, Tailscale attiva l'indirizzo lo stesso ma le
richieste non trovano nessuno, e sembra che il tunnel non funzioni.

### Cosa fa Tailscale, per capire se qualcosa non va

- **La porta 443 è quella che vedi tu** (`https://...`, senza `:porta`): è il
  tunnel a ricevere, e inoltra alla 12000 dell'app. Il numero 12000 non compare
  mai nell'indirizzo pubblico.
- **Le porte pubbliche possibili sono tre** — 443, 8443, 10000 — e sono imposte da
  Tailscale, non dalla nostra app: non si può pubblicare direttamente la 12000.
- **`avvia.bat` dichiara `DIETRO_PROXY=1`.** Senza, l'app vede l'indirizzo del
  tunnel al posto di quello di chi bussa, e il freno ai tentativi di accesso conta
  tutti insieme: chi sbaglia la password farebbe aspettare anche gli altri.
- **Per vedere se è attivo**: `tailscale funnel status` mostra l'indirizzo e su
  cosa inoltra. Per spegnerlo: `tailscale funnel --bg 12000 off`.

### Due cose da sapere

- **La prima volta l'indirizzo può impiegare fino a dieci minuti** a rispondere
  ovunque: bisogna aspettare che il nome si propaghi. Se subito dice che non trova
  il sito, riprova poco dopo.
- **Da fuori casa il microfono funziona, ma va fermato l'app con la coscienza
  tranquilla**: la pagina è raggiungibile da chiunque conosca l'indirizzo. La
  protezione è il nome dell'indirizzo, che è lungo e difficile da indovinare, più
  la password della casa. Per un'app di famiglia basta, ma non è una fortezza. Se
  un giorno vuoi qualcosa di più solido, si mette una pagina di accesso davanti.

### Controllare in un colpo solo

Doppio clic su **`verifica-pubblico.bat`**. Non modifica niente e non tocca i
segreti: legge lo stato e dice cosa manca. In una schermata:

1. **l'indirizzo pubblico** (o l'avviso che Funnel non è attivo);
2. **se l'app risponde** su `127.0.0.1:12000`;
3. **se `avvia.bat` dichiara `DIETRO_PROXY=1`** — dietro il tunnel è un proxy, e
   senza quella riga il freno ai tentativi conta tutti i dispositivi su un
   indirizzo solo.

Se i primi due dicono sì, **dovresti poter accedere da fuori**.

Le tre cose che devono essere vere insieme, perché il tunnel da solo non basta:

| Cosa | Come si ottiene | Come si controlla |
| --- | --- | --- |
| L'indirizzo pubblico è attivo | `dominio.bat`, una volta sola | `verifica-pubblico.bat`, punto 1 |
| L'app è in esecuzione | `avvia.bat` (o `installa.bat`) | `verifica-pubblico.bat`, punto 2 |
| Il computer è sveglio | sospensione su «Mai» quando è collegato alla corrente | — |

**Il computer acceso da solo non basta:** o è sospeso e il tunnel non ha nessuno
a cui inoltrare, o l'app è chiusa e la pagina non risponde. Il tunnel resta
attivo anche se l'app è spenta — è il motivo per cui «sembra che il tunnel non
funzioni» quando invece manca solo l'app.

**La password della casa non si tocca per farlo funzionare.** L'app è raggiungibile
da fuori *con* la sua password: è la protezione normale. E resta valido il
consiglio di usare una password non banale, perché l'indirizzo è pubblico.

---

## Se ho perso la password della casa

La password **non si recupera**: nel registro c'e' solo l'impronta, non la
password. Si puo' pero' metterne una nuova, e non serve quella vecchia:

1. Fai doppio clic su `windows\password.bat`.
2. Guarda l'elenco delle case e i dati di ciascuna (quante ricette, quanto pesa):
   e' il controllo che stai per agire sulla casa giusta.
3. Scrivi la password nuova due volte.

I dati non si toccano: ricette, dispensa e magazzino restano dove sono. Cambia
una sola riga nel registro.

Se la password vecchia la ricordi, si cambia invece dall'app, e li' la vecchia
viene chiesta: e' il caso normale.

---

## La voce neurale (facoltativa)

Senza fare niente, l'app usa la voce del sistema, che è quella meccanica. Per
avere la voce naturale Azure, la chiave si configura **prima di avviare l'app**:
non si mette dalla pagina. Un campo chiave nell'interfaccia significherebbe che
l'app può scrivere il segreto, e chi apre la pagina potrebbe cambiarlo.

Il modo più semplice su Windows è `windows\voce.bat`: doppio clic, incolla la
chiave, Invio, conferma l'area, e riapri l'app. Il programma scrive da solo il
file `segreto.bat` nella forma giusta, quindi gli errori di virgolette, spazi o
maiuscole — la causa più comune di "la chiave c'è ma la voce resta quella del
sistema" — non sono possibili.

La chiave la trovi su `portal.azure.com`, nella tua risorsa **Speech**, pagina
**Chiavi ed endpoint**: sono la chiave 1 (o 2) e l'area.

All'avvio leggerai `Voce neurale Azure attiva`, e nella pagina, sotto **Voce**,
comparirà la scelta della voce neurale con l'anteprima.

### «Servizio vocale non raggiungibile: getaddrinfo failed»

Questo errore **non è un problema di rete**, ed è la diagnosi più frequente.
L'indirizzo del servizio contiene l'area:

```
https://<area>.tts.speech.microsoft.com
```

Quindi un'area scritta male è un nome che **non esiste**: la richiesta non parte
nemmeno, e l'errore parla di "getaddrinfo" (il meccanismo che traduce i nomi in
indirizzi). Sembra internet che non funziona, invece è un refuso.

Cosa controllare, in ordine:

1. **`AZURE_SPEECH_REGION`** — deve essere l'area della risorsa, **tutta
   minuscola** e senza spazi: `westeurope`, `italynorth`, `eastus`… Non `IT`,
   non `Italia`, non `Europe`, non `italy north`.
2. **La pagina della risorsa su Azure** (`portal.azure.com` → la tua risorsa
   Speech → **Chiavi ed endpoint**): lì l'area si chiama **Località/Area** e si
   copia da lì. Un refuso di due lettere è il caso tipico.
3. **`segreto.bat`** — se l'area è giusta ma l'errore resta, guarda qui: spazi
   prima o dietro il valore, o righe di esempio col `REM` tolto a metà.

Da questa versione l'app **controlla l'area prima di chiamare** e, se non è una
delle aree Azure valide, lo dice: «L'area «italynorht» non esiste fra quelle
Azure», con la variabile da correggere. Il messaggio di rete non comparirà più
per un refuso.

**Anche l'avvio lo dice.** Prima stampava `Voce neurale Azure attiva` guardando
solo che chiave e area fossero presenti: con l'area sbagliata la riga era una
bugia, e mandava a cercare il guasto altrove. Ora, se l'area non esiste, leggi
`Voce neurale NON attiva: l'area «...» non esiste fra quelle Azure`.

**E `voce.bat` non accetta più un'area inventata.** Prima qualunque cosa scritta
al prompt finiva in `segreto.bat`, anche una lettera sola: è così che è finita lì
l'area `s` — la `S` della conferma (`Scrivi S per salvare`) scritta al posto
sbagliato, perché il prompt dell'area viene **prima** di quello della conferma e
la domanda non era abbastanza chiara. Ora un'area che non esiste viene rifiutata
e richiesta.

**Il modo più sicuro per correggere**: doppio clic su **`windows\ripara-voce.bat`**.
Corregge **solo l'area** e lascia la chiave com'è (che è probabilmente giusta):
ti chiede l'area, la controlla, e scrive la riga nel file che comanda. Se invece
vuoi rifare tutto, `voce.bat` riscrive il file da zero chiedendo anche la chiave.

`ripara-voce.bat` esiste proprio per il caso più comune: l'area sbagliata e la
chiave giusta. Rifare tutto da capo per una lettera costringerebbe a rincollare
la chiave, con il rischio di sbagliarla.

Da terminale, la stessa cosa senza doppio clic:

```
python ripara_voce.py                  # chiede l'area se serve
python ripara_voce.py --area italynorth
```

### Se l'errore resta dopo aver corretto il file

Succede, e la causa è questa: **su Windows i file dei segreti sono due, e ne
comanda uno solo.**

`avvia.bat` chiama `windows\segreto.bat`, che **imposta l'ambiente** del
programma (`set "AZURE_SPEECH_REGION=..."`). Da quel momento l'app usa quel
valore e **non guarda più `segreto.txt`**. Quindi:

- **`windows\segreto.bat`** — comanda quando c'è. È quello che scrive `voce.bat`.
- **`segreto.txt`** (accanto ad `app.py`) — si usa **solo se** `segreto.bat` non
  esiste.

Se hai corretto `segreto.txt` ma `windows\segreto.bat` c'è ancora con l'area
vecchia, l'errore resta e sembra che la correzione non serva a niente. **Correggi
quello che il messaggio ti dice**, o — meglio — **cancella `windows\segreto.bat`
e rilancia `voce.bat`**: così ne esiste uno solo e non c'è niente da indovinare.

Per vedere da dove viene il valore, senza indovinare, c'è un comando
(da terminale, nella cartella dell'app):

```
./avvia.sh diagnosi
```

Risponde così, senza stampare la chiave:

```
chiave : D58n… (84 caratteri)
        da: /percorso/dell/app/segreto.txt
area   : s
        da: /percorso/dell/app/windows/segreto.bat
area valida: NO — non e' un'area Azure
```


### Se preferisci farlo a mano

1. Copia `windows\segreto.esempio.bat` e rinomina la copia in `windows\segreto.bat`.
2. Apri quel file con il Blocco note e riempi le due righe in fondo con la chiave
   e l'area della tua risorsa Azure (spiegato dentro il file).
3. Salva e riavvia l'app.

**La chiave va in `segreto.bat`, non in `avvia.bat`.** La ragione è semplice: il
codice sta su GitHub, `avvia.bat` compreso, quindi una chiave lì dentro finirebbe
online al primo invio. `segreto.bat` è escluso da git: la chiave resta sul tuo
computer. Lo stesso vale per qualunque altra password che ti venga in mente di
mettere nel codice. Nota: il file `segreto.esempio.bat` **non** è escluso, quindi la
tua chiave va nel file rinominato (`segreto.bat`), mai nel modello.

Il piano gratuito Azure include 500.000 caratteri al mese, senza scadenza: per un
uso di casa non si esaurisce. Le voci disponibili sono quelle della tua area: le
due "HD", per esempio, non esistono in tutte le aree, e l'app mostra solo quelle
che funzionano davvero.

### Se l'app gira sul server (non su Windows)

Nella cartella dell'app si usa un file di testo, `segreto.txt`:

1. Copia `segreto.esempio.txt` e rinomina la copia `segreto.txt`.
2. Apri il file e scrivi la chiave e l'area al posto dei segnaposto:
   `chiave: ...` e `area: italynorth`.
3. Riavvia l'app.

Non c'è sintassi da rispettare: niente `export`, niente virgolette. Il file può
anche chiamarsi solo `segreto`, senza estensione, e le due righe si possono
scrivere senza etichetta (una parola tutta minuscola è l'area, l'altra è la
chiave). Restano validi anche `segreto.sh` e `segreto.bat` per chi li ha già.

Non serve esportare niente a mano: l'app legge il file da sola. È lo stesso
meccanismo di `segreto.bat`, e la ragione è la stessa — senza, ogni riavvio
richiederebbe di ricordarsi la chiave, e un riavvio senza chiave fa tornare la
voce meccanica senza che si capisca il perché.

Per verificare che sia attiva:

```
curl -s localhost:12000/api/voce/config | grep -o '"cloud":[a-z]*'
```

Se dice `"cloud":false` la chiave non è arrivata; se dice `true` la voce naturale
è pronta, e nella pagina compare la scelta della voce con l'anteprima.

## Capire i comandi con un modello (facoltativo)

Senza fare niente, i comandi a voce li capisce un piccolo insieme di regole. Bastano
per le frasi previste («aggiungi il latte in dispensa»), non per tutte le altre:
«dammi la lista della spesa» o «fammi vedere la dispensa» restano senza risposta.
Con un modello linguistico si capiscono anche quelle.

Non è obbligatorio: se non lo configuri, l'app funziona esattamente come prima.

### Il modello in casa, con Ollama (gia' pronto)

Ollama fa girare un modello **dentro il tuo computer**: e' gratuito, non serve una
chiave, non serve internet, e quello che dici non esce di casa. **L'app e' gia'
impostata per usarlo**: non c'e' niente da configurare, bastano due cose.

1. Scarica Ollama da <https://ollama.com/download/windows> e installalo. Si avvia
   da solo e resta nella tray.
2. Apri il terminale (scrivi `cmd` nella barra di ricerca di Windows) e scarica il
   modello che l'app si aspetta:

   ```
   ollama pull qwen2.5:7b-instruct
   ```

   Serve circa 5 GB di spazio e un computer con 16 GB di memoria. Con 8 GB di
   memoria usa `qwen2.5:3b-instruct`: e' piu' leggero e meno preciso, e allora
   va detto anche all'app (vedi come cambiare modello in fondo).
3. Apri l'app con `avvia.bat`, vai in **Profilo → «Capire i comandi»** e accendi
   l'interruttore. Fatto.

Il primo comando e' lento (il modello si sta caricando in memoria, anche mezzo
minuto); dal secondo in poi risponde in pochi secondi.

Dimenticato come si chiama il modello scaricato? `ollama list` lo elenca.

All'avvio `avvia.bat` dice da solo a che punto sei: se Ollama risponde, se il
modello c'e', e — quando tutto e' pronto — che resta da accendere l'interruttore
in **Profilo → «Capire i comandi»**. Per il controllo completo apri
`windows\verifica-modello.bat`: guarda le stesse cose e, se manca qualcosa, dice
cosa fare. Serve proprio perche' le tre cause (Ollama spento, modello non
scaricato, interruttore spento) danno lo stesso sintomo — «il modello non
capisce» — e senza il controllo si confondono fra loro.

### Se vuoi cambiare modello o usare un servizio in rete

Per cambiare modello basta una riga. Copia `windows\segreto.esempio.bat`, rinomina
la copia `windows\segreto.bat`, e in fondo togli il `REM` dalla riga che ti serve:

```bat
set "LLM_MODEL=qwen2.5:3b-instruct"
```

La stessa via vale per un servizio in rete compatibile OpenAI, con in piu' la
chiave e l'indirizzo del servizio:

```bat
set "LLM_BASE_URL=l'indirizzo-del-servizio"
set "LLM_MODEL=il-modello-scelto"
set "LLM_API_KEY=la-tua-chiave"
```

Attenzione: cosi' facendo le frasi che detti escono di casa. Con Ollama no. E la
chiave non va mai in `avvia.bat`: sta nel `segreto.bat`, che e' escluso da git.

### Se il modello «non capisce niente»

Quasi sempre è una delle tre cose, in quest'ordine:

1. **Ollama non è in esecuzione.** Deve esserci la sua icona nella tray. Riapri
   Ollama e riprova; non c'è niente da reinstallare.
2. **Il modello non è quello che l'app si aspetta.** L'app usa
   `qwen2.5:7b-instruct`: controlla con `ollama list`. Se ne hai un altro, o lo
   scarichi, o lo dici all'app (vedi sopra «cambiare modello»).
3. **L'interruttore è spento.** Controlla **Voce → «Capire i comandi»**.

Se dopo questo resta lento o sbaglia spesso, è il modello: un modello piccolo in
casa è meno preciso di uno grande in internet. Non c'è niente di rotto — e quando
sbaglia, l'app usa comunque le regole di prima.

---

## Se qualcosa non va

**Ho scritto `git` e dice "Termine 'git' non riconosciuto".**
Git non è installato, e non serve: va benissimo la strada dello ZIP al Passo 1. Se
proprio vuoi Git, installalo da <https://git-scm.com/download/win>, chiudi e riapri
la finestra, e riprova.

**L'app non parte, la finestra si chiude subito.**
Apri `avvia.bat` e guarda il messaggio: dice cosa manca. Quasi sempre è Python
installato senza la spunta *Add python.exe to PATH*: reinstalla spuntandola.

**`WinError 5 Accesso negato`, con un percorso che comincia con `C:\Windows`.**
La cartella dell'app è stata estratta dentro una cartella protetta da Windows, che
non permette all'app di creare lì il proprio ambiente. Non si è rotto niente: chiudi
la finestra, **sposta la cartella dell'app** in `C:\` (o in *Documenti*, o sul
Desktop) e riapri `avvia.bat`. Vale lo stesso se il percorso contiene `C:\Programmi`
o `C:\Program Files`.

**Non trovo la cartella `windows` (o `avvia.bat`).**
Stai guardando fuori dalla cartella dell'app. Deve essere: `gg-main` (o come l'hai
chiamata) → dentro → `windows` → dentro → `avvia.bat`. Se `windows` non c'è
proprio, hai estratto una cartella diversa: l'indirizzo giusto è quello al Passo 1
(branch `main`).

**Windows dice che il file è bloccato, o non succede niente al doppio clic.**
I file scaricati da internet portano un "marchio" di provenienza, e Windows può
bloccarli per prudenza. Rimedio: clic destro sul file `gg-main.zip` **prima** di
estrarlo → **Proprietà** → in fondo, spunta **Sblocca** → OK. Poi estrai. Se lo hai
già estratto, puoi farlo sui singoli file dentro la cartella `windows`.

**Il telefono non si collega.**
1. Telefono e computer devono essere **sulla stessa rete Wi-Fi**.
2. Windows chiede il permesso la prima volta che l'app accetta connessioni:
   se hai cliccato *Annulla*, il telefono non passa. Per riabilitarlo: *Pannello
   di controllo → Sistema e sicurezza → Windows Defender Firewall → Consenti
   un'app*, e metti la spunta su Python (sia *Privata* che *Pubblica*).
3. L'indirizzo del computer può essere cambiato: rileggilo da `avvia.bat`. Se
   succede spesso, la cura è la prenotazione nel router descritta in **L'indirizzo
   fisso** qui sopra: da lì l'indirizzo non cambia più.

**Da fuori casa non funziona (o il telefono non carica l'indirizzo `ts.net`).**
Quasi sempre manca una delle tre cose, e si distinguono con
**`verifica-pubblico.bat`**:
1. **Funnel non è attivo**: si riattiva con `dominio.bat`. Il tunnel non parte da
   solo al riavvio del computer — una volta attivato con `--bg` resta, ma se è
   stato spento va riacceso.
2. **L'app è spenta**: il tunnel resta attivo anche senza app, ma non c'è nessuno
   a cui inoltrare. Avvia `avvia.bat` (o installa l'avvio automatico con
   `installa.bat`).
3. **Il computer è sospeso**: sospensione e ibernazione interrompono tutto. Metti
   la sospensione su «Mai» quando è collegato alla corrente.

Se invece l'indirizzo risponde **subito dopo l'attivazione** con un errore di
sito non trovato, è normale: il nome può impiegare fino a dieci minuti a
propagarsi. Riprova poco dopo.

**La pagina si apre ma i dati non ci sono.**
Il database è finito nella cartella sbagliata. Guarda dove hai messo il file
`.db`: se nella vecchia casa c'era una cartella `case\`, il file va lì. Riapri
`LEGGIMI.txt` dentro lo `.zip`: indica il percorso esatto.

**La voce non funziona sul telefono.**
È previsto, ed è il browser: sul telefono serve una connessione sicura. Sul
computer, con `localhost`, funziona.

**Ho acceso la comprensione col modello, ma non capisce lo stesso.**
Vai alla sezione **Capire i comandi con un modello**: quasi sempre è Ollama spento,
il modello non è `qwen2.5:7b-instruct`, o l'interruttore in **Voce → «Capire i
comandi»** da riaccendere. Non è un guasto dell'app.

**Voglio salvare i dati su un disco esterno.**
In `avvia.bat` c'è una riga `REM set "MAGGIORDOMO_DATA=..."`: togli `REM`, metti
il percorso, e i dati andranno lì. Attenzione: deve restare lo stesso a ogni
avvio, altrimenti l'app non li trova e sembra vuota.
