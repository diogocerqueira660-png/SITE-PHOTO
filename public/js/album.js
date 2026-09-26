// Page d'un shooting : galerie, visionneuse et téléchargements (si le client y a accès)
const slug = decodeURIComponent(location.hash.slice(1));
let album = null;

function afficherMessage(html) {
  const m = document.getElementById('message');
  m.innerHTML = html;
  m.hidden = false;
}

async function charger() {
  try {
    album = await api(`/api/albums/${encodeURIComponent(slug)}`);
  } catch (err) {
    if (err.status === 401) {
      sessionStorage.setItem('retour', location.pathname + location.hash);
      afficherMessage(`<p>Ce shooting est privé.</p>
        <a class="btn btn-primary" href="connexion.html">Se connecter</a>`);
    } else {
      afficherMessage(`<p>Ce shooting n'existe pas ou tu n'y as pas accès.</p>
        <a href="index.html">Retour au portfolio</a>`);
    }
    return;
  }

  document.title = `${album.titre} — Diogo Car Photography`;
  document.getElementById('albumHead').hidden = false;
  document.getElementById('albumTitre').textContent = album.titre;
  document.getElementById('albumMeta').textContent = [formaterDate(album.date, true), album.lieu].filter(Boolean).join(' · ');
  document.getElementById('albumDesc').textContent = album.description || '';

  const btnZip = document.getElementById('btnZip');
  if (album.peutTelecharger && album.photos.length) {
    btnZip.href = `/api/albums/${encodeURIComponent(album.slug)}/zip`;
    btnZip.hidden = false;
  }

  const gallery = document.getElementById('gallery');
  album.photos.forEach((photo, i) => {
    const img = el('img', {
      src: `/photos/${photo.id}/mini`, alt: `${album.titre} — photo ${i + 1}`,
      loading: 'lazy', width: photo.largeur, height: photo.hauteur,
    });
    const item = el('button', { class: 'gallery-item', 'aria-label': `Agrandir la photo ${i + 1}`, onclick: () => ouvrir(i) }, img);
    item.style.animationDelay = `${Math.min(i, 12) * 50}ms`;
    gallery.append(item);
  });
  if (!album.photos.length) afficherMessage('<p>Les photos arrivent bientôt.</p>');
}

// ===== Visionneuse =====
const lightbox = document.getElementById('lightbox');
const lbImg = document.getElementById('lbImg');
const lbCaption = document.getElementById('lbCaption');
const lbDl = document.getElementById('lbDl');
let courante = 0;

function afficher(i) {
  courante = (i + album.photos.length) % album.photos.length;
  const p = album.photos[courante];
  lbImg.src = `/photos/${p.id}/web`;
  lbImg.alt = `${album.titre} — photo ${courante + 1}`;
  lbCaption.textContent = `${courante + 1} / ${album.photos.length}`;
  lbDl.href = `/photos/${p.id}/original`;
}
function ouvrir(i) {
  afficher(i);
  lbDl.hidden = !album.peutTelecharger;
  lightbox.classList.add('open');
  lightbox.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
}
function fermer() {
  lightbox.classList.remove('open');
  lightbox.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
}
document.getElementById('lbClose').addEventListener('click', fermer);
document.getElementById('lbPrev').addEventListener('click', () => afficher(courante - 1));
document.getElementById('lbNext').addEventListener('click', () => afficher(courante + 1));
lightbox.addEventListener('click', e => { if (e.target === lightbox) fermer(); });
document.addEventListener('keydown', e => {
  if (!lightbox.classList.contains('open')) return;
  if (e.key === 'Escape') fermer();
  if (e.key === 'ArrowLeft') afficher(courante - 1);
  if (e.key === 'ArrowRight') afficher(courante + 1);
});
let debutX = null;
lightbox.addEventListener('touchstart', e => { debutX = e.touches[0].clientX; }, { passive: true });
lightbox.addEventListener('touchend', e => {
  if (debutX === null) return;
  const dx = e.changedTouches[0].clientX - debutX;
  if (Math.abs(dx) > 50) afficher(courante + (dx < 0 ? 1 : -1));
  debutX = null;
});

window.addEventListener('hashchange', () => location.reload());
charger();
