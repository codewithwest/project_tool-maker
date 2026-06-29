# LLM Tool Maker

[![CI](https://github.com/codewithwest/project_tool-maker/actions/workflows/ci.yml/badge.svg)](https://github.com/codewithwest/project_tool-maker/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/llm-tool-maker.svg)](https://pypi.org/project/llm-tool-maker/)
[![Python versions](https://img.shields.io/pypi/pyversions/llm-tool-maker.svg)](https://pypi.org/project/llm-tool-maker/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An intelligent tool-making system that uses local LLMs (via Ollama) to analyze projects, generate tools, and execute them in a sandboxed environment — all through a modern web dashboard or CLI.

## Features

- **Project Analysis** — AST-based scanning of project structure, imports, and entry points
- **LLM Tool Generation** — generates Python tools from natural language descriptions using local LLMs
- **Sandboxed Execution** — subprocess runner with module whitelist, no network, and configurable timeout
- **Autonomous Pipeline** — 6-stage DB-backed pipeline: Analyse → Plan → Validate → Implement → Test → Review, with auto-fix loop
- **Web Dashboard** — 6-page glass-morphism UI (Dashboard, Pipeline, Execute, Analyze, Provider, Config, Docs)
- **Dependency Management** — auto-detects imports, maps to pip packages, auto-installs via `uv`
- **PostgreSQL Persistence** — saves tools, plans, executions, and reviews; migration system included

## Installation

```bash
# Install globally
uv tool install llm-tool-maker

# Or add to a project
uv add llm-tool-maker
```

### From source

```bash
git clone https://github.com/codewithwest/project_tool-maker.git
cd project_tool-maker
uv sync
```

## Quick Start

### 1. Start Ollama

```bash
ollama pull llama3.2  # or any model you prefer
```

### 2. Launch the dashboard

```bash
tool-maker ui
```

Opens at `http://localhost:5000`.

### 3. Or use the CLI

```bash
# Analyze a project
tool-maker analyze /path/to/project

# Run the autonomous pipeline
tool-maker pipeline "Create a function to parse CSV files"

# Execute a saved tool
tool-maker run my-tool
```

## Database Setup

By default, tools work in-memory. For persistence and the full pipeline, set up PostgreSQL:

```bash
# Install PostgreSQL (Ubuntu/Debian)
sudo apt install postgresql
sudo systemctl start postgresql

# Create a database
sudo -u postgres createdb tool_maker

# Set the connection string (or export it)
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/tool_maker"
```

Then start the dashboard — migrations run automatically on first connection.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/tool_maker` | PostgreSQL connection string |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | Default LLM model |
| `SANDBOX_TIMEOUT` | `30` | Tool execution timeout in seconds |
| `MAX_FIX_ATTEMPTS` | `3` | Auto-fix loop retry limit |
| `TOOL_MAKER_CONFIG` | `~/.config/tool-maker/config.toml` | Config file path |

## Web Dashboard

### Pages

- **Dashboard** — overview, live terminal, quick stats
- **Pipeline** — run the 6-stage autonomous pipeline with progress tracking
- **Execute** — edit and run tools in an IDE-style editor; browse saved tools in the sidebar
- **Analyze** — scan a project and inspect its structure
- **Provider** — configure Ollama model and test prompts
- **Config** — manage database, migrations, sandbox whitelist, dependency approvals
- **Docs** — view release notes and this README, rendered as formatted markdown

### API Endpoints

20+ REST endpoints powering the dashboard:

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/pipeline` | Run the autonomous pipeline |
| GET | `/api/analyze` | Analyze a project path |
| POST | `/api/execute` | Execute a tool |
| POST | `/api/fix` | Fix a broken tool via LLM |
| POST | `/api/refine` | Refine a tool with instructions |
| POST | `/api/explain` | Get an LLM explanation of execution |
| GET | `/api/deps/check` | Check tool dependencies |
| POST | `/api/deps/approve` | Approve a package for auto-install |
| GET | `/api/db/migrations` | List migration status |
| POST | `/api/db/migrate` | Run pending migrations |

## Python API

```python
from tool_maker import ToolMaker

tm = ToolMaker(
    llm_provider="ollama",
    base_url="http://localhost:11434",
    model="llama3.2"
)

# Analyze a project
info = tm.analyze_project("/path/to/project")

# Generate and execute a tool
result = tm.create_and_execute_tool("Parse CSV files and return row count")
print(result)

# Or run the full pipeline
result = tm.run_pipeline("Build a CLI tool that counts lines of code")
print(result)
```

## Project Structure

```
src/tool_maker/
├── __init__.py          # ToolMaker orchestrator
├── analyzer/             # AST-based project scanner
├── cli/                  # CLI argument parsing and handlers
├── config.py             # Configuration loading
├── db/                   # PostgreSQL models, connection, migrations
├── llm/                  # Ollama provider (HTTPX-based)
├── planner/              # Planner, validator, executor, reviewer
├── tool/                 # Generator, executor, sandbox, fixer, deps
└── ui/                   # Flask web app (routes, templates, static)
```

## Development

```bash
uv sync
uv run ruff check .
uv run pytest
```

## License

MIT
