"""
Data access layer for the tool-maker PostgreSQL store.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from .connection import get_connection

logger = logging.getLogger(__name__)


def _row_to_dict(cursor, row) -> Dict[str, Any]:
    """Convert a tuple row to a dict using cursor column names."""
    return dict(zip([desc[0] for desc in cursor.description], row))


# ── Config ───────────────────────────────────────────────────────────────────


def get_config(key: str, default: str = "") -> str:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM config WHERE key = %s", (key,))
            row = cur.fetchone()
            return row[0] if row else default


def set_config(key: str, value: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO config (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (key, value),
            )
        conn.commit()


def all_config() -> Dict[str, str]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM config ORDER BY key")
            return dict(cur.fetchall())


# ── Plans ────────────────────────────────────────────────────────────────────


def create_plan(goal: str) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO plans (goal) VALUES (%s) RETURNING id",
                (goal,),
            )
            plan_id = cur.fetchone()[0]
        conn.commit()
        return plan_id


def get_plan(plan_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM plans WHERE id = %s", (plan_id,))
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(
                "SELECT * FROM plan_steps WHERE plan_id = %s ORDER BY step_order",
                (plan_id,),
            )
            steps = [_row_to_dict(cur, s) for s in cur.fetchall()]
            plan = _row_to_dict(cur, row)
            plan["steps"] = steps
            return plan


def update_plan_status(plan_id: int, status: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE plans SET status = %s WHERE id = %s",
                (status, plan_id),
            )
        conn.commit()


def save_plan_step(
    plan_id: int, step_order: int, action: str,
    input_desc: str = "", expected_output: str = "",
    dep_ids: Optional[List[int]] = None,
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO plan_steps "
                "(plan_id, step_order, action, input_desc, expected_output, dep_ids) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (plan_id, step_order, action, input_desc, expected_output,
                 dep_ids or []),
            )
            step_id = cur.fetchone()[0]
        conn.commit()
        return step_id


def update_step_result(
    step_id: int, status: str, result: str = "", error: str = "",
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE plan_steps SET status = %s, result = %s, error = %s "
                "WHERE id = %s",
                (status, result, error, step_id),
            )
        conn.commit()


# ── Tools ────────────────────────────────────────────────────────────────────


def save_tool(
    name: str, code: str,
    description: str = "",
    parameters: Optional[Dict] = None,
    deps: Optional[List[str]] = None,
    plan_id: Optional[int] = None,
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tools "
                "(name, description, code, parameters, deps, plan_id) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (name) DO UPDATE SET "
                "code = EXCLUDED.code, description = EXCLUDED.description, "
                "parameters = EXCLUDED.parameters, deps = EXCLUDED.deps, "
                "updated_at = NOW() "
                "RETURNING id",
                (name, description, code,
                 json.dumps(parameters or {}),
                 deps or [], plan_id),
            )
            tool_id = cur.fetchone()[0]
        conn.commit()
        return tool_id


def get_tool(tool_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM tools WHERE id = %s", (tool_id,))
            row = cur.fetchone()
            return _row_to_dict(cur, row) if row else None


def get_tool_by_name(name: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM tools WHERE name = %s", (name,))
            row = cur.fetchone()
            return _row_to_dict(cur, row) if row else None


def list_tools(status: str = "") -> List[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            if status:
                cur.execute(
                    "SELECT * FROM tools WHERE status = %s ORDER BY updated_at DESC",
                    (status,),
                )
            else:
                cur.execute("SELECT * FROM tools ORDER BY updated_at DESC")
            return [_row_to_dict(cur, r) for r in cur.fetchall()]


def delete_tool(tool_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM executions WHERE tool_id = %s", (tool_id,))
            cur.execute("DELETE FROM reviews WHERE tool_id = %s", (tool_id,))
            cur.execute("DELETE FROM tools WHERE id = %s", (tool_id,))
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted


def update_tool_status(tool_id: int, status: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tools SET status = %s, updated_at = NOW() WHERE id = %s",
                (status, tool_id),
            )
        conn.commit()


# ── Executions ────────────────────────────────────────────────────────────────


def record_execution(
    tool_id: Optional[int], success: bool,
    output: str = "", error: str = "",
    plan_id: Optional[int] = None,
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO executions (tool_id, plan_id, success, output, error) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (tool_id, plan_id, success, output, error),
            )
            exec_id = cur.fetchone()[0]
        conn.commit()
        return exec_id


# ── Reviews ──────────────────────────────────────────────────────────────────


def save_review(
    tool_id: int, passed: bool, score: float = 0.0, feedback: str = "",
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO reviews (tool_id, passed, score, feedback) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (tool_id, passed, score, feedback),
            )
            review_id = cur.fetchone()[0]
        conn.commit()
        return review_id
