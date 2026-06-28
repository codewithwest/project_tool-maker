"""
Flask routes for the Tool Maker UI.
"""

import ast
import glob
import json
import os
import time
from typing import Any, Dict, Optional

from flask import Blueprint, Flask, Response, flash, jsonify, render_template, request

from tool_maker import ToolMaker
from tool_maker.tool.executor import ToolExecutor

from .log_handler import get_log_handler

bp = Blueprint("ui", __name__, url_prefix="")
_tool_maker: Optional[ToolMaker] = None


def _get_tm() -> ToolMaker:
    global _tool_maker
    if _tool_maker is None:
        _tool_maker = ToolMaker()
    return _tool_maker


# ── pages ────────────────────────────────────────────────────────────────


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/analyze", methods=["GET", "POST"])
def analyze():
    result = None
    path = ""
    if request.method == "POST":
        path = request.form.get("path", ".")
        result = _get_tm().analyze_project(path)
    return render_template("analyze.html", result=result, path=path)


@bp.route("/generate", methods=["GET", "POST"])
def generate():
    tool = None
    query = ""
    if request.method == "POST":
        query = request.form.get("query", "")
        path = request.form.get("path", ".")
        tool = _get_tm().create_tool(query, path)
    return render_template("generate.html", tool=tool, query=query)

_SAMPLE_VALUES: Dict[str, Any] = {
    "int": 0,
    "float": 0.0,
    "str": "sample",
    "bool": True,
    "list": [],
    "dict": {},
    "Any": None,
}


def _generate_sample_args(code: str, func_name: str) -> str:
    """Parse the function signature and return sample args as JSON."""
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                args = {}
                for arg in node.args.args:
                    if arg.arg in ("self", "cls"):
                        continue
                    type_hint = None
                    if arg.annotation:
                        type_hint = _resolve_type_name(arg.annotation)
                    args[arg.arg] = _sample_for_type(type_hint)
                return json.dumps(args, indent=2)
    except SyntaxError:
        pass
    return "{}"


def _resolve_type_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _resolve_type_name(node.value)
    if isinstance(node, ast.Constant):
        return str(node.value)
    return "Any"


def _sample_for_type(type_name: Optional[str]) -> Any:
    if type_name is None:
        return ""
    return _SAMPLE_VALUES.get(type_name, "")


@bp.route("/execute", methods=["GET"])
def execute():
    code = ""
    func_name = ""
    args_json = "{}"
    tools = []
    file_tools = []

    tm = _get_tm()
    output_dir = tm.config.output_dir

    # Load tools from DB
    try:
        from tool_maker.db.models import list_tools
        tools = list_tools()
    except Exception:
        pass

    # Load tools from output directory
    output_path = os.path.abspath(output_dir)
    if os.path.isdir(output_path):
        for fpath in sorted(glob.glob(os.path.join(output_path, "*.py"))):
            fname = os.path.basename(fpath)
            fsize = os.path.getsize(fpath)
            file_tools.append({
                "name": fname[:-3],
                "path": fpath,
                "size": fsize,
            })

    return render_template(
        "execute.html",
        code=code,
        func_name=func_name,
        args_json=args_json,
        tools=tools,
        file_tools=file_tools,
        output_dir=output_path,
    )


@bp.route("/provider", methods=["GET", "POST"])
def provider():
    response_text = None
    prompt = ""
    if request.method == "POST":
        prompt = request.form.get("prompt", "")
        tm = _get_tm()
        if tm.llm_provider:
            try:
                response_text = tm.llm_provider.generate(prompt)
            except Exception as e:
                response_text = f"Error: {e}"
        else:
            response_text = "No LLM provider configured"
    return render_template("provider.html", response=response_text, prompt=prompt)


@bp.route("/config", methods=["GET", "POST"])
def config_page():
    """View and update persistent configuration."""
    tm = _get_tm()
    models = []
    if tm.llm_provider and hasattr(tm.llm_provider, "list_models"):
        try:
            models = tm.llm_provider.list_models()
        except Exception:
            pass

    if request.method == "POST":
        if "output_dir" in request.form:
            tm.set_output_dir(request.form["output_dir"])
        if "extra_whitelist" in request.form:
            raw = request.form["extra_whitelist"]
            mods = [m.strip() for m in raw.split(",") if m.strip()]
            if mods:
                tm.add_whitelist(*mods)
        if "llm_base_url" in request.form:
            tm.config.ollama_base_url = request.form["llm_base_url"]
        if "model" in request.form:
            tm.config.model = request.form["model"]
        if "db_dsn" in request.form:
            os.environ["TOOLMAKER_DB_DSN"] = request.form["db_dsn"]
        _save_config_to_db(
            output_dir=tm.file_config.output_dir,
            extra_whitelist=", ".join(tm.file_config.extra_whitelist),
            llm_base_url=tm.config.ollama_base_url,
            model=tm.config.model,
            db_dsn=os.environ.get("TOOLMAKER_DB_DSN", ""),
        )
        flash("Settings saved", "success")

    return render_template(
        "config.html",
        active="config",
        config=tm.file_config,
        output_dir=tm.file_config.output_dir,
        extra_whitelist=", ".join(tm.file_config.extra_whitelist),
        llm_base_url=tm.config.ollama_base_url,
        model=tm.config.model,
        db_dsn=_get_db_dsn(),
        models=[{"name": m["name"], "size": m.get("size", 0)} for m in models],
    )


@bp.route("/pipeline", methods=["GET"])
def pipeline_page():
    """Render the pipeline page (runs via AJAX, not form POST)."""
    return render_template("pipeline.html", result=None, goal="")


# ── API endpoints ────────────────────────────────────────────────────────


@bp.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json() or {}
    path = data.get("path", ".")
    result = _get_tm().analyze_project(path)
    return jsonify(result)


@bp.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json() or {}
    query = data.get("query", "")
    path = data.get("path", ".")
    tool = _get_tm().create_tool(query, path)
    if tool:
        return jsonify({
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
            "code": tool.code,
            "dependencies": tool.dependencies,
        })
    return jsonify({"error": "Tool generation failed"}), 500


@bp.route("/api/provider/generate", methods=["POST"])
def api_provider_generate():
    data = request.get_json() or {}
    prompt = data.get("prompt", "")
    tm = _get_tm()
    if not tm.llm_provider:
        return jsonify({"error": "No LLM provider configured"}), 500
    try:
        response_text = tm.llm_provider.generate(prompt)
        return jsonify({"response": response_text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/pipeline/run", methods=["POST"])
def api_pipeline_run():
    """Run the full pipeline and return the result (streams logs via SSE)."""
    data = request.get_json() or {}
    goal = data.get("goal", "")
    path = data.get("path", ".")
    if not goal:
        return jsonify({"success": False, "error": "goal is required"}), 400

    try:
        from tool_maker.db.pipeline import DBPipeline
        tm = _get_tm()
        if not tm.llm_provider:
            return jsonify(
                {"success": False,
                 "error": "No LLM provider configured"},
            ), 500
        pipeline = DBPipeline(
            llm_provider=tm.llm_provider,
            output_dir=tm.config.output_dir or "./generated_tools",
        )
        result = pipeline.run(goal, project_path=path)
        return jsonify(result)
    except ImportError:
        return jsonify({"success": False, "error": "postgres deps not installed"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/api/execute", methods=["POST"])
def api_execute():
    """Execute a tool and return JSON result."""
    data = request.get_json() or {}
    code = data.get("code", "")
    func_name = data.get("func_name", "tool_fn")
    args_raw = data.get("args_json", "{}")
    try:
        args = json.loads(args_raw) if args_raw else {}
    except json.JSONDecodeError:
        args = {}
    executor = ToolExecutor()
    result = executor.execute_tool(code, func_name, **args)
    return jsonify({
        "success": result.success,
        "output": _serialize(result.output) if result.success else None,
        "error": result.error,
        "code": code,
        "func_name": func_name,
        "args_json": args_raw or "{}",
    })


def _serialize(val: Any) -> str:
    """Convert a return value to a display string."""
    try:
        return json.dumps(val, indent=2, default=str)
    except Exception:
        return str(val)


@bp.route("/api/load", methods=["POST"])
def api_load():
    """Load tool code and return JSON (no page reload)."""
    data = request.get_json() or {}
    tool_id = data.get("tool_id", "")
    tool_file = data.get("tool_file", "")
    code = ""
    func_name = "tool_fn"
    if tool_id:
        try:
            from tool_maker.db.models import get_tool
            t = get_tool(int(tool_id))
            if t:
                code = t["code"]
                func_name = t.get("name", "tool_fn")
        except Exception:
            pass
    elif tool_file:
        try:
            with open(tool_file) as f:
                code = f.read()
            func_name = os.path.basename(tool_file)[:-3]
        except Exception:
            pass
    if not code:
        return jsonify({"error": "Tool not found"}), 404
    args_json = _generate_sample_args(code, func_name)
    return jsonify({"code": code, "func_name": func_name, "args_json": args_json})


@bp.route("/api/delete", methods=["POST"])
def api_delete():
    """Delete a tool file."""
    data = request.get_json() or {}
    tool_file = data.get("tool_file", "")
    if not tool_file:
        return jsonify({"success": False, "error": "No file specified"}), 400
    try:
        os.remove(tool_file)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/api/fix", methods=["POST"])
def api_fix():
    """Fix a tool via LLM and return the fixed code."""
    data = request.get_json() or {}
    code = data.get("code", "")
    func_name = data.get("func_name", "tool_fn")
    if not code:
        return jsonify({"fixed": False, "error": "No code provided"}), 400
    tm = _get_tm()
    try:
        from tool_maker.tool_fixer import ToolFixer
        fixer = ToolFixer(
            llm_provider=tm.llm_provider,
            executor=tm.tool_executor,
        )
        fix_result = fixer.fix_tool_code(code, func_name)
        return jsonify(fix_result)
    except Exception as e:
        return jsonify({"fixed": False, "error": str(e)}), 500


@bp.route("/api/explain", methods=["POST"])
def api_explain():
    """Explain a tool and its execution result via LLM."""
    data = request.get_json() or {}
    code = data.get("code", "")
    last_result = data.get("last_result", "No execution result")
    if not code:
        return jsonify({"explanation": "No code provided"})
    tm = _get_tm()
    try:
        prompt = (
            f"Explain what this tool does and what happened when it ran.\n\n"
            f"Tool code:\n```python\n{code[:2000]}\n```\n"
            f"\nExecution result:\n{last_result}\n"
            f"\nProvide a clear, concise explanation suitable for a developer. "
            f"Cover: what the code does, why the result occurred, "
            f"and any suggestions if it failed."
        )
        if tm.llm_provider:
            explanation = tm.llm_provider.generate(prompt)
        else:
            explanation = "No LLM provider configured"
        return jsonify({"explanation": explanation})
    except Exception as e:
        return jsonify({"explanation": f"Explanation failed: {e}"})


@bp.route("/api/config", methods=["GET", "POST"])
def api_config():
    tm = _get_tm()
    provider = tm.llm_provider

    if request.method == "POST":
        data = request.get_json() or {}
        if "output_dir" in data:
            tm.set_output_dir(data["output_dir"])
        if "extra_whitelist" in data:
            mods = [m.strip() for m in data["extra_whitelist"].split(",") if m.strip()]
            if mods:
                tm.add_whitelist(*mods)
        if "ollama_base_url" in data:
            tm.config.ollama_base_url = data["ollama_base_url"]
        if "model" in data:
            tm.config.model = data["model"]
        if "db_dsn" in data:
            os.environ["TOOLMAKER_DB_DSN"] = data["db_dsn"]
        return jsonify({"success": True})

    models = []
    if provider and hasattr(provider, "list_models"):
        try:
            models = provider.list_models()
        except Exception:
            pass
    return jsonify({
        "llm_provider": tm.config.llm_provider,
        "model": tm.config.model,
        "ollama_base_url": tm.config.ollama_base_url,
        "output_dir": tm.config.output_dir,
        "extra_whitelist": tm.file_config.extra_whitelist,
        "db_dsn": os.environ.get("TOOLMAKER_DB_DSN", ""),
        "models": [
            {"name": m["name"], "size": m.get("size", 0)}
            for m in models
        ],
    })


# ── DB / Migration API ─────────────────────────────────────────────────────


@bp.route("/api/db/migrations", methods=["GET"])
def api_db_migrations():
    try:
        from tool_maker.db.connection import init_schema
        from tool_maker.db.migrator import status
        init_schema()
        entries = status()
        return jsonify({
            "migrations": entries,
            "pending": sum(1 for e in entries if not e["applied"]),
        })
    except ImportError:
        return jsonify(
            {"error": "postgres deps not installed", "migrations": [], "pending": 0},
        )


@bp.route("/api/db/migrate", methods=["POST"])
def api_db_migrate():
    try:
        from tool_maker.db.connection import init_schema
        from tool_maker.db.migrator import migrate
        init_schema()
        applied = migrate()
        return jsonify({"applied": applied})
    except ImportError:
        return jsonify({"error": "postgres deps not installed"}), 500


# ── SSE log stream ───────────────────────────────────────────────────────


@bp.route("/api/logs/stream")
def stream_logs():
    handler = get_log_handler()

    def generate():
        index = handler.count
        while True:
            records = handler.get_since(index)
            for rec in records:
                yield f"data: {json.dumps(rec)}\n\n"
                index += 1
            if not records:
                yield ": heartbeat\n\n"
            time.sleep(0.5)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def register_routes(app: Flask, tool_maker_instance=None):
    global _tool_maker
    _tool_maker = tool_maker_instance
    app.register_blueprint(bp)


def _get_db_dsn() -> str:
    """Return DSN from env or DB config, falling back to default."""
    env_dsn = os.environ.get("TOOLMAKER_DB_DSN")
    if env_dsn:
        return env_dsn
    try:
        from tool_maker.db.models import get_config
        db_dsn = get_config("db_dsn")
        if db_dsn:
            return db_dsn
    except Exception:
        pass
    return "postgresql://localhost:5432/toolmaker"


def _save_config_to_db(
    output_dir: str = "",
    extra_whitelist: str = "",
    llm_base_url: str = "",
    model: str = "",
    db_dsn: str = "",
) -> None:
    """Persist config to the database config table when available."""
    try:
        from tool_maker.db.models import set_config
        set_config("output_dir", output_dir)
        set_config("extra_whitelist", extra_whitelist)
        set_config("llm_base_url", llm_base_url)
        set_config("model", model)
        set_config("db_dsn", db_dsn)
    except ImportError:
        pass
    except Exception:
        pass
