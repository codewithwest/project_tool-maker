"""
ToolMakerConfig - persistent configuration (output dir, extra whitelist, etc.)
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

CONFIG_DIR_NAME = "tool-maker"
CONFIG_FILE_NAME = "config.json"


def _get_config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / CONFIG_DIR_NAME
    return Path.home() / ".config" / CONFIG_DIR_NAME


def _get_config_path() -> Path:
    return _get_config_dir() / CONFIG_FILE_NAME


@dataclass
class ToolMakerConfigFile:
    output_dir: str = "./generated_tools"
    extra_whitelist: List[str] = field(default_factory=list)
    approved_deps: List[str] = field(default_factory=list)
    auto_approve_deps: bool = False

    @classmethod
    def load(cls) -> "ToolMakerConfigFile":
        path = _get_config_path()
        if not path.exists():
            logger.debug("No config at %s, using defaults", path)
            return cls()
        try:
            data = json.loads(path.read_text())
            return cls(**data)
        except Exception as e:
            logger.warning("Failed to load config: %s", e)
            return cls()

    def save(self) -> None:
        path = _get_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "output_dir": self.output_dir,
            "extra_whitelist": self.extra_whitelist,
            "approved_deps": self.approved_deps,
            "auto_approve_deps": self.auto_approve_deps,
        }
        try:
            path.write_text(json.dumps(data, indent=2))
            logger.debug("Config saved to %s", path)
        except Exception as e:
            logger.warning("Failed to save config: %s", e)

    def add_whitelist(self, *modules: str) -> bool:
        added = False
        for m in modules:
            if m not in self.extra_whitelist:
                self.extra_whitelist.append(m)
                added = True
        return added

    def approve_dep(self, module_name: str) -> bool:
        if module_name not in self.approved_deps:
            self.approved_deps.append(module_name)
            self.save()
            return True
        return False
