
import sys
import logging
from typing import Dict
# On peut aussi importer re si besoin, mais on va juste tester la fonction importée
sys.path.append('H:\\ClaraVerse\\py_backend')
from etats_financiers_v2 import calculer_poste_formule

def test_calculer_formule():
    print("--- TEST CALCUL FORMULE ---")
    
    # Mock data
    postes = {
        "TA": 1000.0,
        "RA": 200.0,
        "RB": 50.0,
        "XA": 500.0,
        "TE": 100.0
    }
    
    # Test 1: Simple subtraction
    r1 = calculer_poste_formule("TOTAL1", "TA - RA - RB", postes)
    print(f"Test 1 (1000-200-50): {r1} (Attendu: 750.0)")
    assert r1 == 750.0
    
    # Test 2: Simple addition
    r2 = calculer_poste_formule("TOTAL2", "XA + TE", postes)
    print(f"Test 2 (500+100): {r2} (Attendu: 600.0)")
    assert r2 == 600.0
    
    # Test 3: Missing reference (should be 0)
    r3 = calculer_poste_formule("TOTAL3", "TA - ZZ", postes)
    print(f"Test 3 (1000-0): {r3} (Attendu: 1000.0)")
    assert r3 == 1000.0
    
    # Test 4: Indivision (should handle exception)
    # Note: division by zero in eval
    r4 = calculer_poste_formule("TOTAL4", "TA / 0", postes)
    print(f"Test 4 (Division par 0): {r4} (Attendu: 0.0)")
    assert r4 == 0.0

    print("--- TOUS LES TESTS PASSÉS ✅ ---")

if __name__ == "__main__":
    test_calculer_formule()
