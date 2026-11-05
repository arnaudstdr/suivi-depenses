# UX Design — Suivi des dépenses

**Version :** 0.1  
**Statut :** Direction UX validée, écrans à détailler  
**Direction retenue :** application de gestion budgétaire avec tableaux, indicateurs et graphiques, privilégiant la lisibilité et la rapidité d'action.

## 1. Principes UX

L'application doit permettre de comprendre rapidement la situation financière du foyer et de chaque personne, puis d'agir sans multiplier les écrans.

Principes directeurs :

1. **Lisibilité avant densité** : hiérarchie visuelle claire, chiffres importants visibles, tableaux simplifiés sur mobile.
2. **Action rapide** : ajout d'une dépense accessible depuis les écrans principaux.
3. **Séparation explicite** : dépenses personnelles et dépenses du foyer clairement distinguées.
4. **Pas d'indicateur ambigu** : ne pas afficher de « reste à vivre » ou de solde disponible tant que sa définition métier n'est pas validée.
5. **Confidentialité visible** : les revenus et informations privées ne sont montrés qu'aux personnes autorisées.
6. **Responsive réel** : les écrans mobiles sont conçus comme des vues de premier ordre, pas comme une réduction du desktop.
7. **Progressive disclosure** : afficher l'essentiel d'abord ; réserver les détails, filtres avancés et paramètres aux vues secondaires.

## 2. Direction visuelle

### 2.1 Style

- Interface sobre, contemporaine et fonctionnelle.
- Fond clair légèrement cassé, surfaces blanches, bordures discrètes.
- Couleur primaire sobre (bleu profond ou indigo) réservée aux actions et éléments interactifs.
- Vert réservé aux situations favorables, orange aux alertes et rouge aux dépassements ou erreurs.
- Typographie sans-serif très lisible.
- Graphiques simples, avec légendes explicites et valeurs accessibles.
- Pas de dégradés décoratifs, d'ombres lourdes ou de cartes excessivement arrondies.

La palette exacte, les tokens et les composants seront arrêtés dans la maquette.

### 2.2 Densité

- Desktop : densité modérée, grille de 12 colonnes, navigation latérale persistante.
- Mobile : une colonne, navigation basse, cartes empilées et tableaux convertis en lignes/cartes.
- Les montants utilisent le format français et sont alignés visuellement.
- Les montants sont affichés en euros, les calculs internes restent en centimes.

## 3. Navigation

### Desktop

Navigation latérale :

- Vue d'ensemble
- Transactions
- Budgets
- Récurrences
- Répartition
- Revenus
- Historique
- Paramètres

Un sélecteur de contexte permet de passer de la vue **Foyer** à la vue **Personnel**. Le contexte actif doit rester visible dans l'en-tête.

### Mobile

Barre de navigation basse avec les destinations les plus fréquentes :

- Accueil
- Transactions
- Budgets
- Répartition
- Plus

Le menu « Plus » regroupe récurrences, revenus, historique et paramètres. Un bouton d'ajout de dépense est accessible sans devoir ouvrir plusieurs niveaux de navigation.

## 4. Tableau de bord principal

### 4.1 Objectif

Donner en quelques secondes une vue de la période en cours : dépenses constatées, évolution des budgets, dernières opérations et échéances à venir. Ne pas calculer ni suggérer un solde disponible non défini.

### 4.2 Structure proposée

1. **En-tête de contexte**
   - période sélectionnée ;
   - contexte Foyer / Personnel ;
   - accès aux notifications ;
   - action « Ajouter une dépense ».

2. **Indicateurs principaux**
   - dépenses du mois ;
   - budget alimentaire consommé / budget défini ;
   - dépenses communes ;
   - dépenses personnelles de l'utilisateur connecté.

   Chaque indicateur précise sa période et son périmètre. Les montants privés de l'autre membre ne sont jamais exposés.

3. **Suivi des budgets**
   - progression de chaque budget ;
   - montant consommé et plafond ;
   - alerte lorsque le seuil configuré est atteint ;
   - accès au détail.

4. **Répartition des dépenses**
   - graphique simple par catégorie ;
   - bascule dépenses communes / personnelles ;
   - accès à la liste filtrée correspondante.

5. **Activité récente**
   - date, libellé, catégorie, montant et caractère personnel/commun ;
   - accès au détail de la transaction.

6. **À venir**
   - prochaines occurrences récurrentes ;
   - prévisions manuelles ;
   - échéances nécessitant une confirmation de montant.

7. **Répartition mensuelle**
   - état du calcul : non préparé, prévisualisation ou définitif ;
   - accès au détail des charges et parts ;
   - indication claire de la date du dernier calcul définitif.

### 4.3 Wireframe fonctionnel — Desktop

```text
┌──────────────────┬────────────────────────────────────────────────────┐
│ LOGO             │ Foyer  /  Novembre 2026       Notifications  +      │
│                  ├────────────────────────────────────────────────────┤
│ Vue d'ensemble   │ Vue d'ensemble du foyer                            │
│ Transactions    │                                                     │
│ Budgets          │ ┌────────────┐ ┌────────────┐ ┌────────────┐       │
│ Récurrences      │ │ Dépenses   │ │ Budget     │ │ Dépenses   │       │
│ Répartition      │ │ du mois    │ │ alimentaire│ │ communes   │       │
│ Revenus          │ └────────────┘ └────────────┘ └────────────┘       │
│ Historique       │                                                     │
│ Paramètres       │ ┌────────────────────────┐ ┌─────────────────────┐ │
│                  │ │ Suivi des budgets      │ │ Dépenses par        │ │
│ Foyer / Perso    │ │                        │ │ catégorie           │ │
│                  │ └────────────────────────┘ └─────────────────────┘ │
│                  │                                                     │
│                  │ ┌────────────────────────┐ ┌─────────────────────┐ │
│                  │ │ Activité récente       │ │ À venir             │ │
│                  │ └────────────────────────┘ └─────────────────────┘ │
│                  │                                                     │
│                  │ ┌────────────────────────────────────────────────┐ │
│                  │ │ Répartition mensuelle                          │ │
│                  │ └────────────────────────────────────────────────┘ │
└──────────────────┴────────────────────────────────────────────────────┘
```

Le wireframe fixe l'ordre de lecture, pas les dimensions finales ni le style graphique.

## 5. Écrans fonctionnels à concevoir

| Écran | Contenu principal | Actions prioritaires |
|---|---|---|
| Connexion / invitation | Formulaire simple, état d'invitation | Se connecter, accepter une invitation |
| Vue d'ensemble | Indicateurs, budgets, graphiques, activité | Ajouter une dépense, changer de contexte |
| Transactions | Liste filtrable, recherche, filtres de période | Ajouter, modifier, consulter |
| Détail transaction | Montant, date, catégorie, payeur, visibilité, remboursements | Modifier, ajouter un remboursement |
| Formulaire dépense | Montant, libellé, date, catégorie, périmètre, payeur | Enregistrer |
| Budgets | Enveloppes, progression, historique | Créer et ajuster un budget |
| Budget alimentaire | Plafond partagé et consommation mensuelle | Ajouter une dépense, consulter l'historique |
| Récurrences | Dépenses récurrentes et prochaines occurrences | Créer, suspendre, confirmer un montant |
| Revenus | Revenus de référence et paramètres de confidentialité | Déclarer, modifier, régler la visibilité |
| Répartition | Prévisualisation, charges, règles et parts | Simuler, finaliser, corriger avec motif |
| Historique | Périodes passées et snapshots | Consulter, comparer |
| Paramètres | Profil, foyer, membres, préférences, notifications | Modifier les paramètres autorisés |

## 6. Comportements et composants communs

- Sélecteur de période cohérent sur les vues financières.
- Sélecteur de contexte Foyer / Personnel.
- Filtres persistants pendant la navigation lorsque cela est pertinent.
- Formulaires avec validation immédiate et messages d'erreur proches du champ.
- Confirmation pour les suppressions et opérations irréversibles.
- États de chargement, vide, erreur et hors ligne systématiques.
- Formats localisés : euros, dates françaises et séparateurs français.
- Graphiques accompagnés d'une alternative textuelle ou tabulaire.
- Les actions sensibles indiquent clairement leur portée et leur conséquence.

## 7. Confidentialité dans l'interface

L'interface ne doit jamais déduire qu'une donnée est visible parce qu'elle est présente dans le navigateur.

- Le backend décide des champs accessibles.
- Le frontend masque les blocs non autorisés et gère les champs absents.
- Ne pas afficher de revenu exact privé dans un graphique agrégé si cela permet de le déduire.
- La visibilité d'un montant alloué et d'un pourcentage d'allocation suit les préférences dédiées.
- Le contexte Foyer / Personnel ne modifie pas les autorisations serveur.

## 8. Responsive et accessibilité

- Mobile : largeur cible à partir de 360 px.
- Tablette : mise en page intermédiaire, navigation adaptée.
- Desktop : largeur confortable, navigation latérale.
- Cibles tactiles d'au moins 44 px lorsque possible.
- Navigation clavier et focus visible.
- Labels explicites et erreurs associées aux champs.
- Contrastes conformes aux recommandations WCAG 2.2 AA autant que possible.
- Ne jamais transmettre une information uniquement par la couleur.

## 9. Jeu de données de démonstration

La maquette utilisera uniquement des données fictives et cohérentes entre les écrans.

Exemples de catégories :
- Alimentation
- Logement
- Énergie
- Transport
- Santé
- Enfant
- Loisirs
- Abonnements
- Divers

Les exemples de revenus, dépenses et personnes sont fictifs et ne doivent pas être repris comme valeurs par défaut de production.

## 10. Ordre de réalisation de la maquette

1. Shell applicatif : navigation desktop/mobile, en-tête et contexte.
2. Tableau de bord foyer avec données fictives.
3. Tableau de bord personnel.
4. Liste, formulaire et détail d'une transaction.
5. Budgets et budget alimentaire.
6. Récurrences.
7. Revenus et confidentialité.
8. Répartition et historique.
9. Paramètres.
10. Revue responsive, accessibilité et cohérence des parcours.

La maquette est une interface de démonstration navigable, sans authentification réelle ni persistance métier. Elle ne doit pas appeler l'API backend.

---

**Fin — UX_DESIGN.md v0.1**
