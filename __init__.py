"""
gjalla CLI

A CLI tool that organizes, aggregates, and standardizes requirements and architecture information from markdowns written by agentic coding tools.
"""

__version__ = "0.1.0"
__author__ = "Ellie"

from .config import ConfigurationManager

__all__ = [
    "ConfigurationManager", 
]