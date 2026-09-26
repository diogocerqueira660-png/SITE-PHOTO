// Administration : shootings, envoi des photos, clients
// Navigation par l'adresse : admin.html (liste), #nouveau, #album-12, #clients
const $ = id => document.getElementById(id);
const vues = { albums: $('vueAlbums'), album: $('vueAlbum'), clients: $('vueClients') };
let albumCourant = null;

moi.then(u => {
  if (!u) { sessionStorage.setItem('retour', 'admin.html'); location.replace('connexion.html'); return; }
  if (u.role !== 'admin') { location.replace('espace.html'); return; }
  router();
  window.addEventListener('hashchange', router);
});

function montrerVue(nom, titre) {
  for (const [cle, v] of Object.entries(vues)) v.hidden = cle !== nom;
  $('adminTitre').textContent = titre;
  $('ongletAlbums').classList.toggle('actif', nom !== 'clients');
  $('ongletClients').classList.toggle('actif', nom === 'clients');
  window.scrollTo(0, 0);
}

function router() {
  const h = location.hash.slice(1);
  if (h === 'clients') return afficherClients();
  if (h === 'nouveau') return afficherAlbum(null);
  if (h.startsWith('album-')) return afficherAlbum(Number(h.slice(6)));
  afficherListe();
}

$('ongletAlbums').addEventListener('click', () => { location.hash = ''; });
$('ongletClients').addEventListener('click', () => { location.hash = 'clients'; });
$('btnNouveau').addEventListener('click', () => { location.hash = 'nouveau'; });

// ----- Fenêtre de confirmation -----
function confirmer(titre, texte, libelle = 'Supprimer') {
  return new Promise(resolve => {
    const modal = $('modal');
    $('modalTitre').textContent = titre;
    $('modalTexte').textContent = texte;
    $('modalOk').textContent = libelle;
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
    const fin = ok => {
      modal.classList.remove('open');
      modal.setAttribute('aria-hidden', 'true');
      $('modalOk').onclick = $('modalAnnuler').onclick = null;
      resolve(ok);
    };
    $('modalOk').onclick = () => fin(true);
    $('modalAnnuler').onclick = () => fin(false);
  });
}

function taille(octets) {
  return octets > 1e6 ? `${(octets / 1e6).toFixed(1)} Mo` : `${Math.round(octets / 1e3)} Ko`;
}

// ----- Liste des shootings -----
async function afficherListe() {
  montrerVue('albums', 'Shootings');
  const albums = await api('/api/admin/albums');
  const tbody = $('tableAlbums').querySelector('tbody');
  tbody.replaceChildren(...albums.map(a => {
    const lien = `#album-${a.id}`;
    return el('tr', { class: 'cliquable', onclick: () => { location.hash = lien.slice(1); } },
      el('td', { class: 'td-mini' }, a.couverture ? el('img', { src: `/photos/${a.couverture}/mini`, alt: '' }) : ''),
      el('td', {}, el('a', { href: lien }, a.titre), el('div', { class: 'td-sous' }, a.lieu)),
      el('td', {}, formaterDate(a.date, true)),
      el('td', {}, String(a.nbPhotos)),
      el('td', {}, el('span', { class: `pastille ${a.public ? 'pastille-public' : ''}` }, a.public ? 'Public' : 'Privé')),
      el('td', { class: 'td-sous' }, a.clients.join(', ') || '—'),
    );
  }));
  $('tableAlbums').hidden = !albums.length;
  $('albumsVide').hidden = albums.length > 0;
}

// ----- Création / édition d'un shooting -----
async function afficherAlbum(id) {
  $('erreurAlbum').textContent = '';
  $('albumOk').textContent = '';
  if (id) {
    try {
      albumCourant = await api(`/api/admin/albums/${id}`);
    } catch {
      location.hash = '';
      return;
    }
  } else {
    albumCourant = null;
  }
  const a = albumCourant || { titre: '', date: '', lieu: '', description: '', clients: [], public: false };
  montrerVue('album', id ? a.titre : 'Nouveau shooting');
  $('aTitre').value = a.titre;
  $('aDate').value = a.date;
  $('aLieu').value = a.lieu;
  $('aDesc').value = a.description;
  $('aClients').value = a.clients.join('\n');
  $('aPublic').checked = a.public;
  $('btnEnregistrer').textContent = id ? 'Enregistrer' : 'Créer le shooting';
  $('btnSupprimerAlbum').hidden = !id;
  $('lienVoir').hidden = !id;
  if (id) $('lienVoir').href = `album.html#${encodeURIComponent(a.slug)}`;
  $('zonePhotos').hidden = !id;
  if (id) afficherPhotos();
  else $('aTitre').focus();
}

$('formAlbum').addEventListener('submit', async e => {
  e.preventDefault();
  $('erreurAlbum').textContent = '';
  const donnees = {
    titre: $('aTitre').value, date: $('aDate').value, lieu: $('aLieu').value,
    description: $('aDesc').value, clients: $('aClients').value, public: $('aPublic').checked,
  };
  try {
    if (albumCourant) {
      await api(`/api/admin/albums/${albumCourant.id}`, { method: 'PATCH', body: donnees });
      await afficherAlbum(albumCourant.id);
      $('albumOk').textContent = 'Enregistré ✔';
    } else {
      const cree = await api('/api/admin/albums', { method: 'POST', body: donnees });
      location.hash = `album-${cree.id}`; // ouvre l'album pour ajouter les photos
    }
  } catch (err) {
    $('erreurAlbum').textContent = err.message;
  }
});

$('btnSupprimerAlbum').addEventListener('click', async () => {
  const ok = await confirmer('Supprimer ce shooting ?',
    `« ${albumCourant.titre} » et ses ${albumCourant.photos.length} photos seront définitivement supprimés.`);
  if (!ok) return;
  await api(`/api/admin/albums/${albumCourant.id}`, { method: 'DELETE' });
  location.hash = '';
});

function afficherPhotos() {
  const liste = albumCourant.photos;
  $('nbPhotos').textContent = `(${liste.length})`;
  const couverture = albumCourant.couverture_id || liste[0]?.id;
  $('adminPhotos').replaceChildren(...liste.map(p => el('figure', { class: 'admin-photo' + (p.id === couverture ? ' est-couverture' : '') },
    el('img', { src: `/photos/${p.id}/mini`, alt: p.nom, loading: 'lazy' }),
    el('figcaption', {},
      el('span', { class: 'td-sous', title: p.nom }, `${p.nom} · ${taille(p.taille)}`),
      el('span', { class: 'admin-photo-actions' },
        p.id === couverture
          ? el('span', { class: 'pastille pastille-public' }, 'Couverture')
          : el('button', { class: 'lien-btn', onclick: () => definirCouverture(p.id) }, 'Couverture'),
        el('button', { class: 'lien-btn danger', onclick: () => supprimerPhoto(p) }, 'Supprimer'),
      ),
    ),
  )));
}

async function definirCouverture(photoId) {
  await api(`/api/admin/albums/${albumCourant.id}`, { method: 'PATCH', body: { couverture: photoId } });
  albumCourant.couverture_id = photoId;
  afficherPhotos();
}

async function supprimerPhoto(p) {
  if (!await confirmer('Supprimer cette photo ?', p.nom)) return;
  await api(`/api/admin/photos/${p.id}`, { method: 'DELETE' });
  albumCourant.photos = albumCourant.photos.filter(x => x.id !== p.id);
  if (albumCourant.couverture_id === p.id) albumCourant.couverture_id = null;
  afficherPhotos();
}

// ----- Envoi des photos (une par une, avec progression) -----
function envoyerUne(fichier, surProgres) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `/api/admin/albums/${albumCourant.id}/photos`);
    xhr.setRequestHeader('X-DCP', '1');
    xhr.upload.onprogress = e => e.lengthComputable && surProgres(e.loaded / e.total);
    xhr.onload = () => {
      let rep = null;
      try { rep = JSON.parse(xhr.responseText); } catch { /* vide */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(rep);
      else reject(new Error(rep?.erreur || `Erreur ${xhr.status}`));
    };
    xhr.onerror = () => reject(new Error('Connexion perdue'));
    const fd = new FormData();
    fd.append('photo', fichier);
    xhr.send(fd);
  });
}

async function envoyer(fichiers) {
  fichiers = [...fichiers];
  if (!fichiers.length || !albumCourant) return;
  const erreurs = [];
  $('envoi').hidden = false;
  $('depot').classList.add('occupe');
  for (let i = 0; i < fichiers.length; i++) {
    const f = fichiers[i];
    $('envoiTexte').textContent = `Envoi ${i + 1} / ${fichiers.length} : ${f.name}`;
    try {
      const photo = await envoyerUne(f, p => { $('envoiBarre').style.width = `${((i + p) / fichiers.length) * 100}%`; });
      albumCourant.photos.push(photo);
      afficherPhotos();
    } catch (err) {
      erreurs.push(`${f.name} : ${err.message}`);
    }
  }
  $('envoiBarre').style.width = '100%';
  $('envoiTexte').textContent = erreurs.length
    ? `Terminé, avec ${erreurs.length} erreur(s) — ${erreurs.join(' · ')}`
    : `${fichiers.length} photo(s) ajoutée(s) ✔`;
  $('depot').classList.remove('occupe');
  $('fichiers').value = '';
}

$('fichiers').addEventListener('change', e => envoyer(e.target.files));
const depot = $('depot');
['dragenter', 'dragover'].forEach(t => depot.addEventListener(t, e => { e.preventDefault(); depot.classList.add('survol'); }));
['dragleave', 'drop'].forEach(t => depot.addEventListener(t, () => depot.classList.remove('survol')));
depot.addEventListener('drop', e => { e.preventDefault(); envoyer(e.dataTransfer.files); });

// ----- Clients -----
async function afficherClients() {
  montrerVue('clients', 'Clients');
  const clients = await api('/api/admin/clients');
  const tbody = $('tableClients').querySelector('tbody');
  tbody.replaceChildren(...clients.map(c => el('tr', {},
    el('td', {}, c.nom),
    el('td', {}, c.email),
    el('td', {}, new Date(c.cree_le.replace(' ', 'T') + 'Z').toLocaleDateString('fr-FR')),
    el('td', {}, String(c.nbAlbums)),
    el('td', { class: 'td-actions' },
      el('button', { class: 'lien-btn', onclick: () => nouveauMdp(c) }, 'Nouveau mot de passe'),
      el('button', { class: 'lien-btn danger', onclick: () => supprimerClient(c) }, 'Supprimer'),
    ),
  )));
  $('tableClients').hidden = !clients.length;
  $('clientsVide').hidden = clients.length > 0;
}

async function nouveauMdp(c) {
  if (!await confirmer('Nouveau mot de passe ?',
    `Un mot de passe provisoire va être créé pour ${c.nom}. L'ancien ne marchera plus.`, 'Générer')) return;
  const { motDePasse } = await api(`/api/admin/clients/${c.id}/mot-de-passe`, { method: 'POST' });
  await confirmer('Mot de passe provisoire',
    `Transmets ce mot de passe à ${c.nom} (${c.email}) : ${motDePasse} — il pourra le changer depuis son espace.`, 'Fermer');
}

async function supprimerClient(c) {
  if (!await confirmer('Supprimer ce compte ?',
    `Le compte de ${c.nom} (${c.email}) sera supprimé. Ses shootings restent en ligne et il retrouvera l'accès s'il recrée un compte avec le même email.`)) return;
  await api(`/api/admin/clients/${c.id}`, { method: 'DELETE' });
  afficherClients();
}
