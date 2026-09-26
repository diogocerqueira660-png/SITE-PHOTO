const fs = require('fs');
const Database = require('better-sqlite3');
const { DATA_DIR, PHOTOS_DIR, TMP_DIR, DB_FILE } = require('./config');

for (const dir of [DATA_DIR, PHOTOS_DIR, TMP_DIR]) fs.mkdirSync(dir, { recursive: true });

const db = new Database(DB_FILE);
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

db.exec(`
  CREATE TABLE IF NOT EXISTS utilisateurs (
    id        INTEGER PRIMARY KEY,
    email     TEXT NOT NULL UNIQUE COLLATE NOCASE,
    nom       TEXT NOT NULL,
    hash      TEXT NOT NULL,
    role      TEXT NOT NULL DEFAULT 'client' CHECK (role IN ('client', 'admin')),
    cree_le   TEXT NOT NULL DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS sessions (
    token          TEXT PRIMARY KEY,
    utilisateur_id INTEGER NOT NULL REFERENCES utilisateurs(id) ON DELETE CASCADE,
    expire         INTEGER NOT NULL
  );

  CREATE TABLE IF NOT EXISTS albums (
    id            INTEGER PRIMARY KEY,
    slug          TEXT NOT NULL UNIQUE,
    titre         TEXT NOT NULL,
    date          TEXT NOT NULL DEFAULT '',
    lieu          TEXT NOT NULL DEFAULT '',
    description   TEXT NOT NULL DEFAULT '',
    public        INTEGER NOT NULL DEFAULT 0,
    couverture_id INTEGER,
    cree_le       TEXT NOT NULL DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS photos (
    id          INTEGER PRIMARY KEY,
    album_id    INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    nom_origine TEXT NOT NULL,
    extension   TEXT NOT NULL,
    largeur     INTEGER NOT NULL,
    hauteur     INTEGER NOT NULL,
    taille      INTEGER NOT NULL,
    ordre       INTEGER NOT NULL DEFAULT 0,
    cree_le     TEXT NOT NULL DEFAULT (datetime('now'))
  );
  CREATE INDEX IF NOT EXISTS photos_album ON photos(album_id, ordre);

  -- Les clients qui ont accès à un album, par email : on peut donner l'accès
  -- avant même que le client ait créé son compte.
  CREATE TABLE IF NOT EXISTS acces (
    album_id INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    email    TEXT NOT NULL COLLATE NOCASE,
    PRIMARY KEY (album_id, email)
  );
`);

module.exports = db;
