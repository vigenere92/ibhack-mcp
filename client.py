#!/usr/bin/env python3
"""
Barebones MCP Client for IBHack MCP Server
"""

import json
import asyncio
from typing import Dict, Any, List, Optional
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


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
        
        print(f"Result: {json.dumps(result, indent=2)}")
        return result


async def main():
    """Example usage of the MCP client."""
    # Create client interface
    client_interface = MCPClientInterface()
    
    try:
        # Connect to server
        if not await client_interface.connect():
            print("Failed to connect to server")
            return
        
        # List available tools
        tools = await client_interface.list_available_tools()
        
        if tools:
            # Example: Execute the recommend_tools tool
            result = await client_interface.execute_tool(
                "recommend_tools",
                query_description="I need to process some data",
                top_k=3
            )
        
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await client_interface.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
