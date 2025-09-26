# DOBS MCP Server

A Model Context Protocol (MCP) server that wraps the **DOBS Financial Document Analyzer API** to provide AI clients with access to financial document analysis capabilities.

## Features

The server provides 4 MCP tools:

### GET Endpoints (3 tools)
- **`get_analytics`** - Get combined analytics data across suppliers, contracts, and invoices
- **`get_contracts`** - Get all contracts with pagination, sorting, and filtering
- **`get_invoices`** - Get all invoices with pagination, sorting, and filtering

### POST Endpoints (1 tool)
- **`search_documents`** - Search documents using vector embeddings

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone or download the project
cd Dobs_AI_Engineer

# Set up environment variables
cp .env.example .env
# Edit .env file with your DOBS API key

# Build and run with Docker
docker build -t dobs-mcp-server .
docker run -it --env-file .env dobs-mcp-server
```

Or use docker-compose:

```bash
# Set environment variables
export DOBS_API_KEY=your_api_key_here
export DOBS_BASE_URL=https://api.dobs.ai

# Run with docker-compose
docker-compose up --build
```

### Option 2: Local Python Installation

```bash
# Clone or download the project
cd Dobs_AI_Engineer

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env file with your DOBS API key

# Run the server
python -m dobs_mcp_server.main
```

## Claude Desktop Configuration

Add this to your Claude Desktop config file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%/Claude/claude_desktop_config.json`

### Option 1: Docker Configuration (Recommended)

```json
{
  "mcpServers": {
    "dobs-financial": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "--env-file", "/path/to/your/Dobs_AI_Engineer/.env", "dobs-mcp-server"],
      "cwd": "/path/to/your/Dobs_AI_Engineer"
    }
  }
}
```

### Option 2: Local Python Configuration

```json
{
  "mcpServers": {
    "dobs-financial": {
      "command": "python",
      "args": ["-m", "dobs_mcp_server.main"],
      "cwd": "/path/to/your/Dobs_AI_Engineer",
      "env": {
        "DOBS_API_KEY": "your_api_key_here",
        "DOBS_BASE_URL": "https://api.dobs.ai"
      }
    }
  }
}
```

## Tool Usage Examples

### 1. Get Analytics
```
Use the get_analytics tool to see combined analytics across all suppliers, contracts, and invoices.
```

### 2. Get Contracts
```
Use get_contracts with parameters:
- page: 1 (default)
- per_page: 20 (default)
- sort_by: "created_at" (default)
- sort_order: "desc" (default)
- supplier_id: optional UUID filter
```

### 3. Get Invoices
```
Use get_invoices with the same parameters as contracts.
```

### 4. Search Documents
```
Use search_documents with:
- query: "search terms" (required)
- type: "contract" | "invoice" | "pricing" | "transaction" (required)
- top_k: 5 (default, number of results)
```

## Authentication

The server uses Bearer token authentication with the DOBS API. Make sure your `DOBS_API_KEY` is valid and has the necessary permissions.

## Error Handling

The server provides detailed error messages for:
- Missing API key
- Invalid API responses
- Network errors
- Invalid parameters

## Testing

### Automated Testing
```bash
# Run complete test suite
python test.py
```

Tests include:
- ✅ File structure validation
- ✅ Import and dependency checks
- ✅ API client functionality
- ✅ Environment validation
- ✅ Docker build and run
- ✅ MCP protocol communication

### Manual Testing with Real API
```bash
# 1. Set your real API key
echo "DOBS_API_KEY=your_real_key" > .env

# 2. Test with Docker
docker run -it --env-file .env dobs-mcp-server

# 3. Test individual tools via JSON-RPC
echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | \
  docker run -i --env-file .env dobs-mcp-server
```

### Claude Desktop Testing
1. Add server to Claude Desktop config
2. Ask: *"What tools do you have available?"*
3. Try: *"Get analytics data"* or *"Search contracts for payment terms"*

## Requirements

- Python 3.8+
- MCP package >= 1.0.0
- httpx >= 0.25.0
- python-dotenv >= 1.0.0

## API Reference

This server wraps the [DOBS Financial Document Analyzer API](https://api.dobs.ai/swagger). Refer to the API documentation for detailed information about available endpoints and data schemas.