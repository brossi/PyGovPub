"""
Output formatting utilities for the CLI.

This module provides functions for formatting data in different formats (JSON, XML, text)
and writing output to files.
"""

import json
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, Optional, Union

import dicttoxml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

# Create console for output
console = Console()


class OutputFormat(Enum):
    """Output format options."""
    JSON = auto()
    XML = auto()
    TEXT = auto()


def output_json(data: Dict[str, Any]) -> None:
    """Output data as formatted JSON."""
    json_str = json.dumps(data, indent=2, sort_keys=True)
    console.print_json(json_str)


def output_xml(data: Dict[str, Any]) -> None:
    """Output data as formatted XML."""
    xml_bytes = dicttoxml.dicttoxml(data, custom_root="root", attr_type=False)
    xml_str = xml_bytes.decode("utf-8")
    # Format with indentation for better readability
    try:
        from lxml import etree
        # Parse as bytes to avoid encoding declaration issues
        root = etree.fromstring(xml_bytes)
        formatted_xml = etree.tostring(root, pretty_print=True).decode("utf-8")
        console.print(formatted_xml)
    except ImportError:
        # If lxml not available, print the unformatted XML
        console.print(xml_str)


def output_text(data: Dict[str, Any]) -> None:
    """Output data as readable text."""
    # For simple dictionaries, print key: value pairs
    if isinstance(data, dict) and all(not isinstance(v, dict) for v in data.values()):
        table = Table(show_header=False, box=None)
        table.add_column("Key", style="bold cyan")
        table.add_column("Value")
        
        for key, value in sorted(data.items()):
            table.add_row(str(key), str(value))
        
        console.print(table)
        return
    
    # For more complex nested dictionaries, use a tree view
    root = Tree("Results")
    
    def add_to_tree(tree: Tree, data: Any, name: str = ""):
        """Recursively add data to tree."""
        if isinstance(data, dict):
            branch = tree.add(name) if name else tree
            for key, value in sorted(data.items()):
                add_to_tree(branch, value, key)
        elif isinstance(data, list):
            branch = tree.add(name) if name else tree
            for i, item in enumerate(data):
                add_to_tree(branch, item, f"[{i}]")
        else:
            tree.add(f"{name}: {data}" if name else str(data))
    
    add_to_tree(root, data)
    console.print(root)


def output_to_file(data: Dict[str, Any], file_path: str, format: OutputFormat) -> None:
    """Write output to a file in the specified format."""
    with open(file_path, "w", encoding="utf-8") as f:
        if format == OutputFormat.JSON:
            json.dump(data, f, indent=2, sort_keys=True)
        elif format == OutputFormat.XML:
            xml_bytes = dicttoxml.dicttoxml(data, custom_root="root", attr_type=False)
            xml_str = xml_bytes.decode("utf-8")
            # Format XML if lxml is available
            try:
                from lxml import etree
                root = etree.fromstring(xml_str)
                formatted_xml = etree.tostring(root, pretty_print=True).decode("utf-8")
                f.write(formatted_xml)
            except ImportError:
                f.write(xml_str)
        else:  # TEXT format
            # Simple text representation without rich formatting
            def write_dict(d, indent=0):
                for key, value in sorted(d.items()):
                    prefix = " " * indent
                    if isinstance(value, dict):
                        f.write(f"{prefix}{key}:\n")
                        write_dict(value, indent + 2)
                    elif isinstance(value, list):
                        f.write(f"{prefix}{key}:\n")
                        for i, item in enumerate(value):
                            if isinstance(item, dict):
                                f.write(f"{prefix}  [{i}]:\n")
                                write_dict(item, indent + 4)
                            else:
                                f.write(f"{prefix}  [{i}]: {item}\n")
                    else:
                        f.write(f"{prefix}{key}: {value}\n")
            
            write_dict(data)
    
    console.print(f"Output written to [cyan]{file_path}[/cyan]")


def get_output_format(format_str: Optional[str], output_file: Optional[str] = None) -> OutputFormat:
    """Determine output format from string or file extension."""
    # If format explicitly specified, use it
    if format_str:
        format_map = {
            "json": OutputFormat.JSON,
            "xml": OutputFormat.XML, 
            "text": OutputFormat.TEXT
        }
        if format_str.lower() not in format_map:
            raise ValueError(f"Invalid output format: {format_str}. Valid formats: json, xml, text")
        return format_map[format_str.lower()]
    
    # If output file specified, infer format from extension
    if output_file:
        extension = Path(output_file).suffix.lower()
        if extension == ".json":
            return OutputFormat.JSON
        elif extension == ".xml":
            return OutputFormat.XML
    
    # Default to text if nothing specified
    return OutputFormat.TEXT