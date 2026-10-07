PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS ingredients (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL UNIQUE,
    unit     TEXT NOT NULL DEFAULT 'pz',
    category TEXT NOT NULL DEFAULT 'Altro',
    UNIQUE(name)
);

CREATE TABLE IF NOT EXISTS pantry (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    quantity      REAL NOT NULL DEFAULT 0,
    unit          TEXT NOT NULL DEFAULT 'pz',
    -- La scadenza e' una data, non un istante: quello che scade si guarda al
    -- giorno. Vuota vuol dire "non lo so", che e' diverso da "non scade": una
    -- scadenza inventata farebbe buttare cibo buono, quindi non si indovina.
    expires_at    TEXT,
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(ingredient_id, unit)
);

CREATE TABLE IF NOT EXISTS recipes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    servings     INTEGER NOT NULL DEFAULT 2,
    time_minutes INTEGER,
    difficulty   TEXT NOT NULL DEFAULT 'facile',
    instructions TEXT NOT NULL DEFAULT '',
    image        TEXT NOT NULL DEFAULT '',   -- nome file in static/recipes/
    image_credit TEXT NOT NULL DEFAULT '',   -- autore, licenza e provenienza della foto
    source       TEXT NOT NULL DEFAULT '',   -- da dove viene la ricetta importata
    prep_minutes INTEGER,                    -- preparazione: assorbe l'attenzione
    cook_minutes INTEGER,                    -- cottura: si puo' lasciare andare
    cost         REAL,                       -- costo indicativo per porzione, in euro
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recipe_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id     INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    quantity      REAL NOT NULL DEFAULT 0,
    unit          TEXT NOT NULL DEFAULT 'pz'
);

CREATE TABLE IF NOT EXISTS meal_plan (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    date       TEXT NOT NULL,
    meal       TEXT NOT NULL,
    recipe_id  INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    servings   INTEGER NOT NULL DEFAULT 2,
    UNIQUE(date, meal)
);

CREATE TABLE IF NOT EXISTS shopping_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    quantity      REAL NOT NULL DEFAULT 1,
    unit          TEXT NOT NULL DEFAULT 'pz',
    category      TEXT NOT NULL DEFAULT 'Altro',
    ingredient_id INTEGER REFERENCES ingredients(id) ON DELETE SET NULL,
    checked       INTEGER NOT NULL DEFAULT 0,
    -- 1 se la voce e' stata calcolata dal piano: alla rigenerazione si puo'
    -- ricostruire da zero senza toccare quello che l'utente ha aggiunto a mano
    generated     INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_plan_date ON meal_plan(date);
CREATE INDEX IF NOT EXISTS idx_items_recipe ON recipe_items(recipe_id);

-- Dichiarazione di allergie e intolleranze. Riga singola (id = 1): le preferenze
-- sono di un solo utente locale.
CREATE TABLE IF NOT EXISTS profile (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    full_name  TEXT NOT NULL DEFAULT '',
    restrictions TEXT NOT NULL DEFAULT '',   -- testo libero, una voce per riga o separata da virgole
    onboarded  INTEGER NOT NULL DEFAULT 0,
    -- quanti pasti al giorno l'utente vuole gestire (1-5): da qui si ricava
    -- l'elenco dei pasti mostrati nel piano e accettati dall'API
    meals_per_day INTEGER NOT NULL DEFAULT 2,
    -- 0 finche' il passo di scelta delle preferite non e' stato mostrato:
    -- serve a riproporlo a chi si era profilato prima che esistesse
    fav_prompted INTEGER NOT NULL DEFAULT 0,
    -- giorno fisso della settimana per le pulizie (0 = lunedi' ... 6 = domenica):
    -- la routine crea costanza, dice l'articolo, e il giorno lo sceglie l'utente
    chore_day INTEGER NOT NULL DEFAULT 5,
    -- quanti bucati al giorno fa la casa (0-5). Non e' una preferenza estetica:
    -- da qui si ricava ogni quanto rimettere la lavatrice in moto (vedi
    -- `igiene.cadenza_lavatrice`), cosi' la voce non resta fissa a un giorno e
    -- mezzo quando in casa si fanno due bucati al giorno o uno ogni tre.
    bucati_giorno INTEGER NOT NULL DEFAULT 0,
    -- argomenti delle notizie che interessano, separati da virgola: le sezioni
    -- ANSA da tenere. Vuoto = tutti (vedi `tv.argomenti_scelti`).
    news_topics TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Ricette preferite: tabella a parte invece di una colonna su `recipes` perche'
-- e' una preferenza dell'utente, non un dato della ricetta, e perche' la chiave
-- esterna con CASCADE tiene l'elenco pulito quando una ricetta viene eliminata.
CREATE TABLE IF NOT EXISTS favorites (
    recipe_id  INTEGER PRIMARY KEY REFERENCES recipes(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------- igiene
-- Attivita' di pulizia. Il catalogo di partenza (igiene.py) viene seminato qui
-- come le ricette: si puo' modificare, disattivare o aggiungere senza toccare
-- il codice. `frequency` divide i tre blocchi del metodo (quotidiane,
-- settimanali, mensili) piu' le stagionali, che si fanno nel loro `month`.
CREATE TABLE IF NOT EXISTS chores (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL UNIQUE,
    area      TEXT NOT NULL DEFAULT 'Tutta la casa',
    frequency TEXT NOT NULL DEFAULT 'settimanale',
    minutes   INTEGER NOT NULL DEFAULT 15,
    month     INTEGER,                        -- 1-12, solo per le stagionali
    active    INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Quando un'attivita' e' stata fatta. Le scadenze NON si salvano: si ricavano
-- dall'ultima riga, come i giorni della spesa dal piano. Una tabella di appoggio
-- si disallineerebbe appena si registra un completamento.
CREATE TABLE IF NOT EXISTS chore_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chore_id   INTEGER NOT NULL REFERENCES chores(id) ON DELETE CASCADE,
    date       TEXT NOT NULL,
    minutes    INTEGER NOT NULL DEFAULT 0,    -- tempo impiegato davvero, 0 se non misurato
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_chore_log_chore ON chore_log(chore_id, date);
CREATE INDEX IF NOT EXISTS idx_chores_freq ON chores(frequency, month);

-- ---------------------------------------------------------------- faq
-- Informazioni utili: Wi-Fi, indirizzi, contatti, codici. Le categorie stanno in
-- `faq.py`, non qui: sono la struttura della sezione, non un contenuto
-- dell'utente. `question` e' l'etichetta (breve) e `answer` il valore (puo'
-- essere lungo: un indirizzo completo, gli orari di un ambulatorio).
--
-- La tabella non e' piu' usata dal modulo FAQ: le voci vivono **cifrate** nella
-- `cassaforte` (riga sotto), e al primo aprire della cassaforte quelle gia'
-- presenti qui vengono importate. La tabella resta solo perche' un database
-- vecchio la porta con se' e la migrazione la legge una volta.
CREATE TABLE IF NOT EXISTS faq (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    category   TEXT NOT NULL DEFAULT 'generale',
    question   TEXT NOT NULL,
    answer     TEXT NOT NULL DEFAULT '',
    secret     INTEGER NOT NULL DEFAULT 0,
    pinned     INTEGER NOT NULL DEFAULT 0,   -- in cima all'elenco
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_faq_cat ON faq(category);

-- ------------------------------------------------------------- cassaforte
-- Tutte le voci delle FAQ, **cifrate** con una password della cassaforte. La
-- riservatezza e' vera: il testo non e' mai in chiaro nel file, e non esce
-- dall'API finche' la cassaforte non e' aperta. La password della cassaforte non
-- e' quella dell'app (puo' coincidere, ma non e' detto): entrare nella casa non
-- basta a leggere questi dati.
--
-- La tabella contiene la **scatola**: un solo `dati` cifrato con tutte le voci
-- dentro, e i parametri che servono ad aprirla. Non una riga per voce: cifrare
-- ogni voce separatamente moltiplicherebbe i PBKDF2 (uno per voce), e la cassaforte
-- e' piccola e si legge tutta insieme.
CREATE TABLE IF NOT EXISTS cassaforte (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    dati       TEXT NOT NULL,                 -- il blob cifrato (JSON)
    -- La **scatola per la biometria**: le stesse voci, ma cifrate con la
    -- chiave che il dispositivo custodisce dietro il sensore. Vuota = la
    -- biometria non e' attiva. E' una seconda scatola, non un secondo
    -- segnaposto: si apre senza la password, quindi la password da sola non
    -- deve poterla leggere.
    bio        TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------- progetti
-- Lavori in corso e idee, tenuti fuori dalla cucina. `priority` e' una scelta
-- dell'utente da 1 a 5; le date sono quelle del piano di lavoro, non un
-- promemoria. `done` chiude il progetto senza cancellarlo: la storia resta.
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    start_date  TEXT NOT NULL DEFAULT '',
    end_date    TEXT NOT NULL DEFAULT '',
    priority    INTEGER NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    done        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_projects_done ON projects(done, priority);

-- ---------------------------------------------------------------- magazzino
-- Tutto quello che si tiene in casa e non si mangia: sapone, bagnoschiuma,
-- rasoi, mensole, quadri, batterie. Non centra con la cucina, quindi e' una
-- tabella a parte e non un secondo elenco della dispensa: la dispensa si
-- confronta con le ricette, il magazzino no.
--
-- `min_quantity` e' la soglia sotto la quale vale la pena ricomprare. Non e'
-- automazione: serve a vedere a colpo d'occhio cosa sta finendo, che e' il
-- motivo per cui si tiene un magazzino.
CREATE TABLE IF NOT EXISTS storage (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    category      TEXT NOT NULL DEFAULT 'Altro',
    place         TEXT NOT NULL DEFAULT 'Ripostiglio',
    quantity      REAL NOT NULL DEFAULT 0,
    unit          TEXT NOT NULL DEFAULT 'pz',
    min_quantity  REAL NOT NULL DEFAULT 0,
    notes         TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_storage_cat ON storage(category);

-- Un'impostazione sola: se usare il modello linguistico per capire i comandi
-- oltre al parser a regole. Sta nella casa e non in `localStorage` perche' e'
-- una scelta dell'utente, non del dispositivo: chi amministra la casa decide se
-- e' disposto a spendere per la comprensione, e le altre case non sono toccate.
-- Zero di default: senza una chiave configurata la comprensione non e'
-- disponibile, e un interruttore acceso che non fa niente confonderebbe.
CREATE TABLE IF NOT EXISTS llm_prefs (
    id      INTEGER PRIMARY KEY CHECK (id = 1),
    abilitato INTEGER NOT NULL DEFAULT 0
);

-- La foto di una voce di magazzino, per riconoscerla a colpo d'occhio: e' il
-- motivo per cui si fotografa una mensola o una scatola di cui non si ricorda
-- il nome.
--
-- Sta **nel database della casa**, non su disco, e non e' un dettaglio: cosi'
-- la foto viaggia con `/api/backup` insieme al resto dei dati, e il ripristino
-- resta un file solo invece di un file piu' una cartella da rimettere al posto
-- giusto. Il costo e' un database piu' grande, che per le foto di una casa e'
-- accettabile.
--
-- Una foto per voce: `storage_id` e' UNIQUE, quindi ricaricare sostituisce
-- invece di accumulare. La richiesta era "avere informazione visiva", non un
-- album, e piu' foto per voce complicherebbero il modulo senza aggiungere
-- niente a chi cerca la scatola giusta.
CREATE TABLE IF NOT EXISTS storage_photos (
    storage_id  INTEGER PRIMARY KEY REFERENCES storage(id) ON DELETE CASCADE,
    mime        TEXT NOT NULL,
    data        BLOB NOT NULL,
    hash        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------- tv
-- Quello che le sezioni TV e Cinema hanno scaricato: i video della playlist, le
-- notizie del giorno e la copia del Cinema, in JSON, sotto una chiave ("video",
-- "notizie", "gym", "cinema").
--
-- Sta nel database della casa, non in memoria, perche' e' **la copia di
-- sicurezza della sezione**: se la rete non risponde (o il feed cambia), la
-- sezione si apre lo stesso con quello che c'era, invece di restare vuota. E'
-- il motivo per cui non e' una tabella per i video e una per le notizie: sono
-- elenchi che si leggono sempre interi e non si interrogano per campo. Il
-- Cinema usa la stessa tabella sotto la chiave `cinema`: la forma e' identica,
-- e la sezione cambia solo per la fonte e la scadenza.
CREATE TABLE IF NOT EXISTS tv_cache (
    chiave     TEXT PRIMARY KEY,
    dati       TEXT NOT NULL DEFAULT '[]',
    aggiornato REAL NOT NULL DEFAULT 0    -- secondi dall'epoca: e' un confronto, non una data
);

-- La playlist YouTube scelta dalla casa. Sta nella casa e non in `localStorage`
-- ne' in una costante del modulo: e' una preferenza dell'utente, e due case sullo
-- stesso server non devono vedersi i video l'una dell'altra. Alla variabile
-- d'ambiente `TV_PLAYLIST` resta il ruolo di predefinita per chi non ha ancora
-- scelto, cosi' un'installazione esistente non cambia da sola.
--
-- `gym_playlist` e' la scelta **separata** del GYM: le due sezioni si guardano
-- per motivi diversi, quindi cambiare i video di casa non deve toccare
-- l'allenamento, ne' viceversa. Vuota = si ricade su `GYM_PLAYLIST` o sulla
-- predefinita.
--
-- Una riga sola (id = 1), come `llm_prefs` e `profile`.
CREATE TABLE IF NOT EXISTS tv_prefs (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    playlist     TEXT NOT NULL DEFAULT '',
    gym_playlist TEXT NOT NULL DEFAULT ''
);

-- ------------------------------------------------------------ calendario
-- Gli impegni: appuntamenti, scadenze, ricorrenze. Vivono dentro Progetti
-- perche' sono cose da fare, ma in una tabella a parte: un progetto ha un
-- periodo e una priorita', un impegno ha un giorno preciso e un'ora. Sono due
-- forme diverse, e mescolarle costringerebbe meta' delle righe ad avere campi
-- vuoti che non significano niente.
--
-- `when_date` non si chiama `date` perche' `date` e' una funzione di SQLite
-- (come `time` e `datetime`): un nome cosi' funziona finche' non lo si usa in
-- un'espressione, e allora l'errore arriva nel posto meno aspettato.
--
-- `reminder_days` e' quanti giorni **prima** avvisare, non una data: spostando
-- l'impegno si sposta anche il promemoria, invece di lasciarlo indietro. `time`
-- e' facoltativa: un impegno di giornata intera e' legittimo.
CREATE TABLE IF NOT EXISTS appointments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    when_date     TEXT NOT NULL,
    time          TEXT NOT NULL DEFAULT '',
    category      TEXT NOT NULL DEFAULT 'altro',
    notes         TEXT NOT NULL DEFAULT '',
    reminder_days INTEGER NOT NULL DEFAULT 0,
    done          INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(when_date);
CREATE INDEX IF NOT EXISTS idx_appointments_done ON appointments(done, when_date);

-- ---------------------------------------------------------------- cinema
-- I film che la casa ha segnato come preferiti, in una sezione a se'.
--
-- Si tiene la **scheda intera** (JSON), non solo l'id: i preferiti restano
-- anche quando il film esce dal giro dei "film del momento", e senza la scheda
-- salvata si vedrebbe una locandina vuota. La scheda e' la stessa forma che
-- `cinema._scheda` produce, cosi' il frontend la disegna allo stesso modo.
CREATE TABLE IF NOT EXISTS cinema_preferiti (
    movie_id   INTEGER PRIMARY KEY,
    dati       TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- I film che la casa ha **eliminato** dalla sezione: i titoli che non gradisce.
-- Non si cancellano dalla copia (`tv_cache`) — quella e' la fotografia di
-- TMDB, e cancellarli la lascerebbe sbagliata — e non si salva la scheda
-- intera come per i preferiti: qui basta l'id, perche' un film eliminato non si
-- mostra. L'eliminazione e' **reversibile**: `ripristina` toglie la riga e il
-- film torna al prossimo disegno.
CREATE TABLE IF NOT EXISTS cinema_nascosti (
    movie_id   INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

