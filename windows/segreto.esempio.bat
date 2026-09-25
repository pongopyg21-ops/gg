@echo off
REM Copia questo file e chiamalo `segreto.bat`, poi riempi le due righe in fondo.
REM
REM C'e' un modo piu' semplice anche qui: un file di testo `segreto.txt` nella
REM cartella dell'app, senza virgolette da mettere al posto giusto. Questo file
REM resta per chi usa gia' la forma a script.
REM
REM Perche' cosi': `segreto.bat` e' escluso da git, `avvia.bat` no. La chiave deve
REM stare nel primo, altrimenti finisce su GitHub insieme al codice.

REM ============================================================
REM  Chiave della voce neurale Azure  (facoltativa)
REM ============================================================
REM
REM  Senza queste righe l'app usa la voce del sistema: funziona lo stesso,
REM  semplicemente la voce del browser e' meno bella.
REM
REM  Dove trovarle, nella pagina della risorsa "Speech" di Azure
REM  (portal.azure.com -> la tua risorsa -> Chiavi ed endpoint):
REM
REM    AZURE_SPEECH_KEY     una delle due chiavi (Chiave 1 o Chiave 2)
REM    AZURE_SPEECH_REGION  l'area della risorsa, per esempio westeurope
REM
REM  Attenzione all'area: se non e' quella giusta, la voce non parte. Nella
REM  pagina della risorsa si chiama "Localita'/Area" ed e' in minuscolo,
REM  senza spazi: westeurope, italynorth, eastus...
REM
REM  Se copi la chiave e non funziona, controlla che non abbia spazi
REM  davanti o dietro.

REM Togli il REM dalle due righe qui sotto e metti i tuoi valori:
REM set "AZURE_SPEECH_KEY=incolla-qui-la-chiave"
REM set "AZURE_SPEECH_REGION=westeurope"
