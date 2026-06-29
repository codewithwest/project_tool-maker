# LLM Tool Maker

[![CI](https://github.com/codewithwest/project_tool-maker/actions/workflows/ci.yml/badge.svg)](https://github.com/codewithwest/project_tool-maker/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/llm-tool-maker.svg)](https://pypi.org/project/llm-tool-maker/)
[![Python versions](https://img.shields.io/pypi/pyversions/llm-tool-maker.svg)](https://pypi.org/project/llm-tool-maker/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An intelligent tool-making system that uses LLMs to analyze projects, generate tools, and execute them in a sandboxed environment — all through a modern web dashboard or CLI.

## Quick Start

```bash
# 1. Install
pip install llm-tool-maker

# 2. Initialize (detects Ollama, creates DB, writes .env)
llm-tool-maker init

# 3. Launch the dashboard
llm-tool-maker ui
```

That's it. No PostgreSQL, no external services — just your local Ollama instance. The dashboard opens at `http://localhost:5000`.

## Features

| Feature | Description |
|---|---|
| **Zero-setup persistence** | SQLite by default (stdlib, no dependencies). Opt-in PostgreSQL for production. |
| **Pluggable LLMs** | Ollama (local), OpenAI, or Anthropic — swap via `--provider` |
| **Sandboxed execution** | Subprocess runner with module whitelist, no network, configurable timeout, auto-retry with dep install |
| **Autonomous pipeline** | 6-stage DB-backed pipeline: Analyse → Plan → Validate → Implement → Test → Review, with auto-fix loop |
| **Web dashboard** | 6-page glass-morphism UI (Dashboard, Pipeline, Execute, Analyze, Provider, Config, Docs) |
| **Dependency management** | AST-based import scanning, 200+ stdlib modules, 50+ module→package mappings, auto-install |
| **Remote API client** | `ToolMakerClient` lets you consume Tool Maker as a REST service |
| **Docker Compose** | One-command deployment with Ollama + PostgreSQL + the app |

## Installation

```bash
# From PyPI
pip install llm-tool-maker

# With PostgreSQL support (optional)
pip install 'llm-tool-maker[postgres]'

# All extras
pip install 'llm-tool-maker[all]'

# From source
git clone https://github.com/codewithwest/project_tool-maker.git
cd project_tool-maker
uv sync
```

## Usage

### CLI

```bash
llm-tool-maker init            # One-time setup (checks Ollama, creates DB, writes .env)
llm-tool-maker ui              # Launch web dashboard
llm-tool-maker analyze <path>  # Scan a project
llm-tool-maker pipeline <goal> # Run full autonomous pipeline
llm-tool-maker run <file>      # Execute a tool file
llm-tool-maker config show     # View configuration
llm-tool-maker migrate up      # Run DB migrations
llm-tool-maker --help          # All commands
```

### Python API

```python
from tool_maker import ToolMaker

# Use local Ollama (default)
tm = ToolMaker(llm_provider="ollama", model="llama3.2")

# Or OpenAI
tm = ToolMaker(llm_provider="openai", api_key="sk-...", model="gpt-4o-mini")

# Or Anthropic
tm = ToolMaker(llm_provider="anthropic", api_key="sk-...", model="claude-sonnet-4-20250514")

# Analyze, generate, execute
info = tm.analyze_project("/path/to/project")
result = tm.create_and_execute_tool("Parse CSV files and return row count")
```

### Remote API Client

Use Tool Maker as a remote service from any Python project:

```python
from tool_maker import ToolMakerClient

client = ToolMakerClient("http://localhost:5000")
tools = client.list_tools()
result = client.execute("print('hello world')")
client.run_pipeline("Build a CLI tool that counts lines of code")
```

### API-only Mode

Serve just the REST API (no Jinja templates):

```bash
llm-tool-maker ui --api-only
```

## Database

**Zero-config**: SQLite is used automatically when no `TOOLMAKER_DB_DSN` is set. The database file lives at `~/.config/tool-maker/data.db`.

**PostgreSQL** (for production):

```bash
export TOOLMAKER_DB_DSN="postgresql://user:pass@localhost:5432/toolmaker"
llm-tool-maker ui
```

Migrations run automatically on startup.

## Docker

```bash
docker compose up
```

This starts Ollama, PostgreSQL, and the app — reachable at `http://localhost:5000`.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TOOLMAKER_DB_DSN` | `""` (SQLite) | PostgreSQL DSN. Empty = SQLite backend. |
| `TOOLMAKER_DB_PATH` | `~/.config/tool-maker/data.db` | SQLite database file path |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | Default LLM model |
| `SANDBOX_TIMEOUT` | `30` | Tool execution timeout in seconds |
| `MAX_FIX_ATTEMPTS` | `3` | Auto-fix loop retry limit |
| `TOOL_MAKER_CONFIG` | `~/.config/tool-maker/config.toml` | Config file path |

## Web Dashboard

### Pages

- **Dashboard** — overview, live terminal, quick stats
- **Pipeline** — run the 6-stage autonomous pipeline with progress tracking
- **Execute** — IDE-style editor with sidebar (Saved + Database tools), command bar, tabbed results
- **Analyze** — scan a project and inspect its structure
- **Provider** — configure LLM provider and test prompts
- **Config** — manage database, migrations, sandbox whitelist, dependency approvals
- **Docs** — view release notes and README, rendered as formatted markdown

## Project Structure

```
src/tool_maker/
├── __init__.py          # Public API exports
├── client.py            # ToolMakerClient (remote HTTP client)
├── config.py            # ToolMakerConfigFile
├── tool_maker.py        # Main orchestrator
├── tool_fixer.py        # LLM-driven tool fixer
├── analyzer/            # AST-based project scanner
├── cli/                 # CLI argument parsing and handlers
├── db/                  # SQLite + PostgreSQL backends, models, migrations
├── llm/                 # Ollama, OpenAI, Anthropic providers
├── planner/             # Planner, validator, executor, reviewer
├── tool/                # Generator, executor, sandbox, fixer, deps
└── ui/                  # Flask web app (routes, templates, static)
```

## Development

```bash
uv sync
uv run ruff check .
uv run pytest
```

## License

MIT
