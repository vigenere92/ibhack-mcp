#!/usr/bin/env python3
"""
LLM Service for tool recommendation using Google Gemini
"""

import os
import json
import sys
from typing import Dict, Optional, Any, List

import google.generativeai as genai


class LLMService:
    """Service for LLM operations using Google Gemini."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the LLM service.
        
        Args:
            api_key: Google AI API key. If not provided, will try to get from environment variable GEMINI_API_KEY
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable must be set or api_key must be provided")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
    
    def find_relevant_tools(self, query_description: str, available_tools: Dict[str, Any], top_k: int = 2) -> List[str]:
        """
        Find the most relevant tools for a given description using Gemini.
        
        Args:
            query_description: Description of what the user wants to do
            available_tools: Dictionary of available tools (ToolInfo objects or dicts)
            top_k: Number of top tools to return (default: 2)
            
        Returns:
            List of tool names that are most relevant to the query
        """
        if not available_tools:
            return []
        
        # Prepare tool descriptions for the LLM (only name and description)
        tools_description = self._format_tools_for_llm(available_tools)
        
        # Create the prompt for Gemini
        prompt = f"""
        You are a tool recommendation system. Given a user's request description and a list of available tools, 
        return the top {top_k} most relevant tools.

        User Request: "{query_description}"

        Available Tools:
        {tools_description}

        Please analyze the user's request and return the most relevant tools in the following JSON format:
        {{
            "recommendations": [
                {{
                    "tool_name": "exact_tool_name_from_list",
                    "reasoning": "Brief explanation of why this tool is relevant"
                }},
                {{
                    "tool_name": "exact_tool_name_from_list",
                    "reasoning": "Brief explanation of why this tool is relevant"
                }}
            ]
        }}

        Only return the JSON response, no additional text.
        """
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Parse the JSON response
            if response_text.startswith('```json'):
                response_text = response_text[7:-3].strip()
            elif response_text.startswith('```'):
                response_text = response_text[3:-3].strip()
            
            result = json.loads(response_text)
            
            # Extract just the tool names
            recommendations = result.get('recommendations', [])
            tool_names = []
            
            for rec in recommendations[:top_k]:
                tool_name = rec.get('tool_name')
                if tool_name in available_tools:
                    tool_names.append(tool_name)
            
            return tool_names
            
        except json.JSONDecodeError as e:
            print(f"Error parsing LLM response as JSON: {e}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Error calling Gemini API: {e}", file=sys.stderr)
            return []
    
    def _format_tools_for_llm(self, tools: Dict[str, Any]) -> str:
        """Format tools information for LLM consumption (only name and description)."""
        formatted_tools = []
        for tool_name, tool_info in tools.items():
            # Handle both ToolInfo objects and dictionaries
            if hasattr(tool_info, 'description'):
                # ToolInfo object
                description = tool_info.description
            else:
                # Dictionary
                description = tool_info.get('description', '')
            
            formatted_tools.append(f"- {tool_name}: {description}")
        
        return "\n".join(formatted_tools)
    
    def find_relevant_composio_tool(self, query_description: str, available_tools: Dict[str, Any]) -> Optional[str]:
        """
        Find the most relevant Composio tool for a given description using Gemini.
        
        Args:
            query_description: Description of what the user wants to do
            available_tools: Dictionary of available Composio tools
            
        Returns:
            Tool name if a relevant tool is found, None otherwise
        """
        if not available_tools:
            return None
        
        # Prepare tool descriptions for the LLM (only name and description)
        tools_description = self._format_composio_tools_for_llm(available_tools)
        
        # Create the prompt for Gemini
        prompt = f"""
        You are a tool recommendation system. Given a user's request description and a list of available Composio tools, 
        determine if ANY of these tools can be used to fulfill the user's request.

        User Request: "{query_description}"

        Available Composio Tools:
        {tools_description}

        IMPORTANT: Only return a tool name if you are VERY SURE that the tool can be used for the user's request.
        If you are not confident or if no tool is suitable, return "NONE".

        Return only the tool name (exact match from the list) or "NONE", no additional text.
        """
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Clean up the response
            if response_text.startswith('```'):
                response_text = response_text.split('\n')[0].replace('```', '').strip()
            
            # Check if a valid tool name was returned
            if response_text and response_text != "NONE" and response_text in available_tools:
                return response_text
            else:
                return None
            
        except Exception as e:
            print(f"Error calling Gemini API for Composio tool recommendation: {e}", file=sys.stderr)
            return None
    
    def _format_composio_tools_for_llm(self, tools: Dict[str, Any]) -> str:
        """Format Composio tools information for LLM consumption (only name and description)."""
        formatted_tools = []
        for tool_name, tool_info in tools.items():
            description = tool_info.get('description', '')
            formatted_tools.append(f"- {tool_name}: {description}")
        
        return "\n".join(formatted_tools)
    
    def check_tool_update_vs_new(self, query_description: str, tool_code: str, tool_name: str) -> Dict[str, Any]:
        """
        Check if an existing tool can be updated to support the requested functionality or if a new tool should be created.
        
        Args:
            query_description: Description of what the user wants to do
            tool_code: Complete Python code of the existing tool
            tool_name: Name of the existing tool
            
        Returns:
            Dictionary containing only the can_update boolean
        """
        # Create the prompt for Gemini
        prompt = f"""
        You are a code analysis system. Given a user's request description and an existing tool's complete code, 
        determine if the existing tool can be updated to support the requested functionality or if a new tool should be created.
        If the chosen tool is an api tool, then always create a new tool.

        User Request: "{query_description}"

        Existing Tool Name: {tool_name}

        Existing Tool Code:
        ```python
        {tool_code}
        ```

        Analyze the existing tool's code and the user's request to determine:
        1. Can the existing tool be modified/extended to support the requested functionality?
        2. Would it be better to create a new tool instead?

        Consider factors like:
        - Code complexity and maintainability
        - Whether the requested functionality fits the tool's purpose
        - Whether adding the functionality would make the tool too complex
        - Whether the functionality is significantly different from the tool's current purpose

        Return your analysis in the following JSON format:
        {{
            "can_update": true/false
        }}

        Only return the JSON response, no additional text.
        """
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Parse the JSON response
            if response_text.startswith('```json'):
                response_text = response_text[7:-3].strip()
            elif response_text.startswith('```'):
                response_text = response_text[3:-3].strip()
            
            result = json.loads(response_text)
            
            return {
                "can_update": result.get('can_update', False)
            }
            
        except json.JSONDecodeError as e:
            print(f"Error parsing LLM response as JSON: {e}", file=sys.stderr)
            return {
                "can_update": False
            }
        except Exception as e:
            print(f"Error calling Gemini API for tool update check: {e}", file=sys.stderr)
            return {
                "can_update": False
            }