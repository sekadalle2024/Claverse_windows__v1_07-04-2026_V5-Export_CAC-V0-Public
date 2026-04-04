# ═══════════════════════════════════════════════════════════════════════════════
# Script PowerShell - Test États de Contrôle HTML
# ═══════════════════════════════════════════════════════════════════════════════
# Date: 04 Avril 2026
# Objectif: Ouvrir et tester le fichier HTML des états de contrôle
# ═══════════════════════════════════════════════════════════════════════════════

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  🔍 TEST ÉTATS DE CONTRÔLE HTML" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Vérifier l'existence du fichier
$htmlFile = "test_etats_controle_html.html"

if (Test-Path $htmlFile) {
    Write-Host "✅ Fichier trouvé: $htmlFile" -ForegroundColor Green
    Write-Host ""
    
    # Afficher les informations du fichier
    $fileInfo = Get-Item $htmlFile
    Write-Host "📊 Informations du fichier:" -ForegroundColor Yellow
    Write-Host "   • Nom: $($fileInfo.Name)" -ForegroundColor White
    Write-Host "   • Taille: $([math]::Round($fileInfo.Length / 1KB, 2)) KB" -ForegroundColor White
    Write-Host "   • Date de création: $($fileInfo.CreationTime)" -ForegroundColor White
    Write-Host "   • Dernière modification: $($fileInfo.LastWriteTime)" -ForegroundColor White
    Write-Host ""
    
    # Compter les lignes
    $lines = (Get-Content $htmlFile).Count
    Write-Host "📏 Nombre de lignes: $lines" -ForegroundColor Yellow
    Write-Host ""
    
    # Ouvrir le fichier dans le navigateur par défaut
    Write-Host "🌐 Ouverture du fichier dans le navigateur..." -ForegroundColor Cyan
    Start-Process $htmlFile
    Write-Host ""
    
    Write-Host "✅ Fichier ouvert avec succès !" -ForegroundColor Green
    Write-Host ""
    
    # Afficher les instructions
    Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  📋 INSTRUCTIONS D'UTILISATION" -ForegroundColor Cyan
    Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "1️⃣  NAVIGATION:" -ForegroundColor Yellow
    Write-Host "   • Cliquer sur les en-têtes pour ouvrir/fermer les sections" -ForegroundColor White
    Write-Host "   • Utiliser les boutons de contrôle en haut" -ForegroundColor White
    Write-Host "   • Faire défiler pour voir tous les contrôles" -ForegroundColor White
    Write-Host ""
    
    Write-Host "2️⃣  BOUTONS DE CONTRÔLE:" -ForegroundColor Yellow
    Write-Host "   • 📂 Tout Ouvrir: Ouvre toutes les sections" -ForegroundColor White
    Write-Host "   • 📁 Tout Fermer: Ferme toutes les sections" -ForegroundColor White
    Write-Host "   • 🖨️ Imprimer: Lance l'impression" -ForegroundColor White
    Write-Host ""
    
    Write-Host "3️⃣  LES 8 ÉTATS DE CONTRÔLE:" -ForegroundColor Yellow
    Write-Host "   1. 📊 Statistiques de Couverture" -ForegroundColor White
    Write-Host "   2. ⚖️ Équilibre du Bilan" -ForegroundColor White
    Write-Host "   3. 💰 Cohérence Résultat" -ForegroundColor White
    Write-Host "   4. ⚠️ Comptes Non Intégrés" -ForegroundColor White
    Write-Host "   5. 🔄 Comptes Sens Inversé" -ForegroundColor White
    Write-Host "   6. ⚠️ Comptes en Déséquilibre" -ForegroundColor White
    Write-Host "   7. 💡 Hypothèse Affectation" -ForegroundColor White
    Write-Host "   8. 🚨 Sens Anormal par Nature" -ForegroundColor White
    Write-Host ""
    
    Write-Host "4️⃣  RACCOURCIS CLAVIER:" -ForegroundColor Yellow
    Write-Host "   • Ctrl+F: Rechercher dans la page" -ForegroundColor White
    Write-Host "   • Ctrl+P: Imprimer" -ForegroundColor White
    Write-Host "   • F5: Recharger" -ForegroundColor White
    Write-Host "   • F11: Plein écran" -ForegroundColor White
    Write-Host ""
    
    Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  📚 DOCUMENTATION" -ForegroundColor Cyan
    Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Pour plus d'informations, consulter:" -ForegroundColor White
    Write-Host "   • GUIDE_RAPIDE_TEST_ETATS_CONTROLE.md" -ForegroundColor Yellow
    Write-Host "   • 00_TEST_ETATS_CONTROLE_HTML_CREE_04_AVRIL_2026.txt" -ForegroundColor Yellow
    Write-Host "   • SYNTHESE_VISUELLE_TEST_ETATS_CONTROLE.txt" -ForegroundColor Yellow
    Write-Host ""
    
    # Proposer d'ouvrir la documentation
    Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""
    $openDoc = Read-Host "Voulez-vous ouvrir le guide rapide ? (O/N)"
    
    if ($openDoc -eq "O" -or $openDoc -eq "o") {
        if (Test-Path "GUIDE_RAPIDE_TEST_ETATS_CONTROLE.md") {
            Write-Host ""
            Write-Host "📖 Ouverture du guide rapide..." -ForegroundColor Cyan
            Start-Process "GUIDE_RAPIDE_TEST_ETATS_CONTROLE.md"
            Write-Host "✅ Guide ouvert !" -ForegroundColor Green
        } else {
            Write-Host ""
            Write-Host "⚠️ Fichier guide non trouvé" -ForegroundColor Yellow
        }
    }
    
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  ✅ TEST TERMINÉ AVEC SUCCÈS" -ForegroundColor Green
    Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""
    
} else {
    Write-Host "❌ ERREUR: Fichier non trouvé: $htmlFile" -ForegroundColor Red
    Write-Host ""
    Write-Host "Vérifier que le fichier existe dans le répertoire courant." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Répertoire courant: $(Get-Location)" -ForegroundColor White
    Write-Host ""
    
    # Lister les fichiers HTML disponibles
    Write-Host "Fichiers HTML disponibles:" -ForegroundColor Yellow
    $htmlFiles = Get-ChildItem -Filter "*.html"
    if ($htmlFiles.Count -gt 0) {
        foreach ($file in $htmlFiles) {
            Write-Host "   • $($file.Name)" -ForegroundColor White
        }
    } else {
        Write-Host "   Aucun fichier HTML trouvé" -ForegroundColor Red
    }
    Write-Host ""
}

Write-Host "Appuyez sur une touche pour quitter..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
