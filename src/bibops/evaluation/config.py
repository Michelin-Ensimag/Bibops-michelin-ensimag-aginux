"""
Configuration de la formule d'évaluation des réponses des modèles LLM
Permet d'ajuster les poids
"""

# POIDS RELATIFS 
WEIGHTS = {
    "erreur_penalty": 0.15,      # Pénalité pour "ERREUR" (abscence de réponse valide)
    "feedback": 0.20,            # Feedback utilisateur (Utile/Partiellement utile/Inutile)
    "vitesse": 0.15,             # Performance du temps de réponse
    "efficacite_tokens": 0.15,   # Efficacité (moins de tokens = plus efficace)
    "pertinence": 0.35,          # Pertinence de la réponse (F1-Score KB)
}

# Vérification que la somme = 1.0
assert abs(sum(WEIGHTS.values()) - 1.0) < 0.001, "Les poids doivent sommer à 1.0"

# CRITÈRE DE PERTINENCE
FEEDBACK_SCORES = {
    "Utile": 10,
    "Partiellement utile": 6,
    "Inutile": 0,
}

# CONFIGURATIONS DE TEMPS (en secondes)
# normalisation du score de vitesse
TIME_THRESHOLDS = {
    "excellent": 1.0,      # Plus rapide que ceci = score 10
    "good": 3.0,           # Entre 1 et 3 = score 10 à 7
    "acceptable": 10.0,    # Entre 3 et 10 = score 7 à 1
    "slow": 30.0,          # Plus de 30s = score 0
}

# CONFIGURATIONS DE TOKENS
# Utilisé pour normaliser le score d'efficacité
TOKEN_THRESHOLDS = {
    "excellent": 100,      # Moins de 100 tokens = score 10
    "good": 300,           # 100-300 = score 10 à 7
    "acceptable": 1000,    # 300-1000 = score 7 à 1
    "excessive": 5000,     # Plus de 5000 = score 0
}

# AUTRES PARAMÈTRES
SCORE_MIN = 0
SCORE_MAX = 10
