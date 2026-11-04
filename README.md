# Besoins en logement : base de données publique

Base de données du projet « Besoins en logement » de Procivis. Elle réunit les données publiques utiles pour comprendre les besoins en logement en France, ramenées à une même géographie (les 34 875 communes au 1er janvier 2026) et additionnées à six niveaux : France, régions, départements, zones d'emploi, EPCI, territoires d'industrie.

## Ce qu'elle contient

Plus de 2 400 indicateurs répartis en 13 thèmes :

| Thème | Exemples |
|---|---|
| Territoire et zonages | zonage ABC, densité, aires d'attraction des villes, dispositifs de l'ANCT, QPV, zones tendues |
| Population | âges, évolution depuis 1968, naissances et décès, migrations résidentielles |
| Ménages et familles | ménages par type, taille et âge de la personne de référence, familles |
| Profils de ménages | jeunes actifs seuls, couples, familles, familles monoparentales, seniors, grand âge, étudiants |
| Logement (parc existant) | résidences principales, secondaires, vacantes, statut d'occupation, taille, ancienneté, logement social, vacance du parc privé, copropriétés |
| Construction neuve | logements autorisés et commencés depuis 2012, par type |
| Besoins en logement | besoin par décennie jusqu'en 2050 (méthode du SDES, hypothèses de la CERC Auvergne-Rhône-Alpes), comparaison à la construction actuelle |
| Marché et prix | prix au m2 et nombre de ventes, loyers d'annonce, prêts à taux zéro |
| Revenus et aides | niveau de vie, pauvreté, revenus fiscaux, allocataires de la CAF |
| Emploi et activité | actifs, chômage, emploi salarié privé depuis 2015, déplacements domicile-travail |
| Entreprises et salaires | établissements et effectifs par secteur, créations d'entreprises, salaires |
| Équipements et services | équipements, accès aux médecins, accueil du jeune enfant, gares, hébergements touristiques |
| Risques, climat et énergie | catastrophes naturelles, recul du trait de côte, zones climatiques, diagnostics énergétiques, consommation d'énergie |

Chaque indicateur est défini dans `docs/data/dictionnaire.csv` (définition, unité, année, source, adresse, licence). Les sources repérées par le projet, intégrées ou non, sont dans `docs/data/sources.csv`.

## Consulter

La page de consultation (dossier `docs`, publiée par GitHub Pages) permet de choisir un thème, un niveau, des territoires et des indicateurs, puis d'exporter la sélection en Excel ou en CSV. Chaque thème complet se télécharge aussi en CSV (`docs/data/csv`) ou en Parquet. Les fichiers de `docs/data` (format Parquet) se lisent aussi avec Python, R ou DuckDB.

## Comment les sources sont collectées

Chaque source a son script dans `pipeline/sources/`. Le fichier `COLLECTE.md`, régénéré à chaque exécution, dit pour chaque source d'où viennent les données (page et adresse de téléchargement), quel millésime est utilisé, ce que fait le script et combien d'indicateurs il produit.

## Mise à jour

Un robot (GitHub Actions) relance tous les scripts le 3 de chaque mois et reconstruit la base. Il ne publie la nouvelle version que si toutes les sources ont réussi et qu'aucun indicateur déjà publié n'a disparu ; sinon la base en ligne ne change pas et l'exécution apparaît en échec dans l'onglet Actions, avec le détail par source. Le compte rendu de la dernière exécution est dans `docs/data/derniere_execution.json`.

Limite actuelle : la plupart des scripts visent une édition précise de leur source (indiquée dans `COLLECTE.md`). Une nouvelle édition (nouveau recensement, nouveau fichier LOVAC, nouvel inventaire SRU...) demande d'adapter le script.

## Sources et licence

Données publiques diffusées sous Licence ouverte 2.0 (Etalab) ou équivalente, réutilisées en citant la source : Insee, SDES (ministère chargé du logement), DGFiP, DGALN, Cerema, ANCT, ANIL, Urssaf, Cnaf, DARES, DREES, SNCF, Agence ORE, ADEME, Géorisques. Le détail par indicateur est dans le dictionnaire.

## Limites

Les valeurs à la commune sont des ordres de grandeur pour les petits territoires (secret statistique, estimations du recensement, répartitions de valeurs calculées à la zone d'emploi). Les limites propres à chaque source sont indiquées dans les définitions.
