/*
 * ============================================
 *  LISTE DE TES PHOTOS
 * ============================================
 *  Pour ajouter une photo :
 *   1. Mets le fichier dans le dossier  images/photos/
 *   2. Ajoute une ligne ci-dessous avec :
 *        src       → chemin du fichier
 *        titre     → nom affiché (ex : la voiture)
 *        categorie → sert aux filtres de la galerie (crée-en autant que tu veux)
 *        lieu      → optionnel, affiché dans la légende en grand
 *
 *  Les photos "placeholder-X.svg" sont des exemples : supprime-les
 *  quand tu as mis tes vraies photos.
 */
const PHOTOS = [
  { src: "images/photos/placeholder-1.svg", titre: "Porsche 911 GT3",      categorie: "Sportives",  lieu: "Circuit" },
  { src: "images/photos/placeholder-2.svg", titre: "Nissan Skyline R34",   categorie: "JDM",        lieu: "Parking de nuit" },
  { src: "images/photos/placeholder-3.svg", titre: "Ferrari F40",          categorie: "Supercars",  lieu: "Salon" },
  { src: "images/photos/placeholder-4.svg", titre: "BMW M3 E30",           categorie: "Youngtimers", lieu: "Route de montagne" },
  { src: "images/photos/placeholder-5.svg", titre: "Lamborghini Huracán",  categorie: "Supercars",  lieu: "Rolling shot" },
  { src: "images/photos/placeholder-6.svg", titre: "Toyota Supra MK4",     categorie: "JDM",        lieu: "Meeting" },
  { src: "images/photos/placeholder-7.svg", titre: "Alpine A110",          categorie: "Sportives",  lieu: "Col alpin" },
  { src: "images/photos/placeholder-8.svg", titre: "Peugeot 205 GTI",      categorie: "Youngtimers", lieu: "Rassemblement" },
  { src: "images/photos/placeholder-9.svg", titre: "McLaren 720S",         categorie: "Supercars",  lieu: "Studio" },
];
