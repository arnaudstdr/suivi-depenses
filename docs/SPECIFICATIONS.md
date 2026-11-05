# Spécifications fonctionnelles — Suivi des dépenses

**Version :** 0.3  
**Statut :** Base fonctionnelle validée — à implémenter  
**Application :** Web responsive / PWA  
**Devise :** EUR

## 1. Objectif

L'application permet à deux membres d'un foyer de suivre leurs dépenses sans mélanger le budget personnel et les dépenses communes.

La priorité de l'écran Personnel est de répondre immédiatement à la question : **combien me reste-t-il de budget prévisionnel à dépenser jusqu'à la fin du mois ?**

L'application ne cherche pas à reproduire la comptabilité de plusieurs comptes bancaires. Le seul solde bancaire suivi en V1 est le compte courant personnel de l'utilisateur connecté.

## 2. Deux périmètres distincts

### 2.1 Suivi personnel

Le suivi personnel comprend :
- le solde réel du compte courant personnel, saisi manuellement ;
- les charges récurrentes personnelles restant à payer ;
- les dépenses ponctuelles personnelles prévues et non encore payées ;
- une seule ligne agrégée « Participation au foyer », correspondant à la part de l'utilisateur dans les charges communes prévues et restant à financer.

Aucun revenu futur n'est ajouté au calcul. Les revenus ne servent pas à augmenter artificiellement le disponible du mois.

### 2.2 Suivi du foyer

Le suivi du foyer comprend :
- les charges récurrentes communes ;
- leur répartition entre les deux membres ;
- la contribution de chaque membre ;
- le budget courses commun ;
- les dépenses de courses enregistrées par l'un ou l'autre membre.

Le solde bancaire du compte joint n'est pas suivi en V1.

## 3. Calcul du disponible prévisionnel personnel

Le solde de départ est le solde réel du compte courant personnel saisi manuellement par l'utilisateur. La saisie conserve sa date et son heure.

Formule :

`Disponible prévisionnel = solde personnel saisi - charges personnelles restantes - participation au foyer restante - dépenses personnelles ponctuelles prévues`

Règles :
- Ne pas déduire une dépense déjà payée : son effet est déjà reflété dans le solde bancaire saisi.
- Une charge récurrente est déduite si son échéance est à venir et qu'elle n'est pas marquée payée.
- Une dépense ponctuelle prévue est déduite tant qu'elle n'est pas marquée payée.
- Une participation au foyer déjà transférée/payée n'est pas déduite une seconde fois.
- Les achats de courses communes ne sont jamais déduits du suivi personnel.
- Aucun revenu attendu, même certain, n'est ajouté.
- Le calcul porte sur le reste du mois sélectionné, depuis la date de référence du solde jusqu'à la fin du mois.
- Le tableau de bord affiche la date de dernière saisie du solde.

Le solde manuel est une référence déclarative : l'application ne se connecte pas à la banque et ne le met pas à jour automatiquement.

## 4. Charges récurrentes

L'utilisateur peut créer et gérer toutes ses charges récurrentes, personnelles ou communes.

Champs :
- libellé ;
- montant de référence ;
- catégorie ;
- type : personnelle ou commune ;
- fréquence (hebdomadaire, mensuelle, trimestrielle, semestrielle, annuelle) ;
- date de début et date de fin facultative ;
- jour/date d'échéance ;
- statut actif/inactif ;
- montant fixe ou variable ;
- pour une charge commune, pourcentage de répartition de chaque membre.

Exemples : abonnements, assurances, loyer, énergie, téléphonie, participation au foyer.

### 4.1 Charges personnelles

Une charge personnelle est déduite à 100 % du disponible personnel lorsqu'elle reste à payer sur le mois.

### 4.2 Charges communes

Une charge commune est répartie selon les pourcentages configurés. La répartition par défaut actuelle est 55 % pour l'utilisateur et 45 % pour l'autre membre ; elle doit être modifiable.

La somme des pourcentages doit être égale à 100 %.

Sur le tableau de bord Personnel, toutes les parts personnelles des charges communes restant à financer sont regroupées dans une seule ligne « Participation au foyer ». Le détail reste consultable dans la vue Charges/Récurrences.

Une règle personnalisée peut être définie pour une charge particulière si sa répartition diffère de la répartition par défaut.

## 5. Dépenses ponctuelles

L'utilisateur peut enregistrer une dépense ponctuelle :
- personnelle : elle impacte le disponible personnel tant qu'elle est prévue et non payée ;
- commune hors courses : elle est répartie selon la règle configurée et intégrée à la participation au foyer ;
- courses communes : elle est imputée au budget courses commun, sans impact sur le disponible personnel.

Une dépense ponctuelle peut être prévue, payée ou annulée. Une dépense payée n'est plus une prévision à déduire.

## 6. Budget courses commun

- Enveloppe initiale : **490 € par mois**.
- Budget configurable par le foyer.
- Répartition de contribution actuelle : 55 % utilisateur / 45 % autre membre.
- Contribution théorique de l'utilisateur : 269,50 € ; celle de l'autre membre : 220,50 €.
- Le budget est remis à sa valeur configurée au début de chaque mois.
- Aucun reliquat n'est reporté.
- Une dépense de catégorie « Courses / alimentation » marquée commune est déduite de l'enveloppe.
- La dépense est enregistrée une seule fois.
- Elle n'est pas ajoutée aux dépenses personnelles et ne diminue pas le disponible personnel.
- Le tableau de bord affiche l'enveloppe, le montant dépensé et le montant restant.

Le montant de contribution au budget courses est intégré au calcul de la participation au foyer lorsqu'il est configuré comme engagement mensuel à financer. Les achats individuels de courses restent uniquement des consommations de l'enveloppe.

## 7. Enregistrement d'une dépense

Le formulaire doit rester simple. Champs minimum :
- libellé ;
- montant ;
- date ;
- catégorie ;
- type : personnelle ou commune.

Si la dépense est commune et concerne les courses, elle diminue le budget courses. Si elle est commune et concerne une autre catégorie, sa part personnelle rejoint la participation au foyer.

Les dépenses de courses communes ne doivent pas être confondues avec les autres charges communes.

## 8. Tableau de bord Personnel

Ordre de priorité :
1. **Disponible prévisionnel** (indicateur principal).
2. Solde personnel saisi et date de mise à jour.
3. Détail synthétique des déductions : charges personnelles, participation au foyer, dépenses ponctuelles prévues.
4. Budget courses du foyer : dépensé et restant.
5. Charges récurrentes à venir.
6. Dépenses personnelles récentes.

Le tableau de bord ne doit pas afficher les achats communs comme des dépenses personnelles.

## 9. Tableau de bord Foyer

Afficher :
- liste et total des charges communes ;
- pourcentage et montant de participation de chaque membre ;
- total de la participation mensuelle de chacun ;
- budget courses de 490 €, consommé et restant ;
- historique des dépenses communes.

Aucun solde bancaire joint n'est requis.

## 10. Transactions et historique

Chaque dépense conserve son libellé, montant positif en centimes, date, catégorie, périmètre, créateur et statut. Les remboursements sont des transactions distinctes liées à la dépense d'origine. L'historique ne doit pas être modifié silencieusement.

## 11. Récurrences et occurrences

Les récurrences génèrent des échéances de manière idempotente. Chaque occurrence peut être à payer, confirmée, payée ou ignorée. Les montants variables peuvent être confirmés à chaque échéance. Une occurrence payée référence la transaction correspondante.

## 12. Répartition

Répartition par défaut : 55 % / 45 %. Chaque charge commune peut utiliser la répartition par défaut ou une règle spécifique. Les calculs sont effectués au centime, avec arrondi déterministe. Une modification de la règle ne réécrit pas les périodes passées.

Les revenus peuvent être conservés comme informations de référence pour expliquer ou ajuster manuellement les pourcentages, mais ils ne sont pas utilisés pour calculer le disponible prévisionnel personnel.

## 13. Comptes, sécurité et confidentialité

- Deux comptes utilisateurs distincts rattachés au même foyer.
- Invitation uniquement en V1, pas d'inscription publique.
- Données personnelles accessibles uniquement à leur propriétaire.
- Données du foyer accessibles aux membres.
- Permissions vérifiées côté backend.
- Sessions par cookies sécurisés HttpOnly, Secure, SameSite adapté et protection CSRF.
- Montants stockés en centimes entiers.
- Journalisation des opérations sensibles sans données financières privées inutiles.

## 14. PWA et mode hors ligne

La PWA permet l'installation sur mobile et desktop. En V1, les données déjà synchronisées sont consultables hors ligne en lecture seule. Aucune création ou modification hors ligne.

## 15. Hors périmètre V1

- Synchronisation bancaire automatique.
- Suivi du solde du compte joint.
- Ajout des revenus futurs au disponible prévisionnel.
- Déduction des achats de courses communes du budget personnel.
- Gestion de plusieurs comptes personnels.
- Reconnaissance automatique de tickets par OCR.
- Catégorisation par IA.

## 16. Critères d'acceptation

- Le tableau de bord affiche le disponible prévisionnel en premier.
- Le solde de départ est saisi manuellement et horodaté.
- Les revenus futurs ne sont pas ajoutés au disponible.
- Les charges récurrentes personnelles restant à payer sont déduites.
- Les parts de charges communes restant à financer sont agrégées dans une seule ligne.
- Une charge commune payée ou déjà transférée n'est pas déduite deux fois.
- Une dépense de courses commune diminue le budget courses, pas le disponible personnel.
- Le budget courses est initialisé à 490 €/mois et configurable.
- La répartition par défaut est 55/45 et modifiable.
- Les dépenses ponctuelles personnelles prévues sont déduites jusqu'à leur paiement.
- Les montants sont calculés au centime.

---

**Fin — SPECIFICATIONS.md v0.3**
