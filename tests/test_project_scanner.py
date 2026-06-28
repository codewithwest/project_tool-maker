import tempfile
from pathlib import Path
from tool_maker.analyzer.project_scanner import ProjectScanner


def _create_project(files):
    tmp = Path(tempfile.mkdtemp())
    for rel, content in files.items():
        path = tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return tmp


def test_scan_empty_project():
    tmp = _create_project({})
    scanner = ProjectScanner(str(tmp))
    info = scanner.scan()
    assert info["modules_count"] == 0
    assert info["total_functions"] == 0
    assert info["total_classes"] == 0


def test_scan_single_module():
    tmp = _create_project({
        "hello.py": """
def greet(name):
    return f"Hi {name}"

class Greeter:
    pass
""",
    })
    scanner = ProjectScanner(str(tmp))
    info = scanner.scan()
    assert info["modules_count"] == 1
    assert info["total_functions"] == 1
    assert info["total_classes"] == 1


def test_scan_detects_functions_and_classes():
    tmp = _create_project({
        "mymod.py": """
def foo():
    pass

def bar(x):
    return x

class MyClass:
    def method(self):
        pass
""",
    })
    scanner = ProjectScanner(str(tmp))
    info = scanner.scan()
    module = info["modules"][0]
    assert len(module["functions"]) == 2
    assert len(module["classes"]) == 1


def test_scan_detects_imports():
    tmp = _create_project({
        "app.py": """
import os
import json
from pathlib import Path
from typing import List, Optional
""",
    })
    scanner = ProjectScanner(str(tmp))
    info = scanner.scan()
    imports = info["modules"][0]["imports"]
    assert "os" in imports
    assert "json" in imports
    assert "pathlib.Path" in imports
    assert "typing.List" in imports
    assert "typing.Optional" in imports


def test_scan_skips_virtualenv():
    tmp = _create_project({
        ".venv/lib/python3.10/site-packages/pkg/mod.py": "x = 1",
        "src/main.py": "y = 2",
    })
    scanner = ProjectScanner(str(tmp))
    info = scanner.scan()
    for mod in info["modules"]:
        assert ".venv" not in mod["path"]


def test_scan_requirements():
    tmp = _create_project({
        "requirements.txt": "flask>=2.0\nrequests>=2.0\n",
    })
    scanner = ProjectScanner(str(tmp))
    info = scanner.scan()
    assert "flask>=2.0" in info["dependencies"]
    assert "requests>=2.0" in info["dependencies"]


def test_scan_entry_points():
    tmp = _create_project({
        "app.py": "",
        "main.py": "",
        "setup.py": "",
    })
    scanner = ProjectScanner(str(tmp))
    info = scanner.scan()
    assert "main.py" in info["entry_points"]
    assert "app.py" in info["entry_points"]


def test_get_module_by_name():
    tmp = _create_project({
        "utils/__init__.py": "",
        "utils/helper.py": "def help(): pass",
    })
    scanner = ProjectScanner(str(tmp))
    scanner.scan()
    mod = scanner.get_module_by_name("utils.helper")
    assert mod is not None
    assert mod["name"] == "utils.helper"


def test_save_analysis():
    tmp = _create_project({"mod.py": "x = 1"})
    scanner = ProjectScanner(str(tmp))
    scanner.scan()
    out = tmp / "analysis.json"
    scanner.save_analysis(str(out))
    assert out.exists()
    import json
    data = json.loads(out.read_text())
    assert data["name"] == tmp.name
