# Convenzioni — migrazioni, magazzino, progetti, igiene

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
