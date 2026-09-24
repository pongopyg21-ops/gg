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
-- `secret` fa nascondere il valore finche' non lo si tocca. NON e' una
-- protezione: il valore viaggia comunque nella risposta dell'API. Serve a non
-- tenere una password sullo schermo quando qualcuno passa dietro la scrivania.
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
