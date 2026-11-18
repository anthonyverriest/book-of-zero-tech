# ---------------------------------------------------------------------------
# MCP server reference — FastMCP
#
# A minimal but complete server that exposes one tool, one resource, and
# one prompt. Use it as a starting point: copy, rename, and replace the
# placeholder logic with your own domain.
#
# Run (stdio, default):
#   python mcp-server.example.py
#   # or: fastmcp run mcp-server.example.py
#
# Run (HTTP, remote / multi-user):
#   python mcp-server.example.py --transport http --port 8000
#   # or: fastmcp run mcp-server.example.py --transport http --port 8000
#
# Test with the built-in client (in-memory, no network). Save this file as
# server.py first: "mcp-server.example.py" is not an importable module name.
#   python -c "
#   import asyncio
#   from fastmcp import Client
#   from server import mcp
#
#   async def main():
#       async with Client(mcp) as c:
#           print(await c.call_tool('lookup_order', {'order_id': 'ORD-42'}))
#
#   asyncio.run(main())
#   "
#
# Requirements:
#   pip install "fastmcp>=4.2"   (tested with 4.2.1, MCP spec 2026-07-28)
# ---------------------------------------------------------------------------

from __future__ import annotations

import argparse
import logging
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

# MCP's protocol-level logging is deprecated since spec 2026-07-28: log to
# stderr (never stdout, which carries the stdio transport) or use OpenTelemetry.
logging.basicConfig(level=logging.INFO)  # stderr by default
logger = logging.getLogger("order_service")

mcp = FastMCP(
    name="OrderService",
    instructions=(
        "You are a helpful assistant for an e-commerce order system. "
        "Use the available tools to look up orders, read store policies, "
        "and follow the provided prompts for structured customer interactions."
    ),
)

# ---------------------------------------------------------------------------
# Tool — model-controlled
#
# The model decides when to call a tool based on the user's request.
# Hosts should keep a human in the loop (confirmation prompts, allow-lists);
# annotations such as readOnlyHint help the host decide what to auto-approve.
#
# Tips:
#   - Type hints → automatic JSON Schema generation.
#   - Annotated[T, "..."] adds per-parameter descriptions.
#   - Raise ToolError for business-logic failures (shown to the model).
#   - Log to stderr; use Context (fastmcp.Context) for progress reporting.
# ---------------------------------------------------------------------------


@mcp.tool(
    description="Look up an order by its ID and return status details.",
    tags={"orders", "read"},
    annotations={"readOnlyHint": True},
)
async def lookup_order(
    order_id: Annotated[str, "Order identifier, e.g. ORD-42"],
) -> dict:
    logger.info("Looking up order %s", order_id)

    # --- Replace with a real database / API call ---
    orders = {
        "ORD-42": {
            "order_id": "ORD-42",
            "status": "shipped",
            "items": [{"sku": "WIDGET-7", "qty": 2}],
            "total": 39.98,
        },
    }

    order = orders.get(order_id)
    if order is None:
        raise ToolError(f"Order {order_id!r} not found.")

    return order


# ---------------------------------------------------------------------------
# Resource — application-controlled
#
# The host application decides when to include a resource in the model's
# context. Resources are read-only data identified by URI.
#
# Templates let clients request parameterized data:
#   "policies://{policy_name}" → "policies://returns", "policies://shipping"
# ---------------------------------------------------------------------------


@mcp.resource(
    "policies://{policy_name}",
    name="StorePolicy",
    description="Store policy documents (returns, shipping, warranty).",
    mime_type="text/plain",
    tags={"policies"},
)
def get_policy(policy_name: str) -> str:
    # --- Replace with a file read or CMS lookup ---
    policies = {
        "returns": (
            "Returns accepted within 30 days of delivery. "
            "Items must be unused and in original packaging."
        ),
        "shipping": (
            "Standard shipping: 5-7 business days. "
            "Express shipping: 1-2 business days (extra charge)."
        ),
        "warranty": (
            "All products carry a 1-year limited warranty "
            "covering manufacturing defects."
        ),
    }

    text = policies.get(policy_name)
    if text is None:
        available = ", ".join(sorted(policies))
        raise ValueError(
            f"Unknown policy {policy_name!r}. Available: {available}"
        )
    return text


# ---------------------------------------------------------------------------
# Prompt — user-controlled
#
# The user explicitly selects a prompt (e.g. via a slash command in the UI).
# Prompts return a list of messages that seed the conversation.
# ---------------------------------------------------------------------------


@mcp.prompt(
    name="handle_complaint",
    description="Guide the assistant through a structured customer complaint resolution.",
    tags={"support"},
)
def handle_complaint(
    customer_name: Annotated[str, "Customer's display name"],
    order_id: Annotated[str, "Related order ID"],
) -> list[Message]:
    return [
        Message(
            role="user",
            content=(
                f"Customer {customer_name} has a complaint about order "
                f"{order_id}. Look up the order, review the relevant store "
                "policy, and draft a resolution response."
            ),
        ),
        Message(
            role="assistant",
            content=(
                f"I'll start by looking up order {order_id} to understand "
                "the current status, then review the applicable policy before "
                "drafting a response."
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the MCP order service.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport to use (default: stdio).",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to when using HTTP transport (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on when using HTTP transport (default: 8000).",
    )
    args = parser.parse_args()

    if args.transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run()  # stdio takes no host/port
