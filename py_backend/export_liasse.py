# -*- coding: utf-8 -*-
"""
Module d'export de la liasse officielle Excel remplie avec les valeurs calculées
"""
import pandas as pd
import openpyxl
from openpyxl import load_workbook
from openpyxl.cell.cell import MergedCell
import os
import shutil
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging
import base64
import io

# Import du module de génération de l'onglet contrôle de cohérence
from generer_onglet_controle_coherence import (
    ajouter_onglet_controle_coherence,
    generer_etats_controle_pour_export
)

logger = logging.getLogger("export_liasse")

router = APIRouter(prefix="/export-liasse", tags=["Export Liasse"])


# ==================== MODÈLES PYDANTIC ====================

class ExportLiasseRequest(BaseModel):
    """Requête pour exporter la liasse officielle"""
    results: Dict[str, Any]  # Résultats des états financiers
    nom_entreprise: Optional[str] = "ENTREPRISE"
    exercice: Optional[str] = None

class ExportLiasseResponse(BaseModel):
    success: bool
    message: str
    file_base64: Optional[str] = None
    filename: Optional[str] = None


# ==================== MAPPING POSTES VERS CELLULES ====================

# Mapping des références de postes vers les cellules Excel de la liasse officielle
# Format: {'ref_poste': 'cellule_excel'}

MAPPING_BILAN_ACTIF = {
    # ACTIF IMMOBILISÉ
    'AD': 'C10',   # Charges immobilisées
    'AE': 'C11',   # Frais de recherche et développement
    'AF': 'C12',   # Brevets, licences, logiciels
    'AG': 'C13',   # Fonds commercial
    'AH': 'C14',   # Autres immobilisations incorporelles
    'AI': 'C15',   # Terrains
    'AJ': 'C16',   # Bâtiments
    'AK': 'C17',   # Installations et agencements
    'AL': 'C18',   # Matériel
    'AM': 'C19',   # Matériel de transport
    'AN': 'C20',   # Avances et acomptes versés sur immobilisations
    'AP': 'C21',   # Titres de participation
    'AQ': 'C22',   # Autres immobilisations financières
    'AZ': 'C23',   # TOTAL ACTIF IMMOBILISÉ
    
    # ACTIF CIRCULANT
    'BA': 'C25',   # Actif circulant HAO
    'BB': 'C26',   # Stocks et encours
    'BC': 'C27',   # Marchandises
    'BD': 'C28',   # Matières premières
    'BE': 'C29',   # Autres approvisionnements
    'BF': 'C30',   # En-cours
    'BG': 'C31',   # Produits fabriqués
    'BH': 'C32',   # Fournisseurs, avances versées
    'BI': 'C33',   # Clients
    'BJ': 'C34',   # Autres créances
    'BK': 'C35',   # Capital souscrit, appelé non versé
    'BQ': 'C36',   # TOTAL ACTIF CIRCULANT
    
    # TRÉSORERIE-ACTIF
    'BT': 'C38',   # Titres de placement
    'BU': 'C39',   # Valeurs à encaisser
    'BV': 'C40',   # Banques, chèques postaux, caisse
    'BZ': 'C41',   # TOTAL TRÉSORERIE-ACTIF
    
    # ÉCARTS DE CONVERSION-ACTIF
    'CA': 'C43',   # Diminution des créances
    'CB': 'C44',   # Augmentation des dettes
    'CZ': 'C45',   # TOTAL ÉCARTS DE CONVERSION-ACTIF
}

MAPPING_BILAN_PASSIF = {
    # CAPITAUX PROPRES
    'DA': 'E10',   # Capital
    'DB': 'E11',   # Apporteurs, capital non appelé
    'DC': 'E12',   # Primes liées au capital social
    'DD': 'E13',   # Écarts de réévaluation
    'DE': 'E14',   # Réserves indisponibles
    'DF': 'E15',   # Réserves libres
    'DG': 'E16',   # Report à nouveau
    'DH': 'E17',   # Résultat net de l'exercice
    'DI': 'E18',   # Subventions d'investissement
    'DJ': 'E19',   # Provisions réglementées
    'DZ': 'E20',   # TOTAL CAPITAUX PROPRES
    
    # DETTES FINANCIÈRES ET RESSOURCES ASSIMILÉES
    'RA': 'E22',   # Emprunts
    'RB': 'E23',   # Dettes de crédit-bail et contrats assimilés
    'RC': 'E24',   # Dettes financières diverses
    'RD': 'E25',   # Provisions financières pour risques et charges
    'RZ': 'E26',   # TOTAL DETTES FINANCIÈRES
    
    # PASSIF CIRCULANT
    'TA': 'E28',   # Dettes circulantes HAO
    'TB': 'E29',   # Clients, avances reçues
    'TC': 'E30',   # Fournisseurs d'exploitation
    'TD': 'E31',   # Dettes fiscales
    'TE': 'E32',   # Dettes sociales
    'TF': 'E33',   # Autres dettes
    'TG': 'E34',   # Provisions pour risques à court terme
    'TZ': 'E35',   # TOTAL PASSIF CIRCULANT
    
    # TRÉSORERIE-PASSIF
    'UA': 'E37',   # Banques, crédits d'escompte
    'UB': 'E38',   # Banques, crédits de trésorerie
    'UC': 'E39',   # Banques, découverts
    'UZ': 'E40',   # TOTAL TRÉSORERIE-PASSIF
    
    # ÉCARTS DE CONVERSION-PASSIF
    'VA': 'E42',   # Augmentation des créances
    'VB': 'E43',   # Diminution des dettes
    'VZ': 'E44',   # TOTAL ÉCARTS DE CONVERSION-PASSIF
}

# Mapping unifié Compte de Résultat (onglet RESULTAT)
# Charges: colonne C  |  Produits: colonne E
# (col D = N-1 Charges, col F = N-1 Produits - à compléter si nécessaire)
MAPPING_RESULTAT_CHARGES_COL_N = {
    # Charges d'exploitation
    'TA': 'C10',   # Achats de marchandises
    'TB': 'C11',   # Variation de stocks de marchandises
    'TC': 'C12',   # Achats de matières premières
    'TD': 'C13',   # Variation de stocks de matières
    'TE': 'C14',   # Autres achats
    'TF': 'C15',   # Variation de stocks d'autres approvisionnements
    'TG': 'C16',   # Transports
    'TH': 'C17',   # Services extérieurs
    'TI': 'C18',   # Impôts et taxes
    'TJ': 'C19',   # Autres charges
    'TK': 'C20',   # Charges de personnel
    'TL': 'C21',   # Dotations aux amortissements
    'TM': 'C22',   # Dotations aux provisions
    'TZ': 'C23',   # TOTAL CHARGES D'EXPLOITATION
    # Charges financières
    'UA': 'C25',   # Frais financiers
    'UB': 'C26',   # Pertes de change
    'UC': 'C27',   # Dotations aux amortissements et provisions financières
    'UZ': 'C28',   # TOTAL CHARGES FINANCIÈRES
    # Charges HAO
    'XA': 'C30',   # Valeurs comptables des cessions d'immobilisations
    'XB': 'C31',   # Charges HAO constatées
    'XC': 'C32',   # Dotations HAO
    'XZ': 'C33',   # TOTAL CHARGES HAO
}

MAPPING_RESULTAT_PRODUITS_COL_N = {
    # Produits d'exploitation
    'RA': 'E10',   # Ventes de marchandises
    'RB': 'E11',   # Ventes de produits fabriqués
    'RC': 'E12',   # Travaux, services vendus
    'RD': 'E13',   # Production stockée
    'RE': 'E14',   # Production immobilisée
    'RF': 'E15',   # Subventions d'exploitation
    'RG': 'E16',   # Autres produits
    'RH': 'E17',   # Reprises de provisions
    'RI': 'E18',   # Transferts de charges
    'RZ': 'E19',   # TOTAL PRODUITS D'EXPLOITATION
    # Produits financiers
    'SA': 'E21',   # Revenus financiers
    'SB': 'E22',   # Gains de change
    'SC': 'E23',   # Reprises de provisions financières
    'SD': 'E24',   # Transferts de charges financières
    'SZ': 'E25',   # TOTAL PRODUITS FINANCIERS
    # Produits HAO
    'YA': 'E27',   # Produits des cessions d'immobilisations
    'YB': 'E28',   # Produits HAO constatés
    'YC': 'E29',   # Reprises HAO
    'YD': 'E30',   # Transferts de charges HAO
    'YZ': 'E31',   # TOTAL PRODUITS HAO
}

MAPPING_COMPTE_RESULTAT_CHARGES = {
    # ACTIVITÉ D'EXPLOITATION
    'TA': 'C10',   # Achats de marchandises
    'TB': 'C11',   # Variation de stocks de marchandises
    'TC': 'C12',   # Achats de matières premières
    'TD': 'C13',   # Variation de stocks de matières
    'TE': 'C14',   # Autres achats
    'TF': 'C15',   # Variation de stocks d'autres approvisionnements
    'TG': 'C16',   # Transports
    'TH': 'C17',   # Services extérieurs
    'TI': 'C18',   # Impôts et taxes
    'TJ': 'C19',   # Autres charges
    'TK': 'C20',   # Charges de personnel
    'TL': 'C21',   # Dotations aux amortissements
    'TM': 'C22',   # Dotations aux provisions
    'TZ': 'C23',   # TOTAL CHARGES D'EXPLOITATION
    
    # ACTIVITÉ FINANCIÈRE
    'UA': 'C25',   # Frais financiers
    'UB': 'C26',   # Pertes de change
    'UC': 'C27',   # Dotations aux amortissements et provisions
    'UZ': 'C28',   # TOTAL CHARGES FINANCIÈRES
    
    # HORS ACTIVITÉS ORDINAIRES (HAO)
    'XA': 'C30',   # Valeurs comptables des cessions d'immobilisations
    'XB': 'C31',   # Charges HAO constatées
    'XC': 'C32',   # Dotations HAO
    'XZ': 'C33',   # TOTAL CHARGES HAO
}

MAPPING_COMPTE_RESULTAT_PRODUITS = {
    # ACTIVITÉ D'EXPLOITATION
    'RA': 'E10',   # Ventes de marchandises
    'RB': 'E11',   # Ventes de produits fabriqués
    'RC': 'E12',   # Travaux, services vendus
    'RD': 'E13',   # Production stockée
    'RE': 'E14',   # Production immobilisée
    'RF': 'E15',   # Subventions d'exploitation
    'RG': 'E16',   # Autres produits
    'RH': 'E17',   # Reprises de provisions
    'RI': 'E18',   # Transferts de charges
    'RZ': 'E19',   # TOTAL PRODUITS D'EXPLOITATION
    
    # ACTIVITÉ FINANCIÈRE
    'SA': 'E21',   # Revenus financiers
    'SB': 'E22',   # Gains de change
    'SC': 'E23',   # Reprises de provisions
    'SD': 'E24',   # Transferts de charges
    'SZ': 'E25',   # TOTAL PRODUITS FINANCIERS
    
    # HORS ACTIVITÉS ORDINAIRES (HAO)
    'YA': 'E27',   # Produits des cessions d'immobilisations
    'YB': 'E28',   # Produits HAO constatés
    'YC': 'E29',   # Reprises HAO
    'YD': 'E30',   # Transferts de charges
    'YZ': 'E31',   # TOTAL PRODUITS HAO
}


# ==================== FONCTIONS D'EXPORT ====================

def remplir_liasse_officielle(results: Dict[str, Any], nom_entreprise: str, exercice: str) -> bytes:
    """
    Remplit la liasse officielle avec les valeurs calculées
    
    Args:
        results: Résultats des états financiers
        nom_entreprise: Nom de l'entreprise
        exercice: Exercice comptable (ex: "2024")
    
    Returns:
        Contenu du fichier Excel en bytes
    """
    logger.info("📊 Début du remplissage de la liasse officielle")
    
    # Chemin du template (fichier vierge) - UTILISER Liasse_officielle_revise.xlsx
    template_path = "Liasse_officielle_revise.xlsx"
    if not os.path.exists(template_path):
        # Essayer avec les anciens noms en fallback
        template_path = "LIASSE.xlsx"
        if not os.path.exists(template_path):
            template_path = "Liasse officielle.xlsm"
            if not os.path.exists(template_path):
                raise FileNotFoundError("Fichier template de liasse non trouvé (Liasse_officielle_revise.xlsx, LIASSE.xlsx ou Liasse officielle.xlsm)")
    
    logger.info(f"📂 Template trouvé: {template_path}")
    
    # Charger le workbook
    wb = load_workbook(template_path)
    
    # Log des onglets disponibles
    logger.info(f"📋 Onglets disponibles: {wb.sheetnames[:10]}...")  # Premiers 10 onglets
    
    # Log du format des données reçues
    logger.info(f"📊 Données reçues - Clés: {list(results.keys())}")
    if 'bilan_actif' in results:
        logger.info(f"   Type bilan_actif: {type(results.get('bilan_actif'))}")
        if isinstance(results.get('bilan_actif'), list):
            logger.info(f"   Bilan actif (LIST): {len(results['bilan_actif'])} postes")
        elif isinstance(results.get('bilan_actif'), dict):
            logger.info(f"   Bilan actif (DICT): {len(results['bilan_actif'])} postes")
    
    # ==================== CONVERSION FORMAT DONNÉES ====================
    # Convertir LIST en DICT si nécessaire (etats_financiers_v2.py retourne des listes)
    
    def convert_list_to_dict(data):
        """Convertit une liste de postes en dictionnaire {ref: poste}"""
        if isinstance(data, list):
            return {poste['ref']: poste for poste in data}
        return data if isinstance(data, dict) else {}
    
    bilan_actif_dict = convert_list_to_dict(results.get('bilan_actif', {}))
    bilan_passif_dict = convert_list_to_dict(results.get('bilan_passif', {}))
    charges_dict = convert_list_to_dict(results.get('charges', {}))
    produits_dict = convert_list_to_dict(results.get('produits', {}))
    
    logger.info(f"📊 Données converties:")
    logger.info(f"   - Bilan Actif: {len(bilan_actif_dict)} postes")
    logger.info(f"   - Bilan Passif: {len(bilan_passif_dict)} postes")
    logger.info(f"   - Charges: {len(charges_dict)} postes")
    logger.info(f"   - Produits: {len(produits_dict)} postes")
    
    # ==================== FONCTION POUR ÉCRIRE DANS CELLULE ====================
    
    def write_to_cell(ws, cell_addr, value):
        """
        Écrit une valeur dans une cellule en gérant les cellules fusionnées
        
        Args:
            ws: Worksheet
            cell_addr: Adresse de la cellule (ex: 'C10')
            value: Valeur à écrire
        
        Returns:
            bool: True si succès, False sinon
        """
        try:
            cell = ws[cell_addr]
            target_cell = cell
            
            # Vérifier si c'est une cellule fusionnée
            if isinstance(cell, openpyxl.cell.cell.MergedCell):
                # Trouver la cellule principale de la fusion
                for merged_range in ws.merged_cells.ranges:
                    if cell_addr in merged_range:
                        # Obtenir la vraie cellule de la fusion
                        target_cell = ws.cell(merged_range.start_cell.row, merged_range.start_cell.column)
                        break
            
            # [CRITIQUE] NE JAMAIS ÉCRASER LES FORMULES EXCEL 
            # (Ex: =SUM(H25:H30)) car ce sont elles qui calculent les Rubriques 
            # de Totalisation (BK, BZ, TOTAL GENERAL, etc.) de la Liasse !
            if isinstance(target_cell.value, str) and str(target_cell.value).strip().startswith('='):
                return True
                
            # Cellule normale ou maître
            target_cell.value = value
            return True
        except Exception as e:
            logger.warning(f"   Erreur écriture {cell_addr}: {e}")
            return False
    
    def remplir_onglet_dynamique(ws, postes, col_debut, ligne_debut):
        """
        Remplit un onglet dynamiquement sans mapping fixe
        APPROCHE DYNAMIQUE: Lit les postes générés et les écrit séquentiellement
        
        Args:
            ws: Worksheet
            postes: Liste des postes [{ref, libelle, montant_n, montant_n1}, ...]
            col_debut: Colonne de début pour N (ex: 'C')
            ligne_debut: Ligne de début (ex: 10)
        
        Returns:
            int: Nombre de cellules remplies
        """
        compteur = 0
        ligne = ligne_debut
        
        # Colonne N-1 (suivante)
        col_n1 = chr(ord(col_debut) + 1)
        
        for poste in postes:
            # Écrire montant N
            montant_n = poste.get('montant_n', poste.get('montant', 0))
            if write_to_cell(ws, f'{col_debut}{ligne}', montant_n):
                compteur += 1
            
            # Écrire montant N-1
            montant_n1 = poste.get('montant_n1', 0)
            if write_to_cell(ws, f'{col_n1}{ligne}', montant_n1):
                compteur += 1
            
            ligne += 1
        
        return compteur
    
    # ==================== REMPLISSAGE DES ONGLETS ====================
    
    # Log des onglets disponibles pour diagnostic
    logger.info(f"📋 Onglets disponibles dans le template: {wb.sheetnames}")
    
    # Remplir les informations générales
    if 'BILAN' in wb.sheetnames:
        ws_bilan = wb['BILAN']
        # Cellules pour nom entreprise et exercice (à adapter selon le template)
        write_to_cell(ws_bilan, 'C3', nom_entreprise)
        write_to_cell(ws_bilan, 'E5', f"{exercice}")
    
    # ==================== NOUVELLE APPROCHE : SCANNER DE REF INTELLIGENT ====================
    logger.info("📝 Remplissage par SCANNER INTELLIGENT de la colonne REF...")
    
    total_cellules = 0
    erreurs_total = 0
    
    # ---- Helper interne ----
    def extraire_montant(poste, cle_n='montant_n', cle_fallback='montant'):
        """Extrait le montant N d'un poste, avec fallback"""
        v = poste.get(cle_n, poste.get(cle_fallback, 0))
        return 0 if v is None else float(v)
    
    def extraire_montant_n1(poste):
        """Extrait le montant N-1 d'un poste"""
        v = poste.get('montant_n1', 0)
        return 0 if v is None else float(v)
        
    def remplir_onglet_par_scan(onglet_name, dict_donnees, col_n, col_n1, ref_col_idx=1):
        """Scanne la colonne (par defaut A=1) pour les REF et remplit directement col_n et col_n1."""
        if not dict_donnees:
            return 0, 0
            
        ws = wb[onglet_name]
        compteur = 0
        erreurs = 0
        
        for row in ws.iter_rows(min_col=ref_col_idx, max_col=ref_col_idx):
            cell = row[0]
            ref_val = str(cell.value or '').strip()
            
            if len(ref_val) == 2 and ref_val.isalpha() and ref_val.isupper() and ref_val in dict_donnees:
                row_num = cell.row
                poste = dict_donnees[ref_val]
                montant_n = extraire_montant(poste)
                montant_n1 = extraire_montant_n1(poste)
                
                # Écrire N
                if col_n:
                    if write_to_cell(ws, f"{col_n}{row_num}", montant_n):
                        compteur += 1
                    else:
                        erreurs += 1
                        
                # Écrire N-1
                if col_n1:
                    if write_to_cell(ws, f"{col_n1}{row_num}", montant_n1):
                        compteur += 1
                    else:
                        erreurs += 1
        
        return compteur, erreurs

    # ---- BILAN ACTIF ----
    onglet_actif = next((name for name in wb.sheetnames if 'ACTIF' in name.upper() and 'PASSIF' not in name.upper()), None)
    if onglet_actif:
        logger.info(f"📝 Remplissage {onglet_actif}...")
        # Actif: N en H, N-1 en I
        compteur, erreurs = remplir_onglet_par_scan(onglet_actif, bilan_actif_dict, 'H', 'I')
        total_cellules += compteur
        erreurs_total += erreurs
    
    # ---- BILAN PASSIF ----
    onglet_passif = next((name for name in wb.sheetnames if 'PASSIF' in name.upper()), None)
    if onglet_passif:
        logger.info(f"📝 Remplissage {onglet_passif}...")
        # Passif: N en H, N-1 en I
        compteur, erreurs = remplir_onglet_par_scan(onglet_passif, bilan_passif_dict, 'H', 'I')
        total_cellules += compteur
        erreurs_total += erreurs

    # ---- COMPTE DE RÉSULTAT ----
    # Construire le dict compte_resultat par ref pour accès rapide
    cr_dict = {}
    cr_raw = results.get('compte_resultat', [])
    if isinstance(cr_raw, dict):
        cr_dict = cr_raw
    else:
        cr_dict = {p['ref']: p for p in cr_raw if 'ref' in p}
        
    if not cr_dict:  # Fallback
        c_raw = results.get('charges', {})
        p_raw = results.get('produits', {})
        c_dict = {p['ref']: p for p in c_raw} if isinstance(c_raw, list) else c_raw
        p_dict = {p['ref']: p for p in p_raw} if isinstance(p_raw, list) else p_raw
        cr_dict = {**c_dict, **p_dict}

    onglet_resultat = next((name for name in wb.sheetnames if 'RESULTAT' in name.upper() or 'RÉSULTAT' in name.upper()), None)
    if onglet_resultat:
        logger.info(f"📝 Remplissage {onglet_resultat}...")
        # Compte de résultat: N en I, N-1 en J (Décalage de H/I pour éviter d'écrire sur les NOTES)
        compteur, erreurs = remplir_onglet_par_scan(onglet_resultat, cr_dict, 'I', 'J')
        total_cellules += compteur
        erreurs_total += erreurs
        
    # ---- TFT ----
    tft_dict = {}
    tft_raw = results.get('tft', {})
    if isinstance(tft_raw, dict):
        for cle, montant in tft_raw.items():
            # Extraire prefixe si existant ex FF_decaissement
            prefixe = cle.split('_')[0] if '_' in cle else cle[:2]
            if prefixe.isalpha() and prefixe.isupper() and len(prefixe) == 2:
                tft_dict[prefixe] = {'montant_n': montant, 'montant_n1': 0}
                    
    onglet_tft = next((name for name in wb.sheetnames if 'TFT' in name.upper() or 'TRÉSORERIE' in name.upper() or 'TRESORERIE' in name.upper()), None)
    if onglet_tft and tft_dict:
        logger.info(f"📝 Remplissage {onglet_tft}...")
        # TFT: N en I, N-1 en K (Le modèle DGI a des espaces intercalaires sur cet onglet)
        compteur, erreurs = remplir_onglet_par_scan(onglet_tft, tft_dict, 'I', 'K')
        total_cellules += compteur
        erreurs_total += erreurs
        
    # ---- BILAN ETAT COMPLET (Col A actif, Col J passif) ----
    onglet_bilan = next((name for name in wb.sheetnames if name.strip() == 'BILAN'), None)
    if onglet_bilan:
        logger.info(f"📝 Remplissage {onglet_bilan}...")
        # Actif scan col A (idx=1), valeurs en H et I
        c_actif, err_actif = remplir_onglet_par_scan(onglet_bilan, bilan_actif_dict, 'H', 'I', ref_col_idx=1)
        # Passif scan col J (idx=10), valeurs en M et N
        c_passif, err_passif = remplir_onglet_par_scan(onglet_bilan, bilan_passif_dict, 'M', 'N', ref_col_idx=10)
        
        total_cellules += (c_actif + c_passif)
        erreurs_total += (err_actif + err_passif)

    logger.info(f"✅ TOTAL MAPPING: {total_cellules} cellules remplies, {erreurs_total} erreurs")
    logger.info("✅ Remplissage intelligent terminé")
    
    # ==================== AJOUT ONGLET CONTRÔLE DE COHÉRENCE ====================
    logger.info("📊 Ajout de l'onglet 'Contrôle de cohérence'...")
    try:
        # Générer les 16 états de contrôle
        etats_controle = generer_etats_controle_pour_export(results)
        
        # Ajouter l'onglet au workbook
        ajouter_onglet_controle_coherence(wb, etats_controle)
        
        logger.info("✅ Onglet 'Contrôle de cohérence' ajouté avec succès")
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'ajout de l'onglet Contrôle de cohérence: {e}", exc_info=True)
        logger.warning("⚠️ L'export continue sans l'onglet Contrôle de cohérence")
    
    # ==================== FIN AJOUT ONGLET ====================
    
    # Sauvegarder dans un buffer
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    logger.info("✅ Liasse officielle remplie avec succès")
    
    return output.getvalue()


# ==================== ENDPOINT API ====================

@router.post("/generer", response_model=ExportLiasseResponse)
async def generer_liasse(request: ExportLiasseRequest):
    """
    Génère la liasse officielle Excel remplie avec les valeurs calculées
    """
    try:
        logger.info("📥 Réception demande d'export liasse")
        
        # Déterminer l'exercice
        exercice = request.exercice or datetime.now().year
        
        # Remplir la liasse
        file_content = remplir_liasse_officielle(
            results=request.results,
            nom_entreprise=request.nom_entreprise,
            exercice=str(exercice)
        )
        
        # Encoder en base64
        file_base64 = base64.b64encode(file_content).decode('utf-8')
        
        # Nom du fichier
        filename = f"Liasse_Officielle_{request.nom_entreprise}_{exercice}.xlsx"
        filename = filename.replace(' ', '_').replace('/', '_')
        
        logger.info(f"✅ Liasse générée: {filename}")
        
        return ExportLiasseResponse(
            success=True,
            message=f"Liasse officielle générée avec succès pour {request.nom_entreprise} - Exercice {exercice}",
            file_base64=file_base64,
            filename=filename
        )
        
    except FileNotFoundError as e:
        logger.error(f"❌ Fichier template non trouvé: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Erreur lors de la génération: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
