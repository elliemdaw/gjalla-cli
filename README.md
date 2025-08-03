# gjalla CLI

A CLI for organizing, aggregating, and standardizing requirements and architecture information from markdowns written by agentic coding tools.

## Installation

```bash
# Install from PyPI
pip install gjalla

# Install from source
pip install git+https://github.com/elliemdaw/gjalla-cli.git
```

## 🚀 Quick Start

### Organize Documentation

```bash
# Preview what would be organized
gjalla organize <path to project> --dry-run

# Apply the organization
gjalla organize <path to project>

# Undo if needed
# NOTE: undo has only been tested for the most recent action
gjalla undo <path to project>
```

### Aggregate Requirements

```bash
# Parse structured .kiro requirements
gjalla requirements <path to project> --kiro

# List existing requirements
gjalla requirements <path to project> --list
```

## How It Works

### Organization Process

1. **📋 Document Discovery**: Finds all markdown files. Exclude patterns can be defined in .gjallaignore, otherwise falls back to common ignore patterns
2. **🏷️ File Classification**: Uses regex patterns and lightweight NLP (`spacy`) to classify markdown files by type
3. **🔧 Directory Creation**: Creates missing directories as needed (`specs/`, `specs/features/`, `specs/fixes/`, `specs/references/`... see below!)
4. **📦 File Movement**: Moves files to appropriate locations with conflict resolution
5. **💾 Backup**: Saves backup info for undo functionality

### Directory Structure After Organization

```
my-project/
├── aimarkdowns/
│   ├── features/           # User stories, feature specs
│   ├── fixes/              # Bug reports, fixes
│   ├── reference/          # Documentation, guides
│   ├── requirements_001.md     # Generated requirements summary
|   ├── CLAUDE.md           # if found and not excluded, it will be put here
|   └── GEMINI.md           # if found and not excluded, it will be put here
├── .gjalla/
│   ├── backups/            # Backup files for undo
├── .gjallaignore           # for defining exclusion patterns
```

## Requirements

### Kiro

gjalla supports the structure of docs written by Kiro, found in `.kiro` directories:

```
.kiro/
├── specs/
│   ├── feature-name/
│   │   ├── requirements_001.md   # Kiro requirements
│   │   ├── design.md         # Kiro design
│   │   └── tasks.md          # Kiro tasks
│   └── another-feature/
│       └── requirements_001.md
```

### Non-Kiro

_Working on this!_

## 🚧 Coming Next

- [x] **Update Requirements Status**: Mark requirements as implemented/partial/not-implemented
- [ ] **Aggregate Architecture Spec (Kiro Mode)**: Generate comprehensive architecture documentation from .kiro structure
- [ ] **Aggregate Requirements (Non-Kiro Mode)**: Collect and organize requirements from standard markdown files
- [ ] **Aggregate Architecture (Non-Kiro Mode)**: Generate architecture documentation from existing markdown files

## Contributing

This is an open source project. Contributions welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Directory structure

```
.
├── cli_tools/                 # cli commands and subcommands
├── config/                    # configuration related code (more useful for future features)
├── organize                   # Code related to the organize subcommand
├── requirements               # Code related to the requirements subcommand
│── templates                  # Semantic doc matching template (used in `organize`)
│── tests_and_validations      # test scripts written by Claude
```

## Notes

### Why did I build this

I've been working on [gjalla](https://gjalla.io) which helps give teams an system-level view into how their software works and how it has changed over time... the key pain point here is that docs aren't always reconciled with the actual implementation. One of the challenges is has been doc sprawl and acclerating rate of change to codebases as teams start to adopt agentic coding tools. After testing out Kiro, I really liked the concept of spec-driven development, and liked that kiro seemed to be the first attempt at standardizing some of these specs. I wanted to build a couple of tools to help with actual pain points I have when working with agentic tools, including doc sprawl (this tool will at least put the AI-generated docs into categories) and a lack of aggregate info. More coming soon, and I'd love your feedback and contributions!