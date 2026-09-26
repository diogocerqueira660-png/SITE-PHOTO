// Connexion / création de compte client
const formConnexion = document.getElementById('formConnexion');
const formInscription = document.getElementById('formInscription');
const ongletConnexion = document.getElementById('ongletConnexion');
const ongletInscription = document.getElementById('ongletInscription');

function montrer(inscription) {
  formConnexion.hidden = inscription;
  formInscription.hidden = !inscription;
  ongletConnexion.classList.toggle('actif', !inscription);
  ongletInscription.classList.toggle('actif', inscription);
  ongletConnexion.setAttribute('aria-selected', !inscription);
  ongletInscription.setAttribute('aria-selected', inscription);
}
ongletConnexion.addEventListener('click', () => montrer(false));
ongletInscription.addEventListener('click', () => montrer(true));
if (location.hash === '#inscription') montrer(true);

// Déjà connecté : on va directement à son espace
moi.then(u => { if (u) location.replace(u.role === 'admin' ? 'admin.html' : 'espace.html'); });

// Après connexion, retour à la page d'où l'on venait (ex : un album privé)
function suite(role) {
  const retour = sessionStorage.getItem('retour');
  sessionStorage.removeItem('retour');
  location.href = retour || (role === 'admin' ? 'admin.html' : 'espace.html');
}

async function envoyer(form, url, erreurId) {
  const bouton = form.querySelector('button[type=submit]');
  const erreur = document.getElementById(erreurId);
  erreur.textContent = '';
  bouton.disabled = true;
  try {
    const r = await api(url, { method: 'POST', body: Object.fromEntries(new FormData(form)) });
    suite(r.role);
  } catch (err) {
    erreur.textContent = err.message;
    bouton.disabled = false;
  }
}

formConnexion.addEventListener('submit', e => {
  e.preventDefault();
  envoyer(formConnexion, '/api/connexion', 'erreurConnexion');
});
formInscription.addEventListener('submit', e => {
  e.preventDefault();
  envoyer(formInscription, '/api/inscription', 'erreurInscription');
});
