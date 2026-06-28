"""Tests for ToolMakerConfigFile and ToolFixer."""

from tool_maker.config import ToolMakerConfigFile
from tool_maker.tool_fixer import ToolFixer


class TestToolMakerConfigFile:
    def test_defaults(self):
        cfg = ToolMakerConfigFile()
        assert cfg.output_dir == "./generated_tools"
        assert cfg.extra_whitelist == []

    def test_add_whitelist(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "tool_maker.config._get_config_path",
            lambda: tmp_path / "config.json",
        )
        cfg = ToolMakerConfigFile.load()
        assert cfg.add_whitelist("sqlite3") is True
        assert cfg.add_whitelist("sqlite3") is False
        assert "sqlite3" in cfg.extra_whitelist

    def test_save_is_noop(self, tmp_path, monkeypatch):
        """save() is a no-op — config is stored in DB, not file."""
        config_path = tmp_path / "config.json"
        monkeypatch.setattr(
            "tool_maker.config._get_config_path",
            lambda: config_path,
        )
        cfg = ToolMakerConfigFile(output_dir="/tmp/tools", extra_whitelist=["foo"])
        cfg.save()
        # File should NOT exist — save() does nothing
        assert not config_path.exists()
        # load() always returns defaults regardless of filesystem state
        loaded = ToolMakerConfigFile.load()
        assert loaded.output_dir == "./generated_tools"
        assert loaded.extra_whitelist == []


class TestToolFixer:
    def test_fix_tool_file_not_found(self):
        fixer = ToolFixer()
        result = fixer.fix_tool_file("/nonexistent/file.py")
        assert result["fixed"] is False
        assert "not found" in result["error"]

    def test_fix_tool_code_success(self, tmp_path):
        fixer = ToolFixer()
        code = """
def add(a, b):
    return a + b
"""
        result = fixer.fix_tool_code(code, "add", a=1, b=2)
        assert result["fixed"] is True
        assert result["attempts"] == 1

    def test_fix_tool_code_with_error_no_llm(self):
        fixer = ToolFixer()
        code = """
def fail(x):
    return 1 / 0
"""
        result = fixer.fix_tool_code(code, "fail", x=5)
        assert result["fixed"] is False
        assert "division by zero" in result["error"]
