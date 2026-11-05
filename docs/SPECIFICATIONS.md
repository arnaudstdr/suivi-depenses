# Spécifications fonctionnelles — Budget familial

**Version :** 0.2  
**Statut :** Proposition fonctionnelle à valider  
**Type :** Application web responsive / PWA

## 1. Vision du produit

Application web permettant à deux personnes de gérer leurs finances personnelles et le budget familial depuis une interface unique. Elle remplace les tableaux Numbers/Excel actuels et simplifie le suivi des revenus et dépenses, des charges récurrentes, des dépenses ponctuelles, du budget alimentaire partagé, de la répartition des charges, de l'historique et des imports/exports.

L'application doit être utilisable sur ordinateur, smartphone et tablette, avec possibilité d'installation comme PWA.

## 2. Principes fondamentaux

1. Une dépense doit être enregistrée rapidement.
2. Les calculs budgétaires doivent être automatiques et explicables.
3. Les deux utilisateurs possèdent des comptes indépendants.
4. Les données communes sont synchronisées entre les utilisateurs.
5. Les données personnelles restent privées selon les autorisations configurées.
6. Les données historiques ne sont pas recalculées rétroactivement après un changement de configuration.
7. Les montants sont stockés en centimes entiers.

## 3. Utilisateurs, foyer et confidentialité

### 3.1 Utilisateurs et foyer

La première version démarre avec deux utilisateurs, chacun possédant son compte. Ils appartiennent à un même foyer.

Le foyer centralise les dépenses communes, le budget alimentaire, les charges communes, les revenus du foyer, les règles de répartition et les tableaux de bord communs.

### 3.2 Périmètres

Chaque transaction ou budget est personnel ou commun :
- Personnel : accessible uniquement à son propriétaire.
- Commun : accessible aux membres autorisés du foyer.

Les deux membres disposent des mêmes droits fonctionnels sur les données communes dans la V1.

### 3.3 Confidentialité financière configurable

Chaque utilisateur contrôle individuellement :
- le partage de son revenu exact ;
- l'autorisation d'utiliser son revenu pour les calculs de répartition ;
- le partage de son pourcentage de participation ;
- le partage des montants qui lui sont attribués.

Configuration initiale recommandée :
- revenu exact : privé ;
- utilisation pour la répartition : autorisée ;
- pourcentage : partagé ;
- montant réparti : partagé.

Le backend applique les permissions avant de retourner les données. Le masquage dans le frontend ne constitue pas une protection suffisante.

Un revenu non autorisé pour le calcul ne doit pas être remplacé par une valeur fictive. Le calcul est déclaré incomplet ou utilise une règle manuelle convenue.

## 4. Tableau de bord

### 4.1 Vue foyer

Afficher les revenus du foyer, dépenses communes, dépenses alimentaires, charges récurrentes, dépenses ponctuelles, budget commun restant et participation financière de chaque membre.

### 4.2 Vue personnelle

Afficher les revenus personnels, dépenses personnelles, participation aux charges communes, objectifs et enveloppes personnels, et solde prévisionnel.

### 4.3 Navigation temporelle

Le tableau de bord possède un sélecteur de mois. Les périodes historiques restent consultables.

## 5. Transactions

### 5.1 Types

- Revenu.
- Dépense.
- Remboursement.
- Transfert entre comptes : à arbitrer, hors périmètre initial si non nécessaire.

### 5.2 Informations

Une transaction comporte :
- libellé, montant positif, date, type, catégorie et périmètre ;
- utilisateur créateur ;
- personne ayant payé, si applicable ;
- moyen de paiement facultatif ;
- commentaire facultatif.

Le type détermine le traitement comptable. Un remboursement est une transaction distincte, pas une modification de la dépense d'origine.

### 5.3 Actions

Ajouter, modifier et supprimer une transaction ; filtrer par mois, catégorie, utilisateur et périmètre ; rechercher par libellé ; consulter l'historique.

### 5.4 Catégories

Catégories initiales : logement, nourriture, transport, santé, assurances, abonnements, loisirs, épargne, enfants et divers. Elles doivent être configurables.

### 5.5 Dépenses communes payées individuellement

Une dépense commune peut être payée par un seul membre. Le paiement réel et la participation théorique calculée sont deux notions distinctes.

La V1 ne crée pas automatiquement de créance ni de remboursement entre membres. La régularisation reste manuelle.

## 6. Dépenses récurrentes

Une dépense récurrente comprend un libellé, montant de référence, catégorie, périmètre, fréquence, date de début et date de fin facultative, jour d'échéance, propriétaire ou foyer, statut actif/inactif et indicateur de confirmation obligatoire du montant.

Fréquences initiales : hebdomadaire, mensuelle, trimestrielle, semestrielle et annuelle.

Chaque occurrence concrète peut être en attente de confirmation, confirmée, payée ou ignorée.

Pour une dépense variable, le montant doit être confirmé à chaque échéance avant d'être comptabilisé comme dépense réelle. Une occurrence payée référence une transaction. Une occurrence ignorée n'est pas comptabilisée. Une contrainte d'unicité empêche de générer deux fois la même échéance.

Les modifications de la définition ne changent pas les occurrences passées.

## 7. Budget alimentaire partagé

Le foyer dispose d'une enveloppe alimentaire commune. Budget de référence initial : 490 € par mois, valeur configurable.

Les deux membres peuvent ajouter des dépenses alimentaires. Après synchronisation, chaque achat est visible par les deux.

Afficher le budget initial, montant dépensé, montant restant, pourcentage consommé, barre de progression, historique des achats, date, montant et auteur de chaque achat.

Calcul : budget restant = enveloppe du mois − dépenses alimentaires éligibles.

Les achats sont enregistrés une seule fois dans les transactions ; le budget alimentaire agrège les transactions éligibles et ne crée pas une seconde dépense.

Seuils d'alerte configurables, proposés par défaut à 70 %, 85 % et 100 % de consommation.

Aucun report : chaque mois démarre avec sa propre enveloppe. Le reliquat non consommé du mois précédent est perdu.

## 8. Répartition des charges communes

### 8.1 Répartition proportionnelle

La méthode par défaut calcule la participation à partir des revenus admissibles de chaque membre.

Exemple :
- Anne : 1 800 € ;
- Arnaud : 2 200 € ;
- total admissible : 4 000 € ;
- proportions : 45 % et 55 %.

Les calculs sont effectués au centime. Le reliquat d'arrondi est attribué de manière déterministe pour que la somme soit égale au total.

### 8.2 Règles personnalisées

Certaines charges, notamment les crédits, peuvent utiliser des proportions spécifiques.

Exemple :
- loyer : Anne 45 %, Arnaud 55 % ;
- crèche : Anne 45 %, Arnaud 55 % ;
- crédit voiture : Anne 0 %, Arnaud 100 %.

Une règle personnalisée doit totaliser 100 %.

### 8.3 CAF et autres aides

Les aides CAF sont enregistrées comme revenus du foyer, et non comme revenus personnels par défaut.

Leur inclusion dans la base de calcul des proportions doit rester configurable par type de revenu ou règle de calcul. Il ne faut pas supposer que toute aide est automatiquement incluse dans le calcul des participations.

### 8.4 Historique

Chaque période conserve les revenus admissibles, proportions et montants calculés. Une modification des revenus ou règles ne recalcule pas silencieusement les mois précédents.

## 9. Budgets personnels

Chaque utilisateur peut définir ses enveloppes et objectifs personnels, et suivre ses revenus et dépenses privés. Les informations personnelles ne sont pas visibles par l'autre membre sauf autorisation explicite.

## 10. Historique et statistiques

Conserver les transactions et configurations mensuelles.

Comparer les dépenses totales, alimentation, charges fixes, dépenses ponctuelles, revenus et épargne.

Visualisations envisagées : évolution des dépenses sur 12 mois, répartition par catégorie, dépenses personnelles contre communes, évolution du budget alimentaire, évolution des revenus et dépenses.

## 11. Import et export

### 11.1 Import CSV/XLSX

Étapes : sélection du fichier, lecture des colonnes, association des colonnes aux champs, prévisualisation, détection des doublons, validation et import.

Aucune donnée ne doit être importée sans validation préalable.

### 11.2 Export

Formats CSV et XLSX pour les transactions, dépenses récurrentes, budgets, répartitions et historiques. Les exports respectent les permissions de l'utilisateur.

## 12. Notifications

Notifications dans l'application et push PWA lorsque le navigateur et le système le permettent.

Types : budget alimentaire proche du seuil, budget alimentaire dépassé, dépense récurrente à confirmer, nouvelle dépense commune et dépense commune modifiée.

Chaque utilisateur peut configurer ses préférences par catégorie et canal.

## 13. PWA et fonctionnement hors ligne

L'application doit être installable sur iPhone, Android, macOS et Windows, dans les limites des capacités du navigateur.

Mode hors ligne :
- consultation des données déjà mises en cache ;
- consultation du dernier tableau de bord chargé ;
- consultation des dernières transactions synchronisées ;
- aucune création ni modification hors ligne en V1 ;
- indication claire de l'état de connexion.

Le cache doit être limité aux données auxquelles l'utilisateur a accès.

## 14. Sécurité

Authentification sécurisée et mots de passe hachés ; gestion des sessions ; contrôle d'accès côté backend ; isolation des données personnelles ; HTTPS obligatoire en production ; sauvegardes PostgreSQL régulières ; journalisation des actions sensibles ; aucune donnée financière privée inutile dans les logs.

## 15. Stack cible

- Python 3.12.
- FastAPI et Pydantic.
- SQLAlchemy 2 et Alembic.
- PostgreSQL.
- React, TypeScript et Vite.
- Tailwind CSS et shadcn/ui.
- vite-plugin-pwa.
- Docker Compose.

## 16. Périmètre MVP

Inclus : deux comptes et un foyer ; transactions personnelles et communes ; catégories ; dépenses récurrentes ; budget alimentaire partagé ; répartition proportionnelle et règles personnalisées ; budgets personnels ; tableau de bord ; historique mensuel ; import CSV/XLSX ; export CSV/XLSX ; notifications ; PWA avec consultation hors ligne.

Hors périmètre initial : connexion bancaire automatique ; OCR de tickets ; catégorisation par IA ; gestion de plusieurs devises ; synchronisation bancaire temps réel.

## 17. Critères d'acceptation

- Deux utilisateurs peuvent se connecter séparément.
- Une dépense personnelle reste privée.
- Une dépense commune est visible par les membres du foyer.
- Une dépense alimentaire diminue l'enveloppe après synchronisation.
- Les dépenses récurrentes ne sont pas générées en double.
- Une occurrence variable nécessite confirmation avant comptabilisation.
- Les répartitions sont exactes au centime.
- Les changements de revenus ne modifient pas les mois précédents.
- Les budgets ne sont pas reportés.
- Les remboursements sont des transactions distinctes.
- Imports et exports respectent les permissions.
- Les dernières données synchronisées sont consultables hors ligne.

## 18. Points encore à arbitrer

- Règle exacte d'inclusion des différentes aides dans la base de répartition.
- Définition du solde disponible personnel.
- Gestion des transferts entre comptes.
- Gestion des revenus variables et des périodes sans revenu.
- Gestion des dépenses partiellement remboursées.
- Règles d'arrondi et d'affichage des répartitions historiques.
