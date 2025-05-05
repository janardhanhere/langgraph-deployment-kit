from typing import Annotated

from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from typing import List


class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]
    reformated: str
    docs: List[str]
    suggestions: List[str]


graph_builder = StateGraph(State)

from langchain.chat_models import init_chat_model

# Change the model to use OpenAI GPT-4 instead of Claude
llm = init_chat_model("openai:gpt-4-turbo")

async def reformulate_query(state: State):
    # The function now returns a coroutine
    return {'reformated': 'this is a reformated query'}

async def search(state: State):
    # The function now returns a coroutine
    return {
        "docs": ["doc1", "doc2", "doc3"]
    }

async def chatbot(state: State):
    # Use await with the LLM invoke
    return {"messages": [await llm.ainvoke(state["messages"])]}

async def suggest(state: State):
    # The function now returns a coroutine
    return {
        "suggestions": ["suggestion1", "suggestion2", "suggestion3"]
    }

# The first argument is the unique node name
# The second argument is the function or object that will be called whenever
# the node is used.

graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("reformulate_query", reformulate_query)
graph_builder.add_node("search", search)
graph_builder.add_node("suggest", suggest)

graph_builder.add_edge(START, "reformulate_query")
graph_builder.add_edge("reformulate_query", "search")
graph_builder.add_edge("search", "chatbot")
graph_builder.add_edge("chatbot", 'suggest')
graph_builder.add_edge("suggest", END)
research_assistant = graph_builder.compile()