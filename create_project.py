import os

BASE = "multi_agent_system"

files = {
f"{BASE}/app/__init__.py": "",

f"{BASE}/app/registry.py": """
AGENTS = {}

def agent(name):
    def wrapper(func):
        AGENTS[name] = func
        return func
    return wrapper
""",

f"{BASE}/app/load_agents.py": """
import pkgutil
import importlib
import app.agents as agents_pkg

def load_agents():
    for _, module_name, _ in pkgutil.iter_modules(agents_pkg.__path__):
        importlib.import_module(f"app.agents.{module_name}")
""",

f"{BASE}/app/config.py": """
import os
from langchain_openai import AzureChatOpenAI

llm = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-02-15-preview",
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
    temperature=0
)
""",

f"{BASE}/app/state.py": """
from typing import TypedDict

class State(TypedDict):
    user_query: str
    route: str
    response: str
""",

f"{BASE}/app/router.py": """
from app.config import llm
from app.registry import AGENTS

def router_node(state):

    agent_list = " | ".join(list(AGENTS.keys()))

    prompt = f\"\"\"
    Route into one of these agents:
    {agent_list} | general

    Query: {state['user_query']}
    \"\"\"

    route = llm.invoke(prompt).content.strip().lower()

    return {"route": route}
""",

f"{BASE}/app/dispatcher.py": """
from app.registry import AGENTS

def dispatcher(state):

    route = state["route"]

    if route not in AGENTS:
        route = "general"

    return AGENTS[route](state)
""",

f"{BASE}/app/mcp_client.py": """
import asyncio

async def call_mcp(server_script, tool, args):

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server = StdioServerParameters(command="python", args=[server_script])

    async with stdio_client(server) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.call_tool(tool, args)

            if result.content:
                return result.content[0].text

            return str(result)
""",

f"{BASE}/app/agents/general.py": """
from app.registry import agent
from app.config import llm

@agent("general")
def general(state):
    res = llm.invoke(state["user_query"])
    return {"response": res.content}
""",

f"{BASE}/app/agents/calculator.py": """
import re, asyncio
from app.registry import agent
from app.mcp_client import call_mcp

@agent("calculator")
def calculator(state):

    nums = re.findall(r"\\d+", state["user_query"])
    expr = f"{nums[0]} * {nums[1]}" if len(nums) >= 2 else "0"

    result = asyncio.run(call_mcp(
        "servers/calculator_agent.py",
        "calculate",
        {"expression": expr}
    ))

    return {"response": result}
""",

f"{BASE}/app/agents/weather.py": """
import re, asyncio
from app.registry import agent
from app.mcp_client import call_mcp

@agent("weather")
def weather(state):

    match = re.search(r"in\\s+([a-zA-Z\\s]+)", state["user_query"], re.I)
    location = match.group(1) if match else "India"

    result = asyncio.run(call_mcp(
        "servers/weather_agent.py",
        "get_weather",
        {"location": location}
    ))

    return {"response": result}
""",

f"{BASE}/app/agents/booking.py": """
import asyncio
from app.registry import agent
from app.mcp_client import call_mcp

@agent("booking")
def booking(state):

    result = asyncio.run(call_mcp(
        "servers/booking_agent.py",
        "create_booking",
        {"service": "Hotel Room", "date": "Tomorrow"}
    ))

    return {"response": result}
""",

f"{BASE}/app/main.py": """
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.state import State
from app.router import router_node
from app.dispatcher import dispatcher
from app.load_agents import load_agents

load_agents()

builder = StateGraph(State)

builder.add_node("router", router_node)
builder.add_node("dispatcher", dispatcher)

builder.add_edge(START, "router")
builder.add_edge("router", "dispatcher")
builder.add_edge("dispatcher", END)

app = builder.compile(checkpointer=MemorySaver())

if __name__ == "__main__":

    print("\\n=== MULTI AGENT SYSTEM READY ===\\n")

    config = {"configurable": {"thread_id": "user-1"}}

    while True:
        q = input("\\nYou: ")
        if q.lower() in ["exit", "quit"]:
            break

        res = app.invoke({"user_query": q}, config=config)
        print("\\nResponse:", res["response"])
""",

f"{BASE}/requirements.txt": """
langchain-openai
langgraph
pydantic
mcp
"""
}

for path, content in files.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.strip())

print("✅ Project created successfully: multi_agent_system")