"""
Flask Integration Example - Using Tool Maker with Flask (Ollama).
"""

from flask import Flask, jsonify, request
from tool_maker.flask import ToolMakerExtension


def create_app():
    """Create and configure the Flask app."""
    app = Flask(__name__)

    tm = ToolMakerExtension(
        app,
        llm_provider="ollama",
        model="gemma4:31b-cloud",
    )

    @app.route('/')
    def index():
        return jsonify({
            "message": "Tool Maker API (Ollama)",
            "endpoints": [
                "/health",
                "/analyze",
                "/tools",
                "/tools/list"
            ]
        })

    @app.route('/analyze', methods=['POST'])
    def analyze_project():
        data = request.get_json()
        if not data or 'project_path' not in data:
            return jsonify({"error": "project_path is required"}), 400

        try:
            result = tm.analyze_project(data['project_path'])
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/tools/create', methods=['POST'])
    def create_tool():
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({"error": "query is required"}), 400

        try:
            project_path = data.get('project_path', '.')
            result = tm.create_and_execute_tool(data['query'], project_path)
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app


def main():
    """Run the Flask app."""
    app = create_app()

    print("Tool Maker Flask App (Ollama)")
    print("=" * 50)
    print("\nAvailable endpoints:")
    print("  GET  /              - API information")
    print("  POST /analyze       - Analyze a project")
    print("  POST /tools/create  - Create a new tool")
    print("\nStarting server on http://localhost:5000...")
    print("Press Ctrl+C to stop\n")

    app.run(debug=True, host='0.0.0.0', port=5000)


if __name__ == "__main__":
    main()
