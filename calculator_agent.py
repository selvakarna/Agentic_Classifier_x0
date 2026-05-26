import sys
from mcp.server.fastmcp import FastMCP

# Create a FastMCP server instance for the Calculator agent
mcp = FastMCP("CalculatorAgent")

@mcp.tool()
def calculate(expression: str) -> str:
    """Evaluates simple mathematical expressions like '2 + 2' or '10 * 5' safely."""
    try:
        # Simple evaluation logic for testing
        allowed_chars = "0123456789+-*/(). "
        if not all(c in allowed_chars for c in expression):
            return "Error: Invalid characters detected."
        return str(eval(expression))
    except Exception as e:
        return f"Error evaluating expression: {str(e)}"

if __name__ == "__main__":
    mcp.run()
