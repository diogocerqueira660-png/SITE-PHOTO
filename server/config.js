const path = require('path');

const RACINE = path.resolve(__dirname, '..');
const DATA_DIR = path.resolve(process.env.DATA_DIR || path.join(RACINE, 'data'));

module.exports = {
  RACINE,
  DATA_DIR,
  PHOTOS_DIR: path.join(DATA_DIR, 'photos'),
  TMP_DIR: path.join(DATA_DIR, 'tmp'),
  DB_FILE: path.join(DATA_DIR, 'site.sqlite'),
  PORT: Number(process.env.PORT) || 3000,
  ADMIN_EMAIL: (process.env.ADMIN_EMAIL || '').trim(),
  ADMIN_PASSWORD: process.env.ADMIN_PASSWORD || '',
  SESSION_JOURS: 30,
  TAILLE_WEB: 2000,
  TAILLE_MINI: 800,
  TAILLE_MAX_FICHIER: 200 * 1024 * 1024, // 200 Mo par photo
};
