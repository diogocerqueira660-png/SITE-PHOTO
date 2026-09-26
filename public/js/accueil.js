// Portfolio public : les shootings marqués « public » par l'admin
api('/api/albums').then(albums => {
  const conteneur = document.getElementById('albums');
  albums.forEach((a, i) => conteneur.append(carteAlbum(a, i)));
  document.getElementById('vide').hidden = albums.length > 0;
}).catch(() => {
  document.getElementById('vide').hidden = false;
});
