# Capire i comandi con un modello

## Capire i comandi con un modello (sempre attivo)

> **Stato attuale: la comprensione col modello e' sempre attiva.** Non c'e' piu'
> un pannello ne' una preferenza da accendere: `_comprendi` prova **sempre** il
> modello quando e' configurato e ricade sul parser a regole se non risponde.
> L'interruttore «Capire i comandi» e' stato tolto dal Profilo, e in un secondo
> momento e' stata tolta anche la preferenza per casa (`llm_prefs.abilitato`):
> la tabella resta nel database ma non viene piu' letta. La rotta
> `PUT /api/voce/llm` sopravvive come **stato** (risponde 400 con la causa se il
> modello non risponde), senza piu' accendere niente. Il capitolo spiega come
> funziona la parte server.

Il parser a regole di `voice.py` capisce le frasi previste e lascia fuori le
altre: «dammi la lista della spesa», «fammi vedere la dispensa», «metti via il
vino in cantina». Non e' un difetto del riconoscimento — la trascrizione Azure e'
buona — e' che le regole sono una grammatica scritta a mano, e la lingua parlata
non ci sta dentro. `comprensione.py` fa la stessa comprensione con un modello
linguistico.

**Fallisce in modo aperto**, ed e' la proprieta' che rende sicuro averlo attivo.
Il parser diventa cosi': si prova il modello, e se risponde `unknown` o non
risponde (manca la rete, il modello e' spento, risposta storta) si usa il
risultato di `voice.parse`. Quindi o capisce di piu', o non cambia niente:

```
cmd = comprensione.chiama(testo)
if not cmd or cmd["intent"] == "unknown":
    cmd = voice.parse(testo)     # la rete di sicurezza di sempre
```

E' un test (`test_se_il_modello_non_capisce_si_usa_il_parser`) e non una
promessa. Il modello si preferisce **anche** quando il parser crede di aver
capito, perche' proprio li' stanno gli errori da correggere («metti via il vino
in cantina» diventava un articolo in magazzino chiamato «via il vino»).

**Perche' sempre attivo e non un interruttore.** Un interruttore acceso a `0`
di partenza significa che la funzione *esiste* ma non fa niente finche' qualcuno
non sa che c'e'. Il costo (nessuna chiamata quando il modello non c'e') e' gia'
coperto da `configurato()`: se non c'e' un endpoint non si chiama nessuno. Averlo
sempre attivo toglie la causa piu' silenziosa del «non capisce» — la preferenza
spenta — e non peggiora niente grazie al ripiego. In questo ambiente il modello
di casa e' Ollama: se e' spento, `chiama()` fallisce e si usano le regole.

Le scelte che contano:

- **Il modello non inventa intenti.** La risposta viene ripulita con
  `_ripulisci()`: un intento fuori da `INTENTI`, un'unita' fuori da `UNITA`, una
  quantita' non numerica vengono scartati. Se resta poco, il comando vale
  `unknown`. Una comprensione sbagliata deve restare una frase, non un'azione:
  meglio «non ho capito» di una voce sbagliata in dispensa per sempre.
- **Si usa quando e' configurato, non quando e' "acceso".** Non c'e' piu' una
  preferenza di casa da leggere: `_comprendi` guarda solo `configurato()`. Se non
  c'e' un endpoint (ne' locale predefinito ne' chiave per un servizio in rete) non
  si chiama nessuno. Se c'e', si chiama: il modello di casa predefinito e' Ollama,
  che e' sempre "configurato" per via dell'endpoint locale, ma se e' spento
  `chiama()` fallisce e si ricade sulle regole senza che l'utente debba saperlo.
- **La rotta di stato non accende piu' niente.** `PUT /api/voce/llm` e' rimasta
  per compatibilita' e risponde con lo stato; se il modello non e'
  **raggiungibile** risponde **400** dicendo cosa manca (per un servizio in rete
  il nome della variabile `LLM_API_KEY`, per un modello di casa la causa vera:
  Ollama spento / modello non scaricato). Tacerlo farebbe credere che il modello
  stia capendo mentre ogni frase finisce sulle regole.
- **`configurato()` non e' `raggiungibile()`.** Sono due cose diverse: un endpoint
  locale c'e' **sempre** (e' il predefinito), quindi `configurato()` e' vero anche
  a Ollama spento. `/api/voce/config` espone `llm_disponibile` (c'e' la
  configurazione), `llm_pronto` (il modello risponde **adesso**) e `llm_manca` (la
  causa, se manca). `raggiungibile()` e' una verifica di rete breve
  (`TIMEOUT_VERIFICA` 1.5 s) contro l'elenco dei modelli: `/api/tags` per Ollama
  (porta 11434), `/models` per un servizio in rete. Un guasto di rete qui non e'
  un errore, e' "non pronto": si resta sulle regole senza rompere niente.

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
o modello non scaricato); la comprensione resta attiva ma ricade sulle regole
finche' il modello non torna.
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

