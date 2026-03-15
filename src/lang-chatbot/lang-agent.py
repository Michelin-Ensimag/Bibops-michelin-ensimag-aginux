from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from langchain.agents.middleware import ModelFallbackMiddleware

llm = ChatOllama(model="mistral:latest",temperature=0)
llm_secours = ChatOllama(model="phi3:latest",temperature=0)

agent = create_agent(model = llm,
                    tools = tools,
                     middleware = [ModelFallbackMiddleware(llm_secours)])