#!/usr/bin/env python3
"""
Main entry point for the gjalla CLI.
"""

def main():
    """Entry point for the CLI application"""
    import sys
    try:
        from .cli_tools.main_cli import main as cli_main
    except ImportError:
        from cli_tools.main_cli import main as cli_main
    
    sys.exit(cli_main())

if __name__ == "__main__":
    main()