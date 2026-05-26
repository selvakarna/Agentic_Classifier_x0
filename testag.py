import sys
import os
import re
import asyncio
from typing import TypedDict, Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

# =========================================================================
# 1. CRITICAL CORPORATE NETWORK PROXY CONFIGURATION
# =========================================================================
# Paste your working OpenAI API key here
OPENAI_API_KEY = "1kKtXUC9zZN1j6Z0HUjyauHwrogApzDRugViHJ0Zpnv1Oq2lCiYyJQQJ99BLACYeBjFXJ3w3AAABACOGuWl1"

# Enter your corporate proxy URL and port (e.g., http://quest-global.com)
# This forces Python to pass through Zscaler instead of getting intercepted
CORPORATE_PROXY = "http://YOUR_PROXY_ADDRESS:PORT" 

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["HTTP_PROXY"] = CORPORATE_PROXY
os.environ["HTTPS_PROXY"] = CORPORATE_PROXY

# =========================================================================
# 2. STATE & SCHEMA DEFINITIONS
# =========================================================================
class RoutingDecision(BaseModel):
    intent: Literal["calculator", "weather", "booking", "general"] = Field(
        description="The target domain matching the user request."
    )

class OrchestratorState(TypedDict):
    user_query: str
    intent: str
    response: str

# =========================================================================
# 3. REAL OPENAI INTENT CLASSIFIER NODE (FIXED REGEX LOOKUPS)
# =========================================================================
def intent_classifier(state: OrchestratorState):
    # Fallback to check if proxy variables are still default placeholders
    if "YOUR_PROXY_ADDRESS" in CORPORATE_PROXY:
        # Programmatic safe matching if you haven't filled in your corporate proxy settings yet
        text = state["user_query"].lower()
        calc_keywords = ["calculate", "math", "multiply", "divide", "solve", "+", "-", "*", "/"]
        
        # FIXED: re.escape avoids the "nothing to repeat" compiler crash
        if any(re.search(rf"\b{re.escape(k)}\b", text) for k in calc_keywords):
            intent = "calculator"
        elif any(re.search(rf"\b{re.escape(k)}\b", text) for k in ["weather", "forecast", "temperature", "rain", "cold", "hot", "india"]):
            intent = "weather"
        elif any(re.search(rf"\b{re.escape(k)}\b", text) for k in ["book", "reserve", "ticket", "reservation", "schedule", "hotel", "room"]):
            intent = "booking"
        else:
            intent = "general"
        print(f"\n[ORCHESTRATOR] Local matching routed query to: 'NODE_{intent.upper()}'")
        return {"intent": intent}

    # If your corporate proxy config is set up, use the real OpenAI API call
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    structured_llm = llm.with_structured_output(RoutingDecision)
    decision = structured_llm.invoke(
        f"Analyze this prompt and classify the department into 'calculator', 'weather', 'booking', or 'general': {state['user_query']}"
    )
    print(f"\n[ORCHESTRATOR] OpenAI classified query intent as: 'NODE_{decision.intent.upper()}'")
    return {"intent": decision.intent}

# =========================================================================
# 4. MCP CLIENT TRANS-PROCESS ROUTING ENGINE (A2A Protocol)
# =========================================================================
async def call_mcp_agent(server_script: str, tool_name: str, arguments: dict) -> str:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    
    server_params = StdioServerParameters(command="python", args=[server_script])
    
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            
            # Unpack FastMCP structural list response schemas safely
            if hasattr(result, "content") and isinstance(result.content, list):
                if len(result.content) > 0 and hasattr(result.content, "text"):
                    return result.content.text
            return str(result)

# =========================================================================
# 5. REAL WORKER AGENT GRAPH NODES
# =========================================================================
def handle_calculator(state: OrchestratorState):
    if "YOUR_PROXY_ADDRESS" in CORPORATE_PROXY:
        numbers = re.findall(r'\d+', state["user_query"])
        tool_args = {"expression": f"{numbers[0]} * {numbers[1]}" if len(numbers) >= 2 else "0"}
    else:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools([
            {"name": "calculate", "description": "Safely evaluates mathematical equations like multiplication.", 
             "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}}
        ])
        ai_msg = llm.invoke(state["user_query"])
        tool_args = ai_msg.tool_calls[0]["args"] if ai_msg.tool_calls else {"expression": "0"}

    res = asyncio.run(call_mcp_agent("servers/calculator_agent.py", "calculate", tool_args))
    return {"response": res}

def handle_weather(state: OrchestratorState):
    if "YOUR_PROXY_ADDRESS" in CORPORATE_PROXY:
        text = state["user_query"]
        match = re.search(r'\bin\s+([a-zA-Z\s]+)', text, re.IGNORECASE)
        tool_args = {"location": match.group(1).strip().title() if match else "India"}
    else:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools([
            {"name": "get_weather", "description": "Fetches regional weather for a location string.", 
             "parameters": {"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"]}}
        ])
        ai_msg = llm.invoke(state["user_query"])
        tool_args = ai_msg.tool_calls[0]["args"] if ai_msg.tool_calls else {"location": "India"}

    res = asyncio.run(call_mcp_agent("servers/weather_agent.py", "get_weather", tool_args))
    return {"response": res}

def handle_booking(state: OrchestratorState):
    if "YOUR_PROXY_ADDRESS" in CORPORATE_PROXY:
        service = "Hotel Room" if "hotel" in state["user_query"].lower() else "Flight Ticket"
        tool_args = {"service": service, "date": "Next Friday night"}
    else:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools([
            {"name": "create_booking", "description": "Reserves service schedules for explicit dates.", 
             "parameters": {"type": "object", "properties": {"service": {"type": "string"}, "date": {"type": "string"}}, "required": ["service", "date"]}}
        ])
        ai_msg = llm.invoke(state["user_query"])
        tool_args = ai_msg.tool_calls[0]["args"] if ai_msg.tool_calls else {"service": "Hotel Room", "date": "Today"}

    res = asyncio.run(call_mcp_agent("servers/booking_agent.py", "create_booking", tool_args))
    return {"response": res}

def handle_general(state: OrchestratorState):
    if "YOUR_PROXY_ADDRESS" in CORPORATE_PROXY:
        return {"response": "[Local General Agent]: Hello! Running in local-safe developer fallback mode."}
    llm = ChatOpenAI(model="gpt-4o-mini")
    res = llm.invoke(state["user_query"])
    return {"response": res.content}

# =========================================================================
# 6. GRAPH MANAGEMENT & TOPOLOGY BUILDING
# =========================================================================
def router_edge(state: OrchestratorState) -> str:
    return f"node_{state['intent']}"

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

# =========================================================================
# 7. RUN EXECUTABLE TERMINAL LAYER
# =========================================================================
if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        output = app.invoke({"user_query": query})
        print(f"\n[AI CLASSIFIED ROUTE]: {output['intent'].upper()}")
        print(f"Final Outcome: {output['response']}")
    else:
        print("Usage: python main.py '<your query>'")
