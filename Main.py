import sys
import re
import asyncio
from typing import TypedDict, Literal
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END

# =========================================================================
# 1. DEFINE SYSTEM ARCHITECTURE STATE
# =========================================================================
class RoutingDecision(BaseModel):
    intent: Literal["calculator", "weather", "booking", "general"] = Field(
        description="The target department matching the user request."
    )

class OrchestratorState(TypedDict):
    user_query: str
    intent: str
    response: str

# =========================================================================
# 2. LOCAL INTENT CLASSIFIER (Bypasses Zscaler Proxy Safely)
# =========================================================================
def intent_classifier(state: OrchestratorState):
    text = state["user_query"].lower()
    
    # Check for whole words using regular expression boundaries (\b)
    if any(re.search(rf"\b{k}\b", text) for k in ["calculate", "math", "multiply", "divide", "solve", "+", "-", "*", "/"]):
        intent = "calculator"
    elif any(re.search(rf"\b{k}\b", text) for k in ["weather", "forecast", "temperature", "rain", "cold", "hot"]):
        intent = "weather"
    elif any(re.search(rf"\b{k}\b", text) for k in ["book", "reserve", "ticket", "reservation", "schedule", "hotel", "room"]):
        intent = "booking"
    else:
        intent = "general"
        
    print(f"\n[ORCHESTRATOR] Local routing matched query to: 'NODE_{intent.upper()}'")
    return {"intent": intent}
# def intent_classifier(state: OrchestratorState):
#     text = state["user_query"].lower()
    
#     if any(k in text for k in ["calculate", "math", "multiply", "divide", "solve", "+", "-", "*", "/"]):
#         intent = "calculator"
#     elif any(k in text for k in ["weather", "forecast", "temperature", "rain", "cold", "hot"]):
#         intent = "weather"
#     elif any(k in text for k in ["book", "reserve", "ticket", "reservation", "schedule"]):
#         intent = "booking"
#     else:
#         intent = "general"
        
#     print(f"\n[ORCHESTRATOR] Local routing matched query to: 'NODE_{intent.upper()}'")
#     return {"intent": intent}

# =========================================================================
# 3. FIXED MCP CLIENT ENGINE (Handles Array Responses Natively)
# =========================================================================
async def call_mcp_agent(server_script: str, tool_name: str, arguments: dict) -> str:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    
    server_params = StdioServerParameters(command="python", args=[server_script])
    
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            
            # Unpack FastMCP list structure to fix the AttributeError
            if hasattr(result, 'content') and isinstance(result.content, list):
                if len(result.content) > 0 and hasattr(result.content[0], 'text'):
                    return result.content[0].text
            return str(result)

# =========================================================================
# 4. PROGRAMMATIC WORKER AGENT NODES (Bypasses LLM Network Dependencies)
# =========================================================================
def handle_calculator(state: OrchestratorState):
    text = state["user_query"]
    numbers = re.findall(r'\d+', text)
    
    if len(numbers) >= 2:
        expression = f"{numbers[0]} * {numbers[1]}"  # Default multiplication
        if "divide" in text.lower() or "divided" in text.lower() or "/" in text:
            expression = f"{numbers[0]} / {numbers[1]}"
        elif "add" in text.lower() or "plus" in text.lower() or "+" in text:
            expression = f"{numbers[0]} + {numbers[1]}"
        elif "subtract" in text.lower() or "minus" in text.lower() or "-" in text:
            expression = f"{numbers[0]} - {numbers[1]}"
            
        tool_args = {"expression": expression}
        print(f"[A2A PROTOCOL] Passing arguments {tool_args} to Calculator MCP Server...")
        res = asyncio.run(call_mcp_agent("servers/calculator_agent.py", "calculate", tool_args))
        return {"response": res}
        
    return {"response": "[Calculator Agent Error]: Could not parse numeric inputs."}

def handle_weather(state: OrchestratorState):
    text = state["user_query"]
    
    location = "London"  # Default fallback
    for city in ["london", "tokyo", "new york"]:
        if city in text.lower():
            location = city.title()
            
    tool_args = {"location": location}
    print(f"[A2A PROTOCOL] Passing arguments {tool_args} to Weather MCP Server...")
    res = asyncio.run(call_mcp_agent("servers/weather_agent.py", "get_weather", tool_args))
    return {"response": res}

def handle_booking(state: OrchestratorState):
    text = state["user_query"]
    
    service = "Flight Ticket"
    if "hotel" in text.lower() or "room" in text.lower():
        service = "Hotel Room"
    elif "table" in text.lower() or "dinner" in text.lower():
        service = "Restaurant Table"
        
    tool_args = {"service": service, "date": "June 15th"}
    print(f"[A2A PROTOCOL] Passing arguments {tool_args} to Booking MCP Server...")
    res = asyncio.run(call_mcp_agent("servers/booking_agent.py", "create_booking", tool_args))
    return {"response": res}

def handle_general(state: OrchestratorState):
    return {"response": "[Local General Agent Response]: Hello! I am running in local-safe developer mode."}

# =========================================================================
# 5. GRAPH ROUTING CONNECTIONS
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
# 6. RUN EXECUTABLE TERMINAL HANDLER
# =========================================================================
if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        output = app.invoke({"user_query": query})
        print(f"\n[AI CLASSIFIED ROUTE]: {output['intent'].upper()}")
        print(f"Final Outcome: {output['response']}")
    else:
        print("Usage: python main.py '<your query>'")
