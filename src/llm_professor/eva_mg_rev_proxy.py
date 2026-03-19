import sqlite3
import time
# ON CHANGE L'IMPORT ICI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

# schéma JSON attendu (Inchangé)
class EvaluationResult(BaseModel):
    note: int = Field(description="Note entière de 1 à 5")
    justification: str = Field(description="Explication courte de la note")


class LLMProfessor:
    # On change le modèle par défaut pour utiliser celui de Copilot (ex: gpt-4o ou claude-3.5-sonnet)
    def __init__(self, db_path, modele_juge="claude-sonnet-4.6"):  # <-- Il utilisera claude-sonnet-4.6 ici
        self.db_path = db_path

        # ON MODIFIE LE CLIENT LLM ICI
        # On utilise ChatOpenAI en le pointant vers le proxy local (Port 4141)
        self.juge_llm = ChatOpenAI(
            base_url="http://localhost:4141/v1",
            api_key="dummy", # Le proxy n'a pas besoin de vraie clé API, "dummy" suffit
            model=modele_juge,
            temperature=0.0,
            # On demande explicitement du JSON
            model_kwargs={"response_format": {"type": "json_object"}}
        )
        self.parser = JsonOutputParser(pydantic_object=EvaluationResult)

        # Le Prompt d'évaluation (Inchangé)
        prompt_template = """Tu es un expert en support IT (BibOps LLM Professor). 
    Ta mission est d'évaluer la réponse d'un agent IA à un ticket utilisateur.
    
    Critères d'évaluation :
    0. execute a chain of thought 
    1. Pertinence : La réponse adresse-t-elle le problème exact ?
    2. Clarté : Les instructions sont-elles faciles à suivre ?
    3. Complétude : Manque-t-il des étapes cruciales ?
    
    Renvoie UNIQUEMENT un objet JSON valide avec 'note' (entier 1-5) et 'justification' (string).
    {format_instructions}
    
    Ticket Utilisateur : {ticket}
    Réponse de l'Agent : {reponse_agent}"""

        self.prompt = ChatPromptTemplate.from_template(prompt_template)
        # la chaîne (Pipeline)
        self.chain = self.prompt | self.juge_llm | self.parser

    def evaluer_reponse(self, ticket_id, ticket_texte, reponse_agent, modele_agent, temps_reponse):
        """Demande au Juge de noter la réponse et sauvegarde le tout dans SQLite."""
        print(f"\n[🎓 LLM Professor] Analyse de la réponse de {modele_agent} par le Juge Copilot en cours...")

        try:
            # Invocation de la chaîne
            resultat = self.chain.invoke({
                "ticket": ticket_texte,
                "reponse_agent": reponse_agent,
                "format_instructions": self.parser.get_format_instructions()
            })

            note = resultat.get("note")
            justification = resultat.get("justification")

            print(f" -> Note : {note}/5")
            print(f" -> Justification : {justification}")

            self._sauvegarder_en_base(ticket_id, modele_agent, reponse_agent, temps_reponse, note, justification)
            return resultat

        except Exception as e:
            print(f"[❌ Erreur d'évaluation] : {e}")
            return None

    def _sauvegarder_en_base(self, ticket_id, modele, reponse, temps, note, justification):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO evaluations (ticket_id, modele, reponse_ia, temps_reponse_s, note_juge, justification_juge)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (ticket_id, modele, reponse, temps, note, justification))
            conn.commit()
        print("[🗄️ DB] Évaluation sauvegardée dans la table 'evaluations'.")