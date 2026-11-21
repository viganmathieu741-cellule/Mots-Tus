"""NOVA - Memory Engine : mémoire persistante dans un simple fichier SQLite (gratuit, sans serveur)."""
import json
import os
import re
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY, ts REAL, tags TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS agents (name TEXT PRIMARY KEY, ts REAL, spec TEXT);
CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY, ts REAL, name TEXT, status TEXT, plan TEXT);
CREATE TABLE IF NOT EXISTS chat (id INTEGER PRIMARY KEY, ts REAL, role TEXT, text TEXT);
"""


def _words(t):
    return set(re.findall(r"[a-zàâçéèêëîïôûùüÿœ0-9]{3,}", t.lower()))


class Memory:
    def __init__(self, path=None):
        self.path = str(path or os.environ.get("NOVA_DB", "nova.db"))
        with self._c() as c:
            c.executescript(SCHEMA)

    def _c(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    # --- souvenirs
    def remember(self, text, tags=""):
        with self._c() as c:
            c.execute("INSERT INTO memory(ts,tags,text) VALUES(?,?,?)", (time.time(), tags, text))

    def recall(self, query, limit=5):
        q = _words(query)
        with self._c() as c:
            rows = c.execute("SELECT text, ts FROM memory ORDER BY ts DESC LIMIT 500").fetchall()
        scored = sorted(((len(q & _words(r["text"])), r["ts"], r["text"]) for r in rows), reverse=True)
        return [t for s, _, t in scored if s > 0][:limit]

    # --- agents
    def save_agent(self, spec):
        with self._c() as c:
            c.execute("INSERT OR REPLACE INTO agents(name,ts,spec) VALUES(?,?,?)",
                      (spec["name"], time.time(), json.dumps(spec, ensure_ascii=False)))

    def get_agent(self, name):
        with self._c() as c:
            r = c.execute("SELECT spec FROM agents WHERE name=?", (name,)).fetchone()
        return json.loads(r["spec"]) if r else None

    def list_agents(self):
        with self._c() as c:
            return [json.loads(r["spec"]) for r in c.execute("SELECT spec FROM agents ORDER BY name")]

    # --- projets
    def add_project(self, name, status, plan):
        with self._c() as c:
            c.execute("INSERT INTO projects(ts,name,status,plan) VALUES(?,?,?,?)",
                      (time.time(), name, status, json.dumps(plan, ensure_ascii=False)))

    def list_projects(self):
        with self._c() as c:
            return [dict(r) for r in c.execute("SELECT id,name,status,plan FROM projects ORDER BY id DESC")]

    # --- conversation
    def log(self, role, text):
        with self._c() as c:
            c.execute("INSERT INTO chat(ts,role,text) VALUES(?,?,?)", (time.time(), role, text))

    def history(self, n=6):
        with self._c() as c:
            rows = c.execute("SELECT role,text FROM chat ORDER BY id DESC LIMIT ?", (n,)).fetchall()
        return [dict(r) for r in reversed(rows)]
