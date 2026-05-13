def generate_puml():
    puml = """@startgantt
Project starts 2026-02-06
[Analyse détaillée du sujet & prise de contact] lasts 1 week
[Setup Git & planning & premier cas d'usage] lasts 1 week
[Revue de la littérature & dataset tickets & métriques] lasts 1 week
[Finalisation dataset & implémentation métriques auto] lasts 5 weeks
[Architecture Multi-Agents (A2A, LangGraph)] lasts 3 weeks
[Système d'évaluation (LLM Judge, RAGAS, FinOps)] lasts 3 weeks
[Déploiement, Tests finaux & Rédaction rapport] lasts 3 weeks

[Setup Git & planning & premier cas d'usage] starts at [Analyse détaillée du sujet & prise de contact]'s end
[Revue de la littérature & dataset tickets & métriques] starts at [Setup Git & planning & premier cas d'usage]'s end
[Finalisation dataset & implémentation métriques auto] starts at [Revue de la littérature & dataset tickets & métriques]'s end
[Architecture Multi-Agents (A2A, LangGraph)] starts at 2026-03-06
[Système d'évaluation (LLM Judge, RAGAS, FinOps)] starts at 2026-03-06
[Déploiement, Tests finaux & Rédaction rapport] starts at 2026-04-10
@endgantt"""
    print(puml)

generate_puml()
