# Guide des États de Contrôle - États Financiers SYSCOHADA

## Vue d'Ensemble

Le système génère automatiquement 6 états de contrôle exhaustifs pour garantir la fiabilité et la cohérence des états financiers produits.

## 1. Statistiques de Couverture 📊

### Objectif
Mesurer le taux d'intégration des comptes de la balance dans les états financiers.

### Indicateurs
- **Comptes intégrés** : Nombre de comptes reconnus et intégrés
- **Comptes non intégrés** : Nombre de comptes non reconnus
- **Taux de couverture** : Pourcentage de comptes intégrés

### Interprétation
- **≥ 95%** : ✅ Excellent (badge vert)
- **80-94%** : ⚠️ Acceptable (badge orange)
- **< 80%** : ❌ Insuffisant (badge rouge)

### Actions Correctives
- Vérifier le tableau de correspondance
- Ajouter les racines de comptes manquantes
- Contrôler la codification des comptes

---

## 2. Équilibre du Bilan ⚖️

### Objectif
Vérifier que le bilan est équilibré (Actif = Passif).

### Contrôles
- **Total Actif** : Somme de tous les postes d'actif
- **Total Passif** : Somme de tous les postes de passif
- **Différence** : Actif - Passif
- **Pourcentage d'écart** : (Différence / Actif) × 100

### Seuil de Tolérance
- **< 0,01** : ✅ Équilibré
- **≥ 0,01** : ❌ Déséquilibré

### Causes Possibles de Déséquilibre
1. Comptes avec sens inversé
2. Comptes non intégrés
3. Erreurs de saisie dans la balance
4. Mauvaise application du sens débit/crédit

---

## 3. Cohérence Résultat (Bilan vs Compte de Résultat) 💰

### Objectif
Vérifier que le résultat calculé par le compte de résultat correspond au résultat du bilan.

### Formules
- **Résultat CR** : Produits - Charges
- **Résultat Bilan** : Actif - Passif
- **Différence** : Résultat CR - Résultat Bilan

### Interprétation
- **Différence < 0,01** : ✅ Cohérent
- **Différence ≥ 0,01** : ⚠️ Incohérent

### Causes Possibles d'Incohérence
1. Résultat non affecté au bilan (compte 13)
2. Comptes de gestion mal classés
3. Comptes de bilan mal classés
4. Erreurs dans le tableau de correspondance

---

## 4. Comptes Non Intégrés ⚠️

### Objectif
Identifier les comptes de la balance qui n'ont pas été intégrés dans les états financiers.

### Informations Affichées
| Colonne | Description |
|---------|-------------|
| N° Compte | Numéro du compte |
| Intitulé | Libellé du compte |
| Classe | Première lettre du compte (1-8) |
| Solde Débit | Montant au débit |
| Solde Crédit | Montant au crédit |
| Solde Net | Débit - Crédit |
| Raison | Cause de la non-intégration |

### Impact
- **Montant total** : Somme des valeurs absolues des soldes nets
- **Pourcentage de l'actif** : Impact relatif sur le total actif

### Actions Correctives
1. Vérifier la codification du compte
2. Ajouter la racine dans `correspondances_syscohada.json`
3. Vérifier si le compte doit être intégré
4. Contrôler la cohérence avec le plan comptable SYSCOHADA

---

## 5. Comptes avec Sens Inversé 🔄

### Objectif
Détecter les comptes ayant un solde contraire au sens normal de leur classe.

### Sens Normal par Classe
| Classe | Sens Normal | Description |
|--------|-------------|-------------|
| 1 | Crédit | Capitaux propres et dettes |
| 2 | Débit | Immobilisations |
| 3 | Débit | Stocks |
| 4 | Variable | Comptes de tiers (mixte) |
| 5 | Débit | Trésorerie |
| 6 | Débit | Charges |
| 7 | Crédit | Produits |
| 8 | Variable | Comptes spéciaux |

### Informations Affichées
- N° Compte
- Intitulé
- Classe
- Sens Attendu
- Sens Réel (en rouge)
- Solde Net

### Interprétation
Un compte avec sens inversé peut indiquer :
- Une erreur de saisie
- Une opération exceptionnelle
- Un compte de régularisation
- Une anomalie comptable

### Actions
1. Vérifier la nature de l'opération
2. Contrôler les écritures comptables
3. Valider avec le comptable si nécessaire

---

## 6. Comptes Créant un Déséquilibre ⚠️

### Objectif
Identifier les comptes qui créent un déséquilibre en raison d'un sens incorrect pour leur section.

### Règles de Sens par Section

#### Bilan Actif
- **Sens attendu** : Débit (positif)
- **Problème** : Solde créditeur sur un compte d'actif

#### Bilan Passif
- **Sens attendu** : Crédit (négatif)
- **Problème** : Solde débiteur sur un compte de passif

#### Charges
- **Sens attendu** : Débit (positif)
- **Problème** : Solde créditeur sur un compte de charges

#### Produits
- **Sens attendu** : Crédit (négatif)
- **Problème** : Solde débiteur sur un compte de produits

### Informations Affichées
- N° Compte
- Intitulé
- Section
- Problème (description)
- Solde

### Impact
Ces comptes créent un déséquilibre car leur sens est contraire à celui attendu pour leur section, ce qui fausse les totaux.

### Actions Correctives
1. Vérifier la classification du compte
2. Contrôler les écritures comptables
3. Vérifier le tableau de correspondance
4. Corriger la balance si nécessaire

---

## Utilisation des États de Contrôle

### Workflow Recommandé

1. **Génération des états**
   - Taper "Etat fin"
   - Sélectionner le fichier Balance Excel
   - Consulter les états de contrôle en premier

2. **Analyse des contrôles**
   - Vérifier le taux de couverture (objectif : ≥ 95%)
   - Contrôler l'équilibre du bilan
   - Vérifier la cohérence du résultat

3. **Traitement des anomalies**
   - Examiner les comptes non intégrés
   - Analyser les comptes avec sens inversé
   - Corriger les comptes en déséquilibre

4. **Validation**
   - Tous les contrôles au vert
   - Taux de couverture satisfaisant
   - Équilibres respectés

### Seuils de Qualité

| Indicateur | Excellent | Acceptable | Insuffisant |
|------------|-----------|------------|-------------|
| Taux de couverture | ≥ 95% | 80-94% | < 80% |
| Équilibre bilan | < 0,01 | 0,01-0,1 | > 0,1 |
| Cohérence résultat | < 0,01 | 0,01-0,1 | > 0,1 |
| Comptes non intégrés | 0-5 | 6-20 | > 20 |

---

## Exemples de Corrections

### Exemple 1 : Compte Non Intégré

**Problème** : Compte 2154000 "Matériel informatique" non intégré

**Solution** :
1. Ouvrir `py_backend/correspondances_syscohada.json`
2. Trouver le poste AM "Matériel"
3. Ajouter la racine "2154" si manquante
4. Relancer le traitement

### Exemple 2 : Sens Inversé

**Problème** : Compte 401 "Fournisseurs" avec solde débiteur

**Analyse** :
- Classe 4 (Tiers) : sens variable
- Solde débiteur = avance versée au fournisseur
- Situation normale si avance réelle

**Action** : Vérifier la nature de l'opération

### Exemple 3 : Déséquilibre

**Problème** : Compte 211 "Frais de développement" avec solde créditeur

**Analyse** :
- Compte d'actif avec solde créditeur
- Crée un déséquilibre au bilan

**Solution** :
- Vérifier les écritures comptables
- Corriger la balance si erreur de saisie

---

## Fichiers Concernés

- `py_backend/etats_financiers.py` : Logique de contrôle
- `py_backend/correspondances_syscohada.json` : Tableau de correspondance
- `public/EtatFinAutoTrigger.js` : Affichage des contrôles

## Date de Création
22 mars 2026
