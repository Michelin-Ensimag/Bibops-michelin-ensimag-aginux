class ShortTermMemory:
    def __init__(self, max_messages=50):
        self.conversation_history = []
        self.max_messages = max_messages

    def add_message(self, role, content):
        self.conversation_history.append({
            "role": role,
            "content": content
        })
        # Trim old messages if exceeding limit
        if len(self.conversation_history) > self.max_messages:
            self.conversation_history = self.conversation_history[-self.max_messages:]


def keep_everything(conversation_history, new_message):
    """Simple approach: retain all messages"""
    conversation_history.append(new_message)

    return conversation_history


def sliding_window(conversation_history, new_message, window_size=10):
    """Keep only the last N messages"""
    conversation_history.append(new_message)
    if len(conversation_history) > window_size:
        conversation_history = conversation_history[-window_size:]

    return conversation_history


def importance_based(conversation_history, new_message):
    """Retain only messages marked as important"""
    if is_important(new_message):
        conversation_history.append(new_message)

    return conversation_history


def summarization_strategy(conversation_history, threshold=20):
    """Summarize old messages when history grows too long"""
    summary = summarize(conversation_history[:threshold])
    conversation_history = [summary] + conversation_history[threshold:]

    return conversation_history