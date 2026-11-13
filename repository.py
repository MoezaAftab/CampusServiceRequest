"""Data access layer: all SQL lives here."""
import sqlite3
from datetime import datetime
from typing import List, Optional

from models import Role, ServiceRequest, Status, User

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    location TEXT NOT NULL,
    description TEXT NOT NULL,
    priority TEXT NOT NULL,
    status TEXT NOT NULL,
    created_by INTEGER NOT NULL REFERENCES users(id),
    assigned_to INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_requests_created_by ON requests(created_by);
CREATE INDEX IF NOT EXISTS idx_requests_assigned_to ON requests(assigned_to);
"""

_SELECT = """
SELECT r.*, c.full_name AS creator_name, COALESCE(a.full_name, '') AS assignee_name
FROM requests r
JOIN users c ON c.id = r.created_by
LEFT JOIN users a ON a.id = r.assigned_to
"""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Repository:
    def __init__(self, path: str):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    # ---- users -------------------------------------------------------
    @staticmethod
    def _user(row) -> User:
        return User(row["id"], row["username"], row["full_name"], Role(row["role"]), row["password_hash"])

    def add_user(self, username, full_name, role: Role, password_hash) -> User:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, full_name, role, password_hash) VALUES (?, ?, ?, ?)",
                (username, full_name, role.value, password_hash),
            )
            return User(cur.lastrowid, username, full_name, role, password_hash)

    def get_user(self, user_id: int) -> Optional[User]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._user(row) if row else None

    def get_user_by_username(self, username: str) -> Optional[User]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return self._user(row) if row else None

    def list_users(self, role: Optional[Role] = None) -> List[User]:
        with self._connect() as conn:
            if role:
                rows = conn.execute("SELECT * FROM users WHERE role = ? ORDER BY full_name", (role.value,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
        return [self._user(r) for r in rows]

    def count_users(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    # ---- requests ----------------------------------------------------
    @staticmethod
    def _request(row) -> ServiceRequest:
        return ServiceRequest(
            id=row["id"], title=row["title"], category=row["category"], location=row["location"],
            description=row["description"], priority=row["priority"], status=Status(row["status"]),
            created_by=row["created_by"], assigned_to=row["assigned_to"],
            created_at=row["created_at"], updated_at=row["updated_at"],
            creator_name=row["creator_name"], assignee_name=row["assignee_name"],
        )

    def add_request(self, title, category, location, description, priority, created_by: int) -> int:
        now = _now()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO requests (title, category, location, description, priority, status,"
                " created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (title, category, location, description, priority, Status.OPEN.value, created_by, now, now),
            )
            return cur.lastrowid

    def get_request(self, request_id: int) -> Optional[ServiceRequest]:
        with self._connect() as conn:
            row = conn.execute(_SELECT + " WHERE r.id = ?", (request_id,)).fetchone()
        return self._request(row) if row else None

    def list_requests(self, created_by: Optional[int] = None, assigned_to: Optional[int] = None,
                      status: Optional[str] = None) -> List[ServiceRequest]:
        sql, params, clauses = _SELECT, [], []
        if created_by is not None:
            clauses.append("r.created_by = ?")
            params.append(created_by)
        if assigned_to is not None:
            clauses.append("r.assigned_to = ?")
            params.append(assigned_to)
        if status:
            clauses.append("r.status = ?")
            params.append(status)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY r.id DESC"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._request(r) for r in rows]

    def assign_request(self, request_id: int, staff_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE requests SET assigned_to = ?, status = ?, updated_at = ? WHERE id = ?",
                (staff_id, Status.ASSIGNED.value, _now(), request_id),
            )

    def set_status(self, request_id: int, status: Status) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE requests SET status = ?, updated_at = ? WHERE id = ?",
                         (status.value, _now(), request_id))
