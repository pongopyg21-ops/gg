# Il Maggiordomo su Windows

Questa cartella serve a far girare l'app su un computer di casa, sempre accesa,
così il telefono e gli altri dispositivi la trovano sempre allo stesso indirizzo.

Sono tre file:

| File | A cosa serve |
| --- | --- |
| `avvia.bat` | Avvia l'app. La prima volta prepara tutto da solo |
| `installa.bat` | Fa partire l'app da sola a ogni accesso a Windows |
| `indirizzo.ps1` | Usato da `avvia.bat`, non serve toccarlo |

Sono due passi, nell'ordine scritto. Servono all'incirca dieci minuti, più il tempo
dei download, che sono due: **Python** (installazione, circa 30 MB) e **l'app**
(un file ZIP, circa 2 MB). **Git non serve.**

---

## Passo 1 — Porta l'app sul computer

Sono due clic, e si fa prima di installare Python: è più facile quando si è già
visto dove finiscono i file.

1. Apri questo indirizzo nel browser:
   <https://github.com/pongopyg21-ops/gg/archive/refs/heads/gg.zip>
   Il download parte da solo (circa 2 MB).
2. Vai nella cartella **Download**, clic destro sul file `gg-gg.zip` → **Estrai
   tutto** → **Estrai**.
3. Ottieni una cartella dal nome strano, **`gg-gg`**. Va benissimo così: il nome
   della cartella non conta, puoi anche rinominarla in `Maggiordomo` se preferisci.
   Spostala dove vuoi tenere l'app (per esempio in `C:\`), e **dentro quella
   cartella** troverai la sottocartella `windows`.

Da qui in avanti, quando queste istruzioni dicono `windows\avvia.bat`, significa:
dentro la cartella `gg-gg` (o come l'hai chiamata), la sottocartella `windows`, il
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
git checkout gg
```

Il terzo comando **non è facoltativo.** Il branch principale (`main`) è fermo a
una versione vecchia: senza `git checkout gg` ti trovi un'app senza case separate,
senza voce neurale e — soprattutto — **senza la cartella `windows\`**, e quindi
senza `avvia.bat`. Se dopo il clone non vedi la cartella `windows`, è questo il
motivo.

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

## La voce neurale (facoltativa)

Senza fare niente, l'app usa la voce del sistema. Per la voce neurale Azure:

1. Copia `windows\segreto.esempio.bat` e rinomina la copia in `windows\segreto.bat`.
2. Apri quel file con il Blocco note e riempi le due righe in fondo con la chiave
   e l'area della tua risorsa Azure (spiegato dentro il file).
3. Salva e riavvia l'app.

All'avvio leggerai `Voce neurale Azure attiva`, e nella pagina, sotto **Voce**,
comparirà la scelta della voce neurale con l'anteprima.

**La chiave va in `segreto.bat`, non in `avvia.bat`.** La ragione è semplice: il
codice sta su GitHub, `avvia.bat` compreso, quindi una chiave lì dentro finirebbe
online al primo invio. `segreto.bat` è escluso da git: la chiave resta sul tuo
computer. Lo stesso vale per qualunque altra password che ti venga in mente di
mettere nel codice. Nota: il file `segreto.esempio.bat` **non** è escluso, quindi la
tua chiave va nel file rinominato (`segreto.bat`), mai nel modello.

Il piano gratuito Azure include 500.000 caratteri al mese, senza scadenza: per un
uso di casa non si esaurisce.

---

## Se qualcosa non va

**Ho scritto `git` e dice "Termine 'git' non riconosciuto".**
Git non è installato, e non serve: va benissimo la strada dello ZIP al Passo 1. Se
proprio vuoi Git, installalo da <https://git-scm.com/download/win>, chiudi e riapri
la finestra, e riprova.

**L'app non parte, la finestra si chiude subito.**
Apri `avvia.bat` e guarda il messaggio: dice cosa manca. Quasi sempre è Python
installato senza la spunta *Add python.exe to PATH*: reinstalla spuntandola.

**Non trovo la cartella `windows` (o `avvia.bat`).**
Stai guardando fuori dalla cartella dell'app. Deve essere: `gg-gg` (o come l'hai
chiamata) → dentro → `windows` → dentro → `avvia.bat`. Se `windows` non c'è
proprio, hai scaricato lo ZIP sbagliato: deve essere quello del branch `gg`
(l'indirizzo al Passo 1), non quello di `main`.

**Windows dice che il file è bloccato, o non succede niente al doppio clic.**
I file scaricati da internet portano un "marchio" di provenienza, e Windows può
bloccarli per prudenza. Rimedio: clic destro sul file `gg-gg.zip` **prima** di
estrarlo → **Proprietà** → in fondo, spunta **Sblocca** → OK. Poi estrai. Se lo hai
già estratto, puoi farlo sui singoli file dentro la cartella `windows`.

**Il telefono non si collega.**
1. Telefono e computer devono essere **sulla stessa rete Wi-Fi**.
2. Windows chiede il permesso la prima volta che l'app accetta connessioni:
   se hai cliccato *Annulla*, il telefono non passa. Per riabilitarlo: *Pannello
   di controllo → Sistema e sicurezza → Windows Defender Firewall → Consenti
   un'app*, e metti la spunta su Python (sia *Privata* che *Pubblica*).
3. L'indirizzo del computer può essere cambiato: rileggilo da `avvia.bat`.

**La pagina si apre ma i dati non ci sono.**
Il database è finito nella cartella sbagliata. Guarda dove hai messo il file
`.db`: se nella vecchia casa c'era una cartella `case\`, il file va lì. Riapri
`LEGGIMI.txt` dentro lo `.zip`: indica il percorso esatto.

**La voce non funziona sul telefono.**
È previsto, ed è il browser: sul telefono serve una connessione sicura. Sul
computer, con `localhost`, funziona.

**Voglio salvare i dati su un disco esterno.**
In `avvia.bat` c'è una riga `REM set "MAGGIORDOMO_DATA=..."`: togli `REM`, metti
il percorso, e i dati andranno lì. Attenzione: deve restare lo stesso a ogni
avvio, altrimenti l'app non li trova e sembra vuota.
