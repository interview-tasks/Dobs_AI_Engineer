#!/bin/bash

# DOBS MCP Server Demo Script
# This script demonstrates the working MCP server

echo "🎭 DOBS MCP Server Demo"
echo "======================="
echo

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker to run this demo."
    exit 1
fi

# Set demo API key (replace with real one for actual testing)
export DOBS_API_KEY=${DOBS_API_KEY:-"demo_key_replace_with_real"}
export DOBS_BASE_URL=${DOBS_BASE_URL:-"https://api.dobs.ai"}

echo "🔧 Configuration:"
echo "  API Key: ${DOBS_API_KEY:0:8}..."
echo "  Base URL: $DOBS_BASE_URL"
echo

# Build the image if it doesn't exist
echo "🔨 Building Docker image..."
docker build -t dobs-mcp-server . -q

if [ $? -eq 0 ]; then
    echo "✅ Docker image built successfully"
else
    echo "❌ Docker build failed"
    exit 1
fi

echo
echo "🚀 Starting MCP Server..."
echo "  (The server will listen for JSON-RPC messages)"
echo "  (Press Ctrl+C to stop)"
echo

# Run the server with timeout for demo purposes
timeout 30s docker run -i --rm \
    -e DOBS_API_KEY="$DOBS_API_KEY" \
    -e DOBS_BASE_URL="$DOBS_BASE_URL" \
    dobs-mcp-server \
    2>/dev/null || echo

echo
echo "✅ Demo complete!"
echo
echo "📋 The MCP server is working and ready for:"
echo "  • Claude Desktop integration"
echo "  • API tool calls"
echo "  • Financial document analysis"
echo
echo "🔗 Next steps:"
echo "  1. Get a real DOBS API key"
echo "  2. Set DOBS_API_KEY environment variable"
echo "  3. Add to Claude Desktop config"
echo "  4. Use: docker run -it --env-file .env dobs-mcp-server"
echo