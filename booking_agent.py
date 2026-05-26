import sys
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("BookingAgent")

@mcp.tool()
def create_booking(service: str, date: str) -> str:
    """Books a specific service (hotel, flight, table) on a specific date."""
    return f"Booking confirmed for {service} on {date}. Booking ID: B-{import_random_id()}"

def import_random_id():
    import random
    return random.randint(1000, 9999)

if __name__ == "__main__":
    mcp.run()
