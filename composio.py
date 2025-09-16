"""
Composio module for MCP server integration.

This module provides integration with Composio for various automation tasks.
"""

import logging
from composio_client import Composio
import os

logger = logging.getLogger(__name__)


class ComposioModule:
    """
    Main class for Composio integration functionality.
    """
    
    def __init__(self):
        """Initialize the Composio module."""
        self.api_key = os.getenv('COMPOSIO_API_KEY')
        if not self.api_key:
            raise ValueError("COMPOSIO_API_KEY environment variable must be set")
        
        self.client = Composio(api_key=self.api_key)
        self.toolkits = {}
        self.tools = {}
        self.populate_available_tools()
        
    
    def get_available_toolkits(self):
        toolkits = self.client.toolkits.list(limit=1000)
        self.toolkits = {}
        
        for item in toolkits.items:
            self.toolkits[item.slug] = {
                'name': item.name,
                'auth_schemes': item.auth_schemes,
            }
            
            
    def get_available_tools(self):
        tools = self.client.tools.list(limit=15000)
        self.tools = {}
        
        for item in tools.items:
            self.tools[item.slug] = {
                'description': item.description,
                'input_parameters': item.input_parameters,
                'output_parameters': item.output_parameters,
                'toolkit': item.toolkit.slug,
            }
    
    def populate_available_tools(self):
        """Populate the available tools."""
        self.get_available_toolkits()
        self.get_available_tools()
        
COMPOSIO_MODULE = ComposioModule()
        
        
