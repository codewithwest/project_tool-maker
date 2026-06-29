"""
ToolMakerClient — remote HTTP client for consuming Tool Maker as a service.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class ToolMakerClient:
    """HTTP client for a remote Tool Maker server.

    Usage::

        client = ToolMakerClient("http://localhost:5000")
        result = client.execute("print('hello')")
        tools = client.list_tools()
    """

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self._headers = {}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _request(self, method: str, path: str, **kwargs) -> Any:
        kwargs.setdefault("headers", {}).update(self._headers)
        kwargs.setdefault("timeout", 30)
        resp = httpx.request(method, self._url(path), **kwargs)
        resp.raise_for_status()
        return resp.json()

    # ── Tools ────────────────────────────────────────────────────────────

    def list_tools(self, status: str = "") -> List[Dict]:
        params = {"status": status} if status else {}
        return self._request("GET", "/api/tools", params=params)

    def get_tool(self, tool_id: int) -> Optional[Dict]:
        return self._request("GET", f"/api/tools/{tool_id}")

    def delete_tool(self, tool_id: int) -> bool:
        result = self._request("DELETE", f"/api/tools/{tool_id}")
        return result.get("success", False)

    # ── Execution ────────────────────────────────────────────────────────

    def execute(self, code: str, name: str = "unnamed", **kwargs) -> Dict:
        payload = {"code": code, "name": name, **kwargs}
        return self._request("POST", "/api/execute", json=payload)

    def explain(self, code: str, name: str = "") -> Dict:
        return self._request("POST", "/api/explain", json={"code": code, "name": name})

    def refine(self, code: str, instruction: str, name: str = "") -> Dict:
        return self._request(
            "POST",
            "/api/refine",
            json={"code": code, "instruction": instruction, "name": name},
        )

    def fix(self, code: str, name: str = "") -> Dict:
        return self._request("POST", "/api/fix", json={"code": code, "name": name})

    # ── Pipeline ─────────────────────────────────────────────────────────

    def run_pipeline(
        self, goal: str, project_path: str = ".", output_dir: str = ""
    ) -> Dict:
        return self._request(
            "GET",
            "/api/pipeline",
            params={
                "goal": goal,
                "project_path": project_path,
                "output_dir": output_dir,
            },
        )

    # ── Analysis ─────────────────────────────────────────────────────────

    def analyze(self, project_path: str) -> Dict:
        return self._request(
            "GET", "/api/analyze", params={"project_path": project_path}
        )

    # ── Dependencies ─────────────────────────────────────────────────────

    def check_deps(self, code: str) -> Dict:
        return self._request("POST", "/api/deps/check", json={"code": code})

    def approve_dep(self, module: str) -> Dict:
        return self._request("POST", "/api/deps/approve", json={"module": module})

    # ── Config ───────────────────────────────────────────────────────────

    def get_config(self) -> Dict:
        return self._request("GET", "/api/config")

    def set_config(self, key: str, value: str) -> Dict:
        return self._request("POST", "/api/config", json={"key": key, "value": value})

    # ── Database ─────────────────────────────────────────────────────────

    def db_migrations(self) -> List[Dict]:
        return self._request("GET", "/api/db/migrations")

    def db_migrate(self) -> List[str]:
        result = self._request("POST", "/api/db/migrate")
        return result.get("applied", [])
