# Tool Maker Package - Project Plan

## Overview
A Python package using `uv` that acts as an intelligent tool-making assistant. It leverages an LLM to analyze projects, understand their structure, and generate appropriate tools to fulfill user requests.

## Core Concepts

### Package Name
`tool-maker` or `toolmaker`

### Key Features
1. **Project Analysis**: Scans target project to understand its purpose and available modules
2. **LLM Integration**: Uses an assigned LLM for intelligent prompt formulation and tool generation
3. **Tool Generation**: Creates appropriate tools based on project capabilities
4. **Flask Integration**: Can be integrated into Flask applications or installed standalone

## Project Structure

```
tool_maker/
├── pyproject.toml          # uv project configuration
├── README.md
├── src/
│   └── tool_maker/
│       ├── __init__.py
│       ├── analyzer/       # Project analysis module
│       │   ├── __init__.py
│       │   └── project_scanner.py
│       ├── llm/            # LLM integration module
│       │   ├── __init__.py
│       │   └── provider.py
│       ├── tool/           # Tool generation and execution
│       │   ├── __init__.py
│       │   ├── generator.py
│       │   └── executor.py
│       ├── flask/          # Flask integration
│       │   ├── __init__.py
│       │   └── extension.py
│       └── cli/            # Command-line interface
│           ├── __init__.py
│           └── main.py
├── tests/
│   ├── __init__.py
│   └── test_tool_maker.py
└── examples/
    ├── basic_usage.py
    └── flask_integration.py
```

## Core Modules

### 1. Project Analyzer (`tool_maker.analyzer`)
- Scans project structure
- Identifies dependencies and modules
- Maps available functionality
- Creates project profile for LLM context

### 2. LLM Integration (`tool_maker.llm`)
- Abstracts LLM providers (OpenAI, Anthropic, local models)
- Manages prompt construction
- Handles context window and token management
- Supports custom LLM configurations

### 3. Tool Generator (`tool_maker.tool`)
- Generates tools based on project capabilities
- Creates tool schemas and documentation
- Handles tool registration and discovery
- Manages tool execution

### 4. Flask Integration (`tool_maker.flask`)
- Flask extension for easy integration
- Provides API endpoints for tool operations
- Supports both standalone and integrated usage

## Installation

### As a standalone package
```bash
uv tool install tool-maker
```

### In a Flask project
```bash
uv add tool-maker
```

## Usage Examples

### Standalone Usage
```python
from tool_maker import ToolMaker

# Initialize
tm = ToolMaker(llm_provider="openai", api_key="...")

# Analyze project
project_info = tm.analyze_project("/path/to/project")

# Generate and execute tools
result = tm.create_and_execute_tool("create a function to parse CSV files")
```

### Flask Integration
```python
from flask import Flask
from tool_maker.flask import ToolMakerExtension

app = Flask(__name__)
tm = ToolMakerExtension(app, llm_provider="openai", api_key="...")

@app.route('/tools', methods=['POST'])
def create_tool():
    return tm.create_tool(request.json['query'])
```

## Dependencies

### Core Dependencies
- `requests` or `httpx` for LLM API calls
- `pathlib` for project analysis
- `importlib` for module discovery

### Optional Dependencies
- `openai` for OpenAI integration
- `anthropic` for Claude integration
- `flask` for Flask integration

## Development Setup with uv

```bash
# Initialize uv project
uv init
uv add requests httpx

# Add development dependencies
uv add --dev pytest black ruff
```

## Next Steps

1. Set up the uv project structure
2. Implement the project analyzer
3. Add LLM integration layer
4. Create tool generation logic
5. Implement Flask extension
6. Add tests and examples
