// ===== Menu mobile =====
const header = document.getElementById('header');
const nav = document.getElementById('nav');
const navToggle = document.getElementById('navToggle');

navToggle.addEventListener('click', () => {
  const open = nav.classList.toggle('open');
  navToggle.classList.toggle('open', open);
  navToggle.setAttribute('aria-expanded', open);
});
nav.querySelectorAll('a').forEach(a => a.addEventListener('click', () => {
  nav.classList.remove('open');
  navToggle.classList.remove('open');
  navToggle.setAttribute('aria-expanded', false);
}));

// ===== En-tête opaque au défilement =====
const onScroll = () => header.classList.toggle('scrolled', window.scrollY > 40);
window.addEventListener('scroll', onScroll, { passive: true });
onScroll();

// ===== Galerie + filtres =====
const gallery = document.getElementById('gallery');
const filtersEl = document.getElementById('filters');
let visible = [];

const categories = ['Tout', ...new Set(PHOTOS.map(p => p.categorie))];
categories.forEach((cat, i) => {
  const btn = document.createElement('button');
  btn.className = 'filter-btn' + (i === 0 ? ' active' : '');
  btn.textContent = cat;
  btn.addEventListener('click', () => {
    filtersEl.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderGallery(cat);
  });
  filtersEl.appendChild(btn);
});

function renderGallery(cat = 'Tout') {
  visible = cat === 'Tout' ? PHOTOS : PHOTOS.filter(p => p.categorie === cat);
  gallery.innerHTML = '';
  visible.forEach((photo, i) => {
    const item = document.createElement('div');
    item.className = 'gallery-item';
    item.style.animationDelay = `${i * 60}ms`;

    const img = document.createElement('img');
    img.src = photo.src;
    img.alt = photo.titre;
    img.loading = 'lazy';

    const overlay = document.createElement('div');
    overlay.className = 'overlay';
    const tag = document.createElement('span');
    tag.textContent = photo.categorie;
    const title = document.createElement('h3');
    title.textContent = photo.titre;
    overlay.append(tag, title);

    item.append(img, overlay);
    item.addEventListener('click', () => openLightbox(i));
    gallery.appendChild(item);
  });
}
renderGallery();

// ===== Lightbox =====
const lightbox = document.getElementById('lightbox');
const lbImg = document.getElementById('lbImg');
const lbCaption = document.getElementById('lbCaption');
let current = 0;

function showPhoto(i) {
  current = (i + visible.length) % visible.length;
  const p = visible[current];
  lbImg.src = p.src;
  lbImg.alt = p.titre;
  lbCaption.textContent = p.lieu ? `${p.titre} — ${p.lieu}` : p.titre;
}
function openLightbox(i) {
  showPhoto(i);
  lightbox.classList.add('open');
  lightbox.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
}
function closeLightbox() {
  lightbox.classList.remove('open');
  lightbox.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
}

document.getElementById('lbClose').addEventListener('click', closeLightbox);
document.getElementById('lbPrev').addEventListener('click', () => showPhoto(current - 1));
document.getElementById('lbNext').addEventListener('click', () => showPhoto(current + 1));
lightbox.addEventListener('click', e => { if (e.target === lightbox) closeLightbox(); });
document.addEventListener('keydown', e => {
  if (!lightbox.classList.contains('open')) return;
  if (e.key === 'Escape') closeLightbox();
  if (e.key === 'ArrowLeft') showPhoto(current - 1);
  if (e.key === 'ArrowRight') showPhoto(current + 1);
});

// ===== Formulaire de contact =====
// Sans serveur, le formulaire ouvre l'application mail du visiteur.
// Pour recevoir les messages directement, branche un service comme Formspree (voir README).
const CONTACT_EMAIL = 'contact@exemple.com';
document.getElementById('contactForm').addEventListener('submit', e => {
  if (e.target.getAttribute('action')) return; // formulaire branché sur Formspree : envoi normal
  e.preventDefault();
  const f = new FormData(e.target);
  const subject = encodeURIComponent(`Demande de shooting — ${f.get('projet') || f.get('nom')}`);
  const body = encodeURIComponent(`${f.get('message')}\n\n${f.get('nom')} (${f.get('email')})`);
  window.location.href = `mailto:${CONTACT_EMAIL}?subject=${subject}&body=${body}`;
  document.getElementById('formNote').textContent = 'Ton application mail va s\'ouvrir pour envoyer le message.';
});

document.getElementById('year').textContent = new Date().getFullYear();
