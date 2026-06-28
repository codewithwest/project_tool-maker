# Tool Maker - Development Setup

## Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) package manager

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/tool_maker.git
cd tool_maker
```

### 2. Set up the development environment with uv

```bash
# Initialize uv project (if not already done)
uv init

# Sync dependencies
uv sync

# Activate the virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install development dependencies

```bash
uv add --dev pytest black ruff
```

## Development Commands

### Running Tests

```bash
uv run pytest
```

### Running Linter

```bash
uv run ruff check .
```

### Formatting Code

```bash
uv run black .
```

### Running Type Checker

```bash
uv run mypy src/tool_maker
```

## Building the Package

```bash
# Build the package
uv build

# Install locally for testing
uv pip install dist/tool_maker-*.whl
```

## Testing the CLI

```bash
# Run the CLI
uv run tool-maker --help

# Analyze a project
uv run tool-maker analyze /path/to/project

# Generate a tool
uv run tool-maker generate "create a CSV parser" --project .
```

## Project Structure

```
tool_maker/
├── src/
│   └── tool_maker/          # Main package
│       ├── analyzer/       # Project analysis
│       ├── llm/           # LLM integration
│       ├── tool/          # Tool generation
│       ├── flask/         # Flask integration
│       └── cli/           # CLI interface
├── tests/                  # Test files
├── examples/              # Usage examples
├── pyproject.toml         # uv project configuration
└── requirements.txt       # Python dependencies
```

## Adding New Features

1. Create a new branch: `git checkout -b feature/your-feature`
2. Implement your feature
3. Add tests for your feature
4. Run linting and tests: `uv run ruff check . && uv run pytest`
5. Format code: `uv run black .`
6. Commit and push: `git commit -m 'Add some feature' && git push origin feature/your-feature`

## LLM Provider Setup

### OpenAI

```bash
export OPENAI_API_KEY="sk-..."
```

### Anthropic (Claude)

```bash
export ANTHROPIC_API_KEY="sk-..."
```

## Documentation

Generate documentation:

```bash
uv run pdoc --html --output-dir docs src/tool_maker
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request
