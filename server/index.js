const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const express = require('express');
const multer = require('multer');
const { ZipArchive } = require('archiver');

const config = require('./config');
const db = require('./db');
const auth = require('./auth');
const photos = require('./photos');

const app = express();
app.set('trust proxy', 1); // derrière l'hébergeur (HTTPS), pour les cookies sécurisés et l'IP réelle
app.disable('x-powered-by');

app.use((req, res, next) => {
  res.set({
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'same-origin',
    'X-Frame-Options': 'DENY',
    'Content-Security-Policy': [
      "default-src 'self'",
      "img-src 'self' data: blob:",
      "style-src 'self' https://fonts.googleapis.com",
      "font-src https://fonts.gstatic.com",
      "script-src 'self'",
      "frame-ancestors 'none'",
    ].join('; '),
  });
  next();
});
app.use(express.json({ limit: '100kb' }));
app.use(auth.chargerUtilisateur);
app.use('/api', auth.protegerCsrf);

// ------------------------------------------------------------------
// Utilitaires
// ------------------------------------------------------------------
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function texte(v, max = 500) {
  return typeof v === 'string' ? v.trim().slice(0, max) : '';
}

function slugifier(t) {
  const base = t.normalize('NFKD').replace(/[̀-ͯ]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'shooting';
  let slug = base;
  for (let i = 2; db.prepare('SELECT 1 FROM albums WHERE slug = ?').get(slug); i++) slug = `${base}-${i}`;
  return slug;
}

function listeEmails(v) {
  const brut = Array.isArray(v) ? v.join(',') : String(v || '');
  return [...new Set(brut.split(/[\s,;]+/).map(e => e.trim().toLowerCase()).filter(e => EMAIL_RE.test(e)))];
}

function aAcces(utilisateur, albumId) {
  if (!utilisateur) return false;
  if (utilisateur.role === 'admin') return true;
  return !!db.prepare('SELECT 1 FROM acces WHERE album_id = ? AND email = ?').get(albumId, utilisateur.email);
}

function peutVoir(utilisateur, album) {
  return !!album.public || aAcces(utilisateur, album.id);
}

// Données d'un album pour les cartes (accueil, espace client)
function resumeAlbum(a) {
  const nb = db.prepare('SELECT COUNT(*) AS n FROM photos WHERE album_id = ?').get(a.id).n;
  const couverture = a.couverture_id
    || db.prepare('SELECT id FROM photos WHERE album_id = ? ORDER BY ordre, id LIMIT 1').get(a.id)?.id
    || null;
  return {
    slug: a.slug, titre: a.titre, date: a.date, lieu: a.lieu,
    public: !!a.public, nbPhotos: nb, couverture,
  };
}

function nomZip(titre) {
  return (titre.normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/[^\w -]+/g, '').trim() || 'photos') + '.zip';
}

// ------------------------------------------------------------------
// Comptes
// ------------------------------------------------------------------
app.post('/api/inscription', auth.limiterEssais, (req, res) => {
  const nom = texte(req.body.nom, 100);
  const email = texte(req.body.email, 200).toLowerCase();
  const motDePasse = typeof req.body.motDePasse === 'string' ? req.body.motDePasse : '';
  if (!nom) return res.status(400).json({ erreur: 'Indique ton nom.' });
  if (!EMAIL_RE.test(email)) return res.status(400).json({ erreur: 'Adresse email invalide.' });
  if (motDePasse.length < 8) return res.status(400).json({ erreur: 'Le mot de passe doit faire au moins 8 caractères.' });
  if (db.prepare('SELECT 1 FROM utilisateurs WHERE email = ?').get(email)) {
    return res.status(409).json({ erreur: 'Un compte existe déjà avec cet email. Connecte-toi.' });
  }
  const { lastInsertRowid } = db.prepare('INSERT INTO utilisateurs (email, nom, hash) VALUES (?, ?, ?)')
    .run(email, nom, auth.hacher(motDePasse));
  auth.ouvrirSession(req, res, lastInsertRowid);
  res.status(201).json({ ok: true, role: 'client' });
});

app.post('/api/connexion', auth.limiterEssais, (req, res) => {
  const email = texte(req.body.email, 200);
  const motDePasse = typeof req.body.motDePasse === 'string' ? req.body.motDePasse : '';
  const u = db.prepare('SELECT id, hash, role FROM utilisateurs WHERE email = ?').get(email);
  if (!u || !auth.verifier(motDePasse, u.hash)) {
    return res.status(401).json({ erreur: 'Email ou mot de passe incorrect.' });
  }
  auth.ouvrirSession(req, res, u.id);
  res.json({ ok: true, role: u.role });
});

app.post('/api/deconnexion', (req, res) => {
  auth.fermerSession(req, res);
  res.json({ ok: true });
});

// Vérification par l'hébergeur que le site répond
app.get('/api/sante', (req, res) => {
  db.prepare('SELECT 1').get();
  res.json({ ok: true });
});

app.get('/api/moi', (req, res) => {
  res.json({ utilisateur: req.utilisateur });
});

app.post('/api/moi/mot-de-passe', auth.exigerConnexion, auth.limiterEssais, (req, res) => {
  const { actuel, nouveau } = req.body;
  const u = db.prepare('SELECT hash FROM utilisateurs WHERE id = ?').get(req.utilisateur.id);
  if (typeof actuel !== 'string' || !auth.verifier(actuel, u.hash)) {
    return res.status(400).json({ erreur: 'Mot de passe actuel incorrect.' });
  }
  if (typeof nouveau !== 'string' || nouveau.length < 8) {
    return res.status(400).json({ erreur: 'Le nouveau mot de passe doit faire au moins 8 caractères.' });
  }
  db.prepare('UPDATE utilisateurs SET hash = ? WHERE id = ?').run(auth.hacher(nouveau), req.utilisateur.id);
  res.json({ ok: true });
});

// ------------------------------------------------------------------
// Albums (public et clients)
// ------------------------------------------------------------------
app.get('/api/albums', (req, res) => {
  const albums = db.prepare("SELECT * FROM albums WHERE public = 1 ORDER BY date DESC, id DESC").all();
  res.json(albums.map(resumeAlbum).filter(a => a.nbPhotos > 0));
});

app.get('/api/mes-albums', auth.exigerConnexion, (req, res) => {
  const albums = db.prepare(`
    SELECT a.* FROM albums a JOIN acces x ON x.album_id = a.id
    WHERE x.email = ? ORDER BY a.date DESC, a.id DESC`).all(req.utilisateur.email);
  res.json(albums.map(resumeAlbum));
});

app.get('/api/albums/:slug', (req, res) => {
  const album = db.prepare('SELECT * FROM albums WHERE slug = ?').get(req.params.slug);
  if (!album || !peutVoir(req.utilisateur, album)) {
    // Un visiteur non connecté est invité à se connecter ; les autres voient « introuvable »
    return res.status(req.utilisateur ? 404 : 401).json({ erreur: 'Shooting introuvable.' });
  }
  const liste = db.prepare('SELECT id, largeur, hauteur, nom_origine FROM photos WHERE album_id = ? ORDER BY ordre, id')
    .all(album.id);
  res.json({
    slug: album.slug, titre: album.titre, date: album.date, lieu: album.lieu,
    description: album.description,
    peutTelecharger: aAcces(req.utilisateur, album.id),
    photos: liste.map(p => ({ id: p.id, largeur: p.largeur, hauteur: p.hauteur, nom: p.nom_origine })),
  });
});

// Photos : /photos/12/mini, /photos/12/web, /photos/12/original
app.get('/photos/:id/:format', (req, res) => {
  const { format } = req.params;
  if (!['mini', 'web', 'original'].includes(format)) return res.sendStatus(404);
  const photo = db.prepare('SELECT * FROM photos WHERE id = ?').get(Number(req.params.id));
  if (!photo) return res.sendStatus(404);
  const album = db.prepare('SELECT * FROM albums WHERE id = ?').get(photo.album_id);
  const autorise = format === 'original' ? aAcces(req.utilisateur, album.id) : peutVoir(req.utilisateur, album);
  if (!autorise) return res.sendStatus(404);

  res.set('Cache-Control', album.public && format !== 'original' ? 'public, max-age=86400' : 'private, max-age=3600');
  if (format === 'original') res.attachment(photo.nom_origine);
  res.sendFile(photos.chemin(photo, format));
});

// Tout le shooting en .zip (originaux), envoyé au fil de l'eau sans fichier temporaire
app.get('/api/albums/:slug/zip', (req, res) => {
  const album = db.prepare('SELECT * FROM albums WHERE slug = ?').get(req.params.slug);
  if (!album || !aAcces(req.utilisateur, album.id)) return res.sendStatus(404);
  const liste = db.prepare('SELECT * FROM photos WHERE album_id = ? ORDER BY ordre, id').all(album.id);

  res.attachment(nomZip(album.titre));
  const zip = new ZipArchive({ store: true }); // les JPEG sont déjà compressés
  zip.on('error', () => res.destroy());
  zip.pipe(res);
  const noms = new Set();
  for (const p of liste) {
    let nom = p.nom_origine;
    for (let i = 2; noms.has(nom.toLowerCase()); i++) nom = p.nom_origine.replace(/(\.[^.]*)?$/, `-${i}$1`);
    noms.add(nom.toLowerCase());
    zip.file(photos.chemin(p, 'original'), { name: nom });
  }
  zip.finalize();
});

// ------------------------------------------------------------------
// Administration
// ------------------------------------------------------------------
const admin = express.Router();
admin.use(auth.exigerAdmin);

function lireAlbum(id) {
  const album = db.prepare('SELECT * FROM albums WHERE id = ?').get(Number(id));
  if (!album) return null;
  album.public = !!album.public;
  album.clients = db.prepare('SELECT email FROM acces WHERE album_id = ? ORDER BY email').all(album.id).map(r => r.email);
  return album;
}

function definirClients(albumId, emails) {
  db.prepare('DELETE FROM acces WHERE album_id = ?').run(albumId);
  const ajout = db.prepare('INSERT INTO acces (album_id, email) VALUES (?, ?)');
  for (const e of emails) ajout.run(albumId, e);
}

admin.get('/albums', (req, res) => {
  const albums = db.prepare('SELECT * FROM albums ORDER BY date DESC, id DESC').all();
  res.json(albums.map(a => ({ id: a.id, ...resumeAlbum(a), clients: lireAlbum(a.id).clients })));
});

admin.post('/albums', (req, res) => {
  const titre = texte(req.body.titre, 150);
  if (!titre) return res.status(400).json({ erreur: 'Donne un titre au shooting.' });
  const creer = db.transaction(() => {
    const { lastInsertRowid } = db.prepare(`
      INSERT INTO albums (slug, titre, date, lieu, description, public) VALUES (?, ?, ?, ?, ?, ?)`)
      .run(slugifier(titre), titre, texte(req.body.date, 10), texte(req.body.lieu, 150),
        texte(req.body.description, 2000), req.body.public ? 1 : 0);
    definirClients(lastInsertRowid, listeEmails(req.body.clients));
    return lastInsertRowid;
  });
  res.status(201).json(lireAlbum(creer()));
});

admin.get('/albums/:id', (req, res) => {
  const album = lireAlbum(req.params.id);
  if (!album) return res.sendStatus(404);
  album.photos = db.prepare('SELECT id, nom_origine AS nom, largeur, hauteur, taille FROM photos WHERE album_id = ? ORDER BY ordre, id')
    .all(album.id);
  res.json(album);
});

admin.patch('/albums/:id', (req, res) => {
  const album = lireAlbum(req.params.id);
  if (!album) return res.sendStatus(404);
  const b = req.body;
  const champs = {
    titre: b.titre !== undefined ? texte(b.titre, 150) || album.titre : album.titre,
    date: b.date !== undefined ? texte(b.date, 10) : album.date,
    lieu: b.lieu !== undefined ? texte(b.lieu, 150) : album.lieu,
    description: b.description !== undefined ? texte(b.description, 2000) : album.description,
    public: b.public !== undefined ? (b.public ? 1 : 0) : (album.public ? 1 : 0),
    couverture_id: album.couverture_id,
  };
  if (b.couverture !== undefined) {
    const ok = db.prepare('SELECT 1 FROM photos WHERE id = ? AND album_id = ?').get(Number(b.couverture), album.id);
    champs.couverture_id = ok ? Number(b.couverture) : null;
  }
  db.transaction(() => {
    db.prepare(`UPDATE albums SET titre = @titre, date = @date, lieu = @lieu, description = @description,
      public = @public, couverture_id = @couverture_id WHERE id = @id`).run({ ...champs, id: album.id });
    if (b.clients !== undefined) definirClients(album.id, listeEmails(b.clients));
  })();
  res.json(lireAlbum(album.id));
});

admin.delete('/albums/:id', (req, res) => {
  const album = lireAlbum(req.params.id);
  if (!album) return res.sendStatus(404);
  db.prepare('DELETE FROM albums WHERE id = ?').run(album.id);
  photos.supprimerAlbum(album.id);
  res.json({ ok: true });
});

const upload = multer({
  dest: config.TMP_DIR,
  limits: { fileSize: config.TAILLE_MAX_FICHIER, files: 1 },
});

admin.post('/albums/:id/photos', upload.single('photo'), async (req, res) => {
  const album = lireAlbum(req.params.id);
  const tmp = req.file?.path;
  const nettoyer = () => tmp && fs.rmSync(tmp, { force: true });
  if (!album) { nettoyer(); return res.sendStatus(404); }
  if (!req.file) return res.status(400).json({ erreur: 'Aucune photo reçue.' });

  const extension = path.extname(req.file.originalname).toLowerCase();
  if (!photos.EXTENSIONS.includes(extension)) {
    nettoyer();
    return res.status(400).json({ erreur: `Format non pris en charge (${extension || 'inconnu'}). Utilise JPG, PNG, WebP ou TIFF.` });
  }
  let dim;
  try {
    dim = await photos.dimensions(tmp);
  } catch {
    nettoyer();
    return res.status(400).json({ erreur: `« ${req.file.originalname} » n'est pas une image lisible.` });
  }

  const ordre = db.prepare('SELECT COALESCE(MAX(ordre), 0) + 1 AS o FROM photos WHERE album_id = ?').get(album.id).o;
  const nom = path.basename(req.file.originalname).replace(/[\\/:*?"<>|]/g, '_').slice(0, 200);
  const { lastInsertRowid } = db.prepare(`
    INSERT INTO photos (album_id, nom_origine, extension, largeur, hauteur, taille, ordre)
    VALUES (?, ?, ?, ?, ?, ?, ?)`).run(album.id, nom, extension, dim.largeur, dim.hauteur, req.file.size, ordre);
  const photo = db.prepare('SELECT * FROM photos WHERE id = ?').get(lastInsertRowid);
  try {
    await photos.enregistrer(photo, tmp);
  } catch (err) {
    db.prepare('DELETE FROM photos WHERE id = ?').run(photo.id);
    photos.supprimer(photo);
    nettoyer();
    throw err;
  }
  res.status(201).json({ id: photo.id, nom, largeur: dim.largeur, hauteur: dim.hauteur, taille: req.file.size });
});

admin.delete('/photos/:id', (req, res) => {
  const photo = db.prepare('SELECT * FROM photos WHERE id = ?').get(Number(req.params.id));
  if (!photo) return res.sendStatus(404);
  db.transaction(() => {
    db.prepare('UPDATE albums SET couverture_id = NULL WHERE couverture_id = ?').run(photo.id);
    db.prepare('DELETE FROM photos WHERE id = ?').run(photo.id);
  })();
  photos.supprimer(photo);
  res.json({ ok: true });
});

admin.get('/clients', (req, res) => {
  const clients = db.prepare(`
    SELECT u.id, u.nom, u.email, u.cree_le,
      (SELECT COUNT(*) FROM acces x WHERE x.email = u.email) AS nbAlbums
    FROM utilisateurs u WHERE u.role = 'client' ORDER BY u.cree_le DESC`).all();
  res.json(clients);
});

// Le client a oublié son mot de passe : on lui en génère un provisoire à lui transmettre
admin.post('/clients/:id/mot-de-passe', (req, res) => {
  const u = db.prepare("SELECT id FROM utilisateurs WHERE id = ? AND role = 'client'").get(Number(req.params.id));
  if (!u) return res.sendStatus(404);
  const provisoire = crypto.randomBytes(6).toString('base64url');
  db.transaction(() => {
    db.prepare('UPDATE utilisateurs SET hash = ? WHERE id = ?').run(auth.hacher(provisoire), u.id);
    db.prepare('DELETE FROM sessions WHERE utilisateur_id = ?').run(u.id);
  })();
  res.json({ motDePasse: provisoire });
});

admin.delete('/clients/:id', (req, res) => {
  const r = db.prepare("DELETE FROM utilisateurs WHERE id = ? AND role = 'client'").run(Number(req.params.id));
  if (!r.changes) return res.sendStatus(404);
  res.json({ ok: true });
});

app.use('/api/admin', admin);

// ------------------------------------------------------------------
// Pages et erreurs
// ------------------------------------------------------------------
app.use(express.static(path.join(config.RACINE, 'public'), { extensions: ['html'] }));

app.use('/api', (req, res) => res.status(404).json({ erreur: 'Adresse inconnue.' }));

app.use((err, req, res, next) => {
  if (err instanceof multer.MulterError) {
    const msg = err.code === 'LIMIT_FILE_SIZE' ? 'Photo trop lourde (200 Mo maximum).' : 'Envoi de la photo refusé.';
    return res.status(400).json({ erreur: msg });
  }
  console.error(err);
  res.status(500).json({ erreur: 'Erreur du serveur. Réessaie dans un instant.' });
});

// ------------------------------------------------------------------
// Démarrage
// ------------------------------------------------------------------
function creerAdminDepuisEnv() {
  if (!config.ADMIN_EMAIL || !config.ADMIN_PASSWORD) return;
  const existant = db.prepare('SELECT id, role FROM utilisateurs WHERE email = ?').get(config.ADMIN_EMAIL);
  if (!existant) {
    db.prepare("INSERT INTO utilisateurs (email, nom, hash, role) VALUES (?, 'Diogo', ?, 'admin')")
      .run(config.ADMIN_EMAIL.toLowerCase(), auth.hacher(config.ADMIN_PASSWORD));
    console.log(`Compte administrateur créé : ${config.ADMIN_EMAIL}`);
  } else if (existant.role !== 'admin') {
    db.prepare("UPDATE utilisateurs SET role = 'admin' WHERE id = ?").run(existant.id);
  }
}

if (require.main === module) {
  creerAdminDepuisEnv();
  if (!db.prepare("SELECT 1 FROM utilisateurs WHERE role = 'admin'").get()) {
    console.warn('⚠ Aucun compte administrateur. Définis ADMIN_EMAIL et ADMIN_PASSWORD (voir README).');
  }
  auth.nettoyerSessions();
  setInterval(auth.nettoyerSessions, 6 * 3600 * 1000).unref();
  app.listen(config.PORT, () => console.log(`Site lancé sur http://localhost:${config.PORT}`));
}

module.exports = app;
