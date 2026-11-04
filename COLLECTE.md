# Comment chaque source est collectée et mise à jour

Ce fichier est produit automatiquement à chaque exécution (`pipeline/collecte.py`), à partir des scripts et de leurs sorties.

## Collecte

Chaque source a son propre script dans `pipeline/sources/`. Le script télécharge les données à l'adresse indiquée plus bas, les ramène aux communes au 1er janvier 2026 (communes fusionnées ou scindées comprises), calcule les indicateurs et documente chacun (libellé, définition, unité, année, source). L'assemblage (`pipeline/assembler.py`) calcule ensuite les six autres niveaux : France, régions, départements, zones d'emploi, EPCI, territoires d'industrie. Les règles que respecte chaque script sont dans `pipeline/CONTRAT_SOURCES.md`.

## Mise à jour

Le robot (GitHub Actions) relance tous les scripts le 3 de chaque mois, ou à la demande depuis l'onglet Actions du dépôt. Les scripts retéléchargent les sources, puis la base est reconstruite. Le robot ne publie la nouvelle version que si toutes les sources ont réussi et qu'aucun indicateur déjà publié n'a disparu. Sinon, la base en ligne reste telle quelle et l'exécution apparaît en échec dans l'onglet Actions, avec le détail par source. Le compte rendu de la dernière exécution publiée est dans `docs/data/derniere_execution.json` ; chaque mise à jour publiée est un commit de l'historique du dépôt.

Limite actuelle : la plupart des scripts visent une édition précise de leur source (ligne « Millésime »). Tant que le script n'est pas modifié, il retélécharge cette même édition. Quand le producteur publie une nouvelle édition (nouveau recensement, nouveau fichier LOVAC, nouvel inventaire SRU...), il faut adapter le script. Les sources diffusées en continu (diagnostics de performance énergétique, statistiques DVF, arrêtés de catastrophe naturelle, référentiel des gares) sont relues à chaque exécution.

## Les sources

35 scripts, 2442 indicateurs produits par les scripts (la base en compte un peu plus : les synthèses du besoin en logements sont calculées à l'assemblage).

| Script | Source | Producteur | Indicateurs |
|---|---|---|---|
| [aav](#aav) | Base des aires d'attraction des villes 2020, base des unités urbaines 2020 et base des bassins de vie 2022 | Insee | 29 |
| [accueil_enfant](#accueil_enfant) | Taux de couverture d'accueil du jeune enfant (communes de plus de 10 000 habitants, EPCI, départements, régions, France) | Caisse nationale des allocations familiales (Cnaf), Observatoire national de la petite enfance | 6 |
| [apl](#apl) | Accessibilité potentielle localisée (APL) aux médecins généralistes | DREES (données Cnam SNDS et Insee) | 6 |
| [besoins_sdes](#besoins_sdes) | Besoins en logements à horizon 2030, 2040 et 2050 - fichiers de données (SDES, juin 2025) | SDES | 20 |
| [caf](#caf) | Cafdata : allocataires par prestation (s_ben_com_f) et bénéficiaires d'une aide au logement selon le type de parc (al_s_type_parc_com_f), par commune | Caisse nationale des allocations familiales (Cnaf) | 21 |
| [catnat](#catnat) | Base GASPAR (Géorisques) : arrêtés de reconnaissance de l état de catastrophe naturelle | Ministère de la Transition écologique (DGPR), diffusion Géorisques (BRGM) | 8 |
| [copro](#copro) | CoproFF - données agrégées du référentiel national des copropriétés | Anah et Cerema (Fichiers fonciers et registre national des copropriétés) | 17 |
| [densite](#densite) | Grille communale de densité 2025 (fichier en géographie 2026) | Insee | 22 |
| [dispositifs_anct](#dispositifs_anct) | Croisement des dispositifs de politique publique de l'ANCT ; liste des communes couvertes par des opérations de revitalisation de territoire | Agence nationale de la cohésion des territoires (ANCT) ; ministère de la Cohésion des territoires (DGALN) pour les ORT | 13 |
| [dpe](#dpe) | Observatoire DPE-Audit : DPE des logements existants (depuis juillet 2021), nombre de DPE par étiquette énergie et par commune | ADEME (observatoire DPE-Audit) | 10 |
| [dvf_stats](#dvf_stats) | Statistiques DVF - prix au m2 et nombre de ventes | data.gouv.fr (Etalab) à partir de DVF (DGFiP) | 20 |
| [economie_insee](#economie_insee) | Flores, établissements et effectifs salariés en 17 secteurs (fin 2024) ; créations d'entreprises et d'établissements (Sidé, 2012-2025) ; salaires du secteur privé (Base tous salariés 2023-2024) ; autres fiches : E7-11, E6-16 | Insee | 487 |
| [energie_conso](#energie_conso) | Consommation annuelle d'électricité et de gaz par commune (secteur résidentiel) | Agence ORE (Opérateurs de réseaux d'énergie : Enedis, GRDF et distributeurs locaux) | 6 |
| [equipements_insee](#equipements_insee) | Base permanente des équipements (BPE) 2025, dénombrement des équipements ; capacités d'hébergements touristiques 2026 (autre fiche : E4-22) | Insee | 324 |
| [filosofi](#filosofi) | Indicateurs sur les revenus et la pauvreté au niveau local en 2023 (Filosofi) ; niveau de vie médian et taux de pauvreté par âge, sexe et statut d'occupation du logement | Insee (Filosofi : Insee, DGFiP, Cnaf, Cnav, CCMSA) | 52 |
| [france_travail](#france_travail) | Inscrits à France Travail, données communales trimestrielles brutes | Dares et France Travail (statistique mensuelle du marché du travail) | 9 |
| [gares](#gares) | Gares de voyageurs (référentiel SNCF) et fréquentation en gares | SNCF Gares & Connexions | 6 |
| [ircom](#ircom) | L'impôt sur le revenu par collectivité territoriale (IRCOM) | DGFiP (Département des études et statistiques fiscales) | 22 |
| [lovac](#lovac) | LOVAC - logements vacants du parc privé par commune | DGALN, Cerema (données DGFiP 1767 bis Com et Fichiers fonciers) | 12 |
| [loyers](#loyers) | Carte des loyers - indicateurs de loyers d'annonce par commune en 2025 | ANIL et DGALN (annonces leboncoin et SeLoger) | 14 |
| [ptz](#ptz) | Base de données PTZ (prêts à taux zéro) | Ministère chargé du logement (données SGFGAS) | 25 |
| [qpv](#qpv) | Quartiers prioritaires de la politique de la ville 2024 (liste) | Agence nationale de la cohésion des territoires (ANCT) | 2 |
| [rp_emploi](#rp_emploi) | Recensement de la population 2023 (dossier complet) : population active et chômage, emploi au lieu de travail, caractéristiques de l'emploi, diplômes, scolarisation, déplacements domicile-travail ; autres fiches : E4-18, P2-001 | Insee | 309 |
| [rp_logement](#rp_logement) | Recensement de la population 2023 : logements (dossier complet), indice de peuplement, résidences principales selon l'âge de la personne de référence (tableaux PRINC) ; autres fiches : E6-10, E6-11, E7-55 | Insee | 245 |
| [rp_menages](#rp_menages) | Recensement de la population 2023 : ménages, familles, tableaux détaillés MEN4, MEN5 et MEN6 (base Couples, familles, ménages) ; autres fiches : E6-13, E6-15, E7-55, P2-001 | Insee | 418 |
| [rp_population](#rp_population) | Recensement de la population 2023 (dossier complet : population, migrations résidentielles), populations historiques 1968-2023, état civil 2008-2025 (naissances, décès) ; autres fiches : E3-23, E6-14, E6-17, P2-001 | Insee | 176 |
| [rpls](#rpls) | Répertoire des logements locatifs des bailleurs sociaux (RPLS), données détaillées au logement agrégées à la commune | SDES (ministère chargé du logement) | 20 |
| [sitadel](#sitadel) | Sit@del2 - logements autorisés et commencés (séries annuelles communales en date réelle ; séries mensuelles départementales estimées) | SDES | 60 |
| [sru](#sru) | Communes et inventaire SRU | DGALN (ministère chargé du logement) | 10 |
| [thrs](#thrs) | Délibérations de fiscalité directe locale des communes 2026 (hors taux) | Direction générale des finances publiques (DGFiP), ministères économiques et financiers | 3 |
| [trait_de_cote](#trait_de_cote) | Liste des communes dont l'action en matière d'urbanisme doit être adaptée au recul du trait de côte (art. L. 321-15 du code de l'environnement) | Ministère de la Transition écologique | 2 |
| [urssaf](#urssaf) | Nombre d'établissements employeurs et effectifs salariés du secteur privé, par commune et code APE (au 31 décembre depuis 2006) | Urssaf Caisse nationale | 45 |
| [zonage_abc](#zonage_abc) | Liste des communes selon le zonage ABC | Ministère chargé du logement (DGALN), publié par le ministère de la Transition écologique | 6 |
| [zone_climatique](#zone_climatique) | Zones climatiques réglementaires (RE2020 et méthode DPE) par département | Ministère chargé de la construction (DHUP) ; table département - zone déduite par le projet de la base des DPE de l'ADEME | 10 |
| [zones_tendues](#zones_tendues) | Communes en zone tendue (taxe sur les logements vacants) et communes à encadrement des loyers | Premier ministre (DILA) : données de référence du simulateur « zones tendues » de service-public.fr, reprenant les deux listes du décret n° 2013-392 modifié ; Naistor : compilation, commune par commune, des décrets de périmètre et des arrêtés préfectoraux d'encadrement des loyers (aucune liste officielle en données ouvertes) | 7 |

### aav

**Base des aires d'attraction des villes 2020, base des unités urbaines 2020 et base des bassins de vie 2022**

- Producteur : Insee
- Référence dans le catalogue des sources du projet : E2-08 ; E2-09
- Page de la source : https://www.insee.fr/fr/information/4803954 ; https://www.insee.fr/fr/information/4802589 ; https://www.insee.fr/fr/information/6676988
- Adresse de téléchargement utilisée : https://www.insee.fr/fr/statistiques/fichier/4803954/AAV2020_au_01-01-2026.zip ; https://www.insee.fr/fr/statistiques/fichier/4802589/UU2020_au_01-01-2026.zip ; https://www.insee.fr/fr/statistiques/fichier/6676988/BV2022_au_01-01-2026.zip
- Millésime : Zonages AAV 2020, UU 2020 et BV 2022 en géographie au 1er janvier 2026 (mise en ligne le 19 mars 2026) ; tranches de taille calculées sur la population 2017
- Licence : Licence ouverte 2.0
- Thèmes de la base : territoire (29 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Zonages d'étude de l'Insee par commune : aires d'attraction des villes 2020, unités urbaines 2020 et bassins de vie 2022 (géographie 2026).
- Script : [`pipeline/sources/aav.py`](pipeline/sources/aav.py)

### accueil_enfant

**Taux de couverture d'accueil du jeune enfant (communes de plus de 10 000 habitants, EPCI, départements, régions, France)**

- Producteur : Caisse nationale des allocations familiales (Cnaf), Observatoire national de la petite enfance
- Référence dans le catalogue des sources du projet : E7-18
- Page de la source : https://www.data.gouv.fr/datasets/taux-de-couverture-daccueil-du-jeune-enfant-communal
- Adresse de téléchargement utilisée : https://data.caf.fr/api/explore/v2.1/catalog/datasets/txcouv_pe_com/exports/csv?delimiter=%3B ; https://data.caf.fr/api/explore/v2.1/catalog/datasets/txcouv_pe_epci/exports/csv?delimiter=%3B ; https://data.caf.fr/api/explore/v2.1/catalog/datasets/txcouv_pe_dep/exports/csv?delimiter=%3B ; https://data.caf.fr/api/explore/v2.1/catalog/datasets/txcouv_pe_reg/exports/csv?delimiter=%3B ; https://data.caf.fr/api/explore/v2.1/catalog/datasets/txcouv_pe_nat/exports/csv?delimiter=%3B
- Millésime : 2023 (offre théorique en décembre 2023)
- Licence : Licence ouverte 2.0
- Thèmes de la base : equipements (6 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Taux de couverture de l'accueil du jeune enfant (Cnaf) : places d'accueil formel pour 100 enfants de moins de 3 ans, communes de plus de 10 000 habitants, EPCI, départements, régions et France.
- Script : [`pipeline/sources/accueil_enfant.py`](pipeline/sources/accueil_enfant.py)

### apl

**Accessibilité potentielle localisée (APL) aux médecins généralistes**

- Producteur : DREES (données Cnam SNDS et Insee)
- Référence dans le catalogue des sources du projet : E7-15
- Page de la source : https://data.drees.solidarites-sante.gouv.fr/explore/dataset/530_l-accessibilite-potentielle-localisee-apl/
- Adresse de téléchargement utilisée : https://data.drees.solidarites-sante.gouv.fr/api/explore/v2.1/catalog/datasets/530_l-accessibilite-potentielle-localisee-apl/attachments/indicateur_d_apl_aux_medecins_generalistes_xlsx
- Millésime : APL 2024 (activité des médecins 2024, populations municipales 2022), feuille « APL 2024 »
- Licence : Licence ouverte 2.0
- Thèmes de la base : equipements (6 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Accessibilité potentielle localisée (APL) aux médecins généralistes par commune (DREES) : offre de consultations accessible par habitant.
- Script : [`pipeline/sources/apl.py`](pipeline/sources/apl.py)

### besoins_sdes

**Besoins en logements à horizon 2030, 2040 et 2050 - fichiers de données (SDES, juin 2025)**

- Producteur : SDES
- Référence dans le catalogue des sources du projet : P2-056
- Page de la source : https://www.statistiques.developpement-durable.gouv.fr/besoins-en-logements-horizon-2030-2040-et-2050
- Adresse de téléchargement utilisée : https://www.statistiques.developpement-durable.gouv.fr/media/8509/download?inline ; 8510 ; 8511 ; 8512 ; 8477
- Millésime : Juin 2025
- Licence : Licence ouverte 2.0
- Thèmes de la base : besoins (20 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Bloc 1 : besoin en logements par commune (méthode SDES juin 2025, scénario haut, hypothèses de la CERC AURA, sans l'industrie). Composantes calculées par le SDES à la zone d'emploi, réparties entre les communes (clés : résidences principales, résidences secondaires, logements vacants du recensement 2023 ; renouvellement au prorata du besoin lié aux ménages 2020-2050).
- Script : [`pipeline/sources/besoins_sdes.py`](pipeline/sources/besoins_sdes.py)

### caf

**Cafdata : allocataires par prestation (s_ben_com_f) et bénéficiaires d'une aide au logement selon le type de parc (al_s_type_parc_com_f), par commune**

- Producteur : Caisse nationale des allocations familiales (Cnaf)
- Référence dans le catalogue des sources du projet : E6-30, E6-31
- Page de la source : https://data.caf.fr/explore/dataset/s_ben_com_f/ ; https://data.caf.fr/explore/dataset/al_s_type_parc_com_f/
- Adresse de téléchargement utilisée : https://data.caf.fr/api/explore/v2.1/catalog/datasets/s_ben_com_f/exports/csv?where=dtreffre%3Ddate%272024-12-01%27&delimiter=%3B ; https://data.caf.fr/api/explore/v2.1/catalog/datasets/al_s_type_parc_com_f/exports/csv?where=dtreffre%3Ddate%272024-12-01%27&delimiter=%3B
- Millésime : décembre 2024 (géographie au 1er janvier 2025)
- Licence : Licence ouverte 2.0
- Thèmes de la base : revenus (21 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Allocataires des CAF par commune (Cafdata) : foyers allocataires, aides au logement par type de parc, RSA, prime d'activité, prestations familiales.
- Script : [`pipeline/sources/caf.py`](pipeline/sources/caf.py)

### catnat

**Base GASPAR (Géorisques) : arrêtés de reconnaissance de l état de catastrophe naturelle**

- Producteur : Ministère de la Transition écologique (DGPR), diffusion Géorisques (BRGM)
- Référence dans le catalogue des sources du projet : P2-069
- Page de la source : https://www.data.gouv.fr/datasets/base-nationale-de-gestion-assistee-des-procedures-administratives-relatives-aux-risques-gaspar
- Adresse de téléchargement utilisée : https://files.georisques.fr/GASPAR/gaspar.zip
- Millésime : Export quotidien GASPAR (fichier catnat_gaspar) ; arrêtés publiés au Journal officiel du 21 septembre 1982 à fin janvier 2026
- Licence : Licence ouverte 2.0
- Thèmes de la base : risques_energie (8 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Reconnaissances de l'état de catastrophe naturelle (arrêtés CatNat) par commune depuis 1982, d'après la base GASPAR de Géorisques.
- Script : [`pipeline/sources/catnat.py`](pipeline/sources/catnat.py)

### copro

**CoproFF - données agrégées du référentiel national des copropriétés**

- Producteur : Anah et Cerema (Fichiers fonciers et registre national des copropriétés)
- Référence dans le catalogue des sources du projet : E7-45
- Page de la source : https://www.data.gouv.fr/datasets/donnees-agregees-du-referentiel-national-des-coproprietes-coproff
- Adresse de téléchargement utilisée : https://static.data.gouv.fr/resources/donnees-agregees-du-referentiel-national-des-coproprietes-coproff/20261030-102306/tableau-synthetique-coproff-com-2025.csv
- Millésime : CoproFF 2025 (publié en octobre 2026)
- Licence : Licence ouverte 2.0
- Thèmes de la base : logement (17 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : CoproFF (Anah, Cerema) : nombre de copropriétés et de logements en copropriété par commune, par taille, période de construction et type de syndic, et taux d'immatriculation.
- Script : [`pipeline/sources/copro.py`](pipeline/sources/copro.py)

### densite

**Grille communale de densité 2025 (fichier en géographie 2026)**

- Producteur : Insee
- Référence dans le catalogue des sources du projet : E7-62
- Page de la source : https://www.insee.fr/fr/information/8571524
- Adresse de téléchargement utilisée : https://www.insee.fr/fr/statistiques/fichier/8571524/fichier_diffusion_2026.xlsx
- Millésime : Grille de densité 2025, géographie au 1er janvier 2026, population municipale 2023 (mise en ligne le 15 mai 2026)
- Licence : Licence ouverte 2.0
- Thèmes de la base : territoire (22 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Grille communale de densité de l'Insee (édition 2025, géographie 2026) : niveaux à 3 et 7 postes, croisement avec les aires d'attraction, population par niveau.
- Script : [`pipeline/sources/densite.py`](pipeline/sources/densite.py)

### dispositifs_anct

**Croisement des dispositifs de politique publique de l'ANCT ; liste des communes couvertes par des opérations de revitalisation de territoire**

- Producteur : Agence nationale de la cohésion des territoires (ANCT) ; ministère de la Cohésion des territoires (DGALN) pour les ORT
- Référence dans le catalogue des sources du projet : E7-31
- Page de la source : https://www.data.gouv.fr/datasets/croisement-des-dispositifs-de-politique-publique-de-lanct ; https://www.data.gouv.fr/datasets/liste-des-communes-couvertes-par-des-operations-de-revitalisation-de-territoire
- Adresse de téléchargement utilisée : https://static.data.gouv.fr/resources/croisement-des-dispositifs-de-politique-publique-de-lanct/20260413-100516/ngeo-anct-cog2025.csv ; https://grist.numerique.gouv.fr/o/dgaln/api/docs/j4i9oKD3jzFtgEUuM9sXnL/download/csv?tableId=BDD
- Millésime : Croisement ANCT mis en ligne le 13 avril 2026 (code géographique 2025, dispositifs mis à jour entre juillet 2024 et septembre 2025) ; suivi des ORT tenu à jour en continu (téléchargé en novembre 2026)
- Licence : Licence ouverte 2.0
- Thèmes de la base : territoire (13 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Programmes de politique publique de l'ANCT par commune (Action coeur de ville, Petites villes de demain, Villages d'avenir, etc.) et opérations de revitalisation de territoire (ORT).
- Script : [`pipeline/sources/dispositifs_anct.py`](pipeline/sources/dispositifs_anct.py)

### dpe

**Observatoire DPE-Audit : DPE des logements existants (depuis juillet 2021), nombre de DPE par étiquette énergie et par commune**

- Producteur : ADEME (observatoire DPE-Audit)
- Référence dans le catalogue des sources du projet : P2-024
- Page de la source : https://data.ademe.fr/datasets/dpe03existant
- Adresse de téléchargement utilisée : https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant/values_agg?field=code_insee_ban%3Betiquette_dpe&agg_size=1000%3B10&size=0&qs=code_departement_ban%3A%22%7Bcode_departement%7D%22 (API d'agrégation data-fair, une requête par département)
- Millésime : DPE établis du 1er juillet 2021 à l'extraction du 2026-11-02
- Licence : Licence ouverte 2.0
- Thèmes de la base : risques_energie (10 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Diagnostics de performance énergétique des logements existants par commune (ADEME, observatoire DPE-Audit) : nombre de DPE par étiquette énergie A à G.
- Script : [`pipeline/sources/dpe.py`](pipeline/sources/dpe.py)

### dvf_stats

**Statistiques DVF - prix au m2 et nombre de ventes**

- Producteur : data.gouv.fr (Etalab) à partir de DVF (DGFiP)
- Référence dans le catalogue des sources du projet : E7-50
- Page de la source : https://www.data.gouv.fr/datasets/statistiques-dvf
- Adresse de téléchargement utilisée : https://data-pipeline-open.s3.sbg.io.cloud.ovh.net/dvf/stats_dvf.csv ; https://data-pipeline-open.s3.sbg.io.cloud.ovh.net/dvf/stats_whole_period.csv
- Millésime : octobre 2026 (ventes de juillet 2021 à juin 2026)
- Licence : Licence ouverte 2.0
- Thèmes de la base : marche (20 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Statistiques DVF : nombre de ventes et prix au m2 des maisons et des appartements par commune et par année (avec valeurs publiées pour les EPCI, les départements et la France).
- Script : [`pipeline/sources/dvf_stats.py`](pipeline/sources/dvf_stats.py)

### economie_insee

**Flores, établissements et effectifs salariés en 17 secteurs (fin 2024) ; créations d'entreprises et d'établissements (Sidé, 2012-2025) ; salaires du secteur privé (Base tous salariés 2023-2024) ; autres fiches : E7-11, E6-16**

- Producteur : Insee
- Référence dans le catalogue des sources du projet : E7-02
- Page de la source : https://catalogue-donnees.insee.fr/fr/catalogue/recherche/DS_FLORES_A17
- Adresse de téléchargement utilisée : https://api.insee.fr/melodi/file/DS_FLORES_A17/DS_FLORES_A17_2024_CSV_FR ; https://api.insee.fr/melodi/file/DS_SIDE_CREA_COM/DS_SIDE_CREA_COM_2025_CSV_FR ; https://api.insee.fr/melodi/file/DS_BTS_SAL_EQTP_SEX_AGE/DS_BTS_SAL_EQTP_SEX_AGE_2024_CSV_FR
- Millésime : Flores fin 2024 ; créations 2012 à 2025 ; salaires 2023 et 2024
- Licence : Licence ouverte 2.0
- Thèmes de la base : economie (487 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Tissu économique des communes : établissements employeurs et salariés par secteur et taille (Flores fin 2024), créations d'entreprises et d'établissements (2012-2025), salaires nets moyens du secteur privé au lieu de travail (2023-2024) ; Insee, Melodi (DS_FLORES_A17, DS_SIDE_CREA_COM, DS_BTS_SAL_EQTP_SEX_AGE). Règles : dernière année de chaque série ; années antérieures seulement pour les totaux (créations 2012-2024, salaire moyen 2023) ; au plus deux dimensions hors total (Flores : secteur x tranche d'effectifs, 342 colonnes, sous le seuil de 400). Le salaire moyen est non additif : valeurs publiées par l'Insee pour les EPCI, départements, régions, zones d'emploi et la France, moyenne pondérée par les effectifs salariés Flores (flores_sal_2024) ailleurs ; il est soumis au secret statistique dans la plupart des petites communes. Pour DS_SIDE_CREA_COM (49 millions de lignes), seules la dernière année et, pour les années antérieures, les lignes au total sont lues.
- Script : [`pipeline/sources/economie_insee.py`](pipeline/sources/economie_insee.py)

### energie_conso

**Consommation annuelle d'électricité et de gaz par commune (secteur résidentiel)**

- Producteur : Agence ORE (Opérateurs de réseaux d'énergie : Enedis, GRDF et distributeurs locaux)
- Référence dans le catalogue des sources du projet : E7-46
- Page de la source : https://opendata.agenceore.fr/datasets/noxwlxv702-ohfyt76f-a3y9
- Adresse de téléchargement utilisée : https://opendata.agenceore.fr/data-fair/api/v1/datasets/noxwlxv702-ohfyt76f-a3y9/lines?qs=annee%3A2025+AND+code_categorie_consommation%3ARES&size=10000&select=operateur%2Cfiliere%2Cannee%2Ccode_commune%2Cnb_sites%2Cconso_totale_mwh%2Cnombre_de_mailles_secretisees
- Millésime : 2025 (mise à jour du 30 octobre 2026)
- Licence : Licence ouverte 2.0
- Thèmes de la base : risques_energie (6 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Consommation résidentielle d'électricité et de gaz par commune (Agence ORE) : consommation annuelle et nombre de points de livraison des logements.
- Script : [`pipeline/sources/energie_conso.py`](pipeline/sources/energie_conso.py)

### equipements_insee

**Base permanente des équipements (BPE) 2025, dénombrement des équipements ; capacités d'hébergements touristiques 2026 (autre fiche : E4-22)**

- Producteur : Insee
- Référence dans le catalogue des sources du projet : E7-13
- Page de la source : https://catalogue-donnees.insee.fr/fr/catalogue/recherche/DS_BPE
- Adresse de téléchargement utilisée : https://api.insee.fr/melodi/file/DS_BPE/DS_BPE_2025_CSV_FR ; https://api.insee.fr/melodi/file/DS_TOUR_CAP/DS_TOUR_CAP_2026_CSV_FR
- Millésime : BPE au 1er janvier 2025 ; hébergements touristiques au 1er janvier 2026
- Licence : Licence ouverte 2.0
- Thèmes de la base : equipements (324 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Équipements et services des communes (Base permanente des équipements au 1er janvier 2025) et capacités d'hébergement touristique au 1er janvier 2026 ; Insee, Melodi (DS_BPE, DS_TOUR_CAP). BPE : domaines, sous-domaines et types d'équipement sont emboîtés et comptent pour une seule dimension ; chaque type d'équipement (235), sous-domaine (27) et domaine (7) donne une colonne, plus le total (270 colonnes). Tourisme : le type d'hébergement n'a pas de total (hôtels, campings, autres hébergements collectifs) et fait partie de la mesure ; sont gardés les croisements avec le classement en étoiles et, pour les campings, la nature des emplacements (à l'année ou de passage). Tous les indicateurs sont des effectifs (somme).
- Script : [`pipeline/sources/equipements_insee.py`](pipeline/sources/equipements_insee.py)

### filosofi

**Indicateurs sur les revenus et la pauvreté au niveau local en 2023 (Filosofi) ; niveau de vie médian et taux de pauvreté par âge, sexe et statut d'occupation du logement**

- Producteur : Insee (Filosofi : Insee, DGFiP, Cnaf, Cnav, CCMSA)
- Référence dans le catalogue des sources du projet : P2-021
- Page de la source : https://catalogue-donnees.insee.fr/fr/catalogue/recherche/DS_FILOSOFI_CC
- Adresse de téléchargement utilisée : https://api.insee.fr/melodi/file/DS_FILOSOFI_CC/DS_FILOSOFI_CC_2023_CSV_FR ; https://api.insee.fr/melodi/file/DS_FILOSOFI_SAGE_LOG_TP_NIVVIE/DS_FILOSOFI_SAGE_LOG_TP_NIVVIE_2023_CSV_FR
- Millésime : Revenus 2023
- Licence : Licence ouverte 2.0
- Thèmes de la base : revenus (52 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Niveaux de vie, pauvreté et composition du revenu disponible en 2023 (Insee, Filosofi, jeux Melodi DS_FILOSOFI_CC et DS_FILOSOFI_SAGE_LOG_TP_NIVVIE). Tous les indicateurs sont non additifs (médianes, déciles, taux, parts, indices) : la base reprend les valeurs publiées par l'Insee pour les EPCI, départements, régions, zones d'emploi et la France ('publies'), et à défaut une moyenne pondérée par la population du recensement 2023 (colonne filo_poids_pop_2023, reprise de DS_RP_POPULATION_PRINC). À la commune, le secret statistique limite fortement la diffusion : le niveau de vie médian est publié pour environ 30 800 communes et le taux de pauvreté pour environ 5 200 (avec des valeurs publiées pour les EPCI et zones d'emploi) ; les déciles, quartiles, indices d'inégalité et la composition du revenu ne sont publiés dans ce jeu que pour les départements, les régions et la France (colonnes vides à la commune). La définition de chaque colonne précise le nombre de communes renseignées et les niveaux publiés. DS_FILOSOFI_SAGE_LOG_TP_NIVVIE (niveau de vie médian et taux de pauvreté par âge, sexe et statut d'occupation du logement) n'existe que pour les départements, les régions et la France métropolitaine : colonnes vides à la commune, valeurs publiées aux niveaux DEP, REG et FRANCE. Pour ces deux jeux, la valeur « France » publiée est celle de la France métropolitaine (pas de valeur France entière dans Melodi).
- Script : [`pipeline/sources/filosofi.py`](pipeline/sources/filosofi.py)

### france_travail

**Inscrits à France Travail, données communales trimestrielles brutes**

- Producteur : Dares et France Travail (statistique mensuelle du marché du travail)
- Référence dans le catalogue des sources du projet : E6-34
- Page de la source : https://www.data.gouv.fr/datasets/inscrits-a-france-travail-donnees-communales-trimestrielles-brutes
- Adresse de téléchargement utilisée : https://data.dares.travail-emploi.gouv.fr/api/explore/v2.1/catalog/datasets/dares_defm_communales-brutes/exports/csv?select=date%2Ccode_commune%2Ccategorie%2Csexe%2Ctranche_d_age%2Cnombre_de_demandeurs_d_emploi&where=date%3D%272024-T4%27+or+%28date%3D%272023-T4%27+and+sexe%3D%27Total%27+and+tranche_d_age%3D%27Total%27%29&delimiter=%3B
- Millésime : 4e trimestre 2024 et 4e trimestre 2023 (moyennes trimestrielles, géographie 2024, mise à jour octobre 2026)
- Licence : Licence ouverte 2.0
- Thèmes de la base : emploi (9 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Demandeurs d'emploi inscrits à France Travail par commune (Dares) : catégories A, B, C au 4e trimestre 2024 et 2023, par sexe et âge.
- Script : [`pipeline/sources/france_travail.py`](pipeline/sources/france_travail.py)

### gares

**Gares de voyageurs (référentiel SNCF) et fréquentation en gares**

- Producteur : SNCF Gares & Connexions
- Référence dans le catalogue des sources du projet : E7-23, E7-22
- Page de la source : https://ressources.data.sncf.com/explore/dataset/gares-de-voyageurs/ ; https://ressources.data.sncf.com/explore/dataset/frequentation-gares/
- Adresse de téléchargement utilisée : https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/gares-de-voyageurs/exports/csv?delimiter=%3B ; https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/frequentation-gares/exports/csv?delimiter=%3B
- Millésime : référentiel des gares au 1er novembre 2026 ; fréquentation 2019 et 2024
- Licence : Licence ouverte 2.0 (Open Licence Etalab)
- Thèmes de la base : equipements (6 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Gares de voyageurs par commune (SNCF Gares & Connexions) : nombre de gares ouvertes aux voyageurs et fréquentation annuelle en 2019 et 2024.
- Script : [`pipeline/sources/gares.py`](pipeline/sources/gares.py)

### ircom

**L'impôt sur le revenu par collectivité territoriale (IRCOM)**

- Producteur : DGFiP (Département des études et statistiques fiscales)
- Référence dans le catalogue des sources du projet : E6-29
- Page de la source : https://www.data.gouv.fr/datasets/limpot-sur-le-revenu-par-collectivite-territoriale-ircom
- Adresse de téléchargement utilisée : https://static.data.gouv.fr/resources/limpot-sur-le-revenu-par-collectivite-territoriale-ircom/20260526-131537/ircom-2025-revenus-2024.zip
- Millésime : revenus 2024 déclarés en 2025 (publication mai 2026)
- Licence : Licence ouverte 2.0
- Thèmes de la base : revenus (22 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Impôt sur le revenu par commune (DGFiP, IRCOM) : foyers fiscaux, foyers imposés, revenu fiscal de référence total et moyen, répartition par tranche de revenu.
- Script : [`pipeline/sources/ircom.py`](pipeline/sources/ircom.py)

### lovac

**LOVAC - logements vacants du parc privé par commune**

- Producteur : DGALN, Cerema (données DGFiP 1767 bis Com et Fichiers fonciers)
- Référence dans le catalogue des sources du projet : P2-006
- Page de la source : https://www.data.gouv.fr/datasets/logements-vacants-du-parc-prive-par-commune-departement-region-france
- Adresse de téléchargement utilisée : https://static.data.gouv.fr/resources/logements-vacants-du-parc-prive-par-commune-departement-region-france/20260625-163627/lovac-opendata-communes26.csv
- Millésime : LOVAC 2026 (juin 2026), séries 2024 à 2026
- Licence : Licence ouverte 2.0
- Thèmes de la base : logement (12 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : LOVAC : logements vacants du parc privé par commune (vacance totale et vacance de plus de 2 ans) et parc privé total.
- Script : [`pipeline/sources/lovac.py`](pipeline/sources/lovac.py)

### loyers

**Carte des loyers - indicateurs de loyers d'annonce par commune en 2025**

- Producteur : ANIL et DGALN (annonces leboncoin et SeLoger)
- Référence dans le catalogue des sources du projet : B2-loyers
- Page de la source : https://www.data.gouv.fr/datasets/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025
- Adresse de téléchargement utilisée : https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-145010/pred-app-mef-dhup.csv ; https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-144934/pred-app12-mef-dhup.csv ; https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-144951/pred-app3-mef-dhup.csv ; https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-145039/pred-mai-mef-dhup.csv
- Millésime : 2025 (biens types mis en location au 3e trimestre 2025, annonces 2019 à 2025, communes au 1er janvier 2025)
- Licence : Licence ouverte 2.0
- Thèmes de la base : marche (14 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Carte des loyers (ANIL, DGALN) : loyer d'annonce prédit au m2, charges comprises, des appartements et des maisons par commune.
- Script : [`pipeline/sources/loyers.py`](pipeline/sources/loyers.py)

### ptz

**Base de données PTZ (prêts à taux zéro)**

- Producteur : Ministère chargé du logement (données SGFGAS)
- Référence dans le catalogue des sources du projet : E1-01
- Page de la source : https://www.data.gouv.fr/datasets/base-de-donnees-ptz-prets-a-taux-zero
- Adresse de téléchargement utilisée : https://static.data.gouv.fr/resources/base-de-donnees-ptz-prets-a-taux-zero/20220412-162011/opendataptz2022.csv
- Millésime : 2022 (prêts émis de 1995 à 2021, données arrêtées au 31 mars 2022)
- Licence : Licence ouverte
- Thèmes de la base : marche (25 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Prêts à taux zéro (PTZ) émis par commune et par année, logements neufs et anciens, montant total et moyen (base SGFGAS, 2017 à 2021).
- Script : [`pipeline/sources/ptz.py`](pipeline/sources/ptz.py)

### qpv

**Quartiers prioritaires de la politique de la ville 2024 (liste)**

- Producteur : Agence nationale de la cohésion des territoires (ANCT)
- Référence dans le catalogue des sources du projet : E7-35
- Page de la source : https://www.data.gouv.fr/datasets/quartiers-prioritaires-de-la-politique-de-la-ville-qpv
- Adresse de téléchargement utilisée : https://static.data.gouv.fr/resources/quartiers-prioritaires-de-la-politique-de-la-ville-qpv/20260721-095036/listeqp2024-cog2025.csv
- Millésime : Liste du 21 juillet 2026 (code géographique 2025) ; quartiers de 2024 pour l'hexagone (décret du 28 décembre 2023), 2025 pour l'outre-mer
- Licence : Licence ouverte 2.0
- Thèmes de la base : territoire (2 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Quartiers prioritaires de la politique de la ville (QPV, génération 2024) : nombre de quartiers par commune.
- Script : [`pipeline/sources/qpv.py`](pipeline/sources/qpv.py)

### rp_emploi

**Recensement de la population 2023 (dossier complet) : population active et chômage, emploi au lieu de travail, caractéristiques de l'emploi, diplômes, scolarisation, déplacements domicile-travail ; autres fiches : E4-18, P2-001**

- Producteur : Insee
- Référence dans le catalogue des sources du projet : E7-55
- Page de la source : https://catalogue-donnees.insee.fr/fr/catalogue/recherche/DS_RP_EMPLOI_LR_PRINC
- Adresse de téléchargement utilisée : https://api.insee.fr/melodi/file/&lt;jeu&gt;/&lt;jeu&gt;_2023_CSV_FR (zips CSV Melodi : DS_RP_EMPLOI_LR_PRINC, DS_RP_EMPLOI_LR_COMP, DS_RP_EMPLOI_LT_PRINC, DS_RP_ACTIVITE_PRINC, DS_RP_DIPLOMES_PRINC, DS_RP_EDUCATION_PRINC, DS_RP_NAVETTES_PRINC)
- Millésime : Recensement 2023 (enquêtes 2021 à 2025), rappels 2012 et 2017
- Licence : Licence ouverte 2.0
- Thèmes de la base : emploi (309 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Emploi et actifs des communes : activité et chômage des habitants, emplois au lieu de travail, statut et conditions d'emploi, diplômes, scolarisation, déplacements domicile-travail (recensement 2023, rappels 2012 et 2017 ; Insee, Melodi). Jeux Melodi (zips CSV lus dans cache/melodi/) : DS_RP_EMPLOI_LR_PRINC, DS_RP_EMPLOI_LR_COMP, DS_RP_EMPLOI_LT_PRINC, DS_RP_ACTIVITE_PRINC, DS_RP_DIPLOMES_PRINC, DS_RP_EDUCATION_PRINC, DS_RP_NAVETTES_PRINC. Les migrations résidentielles (DS_RP_MIGRES_PRINC) sont dans rp_population (thème population). Règles : dernière année de chaque série ; 2012 et 2017 seulement pour les totaux ; au plus deux dimensions hors total. Totaux d'âge retenus : 15 à 64 ans pour l'activité et le chômage, 15 ans ou plus pour les actifs occupés, 2 ans ou plus pour la scolarisation. Écartés (trois dimensions ou plus) : activité x sexe x âge et activité x âge x diplôme par tranche d'âge (seuls les totaux 15-64 ans ou 15 ans ou plus de ces croisements sont gardés) ; actifs occupés croisés par trois ou quatre de temps de travail, sexe, âge et statut ; scolarisation âge x sexe x inscription. Les taux (chômage, activité, emploi, concentration de l'emploi, parts) sont des ratios recalculés à partir des effectifs.
- Script : [`pipeline/sources/rp_emploi.py`](pipeline/sources/rp_emploi.py)

### rp_logement

**Recensement de la population 2023 : logements (dossier complet), indice de peuplement, résidences principales selon l'âge de la personne de référence (tableaux PRINC) ; autres fiches : E6-10, E6-11, E7-55**

- Producteur : Insee
- Référence dans le catalogue des sources du projet : P2-020
- Page de la source : https://catalogue-donnees.insee.fr/fr/catalogue/recherche/DS_RP_LOGEMENT_PRINC
- Adresse de téléchargement utilisée : https://api.insee.fr/melodi/file/&lt;jeu&gt;/&lt;jeu&gt;_2023_CSV_FR (zips CSV Melodi : DS_RP_LOGEMENT_PRINC, DS_RP_LOGEMENT_COMP, DS_RP_TD_LOGEMENT_AGE_PRINC)
- Millésime : Recensement 2023 (enquêtes 2021 à 2025), rappels 2012 et 2017
- Licence : Licence ouverte 2.0
- Thèmes de la base : logement (245 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Parc de logements et résidences principales des communes : catégorie, type, statut d'occupation, taille, époque de construction, ancienneté d'emménagement, équipement, peuplement, croisements avec l'âge de la personne de référence (recensement 2023, rappels 2012 et 2017 ; Insee, Melodi). Jeux Melodi (zips CSV lus dans cache/melodi/) : DS_RP_LOGEMENT_PRINC, DS_RP_LOGEMENT_COMP (indice de peuplement), DS_RP_TD_LOGEMENT_AGE_PRINC (résidences principales selon l'âge de la personne de référence, le type de logement, le nombre de pièces et le statut d'occupation). Règles : dernière année de chaque série ; au plus deux dimensions hors total. Années 2012 et 2017 : totaux, avec une exception assumée pour la catégorie de logement (résidences principales, secondaires, vacants), indispensable aux tendances du parc. Écartés : DS_RP_LOGEMENT_PRINC résidences principales x type x époque de construction (trois dimensions, 21 séries) ; DS_RP_TD_LOGEMENT_AGE_PRINC âge x type x pièces et âge x type x statut (trois dimensions, 231 séries) et la tranche « personne de référence de moins de 15 ans » ; les séries des millésimes 2012 et 2017 qui n'existent plus en 2023 (anciens découpages des époques de construction) ; mode de chauffage « hors logement ordinaire ou hors métropole ». Le nombre total de pièces et l'ancienneté cumulée d'emménagement sont des effectifs additifs : ils servent de numérateurs aux moyennes (pièces par logement, ancienneté moyenne), calculées comme ratios.
- Script : [`pipeline/sources/rp_logement.py`](pipeline/sources/rp_logement.py)

### rp_menages

**Recensement de la population 2023 : ménages, familles, tableaux détaillés MEN4, MEN5 et MEN6 (base Couples, familles, ménages) ; autres fiches : E6-13, E6-15, E7-55, P2-001**

- Producteur : Insee
- Référence dans le catalogue des sources du projet : P2-019
- Page de la source : https://catalogue-donnees.insee.fr/fr/catalogue/recherche/DS_RP_TD_MENAGES_TPH_COMP
- Adresse de téléchargement utilisée : https://api.insee.fr/melodi/file/&lt;jeu&gt;/&lt;jeu&gt;_2023_CSV_FR (zips CSV Melodi : DS_RP_MENAGES_PRINC, DS_RP_MENAGES_COMP, DS_RP_FAMILLE_COMP, DS_RP_TD_MENAGES_TPH_COMP, DS_RP_TD_MENAGES_NOC_COMP, DS_RP_TD_LOGEMENT_AGE_PRINC, DS_RP_MIGRES_PRINC)
- Millésime : Recensement 2023 (enquêtes 2021 à 2025), rappels 2012 et 2017
- Licence : Licence ouverte 2.0
- Thèmes de la base : menages, profils (418 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Ménages et familles des communes (recensement 2023, rappels 2012 et 2017) et nombre de ménages par profil de besoin en logement (Insee, Melodi). Jeux Melodi (zips CSV lus dans cache/melodi/) : DS_RP_MENAGES_PRINC, DS_RP_MENAGES_COMP, DS_RP_FAMILLE_COMP, DS_RP_TD_MENAGES_TPH_COMP (tableaux MEN5 et MEN6 : type de ménage x âge de la personne de référence), DS_RP_TD_MENAGES_NOC_COMP (MEN4 : taille du ménage x sexe x âge de la personne de référence) ; pour les profils, aussi DS_RP_TD_LOGEMENT_AGE_PRINC et DS_RP_MIGRES_PRINC. Bloc 'population' : dernière année de chaque série ; 2012 et 2017 seulement pour les totaux ; au plus deux dimensions hors total. Écarté : MEN4 croisé taille x sexe x âge (168 séries). Les totaux identiques d'un tableau à l'autre (nombre de ménages, population des ménages) ne sont gardés qu'une fois. Bloc 'besoins' : nombre de ménages pour les profils de l'annexe « Profils » (Annexe_base_unique_croisements.xlsx) comptables avec les tableaux détaillés diffusés. L'approximation exacte figure dans la définition de chaque colonne. Profils non comptés : « Ménage modeste éligible à l'accession sociale » (critère de revenu, absent du recensement ; Filosofi ne diffuse pas de déciles par commune et par profil) et « Investisseur particulier » (aucune statistique locale). Les critères d'emploi, de statut d'occupation, de taille de logement et de revenu ne sont jamais croisés à la fois avec l'âge et le type de ménage dans les tableaux diffusés : les profils restent des approximations.
- Script : [`pipeline/sources/rp_menages.py`](pipeline/sources/rp_menages.py)

### rp_population

**Recensement de la population 2023 (dossier complet : population, migrations résidentielles), populations historiques 1968-2023, état civil 2008-2025 (naissances, décès) ; autres fiches : E3-23, E6-14, E6-17, P2-001**

- Producteur : Insee
- Référence dans le catalogue des sources du projet : E7-55
- Page de la source : https://catalogue-donnees.insee.fr/fr/catalogue/recherche/DS_RP_POPULATION_PRINC
- Adresse de téléchargement utilisée : https://api.insee.fr/melodi/file/&lt;jeu&gt;/&lt;fichier&gt;_CSV_FR (zips CSV Melodi : DS_RP_POPULATION_PRINC_2023, DS_RP_POPULATION_COMP_2023, DS_POPULATIONS_HISTORIQUES, DS_ETAT_CIVIL_NAIS_COMMUNES_2025, DS_ETAT_CIVIL_DECES_COMMUNES_2025, DS_RP_MIGRES_PRINC_2023)
- Millésime : Recensement 2023 (enquêtes 2021 à 2025), rappels 2012 et 2017 ; état civil 2008-2025 ; populations 1968-2023
- Licence : Licence ouverte 2.0
- Thèmes de la base : population (176 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Population des communes : structure par sexe, âge et catégorie sociale (recensement 2023, rappels 2012 et 2017), populations municipales depuis 1968, naissances et décès annuels 2008-2025, migrations résidentielles (Insee, Melodi). Jeux Melodi (zips CSV lus dans cache/melodi/) : DS_RP_POPULATION_PRINC, DS_RP_POPULATION_COMP, DS_POPULATIONS_HISTORIQUES, DS_ETAT_CIVIL_NAIS_COMMUNES, DS_ETAT_CIVIL_DECES_COMMUNES, DS_RP_MIGRES_PRINC. Les migrations résidentielles (lieu de résidence un an auparavant) sont placées ici, dans le thème population, plutôt que dans rp_emploi : elles décrivent les arrivées de ménages, utiles à la demande de logement. Règles de sélection (voir sources/_melodi_commun.py) : dernière année de chaque série ; 2012 et 2017 seulement pour les totaux ; au plus deux dimensions hors total. Écarté : DS_RP_POPULATION_COMP croisé sexe x catégorie sociale x âge (48 séries à trois dimensions hors total). Les totaux identiques d'un tableau à l'autre ne sont gardés qu'une fois. Naissances, décès et populations municipales : toutes les années publiées sont gardées (séries sans dimension).
- Script : [`pipeline/sources/rp_population.py`](pipeline/sources/rp_population.py)

### rpls

**Répertoire des logements locatifs des bailleurs sociaux (RPLS), données détaillées au logement agrégées à la commune**

- Producteur : SDES (ministère chargé du logement)
- Référence dans le catalogue des sources du projet : B2-rpls
- Page de la source : https://www.data.gouv.fr/datasets/donnees-detaillees-au-logement-du-repertoire-des-logements-locatifs-des-bailleurs-sociaux-rpls
- Adresse de téléchargement utilisée : https://data.statistiques.developpement-durable.gouv.fr/dido/api/v1/datafiles/f3c2f2cb-8fb1-40fd-8733-964247744c9a/csv?millesime=2025-01&withColumnName=true&withColumnDescription=false&withColumnUnit=false&columns=DEPCOM,TYPECONST_CODE,NBPIECE,FINAN_CODE,LOCAT,DPEENERGIE&DEP_CODE=eq:&lt;departement&gt;
- Millésime : RPLS au 1er janvier 2025
- Licence : Licence ouverte 2.0
- Thèmes de la base : logement (20 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Parc locatif social par commune (RPLS, SDES) : nombre de logements des bailleurs sociaux, mises en service récentes, type, taille, financement et étiquette énergie.
- Script : [`pipeline/sources/rpls.py`](pipeline/sources/rpls.py)

### sitadel

**Sit@del2 - logements autorisés et commencés (séries annuelles communales en date réelle ; séries mensuelles départementales estimées)**

- Producteur : SDES
- Référence dans le catalogue des sources du projet : B1-02
- Page de la source : https://data.statistiques.developpement-durable.gouv.fr/dido/api/v1/datasets/6513ee3a3b05e5cd969c270f
- Adresse de téléchargement utilisée : https://data.statistiques.developpement-durable.gouv.fr/dido/api/v1/datafiles/9c90a880-4ba0-49b4-b99d-d7dd6c810dd0/csv?millesime=2026-10&withColumnName=true&withColumnDescription=false&withColumnUnit=false&ANNEE=gte:2012
- Millésime : Millésime 2026-10
- Licence : Licence ouverte 2.0
- Thèmes de la base : construction (60 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Construction neuve (Sitadel, SDES) : logements autorisés et commencés par commune et par année, par type, et construction actuelle (moyenne 2023-2025 du département, série estimée, répartie selon les communes en 2021-2023).
- Script : [`pipeline/sources/sitadel.py`](pipeline/sources/sitadel.py)

### sru

**Communes et inventaire SRU**

- Producteur : DGALN (ministère chargé du logement)
- Référence dans le catalogue des sources du projet : E7-30
- Page de la source : https://www.data.gouv.fr/datasets/communes-et-inventaire-sru
- Adresse de téléchargement utilisée : https://static.data.gouv.fr/resources/communes-et-inventaire-sru/20260811-123753/donnees-sru-data-gouv-2026.csv
- Millésime : 2026 (inventaire au 1er janvier 2025, situation 2026)
- Licence : Licence ouverte 2.0
- Thèmes de la base : logement (10 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Inventaire SRU : logements sociaux décomptés, taux SRU et situation de la commune au regard de l'article 55 de la loi SRU (soumise, déficitaire, carencée, exemptée).
- Script : [`pipeline/sources/sru.py`](pipeline/sources/sru.py)

### thrs

**Délibérations de fiscalité directe locale des communes 2026 (hors taux)**

- Producteur : Direction générale des finances publiques (DGFiP), ministères économiques et financiers
- Référence dans le catalogue des sources du projet : E7-38
- Page de la source : https://www.data.gouv.fr/datasets/deliberations-de-fiscalite-directe-locale-des-communes-2026-hors-taux
- Adresse de téléchargement utilisée : https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/deliberations-de-fiscalite-directe-locale-des-communes-2026-hors-taux/exports/csv?select=dep,depcom,com,libcom,indtlv,thlvdat,thsurtaxrsdat,thsurtaxrstau&delimiter=%3B
- Millésime : Délibérations applicables en 2026 (mises en ligne le 24 juillet 2026)
- Licence : Licence ouverte 2.0
- Thèmes de la base : territoire (3 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Délibérations fiscales des communes pour 2026 : majoration de la taxe d'habitation sur les résidences secondaires (et son taux), taxe d'habitation sur les logements vacants.
- Script : [`pipeline/sources/thrs.py`](pipeline/sources/thrs.py)

### trait_de_cote

**Liste des communes dont l'action en matière d'urbanisme doit être adaptée au recul du trait de côte (art. L. 321-15 du code de l'environnement)**

- Producteur : Ministère de la Transition écologique
- Référence dans le catalogue des sources du projet : P2-067
- Page de la source : https://www.data.gouv.fr/datasets/liste-des-communes-volontaires-pour-sadapter-au-recul-du-trait-de-cote
- Adresse de téléchargement utilisée : https://static.data.gouv.fr/resources/liste-des-communes-volontaires-pour-sadapter-au-recul-du-trait-de-cote/20260218-105039/trait-de-cote-commune-2026-95.csv
- Millésime : Décret n° 2022-750 du 29 avril 2022 modifié, en dernier lieu par le décret n° 2026-95 du 13 février 2026 (371 communes)
- Licence : Licence ouverte 2.0
- Thèmes de la base : risques_energie (2 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Communes inscrites sur la liste des communes exposées au recul du trait de côte (article L. 321-15 du code de l'environnement).
- Script : [`pipeline/sources/trait_de_cote.py`](pipeline/sources/trait_de_cote.py)

### urssaf

**Nombre d'établissements employeurs et effectifs salariés du secteur privé, par commune et code APE (au 31 décembre depuis 2006)**

- Producteur : Urssaf Caisse nationale
- Référence dans le catalogue des sources du projet : E4-02
- Page de la source : https://open.urssaf.fr/explore/dataset/etablissements-et-effectifs-salaries-au-niveau-commune-x-ape-last/
- Adresse de téléchargement utilisée : https://open.urssaf.fr/api/explore/v2.1/catalog/datasets/etablissements-et-effectifs-salaries-au-niveau-commune-x-ape-last/exports/csv?select=code_commune%2Cgrand_secteur_d_activite%2Csum%28effectifs_salaries_2015%29+as+eff_2015%2Csum%28nombre_d_etablissements_2015%29+as+etab_2015%2Csum%28effectifs_salaries_2016%29+as+eff_2016%2Csum%28nombre_d_etablissements_2016%29+as+etab_2016%2Csum%28effectifs_salaries_2017%29+as+eff_2017%2Csum%28nombre_d_etablissements_2017%29+as+etab_2017%2Csum%28effectifs_salaries_2018%29+as+eff_2018%2Csum%28nombre_d_etablissements_2018%29+as+etab_2018%2Csum%28effectifs_salaries_2019%29+as+eff_2019%2Csum%28nombre_d_etablissements_2019%29+as+etab_2019%2Csum%28effectifs_salaries_2020%29+as+eff_2020%2Csum%28nombre_d_etablissements_2020%29+as+etab_2020%2Csum%28effectifs_salaries_2021%29+as+eff_2021%2Csum%28nombre_d_etablissements_2021%29+as+etab_2021%2Csum%28effectifs_salaries_2022%29+as+eff_2022%2Csum%28nombre_d_etablissements_2022%29+as+etab_2022%2Csum%28effectifs_salaries_2023%29+as+eff_2023%2Csum%28nombre_d_etablissements_2023%29+as+etab_2023%2Csum%28effectifs_salaries_2024%29+as+eff_2024%2Csum%28nombre_d_etablissements_2024%29+as+etab_2024%2Csum%28effectifs_salaries_2025%29+as+eff_2025%2Csum%28nombre_d_etablissements_2025%29+as+etab_2025&where=code_region%3D%27%7Bcode_region%7D%27&group_by=code_commune%2Cgrand_secteur_d_activite&delimiter=%3B (une requête d'agrégation par région)
- Millésime : effectifs au 31 décembre 2015 à 2025 (mise à jour mai 2026)
- Licence : Licence ouverte 2.0
- Thèmes de la base : emploi (45 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Emploi salarié privé par commune (Urssaf) : établissements employeurs et effectifs salariés au 31 décembre de 2015 à 2025, total et industrie.
- Script : [`pipeline/sources/urssaf.py`](pipeline/sources/urssaf.py)

### zonage_abc

**Liste des communes selon le zonage ABC**

- Producteur : Ministère chargé du logement (DGALN), publié par le ministère de la Transition écologique
- Référence dans le catalogue des sources du projet : P2-029
- Page de la source : https://www.data.gouv.fr/datasets/liste-des-communes-selon-le-zonage-abc
- Adresse de téléchargement utilisée : https://static.data.gouv.fr/resources/liste-des-communes-selon-le-zonage-abc/20260703-091314/liste-ensemble-des-communes-zonage-abc-en-vigueur-26-juin-2026.csv
- Millésime : Zonage en vigueur depuis le 26 juin 2026 (arrêté du 1er août 2014 modifié, en dernier lieu le 23 juin 2026), géographie communale 2026
- Licence : Licence ouverte 2.0
- Thèmes de la base : territoire (6 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Zonage ABC des communes (tension du marché du logement), en texte et en colonnes 0/1 par zone.
- Script : [`pipeline/sources/zonage_abc.py`](pipeline/sources/zonage_abc.py)

### zone_climatique

**Zones climatiques réglementaires (RE2020 et méthode DPE) par département**

- Producteur : Ministère chargé de la construction (DHUP) ; table département - zone déduite par le projet de la base des DPE de l'ADEME
- Référence dans le catalogue des sources du projet : E5-13
- Page de la source : https://rt-re-batiment.developpement-durable.gouv.fr/documents-complementaires-a706.html
- Adresse de téléchargement utilisée : Annexe_base_unique_croisements.xlsx, onglet « Zones climatiques » (phase 3 du projet) ; table recopiée dans ce module
- Millésime : Zonage RE2020 (identique à celui de la RT2012) ; table vérifiée sur la base DPE de l'ADEME, extraction du 6 octobre 2026
- Licence : Licence ouverte 2.0 (base DPE ADEME) ; texte réglementaire public
- Thèmes de la base : risques_energie (10 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Zone climatique réglementaire de la construction (RE2020, DPE) de chaque commune, déduite de son département.
- Script : [`pipeline/sources/zone_climatique.py`](pipeline/sources/zone_climatique.py)

### zones_tendues

**Communes en zone tendue (taxe sur les logements vacants) et communes à encadrement des loyers**

- Producteur : Premier ministre (DILA) : données de référence du simulateur « zones tendues » de service-public.fr, reprenant les deux listes du décret n° 2013-392 modifié ; Naistor : compilation, commune par commune, des décrets de périmètre et des arrêtés préfectoraux d'encadrement des loyers (aucune liste officielle en données ouvertes)
- Référence dans le catalogue des sources du projet : P2-112
- Page de la source : https://www.data.gouv.fr/datasets/simulateur-des-zones-tendues ; https://www.data.gouv.fr/datasets/communes-a-encadrement-des-loyers-encadrement-du-niveau-des-loyers-loi-elan-article-140
- Adresse de téléchargement utilisée : https://gitlab.com/pidila/sp-simulateurs-data/-/raw/master/donnees-de-reference/TaxeLogementVacant.json ; https://static.data.gouv.fr/resources/communes-a-encadrement-des-loyers-encadrement-du-niveau-des-loyers-loi-elan-article-140/20261029-231309/communes-encadrement-des-loyers.csv
- Millésime : Listes de zones tendues en vigueur en 2026 (décret n° 2013-392 modifié, notamment par le décret n° 2023-822 du 25 août 2023) ; encadrement des loyers vérifié le 29 octobre 2026
- Licence : Licence ouverte 2.0
- Thèmes de la base : territoire (7 indicateurs)
- Dernier calcul : 2026-11-04
- Ce que fait le script : Communes en zone tendue au sens de la taxe sur les logements vacants et communes où le niveau des loyers est encadré.
- Script : [`pipeline/sources/zones_tendues.py`](pipeline/sources/zones_tendues.py)
