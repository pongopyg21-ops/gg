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

REM ============================================================
REM  Comprensione dei comandi con un modello  (facoltativa)
REM ============================================================
REM
REM  Senza, i comandi sono capiti dal parser a regole e l'app funziona lo
REM  stesso. Con un modello si capiscono anche le frasi non previste
REM  ("dammi la lista della spesa", "fammi vedere la dispensa").
REM
REM  Modello IN LOCALE con Ollama (gratuito, niente chiavi, niente rete):
REM  basta avviare Ollama e scaricare un modello, poi puntare qui l'app.
REM    LLM_BASE_URL = http://127.0.0.1:11434/v1
REM    LLM_API_KEY  = ollama   (segnaposto: Ollama non la controlla)
REM    LLM_MODEL    = qwen2.5:7b-instruct   (o un altro modello scaricato)
REM
REM  Un modello locale su CPU impiega qualche secondo: si alza LLM_TIMEOUT
REM  (in secondi). Senza, il tetto di 8 secondi del cloud lo farebbe scadere.
REM
REM  In alternativa, un servizio in rete compatibile OpenAI: cambiano solo
REM  queste tre variabili.
REM    LLM_BASE_URL = l'indirizzo del servizio
REM    LLM_MODEL    = il modello che offre
REM    LLM_API_KEY  = la-tua-chiave-del-servizio

REM Togli il REM e metti i tuoi valori (esempio con Ollama in locale):
REM set "LLM_BASE_URL=http://127.0.0.1:11434/v1"
REM set "LLM_MODEL=qwen2.5:7b-instruct"
REM set "LLM_API_KEY=ollama"
REM set "LLM_TIMEOUT=30"
