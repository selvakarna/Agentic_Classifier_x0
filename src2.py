# import os
# import re
# import asyncio
# from typing import TypedDict, Literal

# from pydantic import BaseModel, Field
# from langchain_openai import AzureChatOpenAI
# from langgraph.graph import StateGraph, START, END
# from langgraph.checkpoint.memory import MemorySaver

# # =========================================================================
# # 1. AZURE OPENAI CONFIGURATION
# # =========================================================================

# AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
# AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
# AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# if not AZURE_OPENAI_API_KEY:
#     raise ValueError("AZURE_OPENAI_API_KEY not found")

# if not AZURE_OPENAI_ENDPOINT:
#     raise ValueError("AZURE_OPENAI_ENDPOINT not found")

# if not AZURE_OPENAI_DEPLOYMENT:
#     raise ValueError("AZURE_OPENAI_DEPLOYMENT not found")

# print("================================================")
# print("AZURE OPENAI CONFIG LOADED")
# print("================================================")

# print("API KEY:", AZURE_OPENAI_API_KEY[:10])
# print("ENDPOINT:", AZURE_OPENAI_ENDPOINT)
# print("DEPLOYMENT:", AZURE_OPENAI_DEPLOYMENT)

# # =========================================================================
# # 2. SHARED LLM
# # =========================================================================

# llm = AzureChatOpenAI(
#     azure_endpoint=AZURE_OPENAI_ENDPOINT,
#     api_key=AZURE_OPENAI_API_KEY,
#     api_version="2024-02-15-preview",
#     azure_deployment=AZURE_OPENAI_DEPLOYMENT,
#     temperature=0
# )

# # =========================================================================
# # 3. STATE DEFINITIONS
# # =========================================================================

# class RoutingDecision(BaseModel):
#     intent: Literal[
#         "calculator",
#         "weather",
#         "booking",
#         "general"
#     ] = Field(description="Routing target")

# class OrchestratorState(TypedDict):
#     user_query: str
#     intent: str
#     response: str

# # =========================================================================
# # 4. INTENT CLASSIFIER (FIXED WARNING HERE)
# # =========================================================================

# def intent_classifier(state: OrchestratorState):

#     structured_llm = llm.with_structured_output(RoutingDecision)

#     decision = structured_llm.invoke(
#         f"Route this query: {state['user_query']}"
#     )

#     # 🔥 FIX: convert enum object → string
#     intent = decision.intent.value

#     print(f"\n[ORCHESTRATOR] Intent: {intent}")

#     return {
#         "intent": intent
#     }

# # =========================================================================
# # 5. MCP CLIENT
# # =========================================================================

# async def call_mcp_agent(server_script: str, tool_name: str, arguments: dict) -> str:

#     from mcp import ClientSession
#     from mcp import StdioServerParameters
#     from mcp.client.stdio import stdio_client

#     server_params = StdioServerParameters(
#         command="python",
#         args=[server_script]
#     )

#     async with stdio_client(server_params) as (read_stream, write_stream):

#         async with ClientSession(read_stream, write_stream) as session:

#             await session.initialize()

#             result = await session.call_tool(
#                 tool_name,
#                 arguments=arguments
#             )

#             if hasattr(result, "content") and result.content:

#                 text_block = result.content[0]

#                 if hasattr(text_block, "text"):
#                     return text_block.text

#             return str(result)

# # =========================================================================
# # 6. WORKER AGENTS
# # =========================================================================

# def handle_general(state: OrchestratorState):

#     response = llm.invoke(state["user_query"])

#     return {"response": response.content}

# def handle_calculator(state: OrchestratorState):

#     numbers = re.findall(r"\d+", state["user_query"])

#     expression = "0"

#     if len(numbers) >= 2:
#         expression = f"{numbers[0]} * {numbers[1]}"

#     result = asyncio.run(
#         call_mcp_agent(
#             "servers/calculator_agent.py",
#             "calculate",
#             {"expression": expression}
#         )
#     )

#     return {"response": result}

# def handle_weather(state: OrchestratorState):

#     match = re.search(r"\bin\s+([a-zA-Z\s]+)", state["user_query"], re.IGNORECASE)

#     location = match.group(1).strip() if match else "India"

#     result = asyncio.run(
#         call_mcp_agent(
#             "servers/weather_agent.py",
#             "get_weather",
#             {"location": location}
#         )
#     )

#     return {"response": result}

# def handle_booking(state: OrchestratorState):

#     result = asyncio.run(
#         call_mcp_agent(
#             "servers/booking_agent.py",
#             "create_booking",
#             {
#                 "service": "Hotel Room",
#                 "date": "Tomorrow"
#             }
#         )
#     )

#     return {"response": result}

# # =========================================================================
# # 7. ROUTER
# # =========================================================================

# def router_edge(state: OrchestratorState):
#     return f"node_{state['intent']}"

# # =========================================================================
# # 8. BUILD GRAPH
# # =========================================================================

# builder = StateGraph(OrchestratorState)

# builder.add_node("classifier", intent_classifier)
# builder.add_node("node_calculator", handle_calculator)
# builder.add_node("node_weather", handle_weather)
# builder.add_node("node_booking", handle_booking)
# builder.add_node("node_general", handle_general)

# builder.add_edge(START, "classifier")

# builder.add_conditional_edges(
#     "classifier",
#     router_edge,
#     {
#         "node_calculator": "node_calculator",
#         "node_weather": "node_weather",
#         "node_booking": "node_booking",
#         "node_general": "node_general"
#     }
# )

# builder.add_edge("node_calculator", END)
# builder.add_edge("node_weather", END)
# builder.add_edge("node_booking", END)
# builder.add_edge("node_general", END)

# memory_checkpointer = MemorySaver()

# app = builder.compile(checkpointer=memory_checkpointer)

# # =========================================================================
# # 9. MAIN LOOP
# # =========================================================================

# if __name__ == "__main__":

#     print("================================================")
#     print("MULTI AGENT SYSTEM STARTED")
#     print("Type 'exit' to quit")
#     print("================================================")

#     config = {"configurable": {"thread_id": "session-user-123"}}

#     while True:
#         try:
#             user_input = input("\nYou: ").strip()

#             if not user_input:
#                 continue

#             if user_input.lower() in ["exit", "quit"]:
#                 print("Exiting...")
#                 break

#             output = app.invoke(
#                 {"user_query": user_input},
#                 config=config
#             )

#             print(f"\nIntent: {output['intent']}")
#             print(f"Response: {output['response']}")

#         except Exception as e:
#             print(f"\nError: {str(e)}")

################
# import os
# import re
# import asyncio
# from typing import TypedDict, Literal

# from pydantic import BaseModel, Field
# from langchain_openai import AzureChatOpenAI
# from langgraph.graph import StateGraph, START, END
# from langgraph.checkpoint.memory import MemorySaver

# # =========================================================================
# # 1. AZURE OPENAI CONFIGURATION
# # =========================================================================

# AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
# AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
# AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# if not AZURE_OPENAI_API_KEY:
#     raise ValueError("AZURE_OPENAI_API_KEY not found")

# if not AZURE_OPENAI_ENDPOINT:
#     raise ValueError("AZURE_OPENAI_ENDPOINT not found")

# if not AZURE_OPENAI_DEPLOYMENT:
#     raise ValueError("AZURE_OPENAI_DEPLOYMENT not found")

# print("================================================")
# print("AZURE OPENAI CONFIG LOADED")
# print("================================================")

# print("API KEY:", AZURE_OPENAI_API_KEY[:10])
# print("ENDPOINT:", AZURE_OPENAI_ENDPOINT)
# print("DEPLOYMENT:", AZURE_OPENAI_DEPLOYMENT)

# # =========================================================================
# # 2. SHARED LLM
# # =========================================================================

# llm = AzureChatOpenAI(
#     azure_endpoint=AZURE_OPENAI_ENDPOINT,
#     api_key=AZURE_OPENAI_API_KEY,
#     api_version="2024-02-15-preview",
#     azure_deployment=AZURE_OPENAI_DEPLOYMENT,
#     temperature=0
# )

# # =========================================================================
# # 3. STATE DEFINITIONS (SAFE PRIMITIVES ONLY)
# # =========================================================================

# class RoutingDecision(BaseModel):
#     intent: Literal[
#         "calculator",
#         "weather",
#         "booking",
#         "general"
#     ] = Field(description="Routing target")

# class OrchestratorState(TypedDict):
#     user_query: str
#     intent: str
#     response: str

# # =========================================================================
# # 4. INTENT CLASSIFIER (FIXED COMPLETELY)
# # =========================================================================

# def intent_classifier(state: OrchestratorState):

#     structured_llm = llm.with_structured_output(RoutingDecision)

#     decision = structured_llm.invoke(
#         f"Route this query: {state['user_query']}"
#     )

#     # ✅ SAFE conversion (fixes your crash)
#     intent = decision.intent

#     if hasattr(intent, "value"):
#         intent = intent.value

#     intent = str(intent)

#     print(f"\n[ORCHESTRATOR] Intent: {intent}")

#     return {
#         "intent": intent
#     }

# # =========================================================================
# # 5. MCP CLIENT
# # =========================================================================

# async def call_mcp_agent(server_script: str, tool_name: str, arguments: dict) -> str:

#     from mcp import ClientSession, StdioServerParameters
#     from mcp.client.stdio import stdio_client

#     server_params = StdioServerParameters(
#         command="python",
#         args=[server_script]
#     )

#     async with stdio_client(server_params) as (read_stream, write_stream):

#         async with ClientSession(read_stream, write_stream) as session:

#             await session.initialize()

#             result = await session.call_tool(
#                 tool_name,
#                 arguments=arguments
#             )

#             if hasattr(result, "content") and result.content:

#                 text_block = result.content[0]

#                 if hasattr(text_block, "text"):
#                     return text_block.text

#             return str(result)

# # =========================================================================
# # 6. WORKER AGENTS
# # =========================================================================

# def handle_general(state: OrchestratorState):

#     response = llm.invoke(state["user_query"])

#     return {"response": response.content}

# def handle_calculator(state: OrchestratorState):

#     numbers = re.findall(r"\d+", state["user_query"])

#     expression = "0"

#     if len(numbers) >= 2:
#         expression = f"{numbers[0]} * {numbers[1]}"

#     result = asyncio.run(
#         call_mcp_agent(
#             "servers/calculator_agent.py",
#             "calculate",
#             {"expression": expression}
#         )
#     )

#     return {"response": result}

# def handle_weather(state: OrchestratorState):

#     match = re.search(r"\bin\s+([a-zA-Z\s]+)", state["user_query"], re.IGNORECASE)

#     location = match.group(1).strip() if match else "India"

#     result = asyncio.run(
#         call_mcp_agent(
#             "servers/weather_agent.py",
#             "get_weather",
#             {"location": location}
#         )
#     )

#     return {"response": result}

# def handle_booking(state: OrchestratorState):

#     result = asyncio.run(
#         call_mcp_agent(
#             "servers/booking_agent.py",
#             "create_booking",
#             {
#                 "service": "Hotel Room",
#                 "date": "Tomorrow"
#             }
#         )
#     )

#     return {"response": result}

# # =========================================================================
# # 7. ROUTER
# # =========================================================================

# def router_edge(state: OrchestratorState):
#     return f"node_{state['intent']}"

# # =========================================================================
# # 8. BUILD GRAPH
# # =========================================================================

# builder = StateGraph(OrchestratorState)

# builder.add_node("classifier", intent_classifier)
# builder.add_node("node_calculator", handle_calculator)
# builder.add_node("node_weather", handle_weather)
# builder.add_node("node_booking", handle_booking)
# builder.add_node("node_general", handle_general)

# builder.add_edge(START, "classifier")

# builder.add_conditional_edges(
#     "classifier",
#     router_edge,
#     {
#         "node_calculator": "node_calculator",
#         "node_weather": "node_weather",
#         "node_booking": "node_booking",
#         "node_general": "node_general"
#     }
# )

# builder.add_edge("node_calculator", END)
# builder.add_edge("node_weather", END)
# builder.add_edge("node_booking", END)
# builder.add_edge("node_general", END)

# memory_checkpointer = MemorySaver()

# app = builder.compile(checkpointer=memory_checkpointer)

# # =========================================================================
# # 9. MAIN LOOP
# # =========================================================================

# if __name__ == "__main__":

#     print("================================================")
#     print("MULTI AGENT SYSTEM STARTED")
#     print("Type 'exit' to quit")
#     print("================================================")

#     config = {"configurable": {"thread_id": "session-user-123"}}

#     while True:

#         try:
#             user_input = input("\nYou: ").strip()

#             if not user_input:
#                 continue

#             if user_input.lower() in ["exit", "quit"]:
#                 print("Exiting...")
#                 break

#             output = app.invoke(
#                 {"user_query": user_input},
#                 config=config
#             )

#             print(f"\nIntent: {output['intent']}")
#             print(f"Response: {output['response']}")

#         except Exception as e:
#             print(f"\nError: {str(e)}")


######################
import os
import re
import asyncio
from typing import TypedDict, Literal

from pydantic import BaseModel, Field
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
import warnings

# =========================================================
# 1. SILENCE ALL PYDANTIC WARNINGS (SAFE SIMPLE WAY)
# =========================================================
warnings.filterwarnings("ignore")

# =========================================================
# 2. AZURE OPENAI CONFIG
# =========================================================

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")

if not AZURE_OPENAI_API_KEY:
    raise ValueError("AZURE_OPENAI_API_KEY not found")

if not AZURE_OPENAI_ENDPOINT:
    raise ValueError("AZURE_OPENAI_ENDPOINT not found")

if not AZURE_OPENAI_DEPLOYMENT:
    raise ValueError("AZURE_OPENAI_DEPLOYMENT not found")

print("================================================")
print("AZURE OPENAI CONFIG LOADED")
print("================================================")

# =========================================================
# 3. AZURE LLM
# =========================================================

llm = AzureChatOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_API_KEY,
    api_version="2024-02-15-preview",
    azure_deployment=AZURE_OPENAI_DEPLOYMENT,
    temperature=0
)

# =========================================================
# 4. ROUTING MODEL
# =========================================================

class RoutingDecision(BaseModel):
    intent: Literal[
        "calculator",
        "weather",
        "booking",
        "general"
    ] = Field(description="Routing target")

class OrchestratorState(TypedDict):
    user_query: str
    intent: str
    response: str

# =========================================================
# 5. INTENT CLASSIFIER (FIXED COMPLETELY)
# =========================================================

def intent_classifier(state: OrchestratorState):

    structured_llm = llm.with_structured_output(RoutingDecision)

    decision = structured_llm.invoke(
        f"Route this query: {state['user_query']}"
    )

    # 🔥 SAFE: always convert to string (prevents .value crash)
    intent = str(decision.intent)

    print(f"\n[ORCHESTRATOR] Intent: {intent}")

    return {"intent": intent}

# =========================================================
# 6. MCP CLIENT
# =========================================================

async def call_mcp_agent(server_script: str, tool_name: str, arguments: dict) -> str:

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server_params = StdioServerParameters(
        command="python",
        args=[server_script]
    )

    async with stdio_client(server_params) as (read_stream, write_stream):

        async with ClientSession(read_stream, write_stream) as session:

            await session.initialize()

            result = await session.call_tool(
                tool_name,
                arguments=arguments
            )

            if hasattr(result, "content") and result.content:

                text_block = result.content[0]

                if hasattr(text_block, "text"):
                    return text_block.text

            return str(result)

# =========================================================
# 7. WORKER NODES
# =========================================================

def handle_general(state: OrchestratorState):

    res = llm.invoke(state["user_query"])
    return {"response": res.content}

def handle_calculator(state: OrchestratorState):

    numbers = re.findall(r"\d+", state["user_query"])

    expression = "0"
    if len(numbers) >= 2:
        expression = f"{numbers[0]} * {numbers[1]}"

    result = asyncio.run(
        call_mcp_agent(
            "servers/calculator_agent.py",
            "calculate",
            {"expression": expression}
        )
    )

    return {"response": result}

def handle_weather(state: OrchestratorState):

    match = re.search(
        r"\bin\s+([a-zA-Z\s]+)",
        state["user_query"],
        re.IGNORECASE
    )

    location = match.group(1).strip() if match else "India"

    result = asyncio.run(
        call_mcp_agent(
            "servers/weather_agent.py",
            "get_weather",
            {"location": location}
        )
    )

    return {"response": result}

def handle_booking(state: OrchestratorState):

    result = asyncio.run(
        call_mcp_agent(
            "servers/booking_agent.py",
            "create_booking",
            {
                "service": "Hotel Room",
                "date": "Tomorrow"
            }
        )
    )

    return {"response": result}

# =========================================================
# 8. ROUTER
# =========================================================

def router_edge(state: OrchestratorState):
    return f"node_{state['intent']}"

# =========================================================
# 9. BUILD GRAPH
# =========================================================

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

app = builder.compile(checkpointer=MemorySaver())

# =========================================================
# 10. MAIN LOOP
# =========================================================

if __name__ == "__main__":

    print("================================================")
    print("MULTI AGENT SYSTEM STARTED")
    print("Type 'exit' to quit")
    print("================================================")

    config = {"configurable": {"thread_id": "session-user-123"}}

    while True:
        try:

            user_input = input("\nYou: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit"]:
                print("Exiting...")
                break

            output = app.invoke(
                {"user_query": user_input},
                config=config
            )

            print(f"\nIntent: {output['intent']}")
            print(f"Response: {output['response']}")

        except Exception as e:
            print(f"\nError: {str(e)}")