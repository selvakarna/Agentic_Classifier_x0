import sys
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("WeatherAgent")

@mcp.tool()
def get_weather(location: str) -> str:
    """Fetches current weather information for a given city or location."""
    # Mock data for demonstration purposes
    loc = location.lower()
    if "london" in loc:
        return "London: 15°C, Rain"
    elif "new york" in loc:
        return "New York: 22°C, Sunny"
    elif "tokyo" in loc:
        return "Tokyo: 18°C, Cloudy"
    return f"{location.title()}: 20°C, Clear Skies"

if __name__ == "__main__":
    mcp.run()
