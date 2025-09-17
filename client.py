#!/usr/bin/env python3
"""
Barebones MCP Client for IBHack MCP Server with HTTP API
"""

import json
import asyncio
from typing import Dict, Any, List
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from aiohttp import web
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MCPClient:
    """Simple MCP client to interact with the IBHack MCP Server."""
    
    def __init__(self, server_url: str = "http://127.0.0.1:8000/mcp"):
        """
        Initialize the MCP client.
        
        Args:
            server_url: HTTP URL of the MCP server
        """
        self.server_url = server_url
        self.client = None
    
    async def connect(self) -> bool:
        """
        Connect to the MCP server.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            transport = StreamableHttpTransport(self.server_url)
            self.client = Client(transport)
            print(f"Connected to MCP server at {self.server_url}")
            return True
        except Exception as e:
            print(f"Failed to connect to MCP server: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self.client:
            await self.client.close()
            print("Disconnected from MCP server")
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all available tools from the server.
        
        Returns:
            List of available tools with their metadata
        """
        try:
            if not self.client:
                raise ConnectionError("Not connected to server")
            
            async with self.client:
                tools = await self.client.list_tools()
                return tools
        except Exception as e:
            print(f"Error listing tools: {e}")
            return []
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a tool with the given parameters.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Parameters to pass to the tool
            
        Returns:
            Result of the tool execution
        """
        try:
            if not self.client:
                raise ConnectionError("Not connected to server")
            
            async with self.client:
                result = await self.client.call_tool(tool_name, arguments or {})
                return result
        except Exception as e:
            print(f"Error executing tool {tool_name}: {e}")
            return {"error": str(e)}


class MCPClientInterface:
    """Simple interface for interacting with the MCP client."""
    
    def __init__(self, server_url: str = "http://127.0.0.1:8000/mcp"):
        self.client = MCPClient(server_url)
        self.connected = False
    
    async def connect(self) -> bool:
        """Connect to the MCP server."""
        self.connected = await self.client.connect()
        return self.connected
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self.connected:
            await self.client.disconnect()
            self.connected = False
    
    async def list_available_tools(self) -> List[Dict[str, Any]]:
        """
        List all available tools.
        
        Returns:
            List of available tools
        """
        if not self.connected:
            print("Not connected to server. Please connect first.")
            return []
        
        tools = await self.client.list_tools()
        print(f"\nFound {len(tools)} available tools:")
        for i, tool in enumerate(tools, 1):
            print(f"{i}. {tool.name}")
            print(f"   Description: {tool.description}")
            print(f"   Input Schema: {tool.inputSchema}")
        
        return tools
    
    async def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a tool with parameters.
        
        Args:
            tool_name: Name of the tool to execute
            **kwargs: Parameters to pass to the tool
            
        Returns:
            Result of the tool execution
        """
        if not self.connected:
            print("Not connected to server. Please connect first.")
            return {"error": "Not connected"}

        print(f"Executing tool: {tool_name}")
        print(f"Parameters: {kwargs}")
        
        result = await self.client.execute_tool(tool_name, kwargs)
        
        return result.content[0].text


class MCPHTTPServer:
    """HTTP server that exposes MCP tools as REST endpoints."""
    
    def __init__(self, server_url: str = "http://127.0.0.1:8000/mcp", host: str = "0.0.0.0", port: int = 8080):
        """
        Initialize the HTTP server.
        
        Args:
            server_url: URL of the MCP server
            host: Host to bind the HTTP server to
            port: Port to bind the HTTP server to
        """
        self.server_url = server_url
        self.host = host
        self.port = port
        self.client_interface = MCPClientInterface(server_url)
        self.app = web.Application()
        self.setup_routes()
    
    def setup_routes(self):
        """Set up HTTP routes."""
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/tools', self.list_tools)
        self.app.router.add_post('/execute', self.execute_tool)
        self.app.router.add_get('/', self.root_handler)
    
    async def health_check(self, request):
        """Health check endpoint."""
        return web.json_response({
            "status": "healthy",
            "mcp_connected": self.client_interface.connected
        })
    
    async def root_handler(self, request):
        """Root endpoint with API documentation."""
        return web.json_response({
            "message": "MCP HTTP API Server",
            "endpoints": {
                "GET /health": "Health check",
                "GET /tools": "List available tools",
                "POST /execute": "Execute a tool"
            },
            "execute_tool_format": {
                "tool_name": "string",
                "params": "object"
            }
        })
    
    async def list_tools(self, request):
        """List all available tools."""
        try:
            if not self.client_interface.connected:
                await self.client_interface.connect()
            
            tools = await self.client_interface.list_available_tools()
            
            # Convert tools to a more API-friendly format
            tools_data = []
            for tool in tools:
                tools_data.append({
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                })
            
            return web.json_response({
                "tools": tools_data,
                "count": len(tools_data)
            })
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            return web.json_response(
                {"error": f"Failed to list tools: {str(e)}"},
                status=500
            )
    
    async def execute_tool(self, request):
        """Execute a tool with given parameters."""
        try:
            # Parse request body
            try:
                data = await request.json()
            except json.JSONDecodeError:
                return web.json_response(
                    {"error": "Invalid JSON in request body"},
                    status=400
                )
            
            # Validate required fields
            if 'tool_name' not in data:
                return web.json_response(
                    {"error": "Missing required field: tool_name"},
                    status=400
                )
            
            tool_name = data['tool_name']
            params = data.get('params', {})
            
            # Ensure we're connected
            if not self.client_interface.connected:
                await self.client_interface.connect()
            
            # Execute the tool
            result = await self.client_interface.execute_tool(tool_name, **params)

            return web.json_response({
                "tool_name": tool_name,
                "params": params,
                "result": result
            })
            
        except Exception as e:
            logger.error(f"Error executing tool: {e}")
            return web.json_response(
                {"error": f"Failed to execute tool: {str(e)}"},
                status=500
            )
    
    async def start_server(self):
        """Start the HTTP server."""
        try:
            # Connect to MCP server first
            logger.info(f"Connecting to MCP server at {self.server_url}")
            if not await self.client_interface.connect():
                logger.error("Failed to connect to MCP server")
                return False
            
            # Start HTTP server
            logger.info(f"Starting HTTP server on {self.host}:{self.port}")
            runner = web.AppRunner(self.app)
            await runner.setup()
            site = web.TCPSite(runner, self.host, self.port)
            await site.start()
            
            logger.info("HTTP server started successfully!")
            logger.info("Available endpoints:")
            logger.info(f"  GET  http://{self.host}:{self.port}/health")
            logger.info(f"  GET  http://{self.host}:{self.port}/tools")
            logger.info(f"  POST http://{self.host}:{self.port}/execute")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            return False
    
    async def stop_server(self):
        """Stop the HTTP server and disconnect from MCP."""
        try:
            await self.client_interface.disconnect()
            logger.info("Server stopped")
        except Exception as e:
            logger.error(f"Error stopping server: {e}")


async def main():
    """Start the MCP HTTP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description='MCP HTTP API Server')
    parser.add_argument('--mcp-server', default='http://127.0.0.1:8000/mcp',
                       help='URL of the MCP server (default: http://127.0.0.1:8000/mcp)')
    parser.add_argument('--host', default='0.0.0.0',
                       help='Host to bind the HTTP server to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8181,
                       help='Port to bind the HTTP server to (default: 8080)')
    
    args = parser.parse_args()
    
    # Create and start HTTP server
    server = MCPHTTPServer(
        server_url=args.mcp_server,
        host=args.host,
        port=8181
    )
    
    try:
        if await server.start_server():
            logger.info("Server is running. Press Ctrl+C to stop.")
            # Keep the server running
            while True:
                await asyncio.sleep(1)
        else:
            logger.error("Failed to start server")
            return
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
    finally:
        await server.stop_server()


if __name__ == "__main__":
    asyncio.run(main())
