# Standards Masterisation et Parc Poste de Travail

## Hardware Lifecycle (Cycle 2024-2026)
- **Standard Office** : Dell Latitude 5420 (Core i5, 16GB RAM).
- **Standard Engineering/Dev** : Precision 3561 ou MacBook Pro M3 (Pôles RDI).
- **Docking Station** : WD19S (DisplayPort over USB-C uniquement).

## Logiciels Socle (Core Apps)
1. **Zscaler Private Access (ZPA)** : Remplace progressivement le VPN pour les accès applicatifs.
2. **CrowdStrike Falcon** : Agent EDR obligatoire (Service : `csfalconservice`).
3. **Microsoft Endpoint Manager (Intune)** : Utilisé pour le déploiement des patchs de sécurité tous les mardis (Patch Tuesday).

## Stockage
L'utilisation de clés USB non chiffrées est bloquée par GPO (Group Policy Object).