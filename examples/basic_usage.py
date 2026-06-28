"""
Basic Usage Example - Standalone usage of Tool Maker.
"""

from tool_maker import ProjectScanner, ToolGenerator, ToolExecutor


def main():
    """Run basic usage example."""
    print("Tool Maker - Basic Usage Example")
    print("=" * 50)

    # Example 1: Project Analysis
    print("\n1. Project Analysis")
    print("-" * 30)

    scanner = ProjectScanner(".")
    project_info = scanner.scan()

    print(f"Project: {project_info.get('name', 'Unknown')}")
    print(f"Modules: {project_info.get('modules_count', 0)}")
    print(f"Functions: {project_info.get('total_functions', 0)}")
    print(f"Classes: {project_info.get('total_classes', 0)}")

    # Example 2: Tool Generation (without LLM)
    print("\n2. Tool Generation")
    print("-" * 30)

    generator = ToolGenerator(scanner)

    # Generate a file operation tool
    request = "Create a function to read JSON files"
    tool = generator.generate_tool(request, project_info)

    if tool:
        print(f"Generated tool: {tool.name}")
        print(f"Description: {tool.description}")
        print(f"Code preview:\n{tool.code[:200]}...")

    # Example 3: Tool Execution
    print("\n3. Tool Execution")
    print("-" * 30)

    executor = ToolExecutor()

    if tool:
        result = executor.execute_tool(tool.code, tool.name)
        print(f"Execution result: {result.success}")
        if result.success:
            print(f"Output: {result.output}")

    # Example 4: Full Tool Maker Integration
    print("\n4. Full Integration (with LLM)")
    print("-" * 30)

    # Note: This requires an API key
    # api_key = os.environ.get("OPENAI_API_KEY")
    # if api_key:
    #     llm_provider = get_provider("openai", api_key=api_key)
    #     tm = ToolMaker(llm_provider=llm_provider)
    #     result = tm.create_and_execute_tool("Create a CSV parser")
    #     print(f"Result: {result}")
    # else:
    #     print("OpenAI API key not set. Skipping LLM example.")

    print("\nExample completed!")


if __name__ == "__main__":
    main()
