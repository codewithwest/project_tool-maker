# Tool Maker Package

[![CI](https://github.com/codewithwest/project_tool-maker/actions/workflows/ci.yml/badge.svg)](https://github.com/codewithwest/project_tool-maker/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/llm-tool-maker.svg)](https://pypi.org/project/llm-tool-maker/)
[![Python versions](https://img.shields.io/pypi/pyversions/llm-tool-maker.svg)](https://pypi.org/project/llm-tool-maker/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An intelligent tool-making package that leverages LLMs to analyze projects and generate tools.

## Overview

Tool Maker is a Python package that:
- Analyzes projects to understand their structure and capabilities
- Uses LLMs to formulate intelligent prompts and generate tools
- Can be integrated into Flask applications or used standalone
- Provides a CLI for easy command-line usage

## Features

- **Project Analysis**: Automatically scans and analyzes project structure
- **LLM Integration**: Supports multiple LLM providers (OpenAI, Anthropic, local models)
- **Tool Generation**: Creates appropriate tools based on project capabilities
- **Flask Integration**: Easy integration with Flask applications
- **CLI Interface**: Command-line tool for quick usage

## Installation

### Using uv (Recommended)

```bash
# Install globally
uv tool install llm-tool-maker

# Or add to a project
uv add llm-tool-maker
```

### From Source

```bash
git clone https://github.com/codewithwest/project_tool-maker.git
cd tool-maker
uv sync
uv run tool-maker --help
```

## Quick Start

### Standalone Usage

```python
from tool_maker import ToolMaker

# Initialize with your LLM provider
tm = ToolMaker(
    llm_provider="openai",
    api_key="your-api-key"
)

# Analyze a project
project_info = tm.analyze_project("/path/to/project")

# Create and execute a tool
result = tm.create_and_execute_tool("Create a function to parse CSV files")
print(result)
```

### Flask Integration

```python
from flask import Flask, request, jsonify
from tool_maker.flask import ToolMakerExtension

app = Flask(__name__)

# Initialize Tool Maker
tm = ToolMakerExtension(
    app,
    llm_provider="openai",
    api_key="your-api-key"
)

@app.route('/analyze', methods=['POST'])
def analyze():
    project_path = request.json.get('project_path')
    return jsonify(tm.analyze_project(project_path))

@app.route('/tools', methods=['POST'])
def create_tool():
    query = request.json.get('query')
    return jsonify(tm.create_and_execute_tool(query))
```

## Project Structure

```
tool_maker/
├── analyzer/      # Project analysis module
├── llm/          # LLM integration module
├── tool/         # Tool generation and execution
├── flask/        # Flask integration
└── cli/          # Command-line interface
```

## Configuration

### LLM Providers

Tool Maker supports multiple LLM providers:

```python
# OpenAI
tm = ToolMaker(llm_provider="openai", api_key="sk-...")

# Anthropic (Claude)
tm = ToolMaker(llm_provider="anthropic", api_key="sk-...")

# Local LLM (e.g., Ollama)
tm = ToolMaker(
    llm_provider="ollama",
    base_url="http://localhost:11434",
    model="llama2"
)
```

## Development

```bash
# Set up development environment
uv sync
uv run pytest

# Run linter
uv run ruff check .

# Format code
uv run black .
```

## Examples

See the `examples/` directory for more detailed examples:
- `basic_usage.py` - Standalone usage
- `flask_integration.py` - Flask integration
- `custom_analyzer.py` - Custom project analysis

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with [uv](https://github.com/astral-sh/uv) for fast Python package management
- Inspired by AI-powered code generation tools
