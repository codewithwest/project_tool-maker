"""
Flask Extension - Provides Flask integration for Tool Maker.
"""

from flask import Flask, request, jsonify
from typing import Dict, Any, Optional

from tool_maker.analyzer.project_scanner import ProjectScanner


class ToolMakerExtension:
    """Flask extension for Tool Maker."""

    def __init__(self, app: Optional[Flask] = None, **kwargs):
        self.app = None
        self.llm_provider = None
        self.project_scanner = None
        self.tool_generator = None
        self.tool_executor = None
        self.config = {}

        if app is not None:
            self.init_app(app, **kwargs)

    def init_app(self, app: Flask, **kwargs) -> None:
        """Initialize the extension with a Flask app."""
        self.app = app

        # Configure from kwargs
        self.config.update(kwargs)

        # Initialize components
        self._init_components()

        # Register blueprint if app is provided
        self._register_routes()

        # Store extension in app
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        if 'tool_maker' in app.extensions:
            raise RuntimeError("Flask application already initialized")
        app.extensions['tool_maker'] = self

    def _init_components(self) -> None:
        """Initialize Tool Maker components."""
        from tool_maker.llm.provider import get_provider
        from tool_maker.tool.generator import ToolGenerator
        from tool_maker.tool.executor import ToolExecutor

        # Initialize LLM provider
        llm_provider = self.config.get('llm_provider', 'ollama')
        api_key = self.config.get('api_key')

        kwargs = {"api_key": api_key, "model": self.config.get(
            'model', 'gemma4:31b-cloud')}
        if llm_provider == "ollama" and self.config.get('ollama_base_url'):
            kwargs["base_url"] = self.config['ollama_base_url']
        self.llm_provider = get_provider(llm_provider, **kwargs)

        # Initialize other components (scanner will be set per-request)
        self.project_scanner = None
        self.tool_generator = ToolGenerator(None)
        self.tool_executor = ToolExecutor()

    def _register_routes(self) -> None:
        """Register Flask routes."""
        if self.app is None:
            return

        from flask import Blueprint

        bp = Blueprint('tool_maker', __name__)

        @bp.route('/health', methods=['GET'])
        def health():
            return jsonify({"status": "healthy"})

        @bp.route('/analyze', methods=['POST'])
        def analyze():
            data = request.get_json()
            if not data or 'project_path' not in data:
                return jsonify({"error": "project_path is required"}), 400

            project_path = data['project_path']
            result = self.analyze_project(project_path)
            return jsonify(result)

        @bp.route('/tools', methods=['POST'])
        def create_tool():
            data = request.get_json()
            if not data or 'query' not in data:
                return jsonify({"error": "query is required"}), 400

            query = data['query']
            project_path = data.get('project_path', '.')

            result = self.create_and_execute_tool(query, project_path)
            return jsonify(result)

        @bp.route('/tools', methods=['GET'])
        def list_tools():
            tools = self.tool_executor.get_execution_history()
            return jsonify({"tools": tools})

        self.app.register_blueprint(bp)

    def analyze_project(self, project_path: str) -> Dict[str, Any]:
        """Analyze a project and return results."""
        scanner = ProjectScanner(project_path)
        return scanner.scan()

    def create_and_execute_tool(
        self, query: str, project_path: str = "."
    ) -> Dict[str, Any]:
        """Create and execute a tool based on a query."""
        # Analyze project first
        scanner = ProjectScanner(project_path)
        project_info = scanner.scan()

        # Generate tool
        tool = self.tool_generator.generate_tool(query, project_info)

        if not tool:
            return {
                "success": False,
                "error": "Could not generate tool"
            }

        # Execute tool
        result = self.tool_executor.execute_tool(
            tool.code,
            tool.name
        )

        return {
            "success": result.success,
            "tool_name": tool.name,
            "tool_description": tool.description,
            "result": result.output,
            "error": result.error
        }

    def get_provider(self):
        """Get the LLM provider instance."""
        return self.llm_provider

    def get_project_scanner(self):
        """Get the project scanner instance."""
        return self.project_scanner

    def get_tool_generator(self):
        """Get the tool generator instance."""
        return self.tool_generator

    def get_tool_executor(self):
        """Get the tool executor instance."""
        return self.tool_executor


def init_app(app: Flask, **kwargs) -> ToolMakerExtension:
    """Factory function to initialize Tool Maker extension."""
    extension = ToolMakerExtension()
    extension.init_app(app, **kwargs)
    return extension
