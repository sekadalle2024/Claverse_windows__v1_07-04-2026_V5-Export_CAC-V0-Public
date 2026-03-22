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
    Traite une balance comptable et génère les états financiers.
    """
    logger.info("📊 Traitement de la balance pour états financiers")
    
    # Détecter les colonnes de la balance
    col_map = detect_balance_columns(balance_df)
    
    if col_map['numero'] is None:
        raise ValueError("Colonne 'Numéro' non trouvée dans la balance")
    
    # Initialiser les résultats
    results = {
        'bilan_actif': {},
        'bilan_passif': {},
        'charges': {},
        'produits': {}
    }
    
    # Traiter chaque ligne de la balance
    for _, row in balance_df.iterrows():
        numero = str(row.get(col_map['numero'], '')).strip()
        if not numero or numero == 'nan':
            continue
        
        intitule = str(row.get(col_map['intitule'], '')).strip() if col_map['intitule'] else ''
        
        # Calculer le solde net
        solde_debit = clean_number(row.get(col_map['solde_debit'], 0)) if col_map['solde_debit'] else 0
        solde_credit = clean_number(row.get(col_map['solde_credit'], 0)) if col_map['solde_credit'] else 0
        solde_net = solde_debit - solde_credit
        
        # Chercher correspondance dans chaque section
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
                
                results[section_name][ref]['montant'] += solde_net
                results[section_name][ref]['comptes'].append({
                    'numero': numero,
                    'intitule': intitule,
                    'solde': solde_net
                })
                break  # Un compte ne peut être que dans une section
    
    # Calculer les totaux
    total_actif = sum(poste['montant'] for poste in results['bilan_actif'].values())
    total_passif = sum(poste['montant'] for poste in results['bilan_passif'].values())
    total_charges = sum(poste['montant'] for poste in results['charges'].values())
    total_produits = sum(poste['montant'] for poste in results['produits'].values())
    resultat_net = total_produits - total_charges
    
    logger.info(f"✅ États financiers calculés:")
    logger.info(f"   - Total Actif: {format_number(total_actif)}")
    logger.info(f"   - Total Passif: {format_number(total_passif)}")
    logger.info(f"   - Total Charges: {format_number(total_charges)}")
    logger.info(f"   - Total Produits: {format_number(total_produits)}")
    logger.info(f"   - Résultat Net: {format_number(resultat_net)}")
    
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
            'resultat_net': resultat_net
        }
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
    Génère le HTML des accordéons pour afficher les états financiers.
    """
    totaux = results['totaux']
    
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
    </style>
    """
    
    html += f"""
    <div class="etats-fin-container">
        <div class="etats-fin-header">
            <h2>📊 États Financiers SYSCOHADA Révisé</h2>
            <p>Bilan et Compte de Résultat</p>
        </div>
    """
    
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
    
    # Script pour les accordéons
    html += """
    <script>
    document.querySelectorAll('.section-header-ef').forEach(header => {
        header.addEventListener('click', function() {
            this.classList.toggle('active');
            this.nextElementSibling.classList.toggle('active');
        });
    });
    </script>
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
