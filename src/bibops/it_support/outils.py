"""Compatibility layer preserving legacy patch points for tests and callers."""

from src.bibops.it_support import tools as _tools

_get_chroma_collection = _tools._get_chroma_collection
get_tool_policy = _tools.get_tool_policy
get_tool_policies = _tools.get_tool_policies
normaliser_argument_outil = _tools.normaliser_argument_outil


def verifier_statut_serveur(nom_serveur: str) -> str:
    return _tools.verifier_statut_serveur(nom_serveur)


def chercher_dans_kb(requete: str) -> str:
    return _tools.chercher_dans_kb(requete)


def chercher_documentation_technique(mot_cle: str) -> str:
    # Keep backward-compatible monkeypatch behavior on this module-level symbol.
    original = _tools._get_chroma_collection
    _tools._get_chroma_collection = _get_chroma_collection
    try:
        return _tools.chercher_documentation_technique(mot_cle)
    finally:
        _tools._get_chroma_collection = original


__all__ = [
    "_get_chroma_collection",
    "get_tool_policy",
    "get_tool_policies",
    "normaliser_argument_outil",
    "verifier_statut_serveur",
    "chercher_dans_kb",
    "chercher_documentation_technique",
]
