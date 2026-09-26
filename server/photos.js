const fs = require('fs');
const path = require('path');
const sharp = require('sharp');
const { PHOTOS_DIR, TAILLE_WEB, TAILLE_MINI } = require('./config');

const EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff'];

function dossierAlbum(albumId) {
  return path.join(PHOTOS_DIR, String(albumId));
}

function chemin(photo, format) {
  const base = dossierAlbum(photo.album_id);
  if (format === 'original') return path.join(base, 'originaux', `${photo.id}${photo.extension}`);
  return path.join(base, format, `${photo.id}.jpg`);
}

// Lit les dimensions après rotation EXIF (photo prise en portrait, etc.)
async function dimensions(fichier) {
  const meta = await sharp(fichier).metadata();
  const tourne = meta.orientation && meta.orientation >= 5;
  return tourne ? { largeur: meta.height, hauteur: meta.width } : { largeur: meta.width, hauteur: meta.height };
}

// Range l'original et fabrique la version web (2000 px) et la miniature (800 px)
async function enregistrer(photo, fichierTemporaire) {
  const base = dossierAlbum(photo.album_id);
  for (const sous of ['originaux', 'web', 'mini']) fs.mkdirSync(path.join(base, sous), { recursive: true });

  const redim = taille => sharp(fichierTemporaire)
    .rotate()
    .resize(taille, taille, { fit: 'inside', withoutEnlargement: true })
    .jpeg({ quality: 85, progressive: true, mozjpeg: true });
  await redim(TAILLE_WEB).toFile(chemin(photo, 'web'));
  await redim(TAILLE_MINI).toFile(chemin(photo, 'mini'));
  fs.renameSync(fichierTemporaire, chemin(photo, 'original'));
}

function supprimer(photo) {
  for (const format of ['original', 'web', 'mini']) fs.rmSync(chemin(photo, format), { force: true });
}

function supprimerAlbum(albumId) {
  fs.rmSync(dossierAlbum(albumId), { recursive: true, force: true });
}

module.exports = { EXTENSIONS, chemin, dimensions, enregistrer, supprimer, supprimerAlbum };
