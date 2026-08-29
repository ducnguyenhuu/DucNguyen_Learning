#!/bin/bash

# MCP Server Startup Script
# Purpose: Easily launch the FastAPI MCP server for the loan underwriting system
# Usage: ./src/mcp/run_server.sh

echo "=================================================="
echo "Starting MCP (Model Context Protocol) Server"
echo "=================================================="
echo ""
echo "Server endpoints:"
echo "  - GET  /files/{filename}         - Read PDF files"
echo "  - GET  /credit/{ssn}             - Query credit reports"
echo "  - GET  /application/{app_id}     - Get application data"
echo "  - POST /admin/seed_credit_db     - Seed mock credit database"
echo "  - GET  /health                   - Health check"
echo ""
echo "Server will be available at: http://localhost:8000"
echo "API documentation at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=================================================="
echo ""

# Launch uvicorn with auto-reload for development
uvicorn src.mcp.server:app --reload --host 0.0.0.0 --port 8000
