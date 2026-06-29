CREATE TABLE IF NOT EXISTS config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tools (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    code        TEXT NOT NULL,
    parameters  TEXT DEFAULT '{}',
    deps        TEXT DEFAULT '[]',
    status      TEXT DEFAULT 'draft',
    plan_id     INTEGER,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS plans (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    goal       TEXT NOT NULL,
    status     TEXT DEFAULT 'draft',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS plan_steps (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id          INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    step_order       INTEGER NOT NULL,
    action           TEXT NOT NULL,
    input_desc       TEXT,
    expected_output  TEXT,
    dep_ids          TEXT DEFAULT '[]',
    status           TEXT DEFAULT 'pending',
    result           TEXT,
    error            TEXT
);

CREATE TABLE IF NOT EXISTS executions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_id    INTEGER REFERENCES tools(id) ON DELETE SET NULL,
    plan_id    INTEGER REFERENCES plans(id) ON DELETE SET NULL,
    success    INTEGER,
    output     TEXT,
    error      TEXT,
    run_at     TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reviews (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_id    INTEGER NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    passed     INTEGER,
    score      REAL,
    feedback   TEXT,
    reviewed_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_plan_steps_plan   ON plan_steps(plan_id);
CREATE INDEX IF NOT EXISTS idx_executions_tool   ON executions(tool_id);
CREATE INDEX IF NOT EXISTS idx_reviews_tool      ON reviews(tool_id);
