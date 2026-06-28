"""
Project Scanner - Scans and analyzes project structure.
"""

import ast
from pathlib import Path
from typing import Dict, List, Any, Optional
import json


class ProjectScanner:
    """Scans and analyzes project structure to understand capabilities."""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.modules: List[Dict[str, Any]] = []
        self.dependencies: List[str] = []
        self.entry_points: List[str] = []
        self.project_info: Dict[str, Any] = {}

    def scan(self) -> Dict[str, Any]:
        """Scan the project and return analysis results."""
        self._scan_modules()
        self._scan_dependencies()
        self._scan_entry_points()
        self._analyze_project()

        return self.project_info

    def _scan_modules(self) -> None:
        """Scan Python modules in the project."""
        for py_file in self.project_path.rglob("*.py"):
            if self._should_skip_file(py_file):
                continue

            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                module_info = {
                    "path": str(py_file.relative_to(self.project_path)),
                    "name": self._get_module_name(py_file),
                    "functions": [],
                    "classes": [],
                    "imports": []
                }

                try:
                    tree = ast.parse(content)
                    module_info = self._parse_ast(tree, module_info)
                except SyntaxError:
                    pass

                self.modules.append(module_info)
            except Exception:
                # Skip files that can't be read or parsed
                continue

    def _parse_ast(self, tree: ast.AST, module_info: Dict[str, Any]) -> Dict[str, Any]:
        """Parse AST to extract functions, classes, and imports."""
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                module_info["functions"].append({
                    "name": node.name,
                    "line": node.lineno,
                    "docstring": ast.get_docstring(node)
                })
            elif isinstance(node, ast.ClassDef):
                module_info["classes"].append({
                    "name": node.name,
                    "line": node.lineno,
                    "docstring": ast.get_docstring(node)
                })
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    module_info["imports"].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        module_info["imports"].append(f"{node.module}.{alias.name}")

        return module_info

    def _should_skip_file(self, file_path: Path) -> bool:
        """Determine if a file should be skipped during scanning."""
        skip_patterns = [
            "__pycache__",
            ".venv",
            "venv",
            ".git",
            ".env",
            "node_modules",
            ".mypy_cache",
            ".pytest_cache",
            "dist",
            "build"
        ]

        return any(pattern in str(file_path) for pattern in skip_patterns)

    def _get_module_name(self, file_path: Path) -> str:
        """Get the module name from a file path."""
        parts = []
        for part in file_path.relative_to(self.project_path).parts:
            if part == "__init__.py":
                continue
            parts.append(part.replace(".py", ""))

        return ".".join(parts)

    def _scan_dependencies(self) -> None:
        """Scan for project dependencies."""
        # Check for pyproject.toml
        pyproject_path = self.project_path / "pyproject.toml"
        if pyproject_path.exists():
            try:
                import tomli
                with open(pyproject_path, 'rb') as f:
                    data = tomli.load(f)

                if "project" in data and "dependencies" in data["project"]:
                    self.dependencies = data["project"]["dependencies"]
            except ImportError:
                # Try basic parsing if tomli is not available
                pass

        # Check for requirements.txt
        requirements_path = self.project_path / "requirements.txt"
        if requirements_path.exists():
            with open(requirements_path, 'r') as f:
                self.dependencies = [
                    line.strip() for line in f
                    if line.strip() and not line.startswith("#")
                ]

    def _scan_entry_points(self) -> None:
        """Scan for entry points (main files, Flask apps, etc.)."""
        # Look for common entry point patterns
        entry_point_patterns = [
            "main.py",
            "app.py",
            "wsgi.py",
            "run.py",
            "server.py"
        ]

        for pattern in entry_point_patterns:
            entry_path = self.project_path / pattern
            if entry_path.exists():
                self.entry_points.append(str(entry_path.relative_to(self.project_path)))

    def _analyze_project(self) -> None:
        """Analyze the project and create a summary."""
        self.project_info = {
            "path": str(self.project_path),
            "name": self.project_path.name,
            "modules_count": len(self.modules),
            "total_functions": sum(len(m["functions"]) for m in self.modules),
            "total_classes": sum(len(m["classes"]) for m in self.modules),
            "dependencies": self.dependencies,
            "entry_points": self.entry_points,
            "modules": self.modules,
            "summary": self._generate_summary()
        }

    def _generate_summary(self) -> str:
        """Generate a summary of the project."""
        if not self.modules:
            return "No Python modules found."

        summary_parts = [
            f"Project '{self.project_path.name}' contains {len(self.modules)} modules",
            f"with {sum(len(m['functions']) for m in self.modules)} functions and "
            f"{sum(len(m['classes']) for m in self.modules)} classes."
        ]

        if self.dependencies:
            summary_parts.append(f"Has {len(self.dependencies)} dependencies.")

        if self.entry_points:
            summary_parts.append(f"Entry points: {', '.join(self.entry_points)}.")

        return " ".join(summary_parts)

    def get_module_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a module by its name."""
        for module in self.modules:
            if module["name"] == name:
                return module
        return None

    def get_functions_by_module(self, module_name: str) -> List[Dict[str, Any]]:
        """Get all functions in a specific module."""
        module = self.get_module_by_name(module_name)
        if module:
            return module["functions"]
        return []

    def save_analysis(self, output_path: str) -> None:
        """Save the analysis to a JSON file."""
        with open(output_path, 'w') as f:
            json.dump(self.project_info, f, indent=2)
