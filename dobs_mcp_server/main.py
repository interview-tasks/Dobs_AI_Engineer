#!/usr/bin/env python3
"""
MCP Server for DOBS Financial Document Analyzer API
"""

import os
import json
import asyncio
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent
)

# Load environment variables
load_dotenv()

# Configuration
DOBS_API_KEY = os.getenv("DOBS_API_KEY")
DOBS_BASE_URL = os.getenv("DOBS_BASE_URL", "https://api.dobs.ai")

if not DOBS_API_KEY:
    raise ValueError("DOBS_API_KEY environment variable is required")

# Initialize server
server = Server("dobs-mcp-server")

class DobsApiClient:
    """Client for DOBS API"""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    async def make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to DOBS API"""
        url = f"{self.base_url}/api{endpoint}"

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                headers=self.headers,
                **kwargs
            )

            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    raise Exception(f"API Error {response.status_code}: {error_data}")
                except:
                    raise Exception(f"API Error {response.status_code}: {response.text}")

            return response.json()

# Initialize API client
api_client = DobsApiClient(DOBS_BASE_URL, DOBS_API_KEY)

@server.list_tools()
async def list_tools():
    """List available tools"""
    return [
        Tool(
            name="get_analytics",
            description="Get combined analytics data across suppliers, contracts, and invoices",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        ),
        Tool(
            name="get_contracts",
            description="Get all contracts with pagination, sorting, and filtering",
            inputSchema={
                "type": "object",
                "properties": {
                    "page": {"type": "integer", "default": 1, "description": "Page number"},
                    "per_page": {"type": "integer", "default": 20, "description": "Items per page"},
                    "sort_by": {"type": "string", "default": "created_at", "description": "Sort field"},
                    "sort_order": {"type": "string", "enum": ["asc", "desc"], "default": "desc", "description": "Sort order"},
                    "supplier_id": {"type": "string", "description": "Filter by supplier ID"}
                },
                "additionalProperties": False
            }
        ),
        Tool(
            name="get_invoices",
            description="Get all invoices with pagination, sorting, and filtering",
            inputSchema={
                "type": "object",
                "properties": {
                    "page": {"type": "integer", "default": 1, "description": "Page number"},
                    "per_page": {"type": "integer", "default": 20, "description": "Items per page"},
                    "sort_by": {"type": "string", "default": "created_at", "description": "Sort field"},
                    "sort_order": {"type": "string", "enum": ["asc", "desc"], "default": "desc", "description": "Sort order"},
                    "supplier_id": {"type": "string", "description": "Filter by supplier ID"}
                },
                "additionalProperties": False
            }
        ),
        Tool(
            name="search_documents",
            description="Search documents using vector embeddings",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query text"},
                    "type": {"type": "string", "enum": ["contract", "invoice", "pricing", "transaction"], "description": "Document type"},
                    "top_k": {"type": "integer", "default": 5, "description": "Number of results"}
                },
                "required": ["query", "type"],
                "additionalProperties": False
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls"""

    try:
        if name == "get_analytics":
            result = await api_client.make_request("GET", "/analytics")
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_contracts":
            params = {}
            if arguments.get("page"):
                params["page"] = arguments["page"]
            if arguments.get("per_page"):
                params["per_page"] = arguments["per_page"]
            if arguments.get("sort_by"):
                params["sort_by"] = arguments["sort_by"]
            if arguments.get("sort_order"):
                params["sort_order"] = arguments["sort_order"]
            if arguments.get("supplier_id"):
                params["supplier_id"] = arguments["supplier_id"]

            result = await api_client.make_request("GET", "/contracts", params=params)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_invoices":
            params = {}
            if arguments.get("page"):
                params["page"] = arguments["page"]
            if arguments.get("per_page"):
                params["per_page"] = arguments["per_page"]
            if arguments.get("sort_by"):
                params["sort_by"] = arguments["sort_by"]
            if arguments.get("sort_order"):
                params["sort_order"] = arguments["sort_order"]
            if arguments.get("supplier_id"):
                params["supplier_id"] = arguments["supplier_id"]

            result = await api_client.make_request("GET", "/invoices", params=params)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "search_documents":
            payload = {
                "query": arguments["query"],
                "type": arguments["type"]
            }
            if arguments.get("top_k"):
                payload["top_k"] = arguments["top_k"]

            result = await api_client.make_request("POST", "/search", json=payload)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def main():
    """Main server function"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, {})

if __name__ == "__main__":
    asyncio.run(main())