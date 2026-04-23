"""
conftest.py (racine du projet)

Garantit que la racine du projet est dans sys.path afin que les imports
`from src.bibops.it_support.*` fonctionnent indépendamment du répertoire de lancement.

Contient aussi un shim de compatibilité LangChain :
  langchain-core 0.2.x cherche langchain.verbose qui n'existe plus dans
  langchain >= 1.x. On l'injecte ici avant toute instanciation de modèle.

TODO [T0-a]: Ajout automatique du chemin racine pour pytest
TODO [T0-b]: Shim langchain.verbose pour compatibilité langchain-core 0.2 / langchain 1.x
"""
import sys
import os

# TODO [T0-a]: Insère la racine du projet en tête de sys.path
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# TODO [T0-b]: langchain-core 0.2.x appelle langchain.verbose / langchain.debug dans ses
# callbacks internes (get_verbose, get_debug). Ces attributs ont été retirés dans
# langchain >= 1.0. On les injecte ici pour éviter les AttributeError au moment de
# l'initialisation des modèles LangChain (ex: GenericFakeChatModel).
try:
    import langchain as _lc
    for _attr, _default in [("verbose", False), ("debug", False)]:
        if not hasattr(_lc, _attr):
            setattr(_lc, _attr, _default)
except ImportError:
    pass
