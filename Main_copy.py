import sys
import asyncio
from typing import TypedDict, Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 1. Define Routing Targets via Pydantic Schema
class RoutingDecision(BaseModel):
    intent: Literal["calculator", "weather", "booking", "general"] = Field(
        description="The primary domain of the user request."
    )

class OrchestratorState(TypedDict):
    user_query: str
    intent: str
    tool_args: dict
    response: str

# 2. Intent Classifier Layer
def intent_classifier(state: OrchestratorState):
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    structured_llm = llm.with_structured_output(RoutingDecision)
    
    decision = structured_llm.invoke(
        f"Analyze this prompt and classify the department: {state['user_query']}"
    )
    return {"intent": decision.intent}

# 3. Dynamic MCP Client Engine (A2A Protocol Broker)
async def call_mcp_agent(server_script: str, tool_name: str, arguments: dict) -> str:
    """Orchestrates an out-of-process execution to an MCP sub-agent server."""
    server_params = StdioServerParameters(
        command="python",
        args=[server_script],
    )
    
    # Establish A2A connection pipeline via MCP stdio layer
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            return result.content[0].text

# 4. Master Orchestration Graph Workers
def handle_calculator(state: OrchestratorState):
    # LLM infers exact parameters from free text
    llm = ChatOpenAI(model="gpt-4o-mini").bind_tools([
        {"name": "calculate", "description": "Calculate math expression", 
         "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}}}
    ])
    ai_msg = llm.invoke(state["user_query"])
    tool_call = ai_msg.tool_calls[0]["args"]
    
    # Send tool execution command payload to external MCP Server
    res = asyncio.run(call_mcp_agent("servers/calculator_agent.py", "calculate", tool_call))
    return {"response": f"[Calculator Agent Response]: {res}"}

def handle_weather(state: OrchestratorState):
    llm = ChatOpenAI(model="gpt-4o-mini").bind_tools([
        {"name": "get_weather", "description": "Get location weather", 
         "parameters": {"type": "object", "properties": {"location": {"type": "string"}}}}
    ])
    ai_msg = llm.invoke(state["user_query"])
    tool_call = ai_msg.tool_calls[0]["args"]
    
    res = asyncio.run(call_mcp_agent("servers/weather_agent.py", "get_weather", tool_call))
    return {"response": f"[Weather Agent Response]: {res}"}

def handle_booking(state: OrchestratorState):
    llm = ChatOpenAI(model="gpt-4o-mini").bind_tools([
        {"name": "create_booking", "description": "Create a reservation", 
         "parameters": {"type": "object", "properties": {"service": {"type": "string"}, "date": {"type": "string"}}}}
    ])
    ai_msg = llm.invoke(state["user_query"])
    tool_call = ai_msg.tool_calls[0]["args"]
    
    res = asyncio.run(call_mcp_agent("servers/booking_agent.py", "create_booking", tool_call))
    return {"response": f"[Booking Agent Response]: {res}"}

def handle_general(state: OrchestratorState):
    llm = ChatOpenAI(model="gpt-4o-mini")
    res = llm.invoke(state["user_query"])
    return {"response": f"[General Agent Response]: {res.content}"}

# 5. Connect Routing Tracks
def router_edge(state: OrchestratorState) -> str:
    return f"node_{state['intent']}"

# Build Graph Topologies
builder = StateGraph(OrchestratorState)
builder.add_node("classifier", intent_classifier)
builder.add_node("node_calculator", handle_calculator)
builder.add_node("node_weather", handle_weather)
builder.add_node("node_booking", handle_booking)
builder.add_node("node_general", handle_general)

builder.add_edge(START, "classifier")
builder.add_conditional_edges(
    "classifier",
    router_edge,
    {
        "node_calculator": "node_calculator",
        "node_weather": "node_weather",
        "node_booking": "node_booking",
        "node_general": "node_general"
    }
)
builder.add_edge("node_calculator", END)
builder.add_edge("node_weather", END)
builder.add_edge("node_booking", END)
builder.add_edge("node_general", END)

app = builder.compile()

# 6. Terminal Input Broker
if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        output = app.invoke({"user_query": query})
        print(f"\n[Detected Intent]: {output['intent'].upper()}")
        print(f"{output['response']}")
    else:
        print("Usage: python main.py '<your query>'")
