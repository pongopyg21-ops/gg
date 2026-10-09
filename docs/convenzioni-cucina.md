# Convenzioni — Cucina, spesa, home

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
  **L'ordine delle schede è: Cucina, Appunti, Igiene, GYM, TV, FAQ**
  (`test_l_ordine_delle_categorie_in_home` lo fissa). L'ordine è dell'utente,
  non alfabetico. La scheda **Igiene si riconosce dalle bollicine** 🫧, non più
  dalla scopa 🧹: le bollicine dicono «pulito, fresco», mentre la scopa dice
  «sto spazzando» e non è l'idea che deve passare. La stessa emoji compare in
  home, nella barra, nel menu di benvenuto e nel riepilogo «Oggi», così la
  sezione si riconosce a colpo d'occhio ovunque (vedi
  `test_l_icona_dell_igiene_sono_le_bollicine`).
  La scheda **Cucina ha un'icona sua** (`static/icons/cucina.svg`): ora è il
  **cappello da chef** (la toque, corona chiara e bordo ambra). Prima era il
  logo dell'app, poi una pentola sul fuoco col vapore, e il cappello è stato
  rimesso su richiesta dell'utente. **Il disegno è piatto e su fondo
  trasparente**, come le emoji delle altre schede (Appunti, FAQ, TV, GYM,
  Igiene): la prima versione aveva un riquadro di fondo colorato a tutta tela, e
  in mezzo ai simboli piatti sembrava il logo dell'app incollato sulla scheda —
  quella era l'incoerenza. Il bordo del cappello (`#d9b877`) distingue il nuovo
  dal vecchio, così un ritorno alla pentola non passa inosservato
  (`test_la_cucina_ha_la_sua_icona`, che verifica anche l'assenza del riquadro di
  fondo). Le altre schede tengono la loro emoji.
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
