"""
Main CLI entry point for gjalla tool.

This module provides the core command-line interface and dispatches
to specific subcommand modules for actual functionality.
"""

import argparse
import sys
from pathlib import Path


def create_main_parser() -> argparse.ArgumentParser:
    """Create the main argument parser with all subcommands."""
    
    parser = argparse.ArgumentParser(
        prog='gjalla',
        description='Organize, standardize, and track documentation and requirements using regex-based analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
╭──────────────────────────────────────────────────────────────────────────────╮
│                          🚀  GJALLA TOOLKIT GUIDE                            │
╰──────────────────────────────────────────────────────────────────────────────╯

CORE COMMANDS:
─────────────

  1. Preview Markdown Organization Changes (Recommended First Step)
     gjalla organize <project_dir> --dry-run
     • Shows what would be changed without making modifications
     • Safe way to preview organization before applying changes

  2. Organize AI Markdowns
     gjalla organize <project_dir>
     • Discovers and organizes markdown files
     • Creates standardized directory structure

  3. Track Requirements
     gjalla requirements <project_dir> --kiro
     • Discovers requirements from .kiro directory
     • Creates/updates living requirements document

ADDITIONAL COMMANDS:
──────────────────

  • List Requirements
    gjalla requirements <project_dir> --list
    Shows current requirements without new scan

  • Undo Changes
    gjalla undo <project_dir>
    Restores files to their original locations - useful for undoing organization runs

EXAMPLES:
────────

  # 1. Preview organization (recommended first step)
    gjalla organize <project_dir> --dry-run

  # 2. Apply changes after reviewing
    gjalla organize <project_dir>

  # 3. Track requirements
    gjalla requirements <project_dir> --kiro

  # 4. View current requirements
    gjalla requirements <project_dir> --list

TIPS:
────

  💡 Always use --dry-run first to preview changes
  🔑 All features work without external APIs
  📂 Use --kiro for structured requirements tracking
        """
    )
    
    parser.add_argument('--version', action='version', version='%(prog)s 0.1.1')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    setup_requirements_subcommand(subparsers)
    setup_organize_subcommand(subparsers)
    setup_undo_subcommand(subparsers)

    return parser


def setup_requirements_subcommand(subparsers):
    """Set up the requirements tracking subcommand."""
    requirements_parser = subparsers.add_parser(
        'requirements',
        help='Discover and track project requirements',
        description='Analyze documentation, code, and git history to discover requirements and update the living requirements document in EARS format.'
    )
    requirements_parser.add_argument('project_dir', nargs='?', default='.', 
                           help='Project directory to scan (default: current directory)')
    requirements_parser.add_argument('--kiro', action='store_true',
                           help='Use structured .kiro directory parsing (regex-based)')
    requirements_parser.add_argument('--list', action='store_true',
                           help='List existing requirements from requirements.md without scanning')
    requirements_parser.add_argument('--quiet', '-q', action='store_true',
                           help='Suppress detailed output')
    requirements_parser.add_argument('--verbose', '-v', action='store_true',
                           help='Show detailed error information')


def setup_organize_subcommand(subparsers):
    """Set up the organize subcommand."""
    organize_parser = subparsers.add_parser(
        'organize',
        help='Organize and standardize project documentation',
        description='Discover, organize, and standardize markdown documentation files using configurable methods.'
    )
    
    organize_parser.add_argument('project_dir', 
                                 help='Path to the project directory to organize')
    organize_parser.add_argument('--method', choices=['regex'], 
                                 default='regex',
                                 help='Organization method: regex (fast filename-based classification)')
    organize_parser.add_argument('--dry-run', action='store_true',
                                 help='Show what would be done without making changes')
    organize_parser.add_argument('--format-content', action='store_true',
                                 help='Apply content formatting to markdown files')
    organize_parser.add_argument('--create-aggregates', action='store_true', default=False,
                                 help='Create aggregate requirements and architecture files')
    organize_parser.add_argument('--template-dir', type=Path,
                                 help='Custom template directory for organization structure')
    organize_parser.add_argument('--backup-dir', type=Path,
                                 help='Custom backup directory (default: project/.gjalla/backups)')
    organize_parser.add_argument('--quiet', '-q', action='store_true',
                                 help='Suppress detailed output')
    organize_parser.add_argument('--verbose', '-v', action='store_true',
                                 help='Show detailed progress and debug information')


def setup_undo_subcommand(subparsers):
    """Set up the undo subcommand."""
    undo_parser = subparsers.add_parser(
        'undo',
        help='Undo the most recent organization',
        description='Restore files to their original state before the most recent organization operation.'
    )
    
    undo_parser.add_argument('project_dir', 
                           help='Path to the project directory to restore')
    undo_parser.add_argument('--session-id', 
                           help='Specific session ID to undo (default: most recent)')
    undo_parser.add_argument('--list-sessions', action='store_true',
                           help='List available undo sessions')
    undo_parser.add_argument('--dry-run', action='store_true',
                           help='Show what would be restored without making changes')
    undo_parser.add_argument('--quiet', '-q', action='store_true',
                           help='Suppress detailed output')
    undo_parser.add_argument('--verbose', '-v', action='store_true',
                           help='Show detailed restoration information')


def handle_requirements_command(args):
    """Handle the requirements command."""
    try:
        from .requirements_cli import requirements_scan
    except ImportError:
        from requirements_cli import requirements_scan
    return requirements_scan(args)


def handle_organize_command(args):
    """Handle the organize command."""
    try:
        from .organize_cli import reorganize_project
    except ImportError:
        from organize_cli import reorganize_project
    return reorganize_project(args)


def handle_undo_command(args):
    """Handle the undo command."""
    try:
        from .organize_cli import undo_reorganization
    except ImportError:
        from organize_cli import undo_reorganization
    return undo_reorganization(args)


def main():
    """Main entry point for the CLI application."""
    parser = create_main_parser()
    
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0
    
    try:
        if args.command == 'requirements':
            return handle_requirements_command(args)
        elif args.command == 'organize':
            return handle_organize_command(args)
        elif args.command == 'undo':
            return handle_undo_command(args)
        else:
            print(f"Error: Unknown command: {args.command}")
            print("Available commands: requirements, organize, undo")
            print("(Coming soon: generate-hooks, generate-ci)")
            return 1
    
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        return 1
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        if hasattr(args, 'verbose') and args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())