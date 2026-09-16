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
    image_credit TEXT NOT NULL DEFAULT '',   -- autore, licenza e provenienza
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
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
