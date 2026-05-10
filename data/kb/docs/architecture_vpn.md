# Spécifications Techniques VPN Michelin (AnyConnect)

## Infrastructure de Terminaison
Le service repose sur des clusters de **Cisco ASA 5585-X** répartis par zone géographique.
- **Gateway EMEA** : `vpn-clermont.michelin.com` (IP: 163.x.x.x)
- **Protocoles** : Priorité au **DTLS (UDP 443)** pour la performance VoIP/VDI. Repli sur **TLS (TCP 443)** en cas de filtrage réseau local.

## Sécurité & Compliance
- **Posture Check** : L'agent AnyConnect effectue un scan via le module **ISE (Identity Services Engine)** avant d'autoriser la connexion.
- **Conditions de rejet** : Antivirus CrowdStrike non à jour ou Windows Update désactivé depuis plus de 30 jours.
- **Split-Tunneling** : Seuls les réseaux `10.0.0.0/8` et `147.0.0.0/16` sont routés dans le tunnel.