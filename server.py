#!/usr/bin/env python3
"""
Tool Discovery MCP Server using FastMCP
"""

import ast
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass

from fastmcp import FastMCP
from llm_service import LLMService
from composio import COMPOSIO_MODULE


@dataclass
class ToolInfo:
    """Information about a discovered tool."""
    name: str
    description: str
    file_path: str
    class_name: str
    python_code: str  # Complete Python code for the tool
    input_schema: Optional[str] = None
    output_schema: Optional[str] = None


class ToolDiscovery:
    """Discovers tools by scanning Python files in a directory."""
    
    def __init__(self):
        self.tools: Dict[str, ToolInfo] = {}
    
    def scan_directory(self, directory_path: str) -> Dict[str, ToolInfo]:
        """
        Scan a directory for Python files containing tool classes.
        
        Args:
            directory_path: Path to the directory to scan
            
        Returns:
            Dictionary mapping tool names to ToolInfo objects
        """
        self.tools = {}
        directory = Path(directory_path)
        
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        
        if not directory.is_dir():
            raise ValueError(f"Path is not a directory: {directory_path}")
        
        # Find all Python files in the directory and subdirectories recursively
        python_files = list(directory.glob("**/*.py"))
        
        for file_path in python_files:
            try:
                self._scan_file(file_path)
            except Exception as e:
                print(f"Error scanning file {file_path}: {e}", file=sys.stderr)
                continue
        
        return self.tools
    
    def _scan_file(self, file_path: Path) -> None:
        """Scan a single Python file for tool classes."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content, filename=str(file_path))
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    tool_info = self._extract_tool_info(node, file_path)
                    if tool_info:
                        self.tools[tool_info.name] = tool_info
        
        except Exception as e:
            print(f"Error parsing file {file_path}: {e}", file=sys.stderr)
    
    def _extract_tool_info(self, class_node: ast.ClassDef, file_path: Path) -> Optional[ToolInfo]:
        """Extract tool information from a class definition."""
        # Check if this class inherits from BaseTool or has tool-like methods
        if not self._is_tool_class(class_node):
            return None
        
        tool_name = None
        description = ""
        input_schema = None
        output_schema = None
        
        # Look for class methods that define tool metadata
        for method in class_node.body:
            if isinstance(method, ast.FunctionDef) and method.name == "get_name":
                tool_name = self._extract_string_return(method)
            elif isinstance(method, ast.FunctionDef) and method.name == "get_description":
                description = self._extract_string_return(method) or ""
            elif isinstance(method, ast.FunctionDef) and method.name == "get_input_schema":
                input_schema = self._extract_class_reference(method)
            elif isinstance(method, ast.FunctionDef) and method.name == "get_output_schema":
                output_schema = self._extract_class_reference(method)
        
        if not tool_name:
            return None
        
        # Extract complete Python code for the tool
        python_code = self._extract_complete_code(file_path, class_node)
        
        return ToolInfo(
            name=tool_name,
            description=description,
            file_path=str(file_path),
            class_name=class_node.name,
            python_code=python_code,
            input_schema=input_schema,
            output_schema=output_schema
        )
    
    def _is_tool_class(self, class_node: ast.ClassDef) -> bool:
        """Check if a class is likely a tool class."""
        # Check if it has the required methods
        method_names = {method.name for method in class_node.body 
                       if isinstance(method, ast.FunctionDef)}
        
        required_methods = {"get_name", "get_description", "execute"}
        return required_methods.issubset(method_names)
    
    def _extract_string_return(self, method: ast.FunctionDef) -> Optional[str]:
        """Extract string literal from a method that returns a string."""
        for node in ast.walk(method):
            if isinstance(node, ast.Return) and node.value:
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    return node.value.value
                elif isinstance(node.value, ast.Str):  # Python < 3.8 compatibility
                    return node.value.s
        return None
    
    def _extract_class_reference(self, method: ast.FunctionDef) -> Optional[str]:
        """Extract class reference from a method that returns a class."""
        for node in ast.walk(method):
            if isinstance(node, ast.Return) and node.value:
                if isinstance(node.value, ast.Name):
                    return node.value.id
                elif isinstance(node.value, ast.Attribute):
                    return f"{node.value.attr}"
        return None
    
    def _extract_complete_code(self, file_path: Path, tool_class: ast.ClassDef) -> str:
        """Extract complete Python code including all relevant classes, functions, and imports."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content, filename=str(file_path))
            
            # Find all relevant nodes to include
            relevant_nodes = []
            referenced_names = set()
            
            # Start with the tool class and find all references
            self._find_referenced_names(tool_class, referenced_names)
            
            # Walk through all nodes in the file
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    # Include all imports
                    relevant_nodes.append(node)
                elif isinstance(node, ast.ImportFrom):
                    # Include all from imports
                    relevant_nodes.append(node)
                elif isinstance(node, ast.ClassDef):
                    # Include the tool class and any referenced classes
                    if (node.name == tool_class.name or 
                        node.name in referenced_names or
                        self._is_referenced_class(node, tool_class)):
                        relevant_nodes.append(node)
                elif isinstance(node, ast.FunctionDef):
                    # Include functions that are referenced
                    if (node.name in referenced_names or
                        self._is_referenced_function(node, tool_class)):
                        relevant_nodes.append(node)
                elif isinstance(node, ast.Assign):
                    # Include variable assignments that might be referenced
                    if self._is_referenced_assignment(node, tool_class):
                        relevant_nodes.append(node)
            
            # Sort nodes by line number to maintain order
            relevant_nodes.sort(key=lambda n: getattr(n, 'lineno', 0))
            
            # Extract source code for each relevant node
            lines = content.split('\n')
            code_parts = []
            
            for node in relevant_nodes:
                start_line = getattr(node, 'lineno', 1) - 1
                end_line = getattr(node, 'end_lineno', start_line + 1)
                
                # Extract the node's source code
                node_lines = lines[start_line:end_line]
                code_parts.append('\n'.join(node_lines))
            
            return '\n\n'.join(code_parts)
            
        except Exception as e:
            print(f"Error extracting code from {file_path}: {e}", file=sys.stderr)
            return ""
    
    def _find_referenced_names(self, node: ast.AST, referenced_names: set) -> None:
        """Recursively find all referenced names in an AST node."""
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                referenced_names.add(child.id)
            elif isinstance(child, ast.Attribute):
                referenced_names.add(child.attr)
    
    def _is_referenced_class(self, class_node: ast.ClassDef, tool_class: ast.ClassDef) -> bool:
        """Check if a class is referenced by the tool class."""
        referenced_names = set()
        self._find_referenced_names(tool_class, referenced_names)
        return class_node.name in referenced_names
    
    def _is_referenced_function(self, func_node: ast.FunctionDef, tool_class: ast.ClassDef) -> bool:
        """Check if a function is referenced by the tool class."""
        referenced_names = set()
        self._find_referenced_names(tool_class, referenced_names)
        return func_node.name in referenced_names
    
    def _is_referenced_assignment(self, assign_node: ast.Assign, tool_class: ast.ClassDef) -> bool:
        """Check if an assignment is referenced by the tool class."""
        referenced_names = set()
        self._find_referenced_names(tool_class, referenced_names)
        
        # Check if any of the assigned variables are referenced
        for target in assign_node.targets:
            if isinstance(target, ast.Name) and target.id in referenced_names:
                return True
        return False


# Create the MCP server instance
mcp = FastMCP("IBHack MCP Server")

# Initialize tool discovery
tool_discovery = ToolDiscovery()

# Initialize LLM service (will be created when first needed)
llm_service = None

# Perform startup scanning if environment variable is set
def perform_startup_scan():
    """Perform tool scanning during server startup."""
    scan_directory = os.getenv('SCAN_DIRECTORY')
    if scan_directory:
        print(f"Starting up: Scanning directory {scan_directory} for tools...", file=sys.stderr)
        try:
            tools = tool_discovery.scan_directory(scan_directory)
            print(f"Startup scan complete: Found {len(tools)} tools", file=sys.stderr)
            for tool_name, tool_info in tools.items():
                print(f"  - {tool_name}: {tool_info.description}", file=sys.stderr)
        except Exception as e:
            print(f"Startup scan failed: {e}", file=sys.stderr)
    else:
        print("No SCAN_DIRECTORY environment variable set. Skipping startup scan.", file=sys.stderr)

# Run startup scan
perform_startup_scan()

@mcp.tool()
def recommend_tools(query_description: str, top_k: int = 1) -> Dict[str, Any]:
    """
    Find the most relevant tools for a given description using Gemini AI.
    
    Args:
        query_description: Description of what the user wants to do
        top_k: Number of top tools to return (default: 1)
        
    Returns:
        Dictionary containing:
        - tool_from_code: The first recommended tool with complete code
        - tool_create: Boolean indicating if a new tool should be created (true) or existing tool can be updated (false)
        - composio_tool: Relevant Composio tool data
    """
    global llm_service
    
    try:
        # Initialize LLM service if not already done
        if llm_service is None:
            try:
                llm_service = LLMService()
            except ValueError as e:
                return {
                    "success": False,
                    "error": f"LLM service initialization failed: {str(e)}",
                    "tool_from_code": {},
                    "tool_create": False,
                    "composio_tool": {}
                }
        
        # Get available tools
        if not tool_discovery.tools:
            return {
                "success": False,
                "error": "No tools available. Please scan a directory first using scan_tools_directory.",
                "tool_from_code": {},
                "tool_create": False,
                "composio_tool": {}
            }
        
        # Get tool names from LLM
        print(f"Checking query: {query_description} against indexed code.")
        recommended_tool_names = llm_service.find_relevant_tools(
            query_description, 
            tool_discovery.tools, 
            top_k
        )
        
        # Build tool_from_code from the first recommended tool
        tool_from_code = {}
        tool_create = False
        if recommended_tool_names and recommended_tool_names[0] in tool_discovery.tools:
            first_tool_name = recommended_tool_names[0]
            tool_info = tool_discovery.tools[first_tool_name]
            tool_from_code = {
                "tool_name": first_tool_name,
                "description": tool_info.description,
                "file_path": tool_info.file_path,
                "class_name": tool_info.class_name,
                "python_code": tool_info.python_code
            }
            
            # Check if the existing tool can be updated or if a new tool should be created
            try:
                print(f"Checking if existing tool should be updated.")
                update_analysis = llm_service.check_tool_update_vs_new(
                    query_description,
                    tool_info.python_code,
                    first_tool_name
                )
                tool_create = not update_analysis.get('can_update', False)
            except Exception as e:
                print(f"Error checking tool update vs new: {e}", file=sys.stderr)
                tool_create = True  # Default to creating new tool on error
        
        # Check for relevant Composio tools
        composio_tool = {}
        try:
            # Get Composio tools
            composio_tools = COMPOSIO_MODULE.tools
            if composio_tools:
                # Find relevant Composio tool
                print(f"Checking for more context in available registry.")
                relevant_composio_tool_name = llm_service.find_relevant_composio_tool(
                    query_description, 
                    composio_tools
                )
                
                if relevant_composio_tool_name and relevant_composio_tool_name in composio_tools:
                    tool_info = composio_tools[relevant_composio_tool_name]
                    toolkit_slug = tool_info.get('toolkit', '')
                    toolkit_info = COMPOSIO_MODULE.toolkits.get(toolkit_slug, {})
                    
                    composio_tool = {
                        "tool_name": relevant_composio_tool_name,
                        "description": tool_info.get('description', ''),
                        "toolkit_name": toolkit_info.get('name', ''),
                        "auth_schemes": toolkit_info.get('auth_schemes', []),
                        "input_parameters": tool_info.get('input_parameters', {}),
                        "output_parameters": tool_info.get('output_parameters', {})
                    }
        except Exception as e:
            print(f"Error checking Composio tools: {e}", file=sys.stderr)
            composio_tool = {}
        
        return {
            "success": True,
            "query": query_description,
            "total_available_tools": len(tool_discovery.tools),
            "recommendations_requested": top_k,
            "tool_from_code": tool_from_code,
            "tool_create": tool_create,
            "composio_tool": composio_tool
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "tool_from_code": {},
            "tool_create": False,
            "composio_tool": {}
        }


if __name__ == "__main__":
    # Run the server
    mcp.run(transport="http", host="127.0.0.1", port=8000, path="/mcp")
