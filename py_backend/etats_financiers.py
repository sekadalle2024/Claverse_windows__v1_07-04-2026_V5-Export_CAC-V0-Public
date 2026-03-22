import pandas as pd
import numpy as np
import os
import json
import base64
import io
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import re

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("etats_financiers")

# Router FastAPI pour l'API États Financiers
router = APIRouter(prefix="/etats-financiers", tags=["États Financiers"])


# ==================== MODÈLES PYDANTIC ====================

class ExcelUploadRequest(BaseModel):
    """Requête avec fichier Excel encodé en base64"""
    file_base64: str
    filename: str

class EtatsFinanciersResponse(BaseModel):
    success: bool
    message: str
    results: Optional[Dict[str, Any]] = None
    html: Optional[str] = None


# ==================== FONCTIONS UTILITAIRES ====================

def clean_number(value) -> float:
    """Nettoie et convertit une valeur en float"""
    if pd.isna(value) or value == '' or value is None:
        return 0.0
    try:
        cleaned = str(value).replace(' ', '').replace(',', '.')
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0

def format_number(x: float) -> str:
    """Formate un nombre avec séparateurs de milliers"""
    try:
        return f"{x:,.2f}".replace(',', ' ').replace('.', ',')
    except:
        return str(x)


def load_tableau_correspondance(file_path: str = "correspondances_syscohada.json") -> Dict[str, List[Dict]]:
    """
    Charge le tableau de correspondance postes/comptes depuis un fichier JSON.
    Retourne un dictionnaire avec les sections : bilan_actif, bilan_passif, charges, produits
    """
    # Vérifier si le fichier existe
    if not os.path.exists(file_path):
        # Essayer avec le chemin absolu depuis la racine
        alt_path = os.path.join(os.path.dirname(__file__), file_path)
        if os.path.exists(alt_path):
            file_path = alt_path
        else:
            logger.error(f"❌ Fichier non trouvé: {file_path}")
            logger.error(f"❌ Chemin alternatif non trouvé: {alt_path}")
            logger.error(f"❌ Répertoire courant: {os.getcwd()}")
            raise FileNotFoundError(f"Tableau de correspondance non trouvé: {file_path}")
    
    logger.info(f"📂 Chargement du tableau de correspondance: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            correspondances = json.load(f)
        
        # Afficher les statistiques
        logger.info(f"✅ Correspondances chargées depuis JSON:")
        logger.info(f"   - Bilan Actif: {len(correspondances['bilan_actif'])} postes")
        logger.info(f"   - Bilan Passif: {len(correspondances['bilan_passif'])} postes")
        logger.info(f"   - Charges: {len(correspondances['charges'])} postes")
        logger.info(f"   - Produits: {len(correspondances['produits'])} postes")
        
        return correspondances
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du chargement du tableau: {e}")
        raise


def match_compte_to_poste(compte: str, correspondances: List[Dict]) -> Optional[Dict]:
    """
    Trouve le poste correspondant à un compte donné.
    Le compte peut avoir 6 à 8 chiffres.
    """
    compte = str(compte).strip()
    
    for poste in correspondances:
        for racine in poste['racines']:
            if compte.startswith(racine):
                return poste
    
    return None


def process_balance_to_etats_financiers(balance_df: pd.DataFrame, correspondances: Dict) -> Dict[str, Any]:
    """
    Traite une balance comptable et génère les états financiers avec contrôles exhaustifs.
    """
    logger.info("📊 Traitement de la balance pour états financiers")
    
    # Détecter les colonnes de la balance
    col_map = detect_balance_columns(balance_df)
    
    if col_map['numero'] is None:
        raise ValueError("Colonne 'Numéro' non trouvée dans la balance")
    
    # Initialiser les résultats et contrôles
    results = {
        'bilan_actif': {},
        'bilan_passif': {},
        'charges': {},
        'produits': {}
    }
    
    # Structures de contrôle
    controles = {
        'comptes_non_integres': [],  # Comptes non reconnus
        'comptes_sens_inverse': [],  # Comptes avec sens débit/crédit inversé
        'comptes_desequilibre': [],  # Comptes créant un déséquilibre
        'statistiques': {
            'total_comptes_balance': 0,
            'comptes_integres': 0,
            'comptes_non_integres': 0,
            'taux_couverture': 0.0
        }
    }
    
    # Définir les sens normaux des comptes par classe
    sens_normal_comptes = {
        '1': 'credit',  # Capitaux
        '2': 'debit',   # Immobilisations
        '3': 'debit',   # Stocks
        '4': 'variable', # Tiers (mixte)
        '5': 'debit',   # Trésorerie
        '6': 'debit',   # Charges
        '7': 'credit',  # Produits
        '8': 'variable' # Comptes spéciaux
    }
    
    # Traiter chaque ligne de la balance
    for idx, row in balance_df.iterrows():
        numero = str(row.get(col_map['numero'], '')).strip()
        if not numero or numero == 'nan' or not numero[0].isdigit():
            continue
        
        controles['statistiques']['total_comptes_balance'] += 1
        
        intitule = str(row.get(col_map['intitule'], '')).strip() if col_map['intitule'] else ''
        
        # Calculer le solde net
        solde_debit = clean_number(row.get(col_map['solde_debit'], 0)) if col_map['solde_debit'] else 0
        solde_credit = clean_number(row.get(col_map['solde_credit'], 0)) if col_map['solde_credit'] else 0
        solde_net = solde_debit - solde_credit
        
        # Vérifier le sens du compte
        classe = numero[0]
        sens_attendu = sens_normal_comptes.get(classe, 'variable')
        sens_reel = 'debit' if solde_net > 0 else 'credit' if solde_net < 0 else 'nul'
        
        # Détecter les sens inversés (sauf pour les comptes variables)
        if sens_attendu != 'variable' and sens_reel != 'nul' and sens_reel != sens_attendu:
            controles['comptes_sens_inverse'].append({
                'numero': numero,
                'intitule': intitule,
                'classe': classe,
                'sens_attendu': sens_attendu,
                'sens_reel': sens_reel,
                'solde_debit': solde_debit,
                'solde_credit': solde_credit,
                'solde_net': solde_net
            })
        
        # Chercher correspondance dans chaque section
        compte_integre = False
        for section_name, section_correspondances in correspondances.items():
            poste = match_compte_to_poste(numero, section_correspondances)
            if poste:
                ref = poste['ref']
                if ref not in results[section_name]:
                    results[section_name][ref] = {
                        'ref': ref,
                        'libelle': poste['libelle'],
                        'montant': 0,
                        'comptes': []
                    }
                
                # Appliquer le sens correct selon la section
                montant_a_ajouter = solde_net
                
                # Pour le bilan : Actif en débit positif, Passif en crédit positif
                if section_name == 'bilan_actif':
                    # L'actif doit être en débit (positif)
                    if solde_net < 0:
                        controles['comptes_desequilibre'].append({
                            'numero': numero,
                            'intitule': intitule,
                            'section': 'Bilan Actif',
                            'probleme': 'Solde créditeur sur un compte d\'actif',
                            'solde': solde_net
                        })
                
                elif section_name == 'bilan_passif':
                    # Le passif doit être en crédit (négatif), on inverse le signe
                    montant_a_ajouter = -solde_net
                    if solde_net > 0:
                        controles['comptes_desequilibre'].append({
                            'numero': numero,
                            'intitule': intitule,
                            'section': 'Bilan Passif',
                            'probleme': 'Solde débiteur sur un compte de passif',
                            'solde': solde_net
                        })
                
                elif section_name == 'charges':
                    # Les charges doivent être en débit (positif)
                    if solde_net < 0:
                        controles['comptes_desequilibre'].append({
                            'numero': numero,
                            'intitule': intitule,
                            'section': 'Charges',
                            'probleme': 'Solde créditeur sur un compte de charges',
                            'solde': solde_net
                        })
                
                elif section_name == 'produits':
                    # Les produits doivent être en crédit (négatif), on inverse le signe
                    montant_a_ajouter = -solde_net
                    if solde_net > 0:
                        controles['comptes_desequilibre'].append({
                            'numero': numero,
                            'intitule': intitule,
                            'section': 'Produits',
                            'probleme': 'Solde débiteur sur un compte de produits',
                            'solde': solde_net
                        })
                
                results[section_name][ref]['montant'] += montant_a_ajouter
                results[section_name][ref]['comptes'].append({
                    'numero': numero,
                    'intitule': intitule,
                    'solde': solde_net,
                    'montant_integre': montant_a_ajouter
                })
                
                compte_integre = True
                controles['statistiques']['comptes_integres'] += 1
                break  # Un compte ne peut être que dans une section
        
        # Si le compte n'a pas été intégré
        if not compte_integre and abs(solde_net) > 0.01:  # Ignorer les soldes quasi-nuls
            controles['comptes_non_integres'].append({
                'numero': numero,
                'intitule': intitule,
                'classe': classe,
                'solde_debit': solde_debit,
                'solde_credit': solde_credit,
                'solde_net': solde_net,
                'raison': 'Codification non reconnue dans le tableau de correspondance'
            })
            controles['statistiques']['comptes_non_integres'] += 1
    
    # Calculer les totaux
    total_actif = sum(poste['montant'] for poste in results['bilan_actif'].values())
    total_passif = sum(poste['montant'] for poste in results['bilan_passif'].values())
    total_charges = sum(poste['montant'] for poste in results['charges'].values())
    total_produits = sum(poste['montant'] for poste in results['produits'].values())
    resultat_net_cr = total_produits - total_charges
    
    # Calculer le taux de couverture
    if controles['statistiques']['total_comptes_balance'] > 0:
        controles['statistiques']['taux_couverture'] = (
            controles['statistiques']['comptes_integres'] / 
            controles['statistiques']['total_comptes_balance'] * 100
        )
    
    # Contrôles d'équilibre
    controles['equilibre_bilan'] = {
        'actif': total_actif,
        'passif': total_passif,
        'difference': total_actif - total_passif,
        'equilibre': abs(total_actif - total_passif) < 0.01,
        'pourcentage_ecart': abs((total_actif - total_passif) / total_actif * 100) if total_actif != 0 else 0
    }
    
    controles['equilibre_resultat'] = {
        'resultat_cr': resultat_net_cr,
        'resultat_bilan': total_actif - total_passif,
        'difference': resultat_net_cr - (total_actif - total_passif),
        'equilibre': abs(resultat_net_cr - (total_actif - total_passif)) < 0.01
    }
    
    # Contrôle spécifique : Hypothèse d'affectation du résultat
    # Ce contrôle vérifie si l'affectation du résultat au passif équilibrerait le bilan
    passif_avec_resultat = total_passif + resultat_net_cr
    difference_apres_affectation = total_actif - passif_avec_resultat
    
    controles['hypothese_affectation_resultat'] = {
        'resultat_net': resultat_net_cr,
        'passif_avant_affectation': total_passif,
        'passif_apres_affectation': passif_avec_resultat,
        'actif': total_actif,
        'difference_avant': total_actif - total_passif,
        'difference_apres': difference_apres_affectation,
        'equilibre_apres_affectation': abs(difference_apres_affectation) < 0.01,
        'recommandation': 'Affecter le résultat au passif (compte 13)' if abs(difference_apres_affectation) < 0.01 else 'Vérifier les écritures comptables',
        'type_resultat': 'Bénéfice' if resultat_net_cr > 0 else 'Perte' if resultat_net_cr < 0 else 'Nul'
    }
    
    # Impact des comptes non intégrés
    montant_non_integre = sum(abs(c['solde_net']) for c in controles['comptes_non_integres'])
    controles['impact_non_integres'] = {
        'montant_total': montant_non_integre,
        'pourcentage_actif': (montant_non_integre / total_actif * 100) if total_actif != 0 else 0
    }
    
    logger.info(f"✅ États financiers calculés:")
    logger.info(f"   - Total Actif: {format_number(total_actif)}")
    logger.info(f"   - Total Passif: {format_number(total_passif)}")
    logger.info(f"   - Total Charges: {format_number(total_charges)}")
    logger.info(f"   - Total Produits: {format_number(total_produits)}")
    logger.info(f"   - Résultat Net: {format_number(resultat_net_cr)}")
    logger.info(f"   - Comptes intégrés: {controles['statistiques']['comptes_integres']}/{controles['statistiques']['total_comptes_balance']}")
    logger.info(f"   - Taux de couverture: {controles['statistiques']['taux_couverture']:.1f}%")
    
    return {
        'bilan_actif': results['bilan_actif'],
        'bilan_passif': results['bilan_passif'],
        'charges': results['charges'],
        'produits': results['produits'],
        'totaux': {
            'actif': total_actif,
            'passif': total_passif,
            'charges': total_charges,
            'produits': total_produits,
            'resultat_net': resultat_net_cr
        },
        'controles': controles
    }


def detect_balance_columns(df: pd.DataFrame) -> Dict[str, str]:
    """Détecte automatiquement les colonnes de balance"""
    columns = df.columns.tolist()
    columns_lower = [str(c).lower().strip() for c in columns]
    
    mapping = {
        'numero': None,
        'intitule': None,
        'solde_debit': None,
        'solde_credit': None
    }
    
    for idx, col in enumerate(columns_lower):
        original_col = columns[idx]
        
        if 'numéro' in col or 'numero' in col or col == 'n°' or 'compte' in col:
            if mapping['numero'] is None:
                mapping['numero'] = original_col
        
        if 'intitulé' in col or 'intitule' in col or 'libellé' in col or 'libelle' in col:
            if mapping['intitule'] is None:
                mapping['intitule'] = original_col
        
        if 'solde' in col and 'débit' in col:
            mapping['solde_debit'] = original_col
        elif 'solde' in col and 'debit' in col:
            mapping['solde_debit'] = original_col
        
        if 'solde' in col and 'crédit' in col:
            mapping['solde_credit'] = original_col
        elif 'solde' in col and 'credit' in col:
            mapping['solde_credit'] = original_col
    
    logger.info(f"🔍 Colonnes détectées: {mapping}")
    return mapping


def generate_etats_financiers_html(results: Dict[str, Any]) -> str:
    """
    Génère le HTML des accordéons pour afficher les états financiers et les contrôles.
    """
    totaux = results['totaux']
    controles = results.get('controles', {})
    
    # Style CSS
    html = """
    <style>
    .etats-fin-container {
        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
        max-width: 100%;
        margin: 16px 0;
    }
    .etats-fin-header {
        background: linear-gradient(135deg, #1e3a8a, #3b82f6);
        color: white;
        padding: 20px;
        border-radius: 12px 12px 0 0;
        text-align: center;
    }
    .etats-fin-header h2 { margin: 0 0 8px 0; font-size: 22px; }
    .etats-fin-header p { margin: 0; opacity: 0.9; font-size: 16px; }
    
    .etats-fin-section {
        margin: 16px 0;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        overflow: hidden;
    }
    .section-header-ef {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 14px 18px;
        background: #f8f9fa;
        cursor: pointer;
        font-weight: 600;
        font-size: 17px;
        transition: background 0.2s;
    }
    .section-header-ef:hover { background: #e9ecef; }
    .section-header-ef.active { background: #dee2e6; }
    .section-header-ef .arrow {
        transition: transform 0.3s;
        font-size: 18px;
    }
    .section-header-ef.active .arrow { transform: rotate(90deg); }
    
    .section-content-ef {
        max-height: 0;
        overflow: hidden;
        transition: max-height 0.3s ease-out;
        background: white;
    }
    .section-content-ef.active { max-height: 5000px; }
    
    .poste-item {
        padding: 10px 18px;
        border-bottom: 1px solid #f0f0f0;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .poste-item:last-child { border-bottom: none; }
    .poste-ref { font-weight: 600; color: #1e3a8a; min-width: 50px; }
    .poste-libelle { flex: 1; padding: 0 16px; }
    .poste-montant { font-family: 'Consolas', monospace; font-weight: 600; color: #059669; }
    
    .total-section {
        background: #f0f9ff;
        padding: 14px 18px;
        border-top: 2px solid #3b82f6;
        font-weight: 700;
        font-size: 16px;
        display: flex;
        justify-content: space-between;
    }
    .total-section.resultat {
        background: #ecfdf5;
        border-top-color: #059669;
    }
    .total-section.resultat.negatif {
        background: #fef2f2;
        border-top-color: #dc2626;
    }
    
    /* Styles pour les contrôles */
    .controle-section {
        margin: 16px 0;
        border: 2px solid #f59e0b;
        border-radius: 8px;
        overflow: hidden;
    }
    .controle-header {
        background: linear-gradient(135deg, #f59e0b, #d97706);
        color: white;
        padding: 16px 18px;
        font-weight: 700;
        font-size: 18px;
    }
    .controle-item {
        padding: 12px 18px;
        border-bottom: 1px solid #fef3c7;
        background: #fffbeb;
    }
    .controle-item:last-child { border-bottom: none; }
    .controle-item.ok {
        background: #f0fdf4;
        border-bottom-color: #dcfce7;
    }
    .controle-item.warning {
        background: #fef3c7;
        border-bottom-color: #fde68a;
    }
    .controle-item.error {
        background: #fee2e2;
        border-bottom-color: #fecaca;
    }
    .controle-label {
        font-weight: 600;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .controle-value {
        font-family: 'Consolas', monospace;
        font-size: 14px;
    }
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge.success { background: #dcfce7; color: #166534; }
    .badge.warning { background: #fef3c7; color: #92400e; }
    .badge.error { background: #fee2e2; color: #991b1b; }
    
    .compte-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 8px;
        font-size: 13px;
    }
    .compte-table th {
        background: #f3f4f6;
        padding: 8px;
        text-align: left;
        font-weight: 600;
        border-bottom: 2px solid #d1d5db;
    }
    .compte-table td {
        padding: 6px 8px;
        border-bottom: 1px solid #e5e7eb;
    }
    .compte-table tr:last-child td { border-bottom: none; }
    .compte-table tr:hover { background: #f9fafb; }
    </style>
    """
    
    html += f"""
    <div class="etats-fin-container">
        <div class="etats-fin-header">
            <h2>📊 États Financiers SYSCOHADA Révisé</h2>
            <p>Bilan et Compte de Résultat</p>
        </div>
    """
    
    # ÉTATS DE CONTRÔLE EN PREMIER
    html += generate_controles_html(controles, totaux)
    
    # Bilan Actif
    html += generate_section_html(
        "bilan_actif",
        "🏢 BILAN - ACTIF",
        results['bilan_actif'],
        totaux['actif']
    )
    
    # Bilan Passif
    html += generate_section_html(
        "bilan_passif",
        "🏛️ BILAN - PASSIF",
        results['bilan_passif'],
        totaux['passif']
    )
    
    # Compte de Résultat - Charges
    html += generate_section_html(
        "charges",
        "📉 COMPTE DE RÉSULTAT - CHARGES",
        results['charges'],
        totaux['charges']
    )
    
    # Compte de Résultat - Produits
    html += generate_section_html(
        "produits",
        "📈 COMPTE DE RÉSULTAT - PRODUITS",
        results['produits'],
        totaux['produits']
    )
    
    # Résultat Net
    resultat_class = "resultat" if totaux['resultat_net'] >= 0 else "resultat negatif"
    resultat_label = "BÉNÉFICE" if totaux['resultat_net'] >= 0 else "PERTE"
    html += f"""
        <div class="total-section {resultat_class}">
            <span>💰 RÉSULTAT NET ({resultat_label})</span>
            <span>{format_number(abs(totaux['resultat_net']))}</span>
        </div>
    </div>
    """
    
    return html


def generate_controles_html(controles: Dict, totaux: Dict) -> str:
    """Génère le HTML des états de contrôle"""
    if not controles:
        return ''
    
    html = """
    <div class="controle-section">
        <div class="controle-header">
            🔍 ÉTATS DE CONTRÔLE
        </div>
    """
    
    # 1. Statistiques générales
    stats = controles.get('statistiques', {})
    taux = stats.get('taux_couverture', 0)
    badge_class = 'success' if taux >= 95 else 'warning' if taux >= 80 else 'error'
    
    html += f"""
        <div class="controle-item ok">
            <div class="controle-label">
                📊 Statistiques de Couverture
                <span class="badge {badge_class}">{taux:.1f}%</span>
            </div>
            <div class="controle-value">
                Comptes intégrés: {stats.get('comptes_integres', 0)} / {stats.get('total_comptes_balance', 0)}
                <br>Comptes non intégrés: {stats.get('comptes_non_integres', 0)}
            </div>
        </div>
    """
    
    # 2. Équilibre du Bilan
    eq_bilan = controles.get('equilibre_bilan', {})
    equilibre_ok = eq_bilan.get('equilibre', False)
    badge_class = 'success' if equilibre_ok else 'error'
    item_class = 'ok' if equilibre_ok else 'error'
    
    html += f"""
        <div class="controle-item {item_class}">
            <div class="controle-label">
                ⚖️ Équilibre du Bilan
                <span class="badge {badge_class}">{'✓ Équilibré' if equilibre_ok else '✗ Déséquilibré'}</span>
            </div>
            <div class="controle-value">
                Total Actif: {format_number(eq_bilan.get('actif', 0))}
                <br>Total Passif: {format_number(eq_bilan.get('passif', 0))}
                <br>Différence: {format_number(eq_bilan.get('difference', 0))}
                {f"<br>Écart: {eq_bilan.get('pourcentage_ecart', 0):.2f}%" if not equilibre_ok else ''}
            </div>
        </div>
    """
    
    # 3. Équilibre Résultat
    eq_res = controles.get('equilibre_resultat', {})
    equilibre_res_ok = eq_res.get('equilibre', False)
    badge_class = 'success' if equilibre_res_ok else 'warning'
    item_class = 'ok' if equilibre_res_ok else 'warning'
    
    html += f"""
        <div class="controle-item {item_class}">
            <div class="controle-label">
                💰 Cohérence Résultat (Bilan vs Compte de Résultat)
                <span class="badge {badge_class}">{'✓ Cohérent' if equilibre_res_ok else '⚠ Incohérent'}</span>
            </div>
            <div class="controle-value">
                Résultat Compte de Résultat: {format_number(eq_res.get('resultat_cr', 0))}
                <br>Résultat Bilan (Actif - Passif): {format_number(eq_res.get('resultat_bilan', 0))}
                <br>Différence: {format_number(eq_res.get('difference', 0))}
            </div>
        </div>
    """
    
    # 4. Comptes non intégrés
    comptes_ni = controles.get('comptes_non_integres', [])
    if comptes_ni:
        impact = controles.get('impact_non_integres', {})
        html += f"""
        <div class="controle-item warning">
            <div class="controle-label">
                ⚠️ Comptes Non Intégrés
                <span class="badge warning">{len(comptes_ni)} compte(s)</span>
            </div>
            <div class="controle-value">
                Impact total: {format_number(impact.get('montant_total', 0))}
                ({impact.get('pourcentage_actif', 0):.2f}% de l'actif)
            </div>
            <table class="compte-table">
                <thead>
                    <tr>
                        <th>N° Compte</th>
                        <th>Intitulé</th>
                        <th>Classe</th>
                        <th>Solde Débit</th>
                        <th>Solde Crédit</th>
                        <th>Solde Net</th>
                        <th>Raison</th>
                    </tr>
                </thead>
                <tbody>
        """
        for compte in comptes_ni[:20]:  # Limiter à 20 pour la lisibilité
            html += f"""
                    <tr>
                        <td>{compte['numero']}</td>
                        <td>{compte['intitule'][:40]}</td>
                        <td>{compte['classe']}</td>
                        <td>{format_number(compte['solde_debit'])}</td>
                        <td>{format_number(compte['solde_credit'])}</td>
                        <td>{format_number(compte['solde_net'])}</td>
                        <td style="font-size: 11px;">{compte['raison']}</td>
                    </tr>
            """
        if len(comptes_ni) > 20:
            html += f"""
                    <tr>
                        <td colspan="7" style="text-align: center; font-style: italic;">
                            ... et {len(comptes_ni) - 20} autre(s) compte(s)
                        </td>
                    </tr>
            """
        html += """
                </tbody>
            </table>
        </div>
        """
    
    # 5. Comptes avec sens inversé
    comptes_si = controles.get('comptes_sens_inverse', [])
    if comptes_si:
        html += f"""
        <div class="controle-item warning">
            <div class="controle-label">
                🔄 Comptes avec Sens Inversé
                <span class="badge warning">{len(comptes_si)} compte(s)</span>
            </div>
            <div class="controle-value">
                Comptes ayant un solde contraire au sens normal de leur classe
            </div>
            <table class="compte-table">
                <thead>
                    <tr>
                        <th>N° Compte</th>
                        <th>Intitulé</th>
                        <th>Classe</th>
                        <th>Sens Attendu</th>
                        <th>Sens Réel</th>
                        <th>Solde Net</th>
                    </tr>
                </thead>
                <tbody>
        """
        for compte in comptes_si[:15]:
            html += f"""
                    <tr>
                        <td>{compte['numero']}</td>
                        <td>{compte['intitule'][:40]}</td>
                        <td>{compte['classe']}</td>
                        <td>{compte['sens_attendu'].upper()}</td>
                        <td style="color: #dc2626; font-weight: 600;">{compte['sens_reel'].upper()}</td>
                        <td>{format_number(compte['solde_net'])}</td>
                    </tr>
            """
        if len(comptes_si) > 15:
            html += f"""
                    <tr>
                        <td colspan="6" style="text-align: center; font-style: italic;">
                            ... et {len(comptes_si) - 15} autre(s) compte(s)
                        </td>
                    </tr>
            """
        html += """
                </tbody>
            </table>
        </div>
        """
    
    # 6. Comptes en déséquilibre
    comptes_deseq = controles.get('comptes_desequilibre', [])
    if comptes_deseq:
        html += f"""
        <div class="controle-item error">
            <div class="controle-label">
                ⚠️ Comptes Créant un Déséquilibre
                <span class="badge error">{len(comptes_deseq)} compte(s)</span>
            </div>
            <div class="controle-value">
                Comptes avec un sens incorrect pour leur section
            </div>
            <table class="compte-table">
                <thead>
                    <tr>
                        <th>N° Compte</th>
                        <th>Intitulé</th>
                        <th>Section</th>
                        <th>Problème</th>
                        <th>Solde</th>
                    </tr>
                </thead>
                <tbody>
        """
        for compte in comptes_deseq[:15]:
            html += f"""
                    <tr>
                        <td>{compte['numero']}</td>
                        <td>{compte['intitule'][:40]}</td>
                        <td>{compte['section']}</td>
                        <td style="color: #dc2626;">{compte['probleme']}</td>
                        <td>{format_number(compte['solde'])}</td>
                    </tr>
            """
        if len(comptes_deseq) > 15:
            html += f"""
                    <tr>
                        <td colspan="5" style="text-align: center; font-style: italic;">
                            ... et {len(comptes_deseq) - 15} autre(s) compte(s)
                        </td>
                    </tr>
            """
        html += """
                </tbody>
            </table>
        </div>
        """
    
    html += """
    </div>
    """
    
    return html


def generate_section_html(section_id: str, title: str, postes: Dict, total: float) -> str:
    """Génère le HTML pour une section d'états financiers"""
    if not postes:
        return ''
    
    html = f"""
    <div class="etats-fin-section" data-section="{section_id}">
        <div class="section-header-ef">
            <span>{title}</span>
            <span class="arrow">›</span>
        </div>
        <div class="section-content-ef">
    """
    
    # Trier les postes par référence
    sorted_postes = sorted(postes.values(), key=lambda x: x['ref'])
    
    for poste in sorted_postes:
        html += f"""
            <div class="poste-item">
                <span class="poste-ref">{poste['ref']}</span>
                <span class="poste-libelle">{poste['libelle']}</span>
                <span class="poste-montant">{format_number(poste['montant'])}</span>
            </div>
        """
    
    html += f"""
            <div class="total-section">
                <span>TOTAL {title.split('-')[1].strip()}</span>
                <span>{format_number(total)}</span>
            </div>
        </div>
    </div>
    """
    
    return html


# ==================== ENDPOINT API ====================

@router.post("/process-excel", response_model=EtatsFinanciersResponse)
async def process_excel(request: ExcelUploadRequest):
    """
    Traite un fichier Excel de balance et génère les états financiers SYSCOHADA.
    """
    try:
        logger.info(f"📥 Réception fichier: {request.filename}")
        
        # Décoder le fichier base64
        file_content = base64.b64decode(request.file_base64)
        logger.info(f"📂 Fichier décodé: {len(file_content)} bytes")
        
        # Lire le fichier Excel (Balance)
        excel_file = io.BytesIO(file_content)
        balance_df = pd.read_excel(excel_file, sheet_name=0)
        logger.info(f"📊 Balance chargée: {len(balance_df)} lignes")
        
        # Charger le tableau de correspondance
        correspondances = load_tableau_correspondance()
        
        # Traiter la balance et générer les états financiers
        results = process_balance_to_etats_financiers(balance_df, correspondances)
        
        # Générer le HTML
        html = generate_etats_financiers_html(results)
        
        return EtatsFinanciersResponse(
            success=True,
            message=f"États financiers générés avec succès à partir de {request.filename}",
            results=results,
            html=html
        )
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du traitement: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
