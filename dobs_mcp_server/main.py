#!/usr/bin/env python3  # Shebang line to specify Python 3 interpreter
"""
MCP Server for DOBS Financial Document Analyzer API
"""

import os  # Import os module for environment variable access
import json  # Import json module for JSON serialization
import asyncio  # Import asyncio for asynchronous programming support
from typing import Any, Dict, List, Optional  # Import type hints for better code documentation
from dotenv import load_dotenv  # Import load_dotenv to load environment variables from .env file

import httpx  # Import httpx for making async HTTP requests
from mcp.server import Server  # Import Server class from MCP framework
from mcp.server.stdio import stdio_server  # Import stdio_server for standard input/output communication
from mcp.types import (  # Import MCP types for tool definitions
    Tool,  # Tool type for defining available tools
    TextContent  # TextContent type for returning text responses
)

# Load environment variables
load_dotenv()  # Load environment variables from .env file into os.environ

# Configuration
DOBS_API_KEY = os.getenv("DOBS_API_KEY")  # Get DOBS API key from environment variables
DOBS_BASE_URL = os.getenv("DOBS_BASE_URL", "https://api.dobs.ai")  # Get base URL with default fallback

if not DOBS_API_KEY:  # Check if API key is missing
    raise ValueError("DOBS_API_KEY environment variable is required")  # Raise error if API key is not set

# Initialize server
server = Server("dobs-mcp-server")  # Create MCP server instance with name "dobs-mcp-server"

class DobsApiClient:  # Define API client class for DOBS interactions
    """Client for DOBS API"""

    def __init__(self, base_url: str, api_key: str):  # Constructor accepts base URL and API key
        self.base_url = base_url.rstrip("/")  # Store base URL without trailing slash
        self.api_key = api_key  # Store API key for authentication
        self.headers = {  # Set up default headers for all requests
            "Authorization": f"Bearer {api_key}",  # Add Bearer token authorization header
            "Content-Type": "application/json"  # Set content type to JSON
        }

    async def make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:  # Async method to make HTTP requests
        """Make HTTP request to DOBS API"""
        url = f"{self.base_url}/api{endpoint}"  # Construct full API URL

        async with httpx.AsyncClient() as client:  # Create async HTTP client context
            response = await client.request(  # Make async HTTP request
                method=method,  # HTTP method (GET, POST, etc.)
                url=url,  # Full URL to request
                headers=self.headers,  # Include authentication headers
                **kwargs  # Pass through any additional request parameters
            )

            if response.status_code >= 400:  # Check if response indicates an error
                try:  # Attempt to parse error as JSON
                    error_data = response.json()  # Parse error response body
                    raise Exception(f"API Error {response.status_code}: {error_data}")  # Raise exception with parsed error
                except:  # If JSON parsing fails
                    raise Exception(f"API Error {response.status_code}: {response.text}")  # Raise exception with raw text

            return response.json()  # Return parsed JSON response

# Initialize API client
api_client = DobsApiClient(DOBS_BASE_URL, DOBS_API_KEY)  # Create global API client instance

@server.list_tools()  # Decorator to register function as tool list handler
async def list_tools():  # Async function to return available tools
    """List available tools"""
    return [  # Return list of Tool objects
        Tool(  # Define get_analytics tool
            name="get_analytics",  # Tool name identifier
            description="Get combined analytics data across suppliers, contracts, and invoices",  # Tool description
            inputSchema={  # JSON schema for input validation
                "type": "object",  # Schema type is object
                "properties": {},  # No input properties required
                "additionalProperties": False  # Don't allow extra properties
            }
        ),
        Tool(  # Define get_contracts tool
            name="get_contracts",  # Tool name identifier
            description="Get all contracts with pagination, sorting, and filtering",  # Tool description
            inputSchema={  # JSON schema for input validation
                "type": "object",  # Schema type is object
                "properties": {  # Define allowed properties
                    "page": {"type": "integer", "default": 1, "description": "Page number"},  # Page number parameter
                    "per_page": {"type": "integer", "default": 20, "description": "Items per page"},  # Items per page parameter
                    "sort_by": {"type": "string", "default": "created_at", "description": "Sort field"},  # Sort field parameter
                    "sort_order": {"type": "string", "enum": ["asc", "desc"], "default": "desc", "description": "Sort order"},  # Sort order parameter
                    "supplier_id": {"type": "string", "description": "Filter by supplier ID"}  # Supplier filter parameter
                },
                "additionalProperties": False  # Don't allow extra properties
            }
        ),
        Tool(  # Define get_invoices tool
            name="get_invoices",  # Tool name identifier
            description="Get all invoices with pagination, sorting, and filtering",  # Tool description
            inputSchema={  # JSON schema for input validation
                "type": "object",  # Schema type is object
                "properties": {  # Define allowed properties
                    "page": {"type": "integer", "default": 1, "description": "Page number"},  # Page number parameter
                    "per_page": {"type": "integer", "default": 20, "description": "Items per page"},  # Items per page parameter
                    "sort_by": {"type": "string", "default": "created_at", "description": "Sort field"},  # Sort field parameter
                    "sort_order": {"type": "string", "enum": ["asc", "desc"], "default": "desc", "description": "Sort order"},  # Sort order parameter
                    "supplier_id": {"type": "string", "description": "Filter by supplier ID"}  # Supplier filter parameter
                },
                "additionalProperties": False  # Don't allow extra properties
            }
        ),
        Tool(  # Define search_documents tool
            name="search_documents",  # Tool name identifier
            description="Search documents using vector embeddings",  # Tool description
            inputSchema={  # JSON schema for input validation
                "type": "object",  # Schema type is object
                "properties": {  # Define allowed properties
                    "query": {"type": "string", "description": "Search query text"},  # Search query parameter
                    "type": {"type": "string", "enum": ["contract", "invoice", "pricing", "transaction"], "description": "Document type"},  # Document type parameter
                    "top_k": {"type": "integer", "default": 5, "description": "Number of results"}  # Number of results parameter
                },
                "required": ["query", "type"],  # Mark query and type as required
                "additionalProperties": False  # Don't allow extra properties
            }
        )
    ]

@server.call_tool()  # Decorator to register function as tool call handler
async def call_tool(name: str, arguments: dict):  # Async function to handle tool invocations
    """Handle tool calls"""

    try:  # Wrap in try-except to catch errors
        if name == "get_analytics":  # Handle get_analytics tool
            result = await api_client.make_request("GET", "/analytics")  # Make GET request to analytics endpoint
            return [TextContent(type="text", text=json.dumps(result, indent=2))]  # Return formatted JSON response

        elif name == "get_contracts":  # Handle get_contracts tool
            params = {}  # Initialize empty params dictionary
            if arguments.get("page"):  # Check if page argument provided
                params["page"] = arguments["page"]  # Add page to params
            if arguments.get("per_page"):  # Check if per_page argument provided
                params["per_page"] = arguments["per_page"]  # Add per_page to params
            if arguments.get("sort_by"):  # Check if sort_by argument provided
                params["sort_by"] = arguments["sort_by"]  # Add sort_by to params
            if arguments.get("sort_order"):  # Check if sort_order argument provided
                params["sort_order"] = arguments["sort_order"]  # Add sort_order to params
            if arguments.get("supplier_id"):  # Check if supplier_id argument provided
                params["supplier_id"] = arguments["supplier_id"]  # Add supplier_id to params

            result = await api_client.make_request("GET", "/contracts", params=params)  # Make GET request with params
            return [TextContent(type="text", text=json.dumps(result, indent=2))]  # Return formatted JSON response

        elif name == "get_invoices":  # Handle get_invoices tool
            params = {}  # Initialize empty params dictionary
            if arguments.get("page"):  # Check if page argument provided
                params["page"] = arguments["page"]  # Add page to params
            if arguments.get("per_page"):  # Check if per_page argument provided
                params["per_page"] = arguments["per_page"]  # Add per_page to params
            if arguments.get("sort_by"):  # Check if sort_by argument provided
                params["sort_by"] = arguments["sort_by"]  # Add sort_by to params
            if arguments.get("sort_order"):  # Check if sort_order argument provided
                params["sort_order"] = arguments["sort_order"]  # Add sort_order to params
            if arguments.get("supplier_id"):  # Check if supplier_id argument provided
                params["supplier_id"] = arguments["supplier_id"]  # Add supplier_id to params

            result = await api_client.make_request("GET", "/invoices", params=params)  # Make GET request with params
            return [TextContent(type="text", text=json.dumps(result, indent=2))]  # Return formatted JSON response

        elif name == "search_documents":  # Handle search_documents tool
            payload = {  # Initialize payload dictionary
                "query": arguments["query"],  # Add query from arguments
                "type": arguments["type"]  # Add type from arguments
            }
            if arguments.get("top_k"):  # Check if top_k argument provided
                payload["top_k"] = arguments["top_k"]  # Add top_k to payload

            result = await api_client.make_request("POST", "/search", json=payload)  # Make POST request with payload
            return [TextContent(type="text", text=json.dumps(result, indent=2))]  # Return formatted JSON response

        else:  # Handle unknown tool names
            raise ValueError(f"Unknown tool: {name}")  # Raise error for unknown tool

    except Exception as e:  # Catch any exceptions
        return [TextContent(type="text", text=f"Error: {str(e)}")]  # Return error message

async def main():  # Define main async function
    """Main server function"""
    async with stdio_server() as (read_stream, write_stream):  # Create stdio server context with streams
        await server.run(read_stream, write_stream, {})  # Run MCP server with input/output streams

if __name__ == "__main__":  # Check if script is run directly
    asyncio.run(main())  # Run main async function