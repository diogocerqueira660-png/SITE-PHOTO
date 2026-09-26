const crypto = require('crypto');
const bcrypt = require('bcryptjs');
const db = require('./db');
const { SESSION_JOURS } = require('./config');

const COOKIE = 'dcp_session';
const DUREE_MS = SESSION_JOURS * 24 * 3600 * 1000;

function hacher(motDePasse) {
  return bcrypt.hashSync(motDePasse, 12);
}

function verifier(motDePasse, hash) {
  return bcrypt.compareSync(motDePasse, hash);
}

function lireCookies(req) {
  const cookies = {};
  for (const morceau of (req.headers.cookie || '').split(';')) {
    const i = morceau.indexOf('=');
    if (i > 0) cookies[morceau.slice(0, i).trim()] = decodeURIComponent(morceau.slice(i + 1).trim());
  }
  return cookies;
}

function ouvrirSession(req, res, utilisateurId) {
  const token = crypto.randomBytes(32).toString('hex');
  db.prepare('INSERT INTO sessions (token, utilisateur_id, expire) VALUES (?, ?, ?)')
    .run(token, utilisateurId, Date.now() + DUREE_MS);
  res.cookie(COOKIE, token, {
    httpOnly: true,
    sameSite: 'lax',
    secure: req.secure,
    maxAge: DUREE_MS,
    path: '/',
  });
}

function fermerSession(req, res) {
  const token = lireCookies(req)[COOKIE];
  if (token) db.prepare('DELETE FROM sessions WHERE token = ?').run(token);
  res.clearCookie(COOKIE, { path: '/' });
}

// Ajoute req.utilisateur (ou null) à chaque requête
function chargerUtilisateur(req, res, next) {
  req.utilisateur = null;
  const token = lireCookies(req)[COOKIE];
  if (token) {
    const ligne = db.prepare(`
      SELECT u.id, u.email, u.nom, u.role, s.expire
      FROM sessions s JOIN utilisateurs u ON u.id = s.utilisateur_id
      WHERE s.token = ?`).get(token);
    if (ligne && ligne.expire > Date.now()) {
      const { expire, ...utilisateur } = ligne;
      req.utilisateur = utilisateur;
    } else if (ligne) {
      db.prepare('DELETE FROM sessions WHERE token = ?').run(token);
    }
  }
  next();
}

function exigerConnexion(req, res, next) {
  if (!req.utilisateur) return res.status(401).json({ erreur: 'Connecte-toi pour continuer.' });
  next();
}

function exigerAdmin(req, res, next) {
  if (!req.utilisateur) return res.status(401).json({ erreur: 'Connecte-toi pour continuer.' });
  if (req.utilisateur.role !== 'admin') return res.status(403).json({ erreur: 'Accès réservé à l\'administrateur.' });
  next();
}

// Protection CSRF : toute requête qui modifie quelque chose doit venir du site lui-même.
// Les pages envoient l'en-tête X-DCP, qu'un autre site ne peut pas ajouter sans autorisation CORS.
function protegerCsrf(req, res, next) {
  if (['GET', 'HEAD', 'OPTIONS'].includes(req.method)) return next();
  if (req.get('x-dcp') !== '1') return res.status(403).json({ erreur: 'Requête refusée.' });
  next();
}

// Limite les essais de connexion : 10 tentatives par 15 minutes et par adresse IP
const essais = new Map();
function limiterEssais(req, res, next) {
  const maintenant = Date.now();
  const cle = req.ip;
  const entree = essais.get(cle);
  if (!entree || entree.reset < maintenant) {
    essais.set(cle, { n: 1, reset: maintenant + 15 * 60 * 1000 });
    return next();
  }
  if (++entree.n > 10) {
    return res.status(429).json({ erreur: 'Trop de tentatives. Réessaie dans quelques minutes.' });
  }
  next();
}

function nettoyerSessions() {
  db.prepare('DELETE FROM sessions WHERE expire < ?').run(Date.now());
}

module.exports = {
  hacher, verifier, ouvrirSession, fermerSession, chargerUtilisateur,
  exigerConnexion, exigerAdmin, protegerCsrf, limiterEssais, nettoyerSessions,
};
