"""
KiCad Schematic LLM Checker Plugin

This plugin provides AI-powered schematic analysis and verification capabilities
for KiCad using Large Language Models.
"""

from .plugin import SchematicLLMCheckerPlugin

__version__ = "0.1.0"
__author__ = "KiCad LLM Plugin Team"
__email__ = ""
__description__ = "AI-powered schematic analysis and verification for KiCad"

# Plugin registration
def register():
    """Register the plugin with KiCad"""
    return SchematicLLMCheckerPlugin()