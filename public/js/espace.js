// Espace client : les shootings auxquels le client a accès
moi.then(async u => {
  if (!u) { location.replace('connexion.html'); return; }
  if (u.role === 'admin') { location.replace('admin.html'); return; }
  document.getElementById('bonjour').textContent = `Bonjour ${u.nom}`;
  document.getElementById('monEmail').textContent = u.email;

  const albums = await api('/api/mes-albums');
  const conteneur = document.getElementById('albums');
  albums.forEach((a, i) => conteneur.append(carteAlbum(a, i)));
  document.getElementById('vide').hidden = albums.length > 0;
});

document.getElementById('formMdp').addEventListener('submit', async e => {
  e.preventDefault();
  const erreur = document.getElementById('erreurMdp');
  erreur.textContent = '';
  try {
    await api('/api/moi/mot-de-passe', {
      method: 'POST',
      body: { actuel: document.getElementById('mdpActuel').value, nouveau: document.getElementById('mdpNouveau').value },
    });
    e.target.reset();
    erreur.textContent = 'Mot de passe modifié ✔';
  } catch (err) {
    erreur.textContent = err.message;
  }
});
