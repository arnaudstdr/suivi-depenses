# Design UX — Suivi des dépenses

**Version :** 0.6  
**Statut :** Direction UX validée, maquette à aligner  
**Référence métier :** SPECIFICATIONS.md v0.4

## 1. Principes

L'interface doit être directe, lisible et rapide. La question prioritaire sur l'écran Personnel est : **combien me reste-t-il de budget prévisionnel ce mois-ci ?**

- Vue par défaut après connexion : Personnel.
- Sélecteur de contexte Personnel / Foyer.
- Desktop : navigation latérale.
- Mobile : navigation basse.
- Thème clair/sombre adaptatif.
- Couleur principale violette.
- Densité équilibrée.
- Données de démonstration uniquement dans la maquette.

## 2. Tableau de bord Personnel

Ordre de lecture :

1. **Disponible prévisionnel** en très grand, premier indicateur.
2. Solde bancaire personnel saisi manuellement, avec date de dernière mise à jour et action « Mettre à jour le solde ».
3. Participation au foyer, avec montant à virer et statut « À effectuer » / « Virement effectué ». L'action de confirmation ne retire pas la déduction du disponible.
4. Détail des déductions :
   - charges personnelles restantes ;
   - participation au foyer (une seule ligne agrégée) ;
   - dépenses personnelles ponctuelles prévues.
5. Budget courses du foyer : enveloppe, consommé, restant.
6. Prochaines échéances récurrentes.
7. Dernières dépenses personnelles.

Le solde saisi est un instantané daté. Les sorties postérieures à cet instantané restent déduites même après leur paiement ; elles disparaissent du prévisionnel lors de la saisie d'un nouveau solde qui les intègre. Les sorties antérieures à l'instantané ne sont pas déduites. Les revenus futurs et les achats de courses communes sont exclus.

### Wireframe

```text
┌───────────────────────────────────────────────────────────────────┐
│ Personnel                                      Novembre 2026     │
│                                                                   │
│ DISPONIBLE PRÉVISIONNEL                                            │
│ 842,50 €                                                          │
│ Solde saisi : 1 500,00 € · mis à jour le 05/11 à 09:30            │
│                                                                   │
│ Charges personnelles restantes        - 250,00 €                 │
│ Participation au foyer                - 300,00 €                 │
│ Participation au foyer : À pointer · bouton « Pointer »            │
│ Dépenses ponctuelles prévues           - 107,50 €                 │
│                                                                   │
│ BUDGET COURSES DU FOYER                                            │
│ 490,00 € · dépensé 205,80 € · reste 284,20 €                      │
│                                                                   │
│ Charges à venir                      Dernières dépenses perso.    │
└───────────────────────────────────────────────────────────────────┘
```

## 3. Participation au foyer

Le tableau de bord Personnel n'affiche qu'une seule ligne agrégée. Le détail est disponible dans l'écran Charges / Récurrences.

La vue détaillée permet de voir chaque charge commune, le montant total, le pourcentage de chacun et la part individuelle. La contribution aux courses (269,50 € pour la part initiale de 55 %) est incluse dans le total de participation. La participation apparaît comme une échéance pointable, avec la même interaction que les autres charges récurrentes : bouton « Pointer », puis confirmation de la date réelle du virement et du montant réellement transféré. Après validation, le statut devient « Effectué » et le montant/date sont conservés. Une correction ultérieure est explicite et auditée. Le pointage change le statut, pas le montant du disponible. Répartition par défaut actuelle : 55 % / 45 %, modifiable globalement et par charge.

## 4. Budget courses

Une carte dédiée affiche :
- budget mensuel de référence : 490 € ;
- total dépensé ;
- reste disponible ;
- progression ;
- historique des achats communs.

Lors de l'ajout d'une dépense, le choix « Commune » et la catégorie « Courses » dirigent l'opération vers le budget courses. Aucun montant n'est soustrait du disponible personnel.

## 5. Formulaire de dépense

Champs :
- libellé ;
- montant ;
- date ;
- catégorie ;
- périmètre Personnel / Commune.

Comportement :
- Personnelle : ajout au suivi personnel.
- Commune + Courses : consommation du budget courses.
- Commune + autre catégorie : charge du foyer, répartie selon la règle applicable.

Le formulaire ne doit pas demander des informations techniques inutiles à chaque ajout.

## 6. Gestion des charges récurrentes

Écran de liste avec libellé, montant, fréquence, catégorie, type Personnel/Commun, pourcentage si commune, prochaine échéance et statut. Chaque occurrence est présentée individuellement avec sa date d'échéance, son montant attendu/confirmé, son statut et une action « Pointer comme payée » tant qu'elle n'est pas payée ou ignorée.

Création/modification :
- type Personnel ou Commun ;
- montant et fréquence ;
- catégorie ;
- date/jour d'échéance ;
- répartition (uniquement si commune) ;
- montant variable ou fixe.

Pointage d'une échéance récurrente ou de la participation au foyer : ouvrir une confirmation légère avec date réelle du paiement/virement et montant réellement débité/transféré (montant attendu prérempli pour une charge fixe ; saisie obligatoire pour une charge variable). Après validation, afficher le statut « Payée » et le montant réel. Le pointage ne change pas le disponible si le paiement est postérieur au dernier instantané de solde ; la sortie reste provisionnée jusqu'à une nouvelle saisie du solde.

## 7. Vue Foyer

Afficher les charges communes et leur répartition, ainsi que le budget courses et les achats. Ne pas afficher un solde bancaire joint, car il n'est pas suivi.

## 8. Navigation

- Vue d'ensemble
- Dépenses
- Charges récurrentes
- Budget courses
- Répartition
- Historique
- Paramètres

Les vues secondaires peuvent être des écrans de maquette navigables, mais les parcours du tableau de bord, ajout de dépense, gestion d'une charge et suivi des courses sont prioritaires.

## 9. Responsive et accessibilité

- Mobile à partir de 360 px.
- Navigation latérale sur desktop, navigation basse sur mobile.
- Cibles tactiles adaptées, focus visible, labels explicites.
- Les montants et statuts ne sont jamais différenciés uniquement par la couleur.
- Afficher les états chargement, vide, erreur et hors ligne.

## 10. Maquette

La maquette React/Vite est une démonstration statique avec interactions locales. Elle ne persiste pas les données et n'appelle aucune API. Le jeu de données doit être fictif et cohérent avec les règles métier décrites ici.
