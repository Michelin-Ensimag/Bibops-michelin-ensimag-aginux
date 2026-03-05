class ShortTermMemory:
    """Conserve l'historique récent de la conversation pour donner du contexte à l'IA."""
    def __init__(self, max_messages=10):
        self.conversation_history = []
        self.max_messages = max_messages

    def add_message(self, role, content):
        self.conversation_history.append({"role": role, "content": content})
        # Stratégie "Sliding Window" : on oublie les trop vieux messages
        if len(self.conversation_history) > self.max_messages:
            self.conversation_history = self.conversation_history[-self.max_messages:]

    def get_messages(self):
        return self.conversation_history