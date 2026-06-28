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
    ui_parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
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
    elif args.config_cmd == 'set':
        if args.key == 'output_dir':
            cfg.output_dir = args.value
            cfg.save()
            print(f"output_dir set to: {args.value}")
    elif args.config_cmd == 'whitelist':
        added = cfg.add_whitelist(*args.modules)
        if added:
            print(f"Added to whitelist: {args.modules}")
        else:
            print("All modules already in whitelist")
        print(f"  extra_whitelist: {cfg.extra_whitelist}")


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
    pipeline = DBPipeline(llm_provider=tm.llm_provider, output_dir=output_dir)
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
