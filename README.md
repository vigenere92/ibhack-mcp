# IBHack MCP Server

A Model Context Protocol (MCP) server that provides intelligent tool discovery and recommendation capabilities using Google Gemini AI. The server can scan Python directories for tool classes and recommend the most relevant tools based on user queries.

## Features

- **Tool Discovery**: Automatically scans Python directories to discover tool classes
- **AI-Powered Recommendations**: Uses Google Gemini to recommend the most relevant tools based on user queries
- **HTTP Transport**: Runs as an HTTP server for easy integration
- **Complete Code Generation**: Returns full Python code for recommended tools

## Environment Variables

The following environment variables need to be set to run the MCP server:

### Required

- **`GEMINI_API_KEY`**: Your Google AI API key for Gemini integration
  - Example: `export GEMINI_API_KEY="your-api-key-here"`

### Optional

- **`SCAN_DIRECTORY`**: Directory path to scan for tools during startup
  - Example: `export SCAN_DIRECTORY="/path/to/your/tools"`

## Installation

1. **Install Poetry** (if not already installed):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. **Install dependencies**:
   ```bash
   poetry install
   ```

3. **Set environment variables**:
   ```bash
   export GEMINI_API_KEY="your-api-key-here"
   export SCAN_DIRECTORY="/path/to/your/tools"  # Optional
   ```

## Running the Server

### Method 1: Direct Python execution
```bash
python server.py
```

### Method 2: Using Poetry
```bash
poetry run python server.py
```

### Method 3: Using the Poetry script
```bash
poetry run mcp-server
```

The server will start on `http://127.0.0.1:8000/mcp` by default.

## Configuration

### Server Configuration
The server runs with the following default settings:
- **Host**: `127.0.0.1`
- **Port**: `8000`
- **Path**: `/mcp`
- **Transport**: HTTP

To modify these settings, edit the `mcp.run()` call in `server.py`:
```python
mcp.run(transport="http", host="127.0.0.1", port=8000, path="/mcp")
```

### Tool Discovery
The server looks for Python classes that:
- Have methods: `get_name()`, `get_description()`, and `execute()`
- Are located in `.py` files within the specified directory
- Can optionally have `get_input_schema()` and `get_output_schema()` methods

## Available Tools

### `recommend_tools`
Finds the most relevant tools for a given description using Gemini AI.

**Parameters:**
- `query_description` (string): Description of what the user wants to do
- `top_k` (integer, optional): Number of top tools to return (default: 2)

**Returns:**
- Dictionary containing recommended tools with complete Python code
- Success status and error information
- Tool metadata (name, description, file path, class name)

## Example Usage

### Using the Client
```python
import asyncio
from client import MCPClientInterface

async def main():
    client = MCPClientInterface("http://127.0.0.1:8000/mcp")
    
    # Connect to server
    await client.connect()
    
    # Get tool recommendations
    result = await client.execute_tool(
        "recommend_tools",
        query_description="I need to process CSV data",
        top_k=3
    )
    
    print(result)
    
    await client.disconnect()

asyncio.run(main())
```

### Direct HTTP Request
```bash
curl -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "recommend_tools",
      "arguments": {
        "query_description": "I need to analyze data",
        "top_k": 2
      }
    }
  }'
```