"""
CLI interface for requirements tracking and management.

This module provides the command-line interface for the 'requirements' command
which scans and updates project requirements automatically.
"""

import os
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

try:
    from requirements import (
        RequirementsTracker, LivingRequirementsDocument, KiroRequirementsParser,
        RequirementRecord, RequirementsChangeSet,
    )
except ImportError:
    # Try adding parent directory to path for standalone script execution
    import sys
    from pathlib import Path as PathlibPath
    sys.path.insert(0, str(PathlibPath(__file__).parent.parent))
    from requirements import (
        RequirementsTracker, LivingRequirementsDocument, KiroRequirementsParser,
        RequirementRecord, RequirementsChangeSet,
    )

import sys
from pathlib import Path as PathlibPath
sys.path.insert(0, str(PathlibPath(__file__).parent.parent))


def check_kiro_mode(project_path: Path) -> tuple[bool, str]:
    """
    Check if project has .kiro directory with structured requirements.
    
    Returns:
        tuple: (has_kiro, status_message)
    """
    kiro_path = project_path / '.kiro'
    
    if not kiro_path.exists():
        return False, "No .kiro directory found"
    
    parser = KiroRequirementsParser()
    validation = parser.validate_kiro_structure(kiro_path)
    
    if validation["found"]:
        return True, f"Found {len(validation['found'])} structured requirements files"
    else:
        return False, "No structured requirements files found in .kiro directory"


def requirements_scan(args) -> int:
    """Main requirements scanning logic."""
    console = Console()
    project_path = Path(args.project_dir)
    
    if not project_path.exists():
        console.print(f"[red]Error: Project directory does not exist: {args.project_dir}[/red]")
        return 1
    
    if args.list:
        return requirements_list_existing(args, console, project_path)
    
    if args.kiro:
        return requirements_scan_kiro_mode(args, console, project_path)
    else:
        console.print()
        console.print(Panel(
            Text("This version only supports structured requirements analysis.", style="white") + "\n\n" +
            Text("Please use --kiro flag for structured requirements parsing:", style="white") + "\n" +
            Text("   gjalla requirements . --kiro", style="cyan"),
            border_style="yellow",
            padding=(1, 2)
        ))
        return 1


def requirements_list_existing(args, console: Console, project_path: Path) -> int:
    """List existing requirements from requirements.md file."""
    try:
        from requirements import LivingRequirementsDocument
    except ImportError:
        import sys
        from pathlib import Path as PathlibPath
        sys.path.insert(0, str(PathlibPath(__file__).parent.parent))
        from requirements import LivingRequirementsDocument
    
    requirements_file = project_path / 'aimarkdowns' / 'requirements.md'
    living_doc = LivingRequirementsDocument(requirements_file)
    
    if not living_doc.exists():
        console.print()
        console.print(Panel(
            Text("📋 No Requirements Found", style="bold yellow") + "\n\n" +
            Text(f"No requirements.md file found in {requirements_file}", style="white") + "\n\n" +
            Text("💡 Run a scan first:", style="dim") + "\n" +
            Text("   gjalla requirements . --kiro", style="cyan"),
            border_style="yellow",
            padding=(1, 2)
        ))
        return 1
    
    try:
        # Load existing requirements from the living document
        requirements = living_doc.get_all_requirements()
        
        if not requirements:
            console.print()
            console.print(Panel(
                Text("📋 Empty Requirements File", style="bold yellow") + "\n\n" +
                Text("Requirements file exists but contains no requirements", style="white") + "\n\n" +
                Text("💡 Run a scan to populate it:", style="dim") + "\n" +
                Text("   gjalla requirements . --kiro", style="cyan"),
                border_style="yellow",
                padding=(1, 2)
            ))
            return 0
        
        # Show header panel
        console.print()
        console.print(Panel(
            Text("📋 Existing Requirements", style="bold green") + "\n" +
            Text(f"📁 {project_path.absolute()}", style="dim cyan") + "\n" +
            Text(f"📄 Found {len(requirements)} requirements in requirements.md", style="white"),
            border_style="green",
            padding=(1, 2)
        ))
        
        show_requirements_summary(console, requirements)
        console.print()
        console.print(Panel(
            Text("💡 To update requirements run:", style="dim") + "\n" +
            Text("   gjalla requirements . --kiro", style="cyan") + "\n\n" +
            Text("📊 To organize project files run:", style="dim") + "\n" +
            Text("   gjalla organize . --dry-run", style="cyan"),
            border_style="blue",
            padding=(1, 2)
        ))
        
        return 0
        
    except Exception as e:
        console.print(f"[red]Error reading requirements file: {e}[/red]")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def requirements_scan_kiro_mode(args, console: Console, project_path: Path) -> int:
    """Requirements scanning using structured .kiro directory parsing."""
    # Check if .kiro directory exists and has structured requirements
    has_kiro, kiro_status = check_kiro_mode(project_path)
    
    if not has_kiro:
        console.print()
        console.print(Panel(
            Text("📂 Kiro Mode - No Structured Requirements Found", style="bold yellow") + "\n\n" +
            Text(kiro_status, style="white") + "\n\n" +
            Text("To use --kiro mode, ensure you have:", style="white") + "\n" +
            Text("• A .kiro directory in your project", style="dim") + "\n" +
            Text("• requirements.md files with structured EARS format", style="dim") + "\n" +
            Text("• acceptance criteria sections", style="dim") + "\n\n" +
            Text("This version only supports structured requirements via --kiro flag.", style="cyan"),
            border_style="yellow",
            padding=(1, 2)
        ))
        return 1
    
    console.print()
    console.print(Panel(
        Text("📂 Kiro Mode - Structured Requirements Analysis", style="bold green") + "\n" +
        Text(f"📁 {project_path.absolute()}", style="dim cyan") + "\n" + Text("🔧 Using fast regex-based parsing", style="dim green") + "\n" +
        Text(kiro_status, style="white") + "\n\n" +
        Text("Parsing structured requirements...", style="white"),
        border_style="green",
        padding=(1, 2)
    ))
    
    try:
        # Initialize components
        tracker = RequirementsTracker(project_path)
        living_doc = LivingRequirementsDocument(tracker.requirements_file)
        parser = KiroRequirementsParser()
        
        # Determine if this is first run or incremental update
        # If requirements.md doesn't exist, always treat as first run (clean slate)
        if not living_doc.exists():
            is_first_run = True
            # Clean up any orphaned metadata from previous runs
            if tracker.metadata_file.exists():
                tracker.metadata_file.unlink()
                console.print("[dim]Cleaned up orphaned metadata from previous runs[/dim]")
        else:
            # requirements.md exists, check if we should do full vs incremental
            if not tracker.metadata_file.exists():
                is_first_run = True
            else:
                # Check if any .kiro files are newer than last scan
                kiro_path = project_path / '.kiro'
                last_scan_time = tracker.metadata.last_scan_date
                
                # Check modification times of .kiro files
                kiro_files_modified = False
                if kiro_path.exists():
                    for kiro_file in kiro_path.glob('**/*.md'):
                        file_mtime = datetime.fromtimestamp(kiro_file.stat().st_mtime)
                        if file_mtime > last_scan_time:
                            kiro_files_modified = True
                            break
                
                # If .kiro files are newer, do full scan (overwrite)
                is_first_run = kiro_files_modified
        
        scan_type = "Initial" if is_first_run else "Incremental"
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            if is_first_run:
                # First run: Parse all .kiro files
                task = progress.add_task("Initial scan: Parsing all .kiro files...", total=None)
                
                current_commit = tracker.git.get_current_commit()
                kiro_path = project_path / '.kiro'
                kiro_requirements = parser.parse_kiro_directory(kiro_path, current_commit)
                
                progress.update(task, description="Creating living document...")
                living_doc.create_initial_document(kiro_requirements, project_path.name)
                changeset = RequirementsChangeSet(
                    added_requirements=kiro_requirements,
                    from_commit="initial",
                    to_commit=current_commit,
                    scan_date=datetime.now()
                )
                
            else:
                # Incremental run: Only process changed .kiro files since last scan
                task = progress.add_task("Incremental scan: Checking for changes...", total=None)
                
                current_commit = tracker.git.get_current_commit()
                last_commit = tracker.metadata.last_scan_commit
                
                # Get list of changed .kiro files since last scan
                changed_file_objects = tracker.git.get_changed_files_since_commit(last_commit)
                kiro_path = project_path / '.kiro'
                changed_kiro_files = [
                    change.file_path for change in changed_file_objects 
                    if change.file_path.startswith('.kiro/') and change.file_path.endswith('.md')
                ]
                
                if not changed_kiro_files:
                    progress.update(task, description="No changes detected in .kiro files")
                    changeset = RequirementsChangeSet(
                        added_requirements=[],
                        from_commit=last_commit,
                        to_commit=current_commit,
                        scan_date=datetime.now()
                    )
                else:
                    progress.update(task, description=f"Processing {len(changed_kiro_files)} changed files...")
                    
                    # Parse only changed files
                    new_requirements = []
                    for changed_file in changed_kiro_files:
                        file_path = project_path / changed_file
                        if file_path.exists():
                            try:
                                content = file_path.read_text(encoding='utf-8')
                                file_requirements = parser.parse_requirements_file(content, file_path, current_commit)
                                new_requirements.extend(file_requirements)
                            except Exception as e:
                                console.print(f"[yellow]Warning: Failed to parse {changed_file}: {e}[/yellow]")
                    
                    progress.update(task, description="Updating living document...")
                    existing_requirements = tracker._load_existing_requirements()
                    for req in new_requirements:
                        req.id = tracker._generate_next_requirement_id(existing_requirements)
                        existing_requirements[req.id] = req
                    
                    # Update document with all requirements
                    all_requirements = list(existing_requirements.values())
                    changeset = RequirementsChangeSet(
                        added_requirements=new_requirements,
                        from_commit=last_commit,
                        to_commit=current_commit,
                        scan_date=datetime.now()
                    )
                    living_doc.update_document(changeset, all_requirements)
            
            # Update metadata for both cases
            tracker.update_metadata(changeset)
            progress.update(task, description="Complete!")
        
        # Clear any residual spinner output
        console.print()
        
        # Get final requirements count for display
        if is_first_run:
            requirements_for_display = kiro_requirements
            req_count = len(kiro_requirements)
            action_text = "Created initial"
        else:
            requirements_for_display = changeset.added_requirements
            req_count = len(changeset.added_requirements)
            if req_count > 0:
                action_text = "Added"
            else:
                action_text = "No new"
                req_count = ""
        
        console.print()
        console.print(Panel(
            Text(f"✅ {scan_type} Kiro Scan Complete", style="bold green") + "\n\n" +
            Text(f"📊 {action_text}{' ' + str(req_count) if req_count else ''} requirements from .kiro directory", style="white") + "\n" +
            Text(f"📄 Updated: {tracker.requirements_file}", style="dim cyan") + "\n\n" +
            Text("💡 All requirements marked as supported by default", style="dim yellow"),
            border_style="green",
            padding=(1, 2)
        ))
        
        if not args.quiet and requirements_for_display:
            show_requirements_summary(console, requirements_for_display)
            summary_report = parser.generate_summary_report(requirements_for_display)
            console.print()
            console.print(Panel(
                Text("📋 Kiro Requirements Summary", style="bold blue") + "\n\n" +
                Text(summary_report, style="white"),
                border_style="blue",
                padding=(1, 2)
            ))
        
        return 0
        
    except Exception as e:
        console.print(f"[red]Kiro parsing error: {e}[/red]")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def show_requirements_summary(console: Console, requirements: list[RequirementRecord]) -> None:
    """Show a formatted summary of requirements grouped by source folder and sorted numerically."""
    if not requirements:
        console.print("\n[yellow]No requirements found[/yellow]")
        return
    
    # Group requirements by source folder
    grouped_reqs = _group_requirements_by_source(requirements)
    
    # Create table for each source folder
    for source_folder, folder_reqs in grouped_reqs.items():
        table = Table(
            title=f"Requirements - {source_folder}", 
            show_header=True, 
            header_style="bold blue",
            show_lines=True,
            expand=True,
            padding=(0, 1)
        )
        table.add_column("ID", style="cyan", no_wrap=True, min_width=8)
        table.add_column("Status", justify="center", min_width=12)
        table.add_column("Source", style="green", min_width=16)
        table.add_column("EARS Format", style="white", ratio=2)
        
        # Sort requirements numerically within this source folder
        sorted_reqs = _sort_requirements_numerically(folder_reqs)
        
        for req in sorted_reqs:
            # Use source_location for kiro mode (contains folder name) or fallback to source_type
            source_display = req.source_location if hasattr(req, 'source_location') and req.source_location else req.source_type.value.replace('_', ' ').title()
            
            table.add_row(
                req.id,
                f"{req.status_emoji} {req.status.value.title()}",
                source_display,
                req.ears_format
            )
        
        console.print()
        console.print(table)    
    console.print()


def _group_requirements_by_source(requirements: list[RequirementRecord]) -> dict[str, list[RequirementRecord]]:
    """Group requirements by their source folder."""
    grouped = {}
    
    for req in requirements:
        # Get source folder name
        source_folder = req.source_location if hasattr(req, 'source_location') and req.source_location else req.source_type.value
        
        if source_folder not in grouped:
            grouped[source_folder] = []
        grouped[source_folder].append(req)
    
    # Sort source folders alphabetically
    return dict(sorted(grouped.items()))


def _sort_requirements_numerically(requirements: list[RequirementRecord]) -> list[RequirementRecord]:
    """Sort requirements numerically by ID (REQ-1, REQ-1.1, REQ-1.2, REQ-2, etc.)."""
    def numerical_sort_key(req: RequirementRecord) -> tuple:
        """Extract numerical parts from requirement ID for proper sorting."""
        # Remove REQ- prefix and split by dots
        id_without_prefix = req.id.replace('REQ-', '')
        parts = id_without_prefix.split('.')
        
        # Convert each part to integer for numerical comparison
        numerical_parts = []
        for part in parts:
            try:
                numerical_parts.append(int(part))
            except ValueError:
                # If conversion fails, use string value
                numerical_parts.append(part)
        
        return tuple(numerical_parts)
    
    return sorted(requirements, key=numerical_sort_key)