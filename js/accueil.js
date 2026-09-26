// Page d'accueil : une carte par shooting (liste dans albums/albums.js)
const conteneur = document.getElementById('albums');
const albums = typeof ALBUMS !== 'undefined' ? ALBUMS : [];

function formaterDate(iso) {
  if (!iso) return '';
  const d = new Date(iso + 'T00:00:00');
  return isNaN(d) ? iso : d.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
}

albums.forEach((album, i) => {
  const carte = document.createElement('a');
  carte.className = 'album-card';
  carte.href = `album.html#${encodeURIComponent(album.slug)}`;
  carte.style.animationDelay = `${i * 70}ms`;

  const img = document.createElement('img');
  img.src = `albums/${album.slug}/mini/${album.couverture}`;
  img.alt = album.titre;
  img.loading = 'lazy';

  const infos = document.createElement('div');
  infos.className = 'album-card-infos';
  const titre = document.createElement('h2');
  titre.textContent = album.titre;
  const meta = document.createElement('p');
  meta.textContent = [formaterDate(album.date), album.lieu, `${album.photos.length} photos`]
    .filter(Boolean).join(' · ');
  infos.append(titre, meta);

  carte.append(img, infos);
  conteneur.appendChild(carte);
});

document.getElementById('vide').hidden = albums.length > 0;
document.getElementById('year').textContent = new Date().getFullYear();
