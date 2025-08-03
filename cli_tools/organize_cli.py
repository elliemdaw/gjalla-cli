"""
CLI interface for project organization and documentation management.

This module provides the command-line interface for the 'reorganize' and 'undo' subcommands.
The actual functionality will be moved from reorganize_cli.py to the organize package.
"""

from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.tree import Tree


def reorganize_project(args) -> int:
    """
    Reorganize project documentation and files.
    
    This uses the organize package functionality with a clean CLI interface.
    """
    console = Console()
    
    try:
        # Import from the organize package
        try:
            from organize import NameOnlyReorganizer, BackupManager
        except ImportError:
            # Try relative import for standalone script execution
            import sys
            from pathlib import Path as PathlibPath
            sys.path.insert(0, str(PathlibPath(__file__).parent.parent))
            from organize import NameOnlyReorganizer, BackupManager
        
        project_path = Path(args.project_dir)
        
        if not project_path.exists():
            console.print(f"[red]Error: Project directory does not exist: {args.project_dir}[/red]")
            return 1
        
        # Create configuration from args
        config = create_name_only_config_from_args(args)
        
        # Validate configuration  
        config_errors = config.validate()
        if config_errors:
            console.print("[red]Configuration errors:[/red]")
            for error in config_errors:
                console.print(f"  - {error}")
            return 1
        
        # Show what we're about to do
        if args.dry_run:
            console.print()
            console.print(Panel(
                Text("🔍 Dry Run Mode", style="bold magenta") + "\n" +
                Text(f"📁 {project_path.absolute()}", style="dim cyan") + "\n\n" +
                Text("No changes will be made to your files.", style="white") + "\n" +
                Text("This preview shows what would happen during reorganization.", style="dim"),
                border_style="magenta",
                padding=(1, 2)
            ))
        
        # Create backup manager
        backup_dir = project_path / '.gjalla' / '.backup'
        backup_manager = BackupManager(backup_dir)
        
        # Create reorganizer
        reorganizer = NameOnlyReorganizer(backup_manager)
        
        # Perform reorganization
        result = reorganizer.reorganize_repository(project_path, config)
        
        # Show detailed results
        if result.success:
            if args.dry_run:
                _show_dry_run_preview(console, result, project_path, args.verbose)
            else:
                _show_completion_summary(console, result, project_path, args.verbose)
            return 0
        else:
            if hasattr(result, 'error_message') and result.error_message:
                console.print(f"[red]✗ Reorganization failed: {result.error_message}[/red]")
            elif hasattr(result, 'errors') and result.errors:
                error_msg = '; '.join(result.errors)
                console.print(f"[red]✗ Reorganization failed: {error_msg}[/red]")
            else:
                console.print(f"[red]✗ Reorganization failed: Unknown error[/red]")
            return 1
        
    except ImportError as e:
        console.print(f"[red]Import error: {e}[/red]")
        console.print("[yellow]The organization functionality requires the organize package.[/yellow]")
        return 1
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def create_name_only_config_from_args(args):
    """Create NameOnlyConfig from command line arguments."""
    try:
        from organize import NameOnlyConfig
    except ImportError:
        import sys
        from pathlib import Path as PathlibPath
        sys.path.insert(0, str(PathlibPath(__file__).parent.parent))
        from organize import NameOnlyConfig
    
    # Build exclusion patterns
    exclusion_patterns = [
        "README*", "CONTRIBUTING*", "LICENSE*", "CHANGELOG*", "GEMINI.MD", "CLAUDE.MD",
        "*.git*", "*.svn*", "*__pycache__*", "*.DS_Store*", ".gjalla",
        "*node_modules*", "*.vscode*", "*.idea*", ".kiro", "**/dist", "**/build",
        "**/__pycache__", "**/.pytest_cache", "**/.DS_Store", "**/.git", "**/.svn"
    ]
    
    # Add user-specified exclusions
    if hasattr(args, 'exclude') and args.exclude:
        exclusion_patterns.extend(args.exclude)
    
    # Create configuration (using defaults when args not provided)
    template_file = getattr(args, 'template', None)
    if template_file:
        template_file = Path(template_file)
    else:
        template_file = Path("templates/directory.md")  # Use default
    
    config = NameOnlyConfig(
        template_file=template_file,
        confidence_threshold=getattr(args, 'confidence_threshold', 0.3),
        fallback_category=getattr(args, 'fallback_category', 'reference'),
        backup_enabled=not getattr(args, 'no_backup', False),
        exclusion_patterns=exclusion_patterns,
        dry_run=getattr(args, 'dry_run', False)
    )
    
    return config


def _show_dry_run_preview(console: Console, result, project_path: Path, verbose: bool = False):
    """Display beautiful tree-based dry-run preview of reorganization changes."""
    
    # Create main tree
    preview_tree = Tree(
        Text("📋 DETAILED DRY RUN PREVIEW", style="bold magenta"),
        guide_style="bright_blue"
    )
    
    # 1. Directories to be Created
    if result.structure_validation and result.structure_validation.missing_directories:
        dir_branch = preview_tree.add(Text("🏗️  Directories to be Created:", style="bold cyan"))
        for missing_dir in sorted(result.structure_validation.missing_directories):
            try:
                rel_path = missing_dir.relative_to(project_path)
                dir_branch.add(Text(f"📁 {rel_path}/", style="cyan"))
            except ValueError:
                dir_branch.add(Text(f"📁 {missing_dir}/", style="cyan"))
    
    # 2. Files to be Moved
    if result.file_organization and result.file_organization.moved_files:
        moves = result.file_organization.moved_files
        successful_moves = [m for m in moves if m.success and m.target_path != m.source_path]
        
        if successful_moves:
            files_branch = preview_tree.add(Text(f"📄 Files to be Moved ({len(successful_moves)}):", style="bold blue"))
            
            # Group moves by target directory for better organization
            moves_by_target = {}
            for move in successful_moves:
                try:
                    target_dir = move.target_path.parent.relative_to(project_path)
                    source_dir = move.source_path.parent.relative_to(project_path)
                except ValueError:
                    target_dir = move.target_path.parent
                    source_dir = move.source_path.parent
                
                target_key = str(target_dir)
                if target_key not in moves_by_target:
                    moves_by_target[target_key] = []
                moves_by_target[target_key].append((move, source_dir))
            
            # Add each target directory with its files
            for target_dir in sorted(moves_by_target.keys()):
                dir_moves = moves_by_target[target_dir]
                dir_branch = files_branch.add(Text(f"📁 {target_dir}/", style="cyan bold"))
                
                for move, source_dir in dir_moves:
                    # Create file text with confidence styling
                    file_text = Text()
                    
                    # Confidence indicator
                    if hasattr(move, 'confidence'):
                        confidence = getattr(move, 'confidence', 0.8)
                        if confidence > 0.7:
                            file_text.append("✓ ", style="green")
                        elif confidence > 0.5:
                            file_text.append("⚠ ", style="yellow")
                        else:
                            file_text.append("? ", style="red")
                    else:
                        file_text.append("✓ ", style="green")
                    
                    # File name
                    file_text.append(f"{move.source_path.name}", style="bright_white")
                    
                    # Source location
                    source_text = f" (from {source_dir})" if str(source_dir) != "." else " (from project root)"
                    file_text.append(source_text, style="dim")
                    
                    # Conflict resolution marker
                    if move.conflict_resolved:
                        file_text.append(" [renamed]", style="dim yellow")
                    
                    dir_branch.add(file_text)
    
    # 3. File Classification Summary (if verbose)
    if verbose and result.file_classification and result.file_classification.classified_files:
        classified_files = result.file_classification.classified_files
        categories = {}
        for file in classified_files:
            if file.category not in categories:
                categories[file.category] = []
            categories[file.category].append(file)
        
        classification_branch = preview_tree.add(Text("🏷️  Classification Summary:", style="bold yellow"))
        for category in sorted(categories.keys()):
            files = categories[category]
            avg_confidence = sum(f.confidence for f in files) / len(files)
            confidence_style = "green" if avg_confidence > 0.7 else "yellow" if avg_confidence > 0.5 else "red"
            category_text = Text()
            category_text.append(f"{category}: ", style="cyan")
            category_text.append(f"{len(files)} files ", style="white")
            category_text.append(f"({avg_confidence:.1%} confidence)", style=confidence_style)
            classification_branch.add(category_text)
    
    # 4. Next Steps
    next_steps = preview_tree.add(Text("✨ Next Steps:", style="bold green"))
    next_steps.add(Text("1. Review the planned changes above", style="green"))
    next_steps.add(Text("2. Run without --dry-run to apply changes", style="green"))
    next_steps.add(Text("3. Use 'gjalla undo' if you need to revert changes", style="green"))
    
    # Display the tree
    console.print()
    console.print(preview_tree)
    console.print()


def _show_completion_summary(console: Console, result, project_path: Path, verbose: bool = False):
    """Display beautiful tree-based summary of completed reorganization."""
    
    # Create main tree
    summary_tree = Tree(
        Text("✅ REORGANIZATION COMPLETED", style="bold green"),
        guide_style="bright_green"
    )
    
    # 1. Directories Created
    if result.directory_creation and result.directory_creation.created_directories:
        dir_branch = summary_tree.add(Text("🏗️  Directories Created:", style="bold cyan"))
        for created_dir in sorted(result.directory_creation.created_directories):
            try:
                rel_path = created_dir.relative_to(project_path)
                dir_branch.add(Text(f"📁 {rel_path}/", style="cyan"))
            except ValueError:
                dir_branch.add(Text(f"📁 {created_dir}/", style="cyan"))
    
    # 2. Files Moved
    if result.file_organization and result.file_organization.moved_files:
        moves = result.file_organization.moved_files
        successful_moves = [m for m in moves if m.success and m.target_path != m.source_path]
        
        if successful_moves:
            files_branch = summary_tree.add(Text(f"📄 Files Moved ({len(successful_moves)}):", style="bold blue"))
            
            # Group moves by target directory
            moves_by_target = {}
            for move in successful_moves:
                try:
                    target_dir = move.target_path.parent.relative_to(project_path)
                    source_dir = move.source_path.parent.relative_to(project_path)
                except ValueError:
                    target_dir = move.target_path.parent
                    source_dir = move.source_path.parent
                
                target_key = str(target_dir)
                if target_key not in moves_by_target:
                    moves_by_target[target_key] = []
                moves_by_target[target_key].append((move, source_dir))
            
            for target_dir in sorted(moves_by_target.keys()):
                dir_moves = moves_by_target[target_dir]
                dir_branch = files_branch.add(Text(f"📁 {target_dir}/", style="cyan bold"))
                
                for move, source_dir in dir_moves:
                    file_text = Text()
                    file_text.append("✓ ", style="green")
                    file_text.append(f"{move.target_path.name}", style="bright_white")
                    source_text = f" (moved from {source_dir})" if str(source_dir) != "." else " (moved from project root)"
                    file_text.append(source_text, style="dim")
                    dir_branch.add(file_text)
    
    # 3. Summary Stats
    stats_branch = summary_tree.add(Text("📊 Summary:", style="bold magenta"))
    execution_time = getattr(result, 'execution_time', 0)
    stats_branch.add(Text(f"⏱️  Completed in {execution_time:.2f}s", style="white"))
    
    if result.structure_validation:
        stats_branch.add(Text(f"🏗️  Directory compliance: {result.structure_validation.compliance_score:.1%}", style="cyan"))
    
    if result.file_organization:
        total_moves = len([m for m in result.file_organization.moved_files if m.success and m.target_path != m.source_path])
        if total_moves > 0:
            stats_branch.add(Text(f"📦 Files reorganized: {total_moves}", style="blue"))
    
    # 4. Next Steps
    next_steps = summary_tree.add(Text("✨ Available Actions:", style="bold yellow"))
    next_steps.add(Text("• Use 'gjalla undo' to revert these changes", style="yellow"))
    next_steps.add(Text("• Check the new organization with 'ls' or file explorer", style="yellow"))
    next_steps.add(Text("• Run 'gjalla requirements --kiro' to scan new structure", style="yellow"))
    
    # Display the tree
    console.print()
    console.print(summary_tree)
    console.print()


def _show_undo_preview(console: Console, session_data, project_path: Path):
    """Display tree-based preview of undo operations."""
    
    # Create main tree
    undo_tree = Tree(
        Text("↩️  UNDO PREVIEW", style="bold yellow"),
        guide_style="bright_yellow"
    )
    
    # Parse session data
    if hasattr(session_data, 'backed_up_files') and session_data.backed_up_files:
        files_branch = undo_tree.add(Text(f"📄 Files to Restore ({len(session_data.backed_up_files)}):", style="bold blue"))
        
        # Group by original directory
        files_by_dir = {}
        for backed_up_file in session_data.backed_up_files:
            try:
                original_dir = backed_up_file.original_path.parent.relative_to(project_path)
            except ValueError:
                original_dir = backed_up_file.original_path.parent
            
            dir_key = str(original_dir)
            if dir_key not in files_by_dir:
                files_by_dir[dir_key] = []
            files_by_dir[dir_key].append(backed_up_file)
        
        for original_dir in sorted(files_by_dir.keys()):
            files_in_dir = files_by_dir[original_dir]
            dir_branch = files_branch.add(Text(f"📁 {original_dir}/", style="cyan bold"))
            
            for backed_up_file in files_in_dir:
                file_text = Text()
                file_text.append("↩️  ", style="yellow")
                file_text.append(f"{backed_up_file.original_path.name}", style="bright_white")
                
                # Show current location if different
                try:
                    current_location = backed_up_file.original_path.parent.relative_to(project_path)
                    if str(current_location) != original_dir:
                        file_text.append(f" (currently in {current_location})", style="dim")
                except:
                    pass
                
                dir_branch.add(file_text)
    
    # Operations to reverse
    if hasattr(session_data, 'operation_log') and session_data.operation_log:
        ops_branch = undo_tree.add(Text("🔄 Operations to Reverse:", style="bold red"))
        
        # Group operations by type
        op_counts = {}
        for operation in session_data.operation_log:
            op_type = operation.operation_type
            op_counts[op_type] = op_counts.get(op_type, 0) + 1
        
        for op_type, count in op_counts.items():
            op_text = Text()
            if op_type == "CREATE":
                op_text.append("🗑️  ", style="red")
                op_text.append(f"Remove {count} created directories", style="white")
            elif op_type == "MOVE":
                op_text.append("↩️  ", style="yellow")
                op_text.append(f"Move back {count} files", style="white")
            else:
                op_text.append("🔄 ", style="blue")
                op_text.append(f"Reverse {count} {op_type.lower()} operations", style="white")
            
            ops_branch.add(op_text)
    
    # Warning and next steps
    warning_branch = undo_tree.add(Text("⚠️  Important Notes:", style="bold red"))
    warning_branch.add(Text("• This will restore files to their original locations", style="red"))
    warning_branch.add(Text("• Any changes made after reorganization may be lost", style="red"))
    warning_branch.add(Text("• This operation cannot be undone", style="red"))
    
    next_steps = undo_tree.add(Text("✨ Next Steps:", style="bold green"))
    next_steps.add(Text("• Run without --dry-run to perform the undo", style="green"))
    next_steps.add(Text("• Backup any important changes before proceeding", style="green"))
    
    # Display the tree
    console.print()
    console.print(undo_tree)
    console.print()


def undo_reorganization(args) -> int:
    """
    Undo the most recent reorganization.
    
    This uses the organize package backup functionality.
    """
    console = Console()
    
    try:
        try:
            from organize import BackupManager
        except ImportError:
            import sys
            from pathlib import Path as PathlibPath
            sys.path.insert(0, str(PathlibPath(__file__).parent.parent))
            from organize import BackupManager
        
        project_path = Path(args.project_dir)
        
        if not project_path.exists():
            console.print(f"[red]Error: Project directory does not exist: {args.project_dir}[/red]")
            return 1
        
        # Initialize backup manager
        backup_dir = project_path / '.gjalla' / '.backup'
        backup_manager = BackupManager(backup_dir)
        
        # List sessions if requested
        if getattr(args, 'list_sessions', False):
            sessions = backup_manager.list_backup_sessions()
            if not sessions:
                console.print("[yellow]No backup sessions found.[/yellow]")
                return 0
            
            console.print("\n[bold]Available backup sessions:[/bold]")
            for session in sessions:
                console.print(f"  - {session.session_id} ({session.timestamp})")
            return 0
        
        # Get the session to restore
        session_id = getattr(args, 'session_id', None)
        
        if args.dry_run:
            console.print()
            console.print(Panel(
                Text("🔍 Undo Dry Run Mode", style="bold magenta") + "\n" +
                Text(f"📁 {project_path.absolute()}", style="dim cyan") + "\n\n" +
                Text("No changes will be made to your files.", style="white") + "\n" +
                Text("This preview shows what would be restored.", style="dim"),
                border_style="magenta",
                padding=(1, 2)
            ))
            
            # Get session data for preview
            if session_id:
                session_data = backup_manager._load_session_metadata(session_id)
            else:
                sessions = backup_manager.list_backup_sessions()
                session_data = sessions[0] if sessions else None
            
            if session_data:
                _show_undo_preview(console, session_data, project_path)
            else:
                console.print("[yellow]No backup sessions found to preview.[/yellow]")
                return 0
        
        # Perform the undo operation
        if session_id:
            result = backup_manager.restore_specific_session(session_id, dry_run=args.dry_run)
        else:
            result = backup_manager.restore_most_recent_backup(dry_run=args.dry_run)
        
        if result.success:
            if not args.dry_run:
                # Show completion summary for actual undo
                console.print()
                undo_summary_tree = Tree(
                    Text("✅ UNDO COMPLETED", style="bold green"),
                    guide_style="bright_green"
                )
                
                if hasattr(result, 'restored_files') and result.restored_files:
                    files_branch = undo_summary_tree.add(Text(f"↩️  Files Restored ({len(result.restored_files)}):", style="bold blue"))
                    for restored_file in result.restored_files[:10]:  # Show first 10
                        try:
                            rel_path = restored_file.relative_to(project_path)
                            files_branch.add(Text(f"✓ {rel_path}", style="green"))
                        except ValueError:
                            files_branch.add(Text(f"✓ {restored_file.name}", style="green"))
                    if len(result.restored_files) > 10:
                        files_branch.add(Text(f"... and {len(result.restored_files)-10} more files", style="dim"))
                
                next_steps = undo_summary_tree.add(Text("✨ Next Steps:", style="bold yellow"))
                next_steps.add(Text("• Files have been restored to their original locations", style="yellow"))
                next_steps.add(Text("• Check the restored organization", style="yellow"))
                next_steps.add(Text("• Run 'gjalla organize' again if needed", style="yellow"))
                
                console.print(undo_summary_tree)
                console.print()
            return 0
        else:
            if result.errors:
                error_msg = '; '.join(result.errors)
                console.print(f"[red]✗ Undo failed: {error_msg}[/red]")
            else:
                console.print(f"[red]✗ Undo failed: Unknown error[/red]")
            return 1
        
    except ImportError as e:
        console.print(f"[red]Import error: {e}[/red]")
        console.print("[yellow]The undo functionality requires the organize package.[/yellow]")
        return 1
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1