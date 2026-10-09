# Convenzioni вЂ” Cucina, spesa, home

- **Le preparazioni sono dettagliate, a passi.** Il testo di `instructions` sta in
  `RECIPES` (unica fonte: non esiste un secondo dizionario di preparazioni) ed ГЁ
  scritto su paragrafi separati da una riga vuota, perchГ© il client lo mostra come
  elenco numerato (`passiDa` in `static/app.js` divide anche sulle frasi). Almeno
  quattro passi, con tempi e temperature espliciti: В«inforna a 180В°C per 40
  minutiВ», non В«cuociВ». Una preparazione di una frase sola diventa un passo unico e
  non serve a chi cucina; i test `test_ogni_ricetta_ha_una_preparazione_dettagliata`
  e `test_le_preparazioni_dettagliate_escono_come_passi` (quest'ultimo esegue
  `passiDa` vera con node) lo tengono fermo.
- **Le preparazioni arrivano anche ai database esistenti, senza cancellare il
  lavoro dell'utente.** `PREPARAZIONI_PRECEDENTI` ГЁ la fotografia dei testi com'era
  prima di essere riscritti, e `semina()` sostituisce `instructions` **solo se ГЁ
  ancora esattamente quella vecchia**: una preparazione riscritta a mano ГЁ un dato
  dell'utente e non va sovrascritta. Г€ la stessa cautela dell'aggiornamento dei
  minuti in `igiene.py`: le stime ritoccate a mano non si riallineano mai. Senza,
  chi usa l'app da prima vedrebbe i testi nuovi solo creando una
  casa nuova, e chi ha riscritto la ricetta di famiglia se la vedrebbe cancellare.
  Aggiungendo un testo nuovo a `RECIPES`, va aggiunto il testo vecchio anche a
  `PREPARAZIONI_PRECEDENTI`, altrimenti l'aggiornamento non scatta.
- **Ogni ricetta del ricettario ha una foto**, e la foto ГЁ un file in
  `static/recipes/` registrato in `PHOTOS` (`seed.py`) con il suo credito. Il test
  `test_ogni_ricetta_ha_la_sua_foto` verifica tre cose insieme: la voce esiste, il
  file esiste davvero su disco, e il credito ГЁ completo (autore, licenza,
  `Wikimedia Commons`, indirizzo della pagina). Un nome giusto con il file assente
  ГЁ lo stesso difetto di una voce mancante: si nota solo aprendo la scheda.
  Le foto vengono da **Wikimedia Commons** e sono a licenza libera (CC0, CC BY,
  CC BY-SA, pubblico dominio): sono le uniche che si possono ridistribuire in un
  repository pubblico con l'attribuzione. La via per trovarne una **non ГЁ cercare
  il nome del piatto su Commons**: la ricerca restituisce PDF, bancarelle e
  foto di piatti diversi (una В«lasagna soupВ» ГЁ finita su una zuppa di zucca in
  Bolivia). Il criterio che regge ГЁ l'**immagine principale della voce Wikipedia**
  di quel piatto (`prop=pageimages`): ГЁ scelta dagli editori, quindi ГЁ quasi
  sempre il piatto giusto. Quando non c'ГЁ вЂ” В«lasagna soupВ» non ha una voce вЂ” si
  ripiega su una foto **indicativa** e lo si scrive nel credito, come giГ  fa
  `PHOTOS` per altre voci. Non inventare un abbinamento: una foto sbagliata in
  una scheda ГЁ peggio di un riquadro vuoto. Una foto che ГЁ giГ  di un'altra
  ricetta non si riusa (sarebbe un doppione).
- **Le ricette con la foto vengono prima nell'elenco**, quelle senza in fondo
  (`conFotoPrima` in `static/app.js`). L'ordine ГЁ del client, non dell'API, che
  resta alfabetico: `sort` in JS ГЁ stabile, quindi dentro i due gruppi l'ordine
  non cambia. Una ricetta senza foto ГЁ un dato incompleto da completare, e non
  deve stare in mezzo a quelle pronte. La tendina del piano pasti **non** segue
  questo ordine: lГ¬ resta l'ordine dell'API, perchГ© scegliere un pasto ГЁ un'altra
  cosa dal guardare il ricettario.
- **Dal ricettario si aggiunge al piano senza cambiare scheda.** Ogni scheda ha
  un pulsante `+ Piano` (`data-plan`) e il dettaglio della ricetta ha В«Aggiungi
  al pianoВ»: entrambi aprono `openPlanPicker(ricetta)`, che chiede **giorno,
  pasto e porzioni** con la ricetta **giГ  scelta**. Г€ il verso opposto di
  `openMealPicker(date, meal)`, che per un pasto vuoto del Piano fa scegliere la
  ricetta da una tendina. Il motivo ГЁ la richiesta: nel Piano si sceglie una
  ricetta **senza vederne la foto**, e per una cosa che si mangia l'immagine ГЁ
  metГ  della scelta. CosГ¬ si guarda il ricettario e si decide lГ¬.
  Due dettagli non ovvi: (1) le porzioni proposte sono quelle della ricetta
  (`r.servings`), non un 2 fisso, perchГ© ГЁ il numero per cui la ricetta ГЁ
  scritta; (2) alla conferma si ridisegna il Piano **solo se ГЁ la scheda
  aperta** (`#tab-plan.active`), perchГ© `openPlanPicker` si puГІ chiamare anche
  da dentro il dettaglio aperto dal Piano (dove serve il ridisegno) e dal
  ricettario (dove una richiesta a vuoto non serve). Dal dettaglio il pulsante
  В«Aggiungi al pianoВ» c'ГЁ **solo** quando non c'ГЁ giГ  В«Rimuovi dal pianoВ»: le
  due azioni si escludono. `pastiDelGiorno()` ГЁ l'unica definizione dei pasti
  per il selettore, con la stessa riserva del Piano se `MEALS` non ГЁ arrivato.
- **Togliere una ricetta dal ricettario richiede due passaggi, non uno.** Va
  messa in `seed.REMOVED` **e** tolta da `RECIPES` (con `PHOTOS`,
  `PREPARAZIONI_PRECEDENTI` e il file in `static/recipes/`). Solo `REMOVED` non
  basta: in `semina()` la cancellazione avviene **prima** dell'inserimento,
  quindi una ricetta presente in entrambe le liste verrebbe tolta e subito
  rimessa. Solo toglierla da `RECIPES` non basta dall'altra parte:
  `seed.semina()` gira solo quando un database nasce, e `windows\avvia.bat` non
  lo chiama affatto, quindi chi ha giГ  i dati se la terrebbe per sempre. Il
  passaggio che copre i database esistenti ГЁ `app._rimuovi_ricette_tolte`,
  chiamato da `migrate()` вЂ” che `get_db()` esegue a ogni richiesta su ogni casa.
  La cancellazione si fa solo se una delle ricette ГЁ davvero presente, quindi una
  richiesta normale non paga il `rebuild_shopping`.
- **`init_db()` accende le foreign key**, come `get_db()` e `seed.semina()`.
  SQLite le tiene spente per default e `executescript` non le accende: senza,
  il `ON DELETE CASCADE` non scatta e una ricetta cancellata lascia righe orfane
  in `meal_plan`, `recipe_items` e `favorites` вЂ” un danno che non si vede, perchГ©
  il database resta В«validoВ» e le query continuano a rispondere. Il test
  `test_le_ricette_tolte_spariscono_anche_dai_database_esistenti` verifica proprio
  che non resti niente che punti a una ricetta che non esiste piГ№.
- I giorni in cui serve una voce della spesa (`days` in `/api/shopping`) si calcolano
  a ogni lettura dal piano con `_need_by_day`/`_day_breakdown`, non si salvano: una
  tabella di appoggio si disallineerebbe appena si modifica un pasto. L'invariante
  `sum(days) == quantity` va mantenuta, e le quote vanno riscalate sul totale
  effettivo della voce, che l'utente puГІ aver corretto a mano.
- La lista della spesa distingue le voci generate (`shopping_items.generated = 1`)
  da quelle scritte a mano (`0`). La generazione cancella e ricostruisce solo le
  prime: ГЁ una fotografia del piano, quindi una ricetta tolta dal piano porta via
  i suoi ingredienti, e rigenerare due volte non raddoppia le quantitГ . Se esiste
  giГ  una voce manuale aperta per un ingrediente, la generazione la salta
  (`already_listed`) invece di duplicarla o fondersi: quella riga ГЁ dell'utente.
  Aggiungendo un nuovo percorso che crea voci dal piano, va marcato `generated`.
- La lista si ricostruisce **da sola**: `rebuild_shopping()` ГЁ chiamata da ogni
  endpoint che cambia il fabbisogno вЂ” piani, ricette e dispensa вЂ” non solo da
  `/api/shopping/generate`. Il pulsante "Vai alla spesa" nel piano ГЁ quindi solo
  una scorciatoia di navigazione: se un percorso nuovo modifica ingredienti,
  quantitГ  o scorte e non la richiama, la lista resta indietro senza che l'utente
  abbia un modo per accorgersene. La dispensa ГЁ compresa perchГ© quello che si
  compra e si mette via non deve restare anche in lista.
- **Suggerimenti dalla dispensa** (`dispensa.py`, `GET /api/pantry/suggerimenti`):
  sotto l'elenco compare cosa si puГІ cucinare con quello che c'ГЁ. Il criterio ГЁ la
  **copertura**, e il punteggio ГЁ una **frazione**, non un conteggio di ingredienti
  coperti: contando gli ingredienti vincerebbe la ricetta piГ№ lunga вЂ” una da dodici
  con sette in dispensa batterebbe una da quattro con quattro, che ГЁ invece quella
  che si puГІ fare stasera. A paritГ  vince la spesa piГ№ corta.
  Un ingrediente coperto **in parte** conta mezzo punto: con 100 g di farina e 500 g
  richiesti la ricetta non si fa, ma non ГЁ nemmeno da comprare tutta; contarlo intero
  direbbe В«hai tuttoВ» quando non ГЁ vero.
  Le quantitГ  si confrontano solo fra unitГ  **convertibili** (`units.convert`): 200 g
  coprono 0,2 kg, ma una confezione non copre un pezzo, e lГ¬ non si indovina.
  Il filtro allergie sta **sul server**, non nel client: qui l'app dice В«cucina
  questaВ», e proporre un allergene non ГЁ una svista da correggere, ГЁ un errore. Una
  ricetta senza ingredienti non ГЁ un suggerimento (non c'ГЁ niente da consumare), e
  nemmeno una che non usa niente di quello che c'ГЁ.
  La riga dei mancanti ГЁ troncata a `MAX_NOMI` ma **dice quanti ne restano**
  (В«e altri 3В»): senza, l'elenco sembrerebbe completo e l'utente comprerebbe solo
  quelli. Nel client `renderPantry()` carica tabella **e** suggerimenti, mentre il
  filtro di ricerca (`renderPantryTable`) ГЁ locale: non deve rifare la richiesta dei
  suggerimenti, che non dipendono da cosa si sta cercando. Modificare una quantitГ 
  dalla tabella invece li aggiorna, perchГ© cambia cosa risulta coperto.
  Con la dispensa **vuota** il riquadro non resta muto: dice di aggiungere qualche
  ingrediente. Prima spariva e basta, e sembrava che i suggerimenti non esistessero
  вЂ” che ГЁ esattamente quello che si vede al primo avvio, quando la dispensa ГЁ vuota.
- **La scheda condivisibile della spesa** (`GET /api/shopping/condividi`) ГЁ una
  vista, non un secondo archivio: si costruisce da `_voci_spesa`, le stesse voci
  della lista, quindi non puГІ mostrare numeri diversi da quelli a schermo. Le
  regole del periodo sono quelle della vista per giorno вЂ” un giorno porta la
  **quota** di quel giorno (`quota` nella voce), un intervallo il totale вЂ” e le
  voci giГ  spuntate restano fuori (chi compra non ricompra il carrello), mentre
  quelle senza giorni (aggiunte a mano) restano sempre.
  L'endpoint restituisce **dati**, non HTML: la scheda grafica si compone nel
  client (`schedaSpesaHtml` per la pagina, `schedaSpesaCanvas` per il PNG), che
  conosce il tema e il carattere. Aggiungendo un campo alla scheda, si aggiorna
  `_scheda_spesa` in un punto solo; il testo (`testo`) nasce dalle stesse voci.
  I parametri (`giorno` oppure `dal`/`al`, piГ№ `nota`) si validano una volta sola:
  una data storta ГЁ un 400, non una scheda vuota che sembra В«niente da comprareВ».
- **La scadenza in dispensa** (`pantry.expires_at`, `parse_data`). Г€ una data
  facoltativa: vuoto significa В«non lo soВ», che ГЁ **diverso** da В«non scadeВ». Non
  si indovina mai una data, perchГ© una scadenza inventata farebbe buttare cibo
  buono. Nel `PATCH` ogni campo si tocca solo se presente nel corpo (`quantity`,
  `expires_at`): mandare la sola scadenza non deve azzerare la quantitГ , e
  cambiare la quantitГ  non deve cancellare la scadenza; per toglierla si manda
  vuota. Aggiungendo scorte dello stesso ingrediente vince la scadenza **piГ№
  vicina** (`_scadenza_piu_vicina`): ГЁ quella che va guardata prima, e una partita
  senza data non cancella quella che si sapeva. Nel client il colore dice
  l'urgenza (`statoScadenza`: rosso scaduto, ambra entro pochi giorni) senza
  dover leggere la data.
  I suggerimenti **tengono conto delle scadenze**: a paritГ  di copertura sale in
  cima la ricetta che consuma una scorta in scadenza entro `GIORNI_SCADENZA` (7),
  perchГ© ГЁ quella da cucinare adesso. La card dice quali (`sug-scade`), invece di
  lasciarlo intuire dall'ordine. `suggerimenti()` prende un `oggi` opzionale, che
  ГЁ anche l'unico posto in cui il modulo guarda la data vera вЂ” i test lo passano.
- **L'ordine della home**: categorie (le schede), poi il riepilogo В«OggiВ», il
  calendario, le notizie del giorno, il riquadro В«DomaniВ» e in fondo
  l'intestazione В«Il MaggiordomoВ» (`home-hero-basso`, **centrata**:
  `text-align: center` sul blocco, con `.con-icona` a `justify-content: center`).
  Le categorie stanno subito sotto l'invito a parlare: si
  arriva in home per scegliere dove andare, e devono vedersi senza scorrere.
  Tutto il resto ГЁ da leggere, non da premere, quindi viene dopo. Г€ un ordine
  scelto dall'utente, non un dettaglio di stile: prima le schede erano in fondo,
  ed era sbagliato. L'intestazione era invece in cima e spingeva giГ№ le
  categorie: ora chiude la pagina (vedi `test_l_intestazione_chiude_la_home`).
  **L'ordine delle schede ГЁ: Cucina, Appunti, Igiene, GYM, TV, FAQ**
  (`test_l_ordine_delle_categorie_in_home` lo fissa). L'ordine ГЁ dell'utente,
  non alfabetico. La scheda **Igiene si riconosce dalle bollicine** рџ«§, non piГ№
  dalla scopa рџ§№: le bollicine dicono В«pulito, frescoВ», mentre la scopa dice
  В«sto spazzandoВ» e non ГЁ l'idea che deve passare. La stessa emoji compare in
  home, nella barra, nel menu di benvenuto e nel riepilogo В«OggiВ», cosГ¬ la
  sezione si riconosce a colpo d'occhio ovunque (vedi
  `test_l_icona_dell_igiene_sono_le_bollicine`).
  La scheda **Cucina ha un'icona sua** (`static/icons/cucina.svg`): ora ГЁ il
  **cappello da chef** (la toque, corona chiara e bordo ambra). Prima era il
  logo dell'app, poi una pentola sul fuoco col vapore, e il cappello ГЁ stato
  rimesso su richiesta dell'utente. **Il disegno ГЁ piatto e su fondo
  trasparente**, come le emoji delle altre schede (Appunti, FAQ, TV, GYM,
  Igiene): la prima versione aveva un riquadro di fondo colorato a tutta tela, e
  in mezzo ai simboli piatti sembrava il logo dell'app incollato sulla scheda вЂ”
  quella era l'incoerenza. Il bordo del cappello (`#d9b877`) distingue il nuovo
  dal vecchio, cosГ¬ un ritorno alla pentola non passa inosservato
  (`test_la_cucina_ha_la_sua_icona`, che verifica anche l'assenza del riquadro di
  fondo). Le altre schede tengono la loro emoji.
  **Le emoji non sono a colori pieni: ognuna ricalca un colore della palette.**
  Il colore di un'emoji non si cambia con `color` (non ГЁ testo): la si porta a
  silhouette e la si tinge coi filtri CSS (`grayscale`+`brightness`, `sepia`+
  `saturate`, `hue-rotate`). Le sei tinte **restano nella palette «mare»** вЂ”
  acqua (Cucina), verde (Igiene), sabbia (Appunti), argilla (FAQ), ardesia (TV),
  magenta (GYM) вЂ” e la saturazione ГЁ **smorzata** (`--emoji-sat` 1.4-4.0), come
  i toni d'acqua e di terra del resto dell'app: un arcobaleno saturo (blu
  elettrico, verde neon) stona con la palette. Prima le rotazioni erano quasi
  uguali e sembravano tutte ocra; poi erano diventate tinte neon, fuori stile.
  I gradi e le saturazioni non si leggono dalla ruota: la rotazione non ГЁ lineare
  e la saturazione la sposta, quindi vanno scelti **misurando i pixel veri** in
  Chromium (luminanza 0.7 di giorno, 0.85 di notte).
  (`test_le_emoji_delle_schede_restano_nella_palette`.)
- **Le notizie del giorno in home** (`renderHomeNotizie`). In fondo, sotto il
  calendario: solo i titoli con fonte e data, e В«Apri в†’В» che porta alla TV, dove
  stanno il sommario e l'elenco completo. Si riempie da `/api/notizie`, un
  endpoint dedicato: `/api/tv` tirerebbe giГ№ anche i video, che in home non si
  mostrano. Stessa regola dell'endpoint TV (risposta subito dalla cache, un
  filo riprova dopo вЂ” `_aggiorna_notizie_in_sottofondo`) e del riepilogo В«OggiВ»
  (se non c'ГЁ niente, il riquadro resta nascosto). **In home se ne mostrano al
  massimo dieci** (`slice(0, 10)`): ГЁ un assaggio, e il taglio ГЁ della home, non
  del feed вЂ” la sezione TV resta con tutte quelle della cache (`MAX_NOTIZIE`, 20,
  `test_la_home_mostra_dieci_notizie_non_tutte`).
- **Il riquadro В«DomaniВ» in home** (`renderHomeDomani`). Dopo le notizie: gli
  impegni di domani non ancora chiusi e i pasti giГ  scelti. Г€ una sezione a sГ©
  (non una riga dentro В«OggiВ»), perchГ© un impegno di domani non ГЁ ancora scattato
  e i pasti di domani non sono ancora cucinati. Le fonti si chiedono **in
  parallelo** con `.catch` e, se non c'ГЁ niente, il riquadro resta nascosto вЂ”
  stessa regola di В«OggiВ». Si ridisegna all'avvio e al ritorno in home
  (`tornaAlleSezioni`).
- **Il riepilogo В«OggiВ» in home** (`renderHomeOggi`). La home non ГЁ solo un menu:
  mostra i pasti di oggi, le attivitГ  di casa da fare, gli impegni che avvisano
  adesso, **gli impegni di domani** e cosa sta per scadere in dispensa. Gli
  impegni di oggi li manda `prossimi` (i promemoria scattati e le cose in
  ritardo); quelli di domani si chiedono a parte con `?giorno=<domani>` e si
  mostrano come riga «Domani: …», solo quelli **non ancora chiusi** — quelli che
  non avvisano ancora non stanno in `prossimi`, e sapere stasera che domani c'è il
  dentista è utile. È una riga dentro «Oggi», non il riquadro «Domani» più sotto:
  quello resta la vista d'insieme (impegni **e** pasti di domani). Le fonti si
  chiedono **in parallelo** e ognuna fallisce per conto suo (`.catch`): un errore
  sul calendario non deve far sparire i pasti. Se non c'ГЁ niente da dire il
  riquadro resta nascosto вЂ” una home con un riquadro vuoto ГЁ peggio di una home
  senza riquadro.
- **Il calendario degli impegni in fondo alla home** (`renderHomeCalendario`).
  La stessa griglia del mese della scheda Calendario, ma **in sola lettura**: qui
  si sfoglia e si vede quali giorni sono occupati, non si compila. Cliccando un
  giorno o В«Apri в†’В» si va al Calendario nei Progetti, dove si aggiunge e si
  modifica. Il mese mostrato vive in `homeCalVista`, **separato** da `calVista`:
  sfogliare in home non deve spostare il calendario dei Progetti. Se gli impegni
  non arrivano il riquadro resta nascosto (stessa regola del riepilogo В«OggiВ»).
  Si ridisegna all'avvio e al ritorno in home (`tornaAlleSezioni`), cosГ¬ un
  impegno aggiunto nei Progetti compare senza ricaricare la pagina.
- **Le porzioni si scalano nel dettaglio ricetta** (`qtaScalata`). La ricetta ГЁ
  scritta per `servings`; cambiando il numero nel dettaglio, le quantitГ  seguono
  (frazione rispetto al numero base). Una quantitГ  non numerica (В«q.b.В») resta
  com'ГЁ: riscalarla non vorrebbe dire niente.
- **Tempi e costo della ricetta**: `prep_minutes` e `cook_minutes` sono due colonne
  separate perchГ© dicono cose diverse вЂ” la cottura si puГІ lasciare andare da sola, la
  preparazione assorbe l'attenzione вЂ” e il totale ГЁ la loro somma, calcolata nel
  client (`tempiRicetta`) cosГ¬ non puГІ contraddire le due parti. `cost` ГЁ per porzione.
  `time_minutes` **resta com'ГЁ**: ГЁ il totale delle ricette salvate prima, e
  reinterpretarlo vorrebbe dire riscrivere dati inseriti a mano. Una ricetta vecchia
  mostra `time_minutes`; il campo sparisce solo quando si indicano i due tempi, perchГ©
  allora il totale si ricava da quelli (`test_il_totale_vecchio_non_si_perde...`).
  Zero minuti non ГЁ un tempo e diventa `None`; zero **euro** invece ГЁ un costo вЂ” В«non
  costa nienteВ», tipico di una ricetta con gli avanzi вЂ” e si tiene. `parse_minutes` e
  `parse_cost` in `app.py` sono l'unico posto dove questa distinzione ГЁ scritta.
