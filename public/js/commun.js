// Fonctions partagées par toutes les pages

// Appel à l'API du serveur. Renvoie le JSON, ou lève une erreur avec le message du serveur.
async function api(url, options = {}) {
  const opts = { credentials: 'same-origin', ...options, headers: { 'X-DCP': '1', ...(options.headers || {}) } };
  if (opts.body && !(opts.body instanceof FormData) && typeof opts.body !== 'string') {
    opts.body = JSON.stringify(opts.body);
    opts.headers['Content-Type'] = 'application/json';
  }
  const rep = await fetch(url, opts);
  let donnees = null;
  try { donnees = await rep.json(); } catch { /* réponse vide */ }
  if (!rep.ok) {
    const err = new Error(donnees?.erreur || `Erreur ${rep.status}`);
    err.status = rep.status;
    throw err;
  }
  return donnees;
}

function formaterDate(iso, long = false) {
  if (!iso) return '';
  const d = new Date(iso + 'T00:00:00');
  if (isNaN(d)) return iso;
  return d.toLocaleDateString('fr-FR', long ? { day: 'numeric', month: 'long', year: 'numeric' } : { month: 'long', year: 'numeric' });
}

function el(tag, attrs = {}, ...enfants) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') e.className = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) e.setAttribute(k, v === true ? '' : v);
  }
  for (const c of enfants.flat()) if (c != null && c !== false) e.append(c);
  return e;
}

// Carte d'un shooting (accueil et espace client)
function carteAlbum(album, i = 0) {
  const meta = [formaterDate(album.date), album.lieu, `${album.nbPhotos} photo${album.nbPhotos > 1 ? 's' : ''}`]
    .filter(Boolean).join(' · ');
  const carte = el('a', { class: 'album-card', href: `album.html#${encodeURIComponent(album.slug)}` },
    album.couverture
      ? el('img', { src: `/photos/${album.couverture}/mini`, alt: album.titre, loading: 'lazy' })
      : el('div', { class: 'album-card-vide' }, 'Photos à venir'),
    el('div', { class: 'album-card-infos' }, el('h2', {}, album.titre), el('p', {}, meta)),
  );
  carte.style.animationDelay = `${i * 70}ms`;
  return carte;
}

// Utilisateur connecté (ou null), chargé une seule fois par page
const moi = api('/api/moi').then(r => r.utilisateur).catch(() => null);

// Menu du haut selon qu'on est connecté, client ou admin
moi.then(u => {
  const nav = document.getElementById('nav');
  if (!nav) return;
  const page = location.pathname.replace(/\/$/, '/index.html').split('/').pop().replace('.html', '') || 'index';
  const lien = (href, texteLien, cle) => el('a', { href, class: page === cle ? 'actif' : '' }, texteLien);
  nav.replaceChildren(lien('index.html', 'Portfolio', 'index'));
  if (u) {
    if (u.role === 'admin') nav.append(lien('admin.html', 'Admin', 'admin'));
    else nav.append(lien('espace.html', 'Mes photos', 'espace'));
    nav.append(el('button', {
      class: 'nav-btn',
      onclick: async () => { await api('/api/deconnexion', { method: 'POST' }); location.href = 'index.html'; },
    }, 'Déconnexion'));
  } else {
    nav.append(el('a', { href: 'connexion.html', class: 'nav-cta' + (page === 'connexion' ? ' actif' : '') }, 'Espace client'));
  }
});

document.querySelectorAll('.annee').forEach(e => { e.textContent = new Date().getFullYear(); });
