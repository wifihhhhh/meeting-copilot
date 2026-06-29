CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(80) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(120) NOT NULL DEFAULT '',
    created_at VARCHAR(30) NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_users_username ON users(username);

CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL DEFAULT 1,
    title VARCHAR(200) NOT NULL,
    meeting_date VARCHAR(50),
    raw_text TEXT NOT NULL,
    minutes_json TEXT NOT NULL,
    minutes_markdown TEXT NOT NULL,
    created_at VARCHAR(30) NOT NULL,
    updated_at VARCHAR(30) NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_meetings_user_id ON meetings(user_id);
CREATE INDEX IF NOT EXISTS ix_meetings_title ON meetings(title);
CREATE INDEX IF NOT EXISTS ix_meetings_meeting_date ON meetings(meeting_date);

CREATE TABLE IF NOT EXISTS action_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL,
    owner VARCHAR(100) NOT NULL DEFAULT '',
    task TEXT NOT NULL,
    deadline VARCHAR(100) NOT NULL DEFAULT '',
    status VARCHAR(50) NOT NULL DEFAULT '待办',
    created_at VARCHAR(30) NOT NULL,
    FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_action_items_meeting_id ON action_items(meeting_id);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL,
    owner VARCHAR(100) NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    deadline VARCHAR(100) NOT NULL DEFAULT '',
    topic VARCHAR(200) NOT NULL DEFAULT '',
    created_at VARCHAR(30) NOT NULL,
    FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_decisions_meeting_id ON decisions(meeting_id);

CREATE TABLE IF NOT EXISTS evaluation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    meeting_id INTEGER,
    metric_name VARCHAR(100) NOT NULL,
    precision FLOAT,
    recall FLOAT,
    f1 FLOAT,
    score FLOAT,
    notes TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at VARCHAR(30) NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_evaluation_results_user_id ON evaluation_results(user_id);
CREATE INDEX IF NOT EXISTS ix_evaluation_results_meeting_id ON evaluation_results(meeting_id);

CREATE TABLE IF NOT EXISTS qa_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL DEFAULT 1,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources_json TEXT NOT NULL DEFAULT '[]',
    created_at VARCHAR(30) NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_qa_records_user_id ON qa_records(user_id);
