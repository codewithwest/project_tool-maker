"""
Command-line interface for Tool Maker.
"""

import argparse
import sys


def main():
    """Main entry point for the CLI."""
    _auto_migrate()

    parser = argparse.ArgumentParser(
        description="Tool Maker - An intelligent tool-making package"
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze a project')
    analyze_parser.add_argument('project_path', help='Path to the project to analyze')
    analyze_parser.add_argument('--output', '-o', help='Output file for analysis')

    # Generate command
    generate_parser = subparsers.add_parser('generate', help='Generate a tool')
    generate_parser.add_argument('query', help='Description of the tool to generate')
    generate_parser.add_argument('--project', '-p', default='.', help='Project path')
    generate_parser.add_argument(
        '--output', '-o', help='Output directory for generated tool'
    )

    # Run command
    run_parser = subparsers.add_parser('run', help='Run a generated tool')
    run_parser.add_argument('tool_file', help='Path to the tool file to run')

    # UI command
    ui_parser = subparsers.add_parser('ui', help='Launch the web UI')
    ui_parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    ui_parser.add_argument('--port', '-p', type=int, default=5000,
                           help='Port to bind to')
    ui_parser.add_argument('--debug', '-d', action='store_true',
                           help='Run in debug mode')

    # Version command
    subparsers.add_parser('version', help='Show version information')

    # Config command
    config_parser = subparsers.add_parser('config', help='Manage configuration')
    config_sub = config_parser.add_subparsers(dest='config_cmd')
    config_sub.add_parser('show', help='Show current config')
    config_set = config_sub.add_parser('set', help='Set a config value')
    config_set.add_argument('key', choices=['output_dir'],
                            help='Config key')
    config_set.add_argument('value', help='Config value')
    config_whitelist = config_sub.add_parser('whitelist',
                                             help='Add modules to sandbox whitelist')
    config_whitelist.add_argument('modules', nargs='+',
                                  help='Module names to allow')
    config_approve = config_sub.add_parser('approve-dep',
                                           help='Approve a pip package for auto-install')
    config_approve.add_argument('module', help='Module name to approve')
    config_auto = config_sub.add_parser('auto-approve',
                                        help='Enable/disable silent auto-approve of deps')
    config_auto.add_argument('value', choices=['on', 'off'],
                             help='Enable or disable auto-approve')

    # Dep command
    dep_parser = subparsers.add_parser('dep', help='Manage sandbox dependencies')
    dep_sub = dep_parser.add_subparsers(dest='dep_cmd')
    dep_install = dep_sub.add_parser('install',
                                     help='Install deps for a tool')
    dep_install.add_argument('tool_name', nargs='?', default=None,
                             help='Tool name (omit for all tools)')
    dep_sync = dep_sub.add_parser('sync',
                                  help='Install deps for all tools in DB')
    dep_approve = dep_sub.add_parser('approve',
                                     help='Approve a module for auto-install')
    dep_approve.add_argument('module', help='Module name to approve')
    dep_scan = dep_sub.add_parser('scan',
                                  help='Scan a Python file for third-party imports')
    dep_scan.add_argument('file', help='Path to Python file')

    # Fix command
    fix_parser = subparsers.add_parser('fix', help='Fix a broken tool file using LLM')
    fix_parser.add_argument('tool_file', help='Path to the tool file')
    fix_parser.add_argument('--args', '-a', default='{}',
                            help='JSON args to pass when testing')

    # Migrate command
    migrate_parser = subparsers.add_parser('migrate', help='Database migrations')
    migrate_sub = migrate_parser.add_subparsers(dest='migrate_cmd')
    migrate_sub.add_parser('up', help='Apply pending migrations')
    migrate_rollback = migrate_sub.add_parser('rollback', help='Rollback migrations')
    migrate_rollback.add_argument('target', help='Target migration name')
    migrate_sub.add_parser('status', help='Show migration status')

    # Pipeline command
    pipeline_parser = subparsers.add_parser('pipeline', help='Run full DB pipeline')
    pipeline_parser.add_argument('goal', help='The goal for the pipeline')
    pipeline_parser.add_argument('--project', '-p', default='.',
                                 help='Project path to analyse')
    pipeline_parser.add_argument('--output', '-o', default=None,
                                 help='Output directory for generated tools')

    args = parser.parse_args()

    if args.command == 'analyze':
        handle_analyze(args)
    elif args.command == 'generate':
        handle_generate(args)
    elif args.command == 'run':
        handle_run(args)
    elif args.command == 'ui':
        handle_ui(args)
    elif args.command == 'config':
        handle_config(args)
    elif args.command == 'fix':
        handle_fix(args)
    elif args.command == 'migrate':
        handle_migrate(args)
    elif args.command == 'pipeline':
        handle_pipeline(args)
    elif args.command == 'dep':
        handle_dep(args)
    elif args.command == 'version':
        handle_version()
    else:
        parser.print_help()


def handle_analyze(args):
    """Handle the analyze command."""
    from tool_maker.analyzer.project_scanner import ProjectScanner

    scanner = ProjectScanner(args.project_path)
    result = scanner.scan()

    if args.output:
        scanner.save_analysis(args.output)
        print(f"Analysis saved to {args.output}")
    else:
        import json
        print(json.dumps(result, indent=2))


def handle_generate(args):
    """Handle the generate command."""
    from tool_maker.analyzer.project_scanner import ProjectScanner
    from tool_maker.tool.generator import ToolGenerator

    # Analyze project
    scanner = ProjectScanner(args.project)
    project_info = scanner.scan()

    # Generate tool
    generator = ToolGenerator(scanner)
    tool = generator.generate_tool(args.query, project_info)

    if not tool:
        print("Failed to generate tool")
        sys.exit(1)

    # Save tool
    output_dir = args.output or './generated_tools'
    generator.save_tool(tool, output_dir)
    print(f"Tool '{tool.name}' generated successfully")


def handle_run(args):
    """Handle the run command."""
    from tool_maker import ToolMaker

    tm = ToolMaker()
    result = tm.tool_executor.execute_tool_from_file(args.tool_file)
    if result.success:
        print("Tool executed successfully")
        print(f"Result: {result.output}")
    else:
        print(f"Tool execution failed: {result.error}")
        sys.exit(1)


def handle_ui(args):
    """Handle the ui command - launch web UI."""
    try:
        from tool_maker.ui import create_ui_app
    except ImportError as e:
        print("UI dependencies not installed. Run: uv pip install 'tool-maker[flask]'")
        print(f"Error: {e}")
        sys.exit(1)
    app = create_ui_app()
    print(f"  Tool Maker UI running at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


def handle_version():
    """Handle the version command."""
    from tool_maker import __version__
    print(f"Tool Maker version {__version__}")


def handle_config(args):
    """Handle config commands."""
    from tool_maker.config import ToolMakerConfigFile, _get_config_path

    cfg = ToolMakerConfigFile.load()

    if args.config_cmd == 'show' or not args.config_cmd:
        print(f"Config file: {_get_config_path()}")
        print(f"  output_dir: {cfg.output_dir}")
        print(f"  extra_whitelist: {cfg.extra_whitelist}")
        print(f"  approved_deps: {cfg.approved_deps}")
        print(f"  auto_approve_deps: {cfg.auto_approve_deps}")
    elif args.config_cmd == 'set':
        if args.key == 'output_dir':
            cfg.output_dir = args.value
            cfg.save()
            print(f"output_dir set to: {args.value}")
    elif args.config_cmd == 'whitelist':
        added = cfg.add_whitelist(*args.modules)
        if added:
            cfg.save()
            print(f"Added to whitelist: {args.modules}")
        else:
            print("All modules already in whitelist")
        print(f"  extra_whitelist: {cfg.extra_whitelist}")
    elif args.config_cmd == 'approve-dep':
        if cfg.approve_dep(args.module):
            print(f"Approved dep: {args.module}")
        else:
            print(f"'{args.module}' already approved")
    elif args.config_cmd == 'auto-approve':
        cfg.auto_approve_deps = args.value == 'on'
        cfg.save()
        print(f"auto_approve_deps set to: {cfg.auto_approve_deps}")


def handle_fix(args):
    """Handle the fix command."""
    from tool_maker import ToolMaker
    import json

    tm = ToolMaker(output_dir=None)
    kwargs = json.loads(args.args) if args.args else {}
    result = tm.fix_tool(args.tool_file, **kwargs)

    if result["fixed"]:
        print(f"Tool fixed after {result['attempts']} attempt(s)")
    else:
        print(f"Failed to fix after {result['attempts']} attempt(s)")
        print(f"Last error: {result['error']}")
        sys.exit(1)


def handle_migrate(args):
    """Handle database migration commands."""
    try:
        from tool_maker.db.migrator import migrate, rollback, status
        from tool_maker.db.connection import init_schema
    except ImportError:
        print("DB deps not installed. Run: uv pip install 'tool-maker[postgres]'")
        sys.exit(1)

    if args.migrate_cmd == 'up' or not args.migrate_cmd:
        init_schema()
        applied = migrate()
        if applied:
            print(f"Applied: {', '.join(applied)}")
        else:
            print("No pending migrations")
    elif args.migrate_cmd == 'rollback':
        rolled = rollback(args.target)
        if rolled:
            print(f"Rolled back: {', '.join(rolled)}")
        else:
            print("Nothing to rollback")
    elif args.migrate_cmd == 'status':
        init_schema()
        for entry in status():
            mark = "✓" if entry["applied"] else " "
            print(f"  [{mark}] {entry['name']}")


def handle_pipeline(args):
    """Handle the pipeline command."""
    try:
        from tool_maker.db.pipeline import DBPipeline
    except ImportError:
        print("DB deps not installed. Run: uv pip install 'tool-maker[postgres]'")
        sys.exit(1)

    from tool_maker import ToolMaker
    tm = ToolMaker()
    if not tm.llm_provider:
        print("No LLM provider configured")
        sys.exit(1)
    output_dir = args.output or tm.config.output_dir or "./generated_tools"
    pipeline = DBPipeline(
        llm_provider=tm.llm_provider,
        output_dir=output_dir,
        extra_whitelist=tm.file_config.extra_whitelist,
        approved_deps=tm.file_config.approved_deps,
        auto_approve_deps=tm.file_config.auto_approve_deps,
    )
    result = pipeline.run(args.goal, project_path=args.project)

    if result.get("success"):
        print("Pipeline completed successfully")
        print(f"  Tool name: {result.get('tool_name', 'N/A')}")
        print(f"  Tool ID:   {result.get('tool_id', 'N/A')}")
        print(f"  Status:    {result.get('final_status', 'N/A')}")
        print(f"  Review:    passed={result.get('review', {}).get('passed', 'N/A')}")
    else:
        print(f"Pipeline failed: {result.get('error', 'unknown error')}")
        sys.exit(1)


def handle_dep(args):
    """Handle dependency commands."""
    from tool_maker.tool.deps import missing_deps, install, scan_imports, is_third_party

    if args.dep_cmd == 'approve':
        from tool_maker.config import ToolMakerConfigFile
        cfg = ToolMakerConfigFile.load()
        if cfg.approve_dep(args.module):
            print(f"Approved '{args.module}' for auto-install")
        else:
            print(f"'{args.module}' already approved")
        return

    if args.dep_cmd == 'scan':
        from pathlib import Path
        path = Path(args.file)
        if not path.exists():
            print(f"File not found: {args.file}")
            sys.exit(1)
        code = path.read_text()
        imports = scan_imports(code)
        third_party = [m for m in imports if is_third_party(m)]
        if third_party:
            print("Third-party imports detected:")
            for m in third_party:
                print(f"  - {m}")
        else:
            print("No third-party imports detected")
        return

    if args.dep_cmd == 'install':
        from tool_maker.config import ToolMakerConfigFile
        cfg = ToolMakerConfigFile.load()
        if args.tool_name:
            _install_tool_deps(args.tool_name, cfg)
        else:
            _install_all_deps(cfg)
        return

    # dep sync
    from tool_maker.config import ToolMakerConfigFile
    cfg = ToolMakerConfigFile.load()
    _install_all_deps(cfg)


def _install_tool_deps(tool_name: str, cfg) -> None:
    """Install dependencies for a single tool."""
    from tool_maker.tool.deps import install_deps_for_code
    try:
        from tool_maker.db.models import get_tool_by_name
    except ImportError:
        print("DB deps not installed")
        sys.exit(1)
    tool = get_tool_by_name(tool_name)
    if not tool:
        print(f"Tool '{tool_name}' not found")
        sys.exit(1)
    code = tool.get("code", "")
    if not code:
        print(f"Tool '{tool_name}' has no code")
        return
    installed = install_deps_for_code(
        code,
        approved=cfg.approved_deps,
        auto_approve=cfg.auto_approve_deps,
    )
    if installed:
        print(f"Installed: {', '.join(installed)}")
    else:
        print("All dependencies already satisfied")


def _install_all_deps(cfg) -> None:
    """Install dependencies for all tools in the DB."""
    from tool_maker.tool.deps import install_deps_for_code
    try:
        from tool_maker.db.models import list_tools
    except ImportError:
        print("DB deps not installed")
        sys.exit(1)
    tools = list_tools()
    if not tools:
        print("No tools in DB")
        return
    all_installed = []
    for tool in tools:
        code = tool.get("code", "")
        if code:
            installed = install_deps_for_code(
                code,
                approved=cfg.approved_deps,
                auto_approve=cfg.auto_approve_deps,
            )
            all_installed.extend(installed)
    if all_installed:
        unique = list(set(all_installed))
        print(f"Installed: {', '.join(unique)}")
    else:
        print("All dependencies already satisfied")


def _auto_migrate() -> None:
    """Run pending DB migrations on CLI startup (silent if no postgres)."""
    try:
        from tool_maker.dotenv import load_dotenv
        load_dotenv()
        from tool_maker.db.connection import init_schema
        from tool_maker.db.migrator import migrate, status
    except ImportError:
        return

    try:
        init_schema()
    except Exception as e:
        print(f"  DB schema init skipped ({e})", file=__import__('sys').stderr)
        return

    try:
        applied = migrate()
        if applied:
            print(f"  DB migrations applied: {', '.join(applied)}")
        else:
            pending = [s for s in status() if not s["applied"]]
            if pending:
                print(f"  {len(pending)} migration(s) pending")
            else:
                print("  DB migrations up to date")
    except Exception as e:
        print(f"  DB migration skipped ({e})", file=__import__('sys').stderr)


if __name__ == '__main__':
    main()
