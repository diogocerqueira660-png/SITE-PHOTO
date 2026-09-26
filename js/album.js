// Page d'un shooting : galerie, visionneuse et téléchargement protégé par mot de passe
const slug = new URLSearchParams(location.search).get('a');
const album = (typeof ALBUMS !== 'undefined' ? ALBUMS : []).find(a => a.slug === slug);
const dossier = album ? `albums/${album.slug}` : '';

document.getElementById('year').textContent = new Date().getFullYear();

if (!album) {
  document.getElementById('introuvable').hidden = false;
} else {
  afficherAlbum();
}

function formaterDate(iso) {
  if (!iso) return '';
  const d = new Date(iso + 'T00:00:00');
  return isNaN(d) ? iso : d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
}

function afficherAlbum() {
  document.title = `${album.titre} — Diogo Car Photography`;
  document.getElementById('albumTitre').textContent = album.titre;
  document.getElementById('albumMeta').textContent =
    [formaterDate(album.date), album.lieu].filter(Boolean).join(' · ');
  document.getElementById('albumDesc').textContent = album.description || '';
  document.getElementById('btnTelecharger').hidden = !album.telechargement;

  const gallery = document.getElementById('gallery');
  album.photos.forEach((photo, i) => {
    const item = document.createElement('button');
    item.className = 'gallery-item';
    item.style.animationDelay = `${Math.min(i, 12) * 50}ms`;
    item.setAttribute('aria-label', `Agrandir la photo ${i + 1}`);
    const img = document.createElement('img');
    img.src = `${dossier}/mini/${photo.fichier}`;
    img.alt = `${album.titre} — photo ${i + 1}`;
    img.loading = 'lazy';
    img.width = photo.largeur;
    img.height = photo.hauteur;
    item.appendChild(img);
    item.addEventListener('click', () => ouvrirLightbox(i));
    gallery.appendChild(item);
  });
}

// ===== Visionneuse =====
const lightbox = document.getElementById('lightbox');
const lbImg = document.getElementById('lbImg');
const lbCaption = document.getElementById('lbCaption');
const lbDl = document.getElementById('lbDl');
let courante = 0;

function afficherPhoto(i) {
  courante = (i + album.photos.length) % album.photos.length;
  lbImg.src = `${dossier}/web/${album.photos[courante].fichier}`;
  lbImg.alt = `${album.titre} — photo ${courante + 1}`;
  lbCaption.textContent = `${courante + 1} / ${album.photos.length}`;
}
function ouvrirLightbox(i) {
  afficherPhoto(i);
  lbDl.hidden = !cle;
  lightbox.classList.add('open');
  lightbox.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
}
function fermerLightbox() {
  lightbox.classList.remove('open');
  lightbox.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
}
document.getElementById('lbClose').addEventListener('click', fermerLightbox);
document.getElementById('lbPrev').addEventListener('click', () => afficherPhoto(courante - 1));
document.getElementById('lbNext').addEventListener('click', () => afficherPhoto(courante + 1));
lightbox.addEventListener('click', e => { if (e.target === lightbox) fermerLightbox(); });
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { fermerLightbox(); fermerModal(); }
  if (!lightbox.classList.contains('open')) return;
  if (e.key === 'ArrowLeft') afficherPhoto(courante - 1);
  if (e.key === 'ArrowRight') afficherPhoto(courante + 1);
});

// Glisser du doigt sur mobile
let debutX = null;
lightbox.addEventListener('touchstart', e => { debutX = e.touches[0].clientX; }, { passive: true });
lightbox.addEventListener('touchend', e => {
  if (debutX === null) return;
  const dx = e.changedTouches[0].clientX - debutX;
  if (Math.abs(dx) > 50) afficherPhoto(courante + (dx < 0 ? 1 : -1));
  debutX = null;
});

// ===== Téléchargement protégé =====
// Les originaux sont chiffrés (AES-256-GCM) par outils/ajouter_shooting.py.
// Le mot de passe ne quitte jamais le navigateur : il sert à recalculer la clé de déchiffrement.
const modal = document.getElementById('modal');
const formMdp = document.getElementById('formMdp');
const zoneDl = document.getElementById('zoneDl');
const mdpErreur = document.getElementById('mdpErreur');
let cle = null;

const b64 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));

function ouvrirModal() {
  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
  if (!cle) setTimeout(() => document.getElementById('mdp').focus(), 50);
}
function fermerModal() {
  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
}
document.getElementById('btnTelecharger').addEventListener('click', ouvrirModal);
document.getElementById('modalClose').addEventListener('click', fermerModal);
modal.addEventListener('click', e => { if (e.target === modal) fermerModal(); });

async function deriverCle(motDePasse) {
  const { sel, iterations } = album.telechargement;
  const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(motDePasse), 'PBKDF2', false, ['deriveKey']);
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt: b64(sel), iterations, hash: 'SHA-256' },
    base, { name: 'AES-GCM', length: 256 }, false, ['decrypt']
  );
}

async function dechiffrer(k, donnees) {
  const octets = new Uint8Array(donnees);
  return crypto.subtle.decrypt({ name: 'AES-GCM', iv: octets.slice(0, 12) }, k, octets.slice(12));
}

formMdp.addEventListener('submit', async e => {
  e.preventDefault();
  const bouton = document.getElementById('btnValider');
  bouton.disabled = true;
  bouton.textContent = 'Vérification…';
  mdpErreur.textContent = '';
  try {
    const k = await deriverCle(document.getElementById('mdp').value);
    await dechiffrer(k, b64(album.telechargement.verif)); // échoue si le mot de passe est faux
    cle = k;
    formMdp.hidden = true;
    zoneDl.hidden = false;
  } catch {
    mdpErreur.textContent = 'Mot de passe incorrect.';
  } finally {
    bouton.disabled = false;
    bouton.textContent = 'Déverrouiller';
  }
});

async function recupererOriginal(i) {
  const rep = await fetch(`${dossier}/hd/${String(i + 1).padStart(3, '0')}.bin`);
  if (!rep.ok) throw new Error(`Photo ${i + 1} introuvable`);
  return dechiffrer(cle, await rep.arrayBuffer());
}

function enregistrer(blob, nom) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = nom;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

const progress = document.getElementById('progress');
const progressBar = document.getElementById('progressBar');
const progressTxt = document.getElementById('progressTxt');

document.getElementById('btnZip').addEventListener('click', async e => {
  const bouton = e.currentTarget;
  bouton.disabled = true;
  progress.hidden = false;
  try {
    const zip = new JSZip();
    const total = album.photos.length;
    for (let i = 0; i < total; i++) {
      progressTxt.textContent = `Préparation : photo ${i + 1} / ${total}`;
      progressBar.style.width = `${(i / total) * 100}%`;
      zip.file(album.photos[i].original || album.photos[i].fichier, await recupererOriginal(i));
    }
    progressTxt.textContent = 'Création du fichier .zip…';
    const blob = await zip.generateAsync({ type: 'blob', compression: 'STORE' },
      m => { progressBar.style.width = `${m.percent}%`; });
    enregistrer(blob, `${album.slug}.zip`);
    progressTxt.textContent = 'Téléchargement lancé ✔';
  } catch (err) {
    progressTxt.textContent = `Erreur : ${err.message}`;
  } finally {
    bouton.disabled = false;
  }
});

lbDl.addEventListener('click', async () => {
  const photo = album.photos[courante];
  lbDl.disabled = true;
  try {
    enregistrer(new Blob([await recupererOriginal(courante)]), photo.original || photo.fichier);
  } catch (err) {
    alert(`Erreur : ${err.message}`);
  } finally {
    lbDl.disabled = false;
  }
});
