"""Stores every battery-lab run in an SQLite database file, so the dashboard can
show historical statistics.  SQLite keeps the whole database in ONE ordinary file
(energos_history.db) and uses a journal so a crash never leaves it half-written."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "energos_history.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created       TEXT    NOT NULL,
    scheduler     TEXT, governor TEXT, replacement TEXT, disk_algorithm TEXT,
    processes     INTEGER, seed INTEGER, workload TEXT,
    avg_waiting   REAL, total_time REAL,
    energy_cpu    REAL, energy_mem REAL, energy_disk REAL, energy_total REAL,
    avg_power     REAL, battery_hours REAL
);
"""


def connect(path=DB_PATH):
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")      # write-ahead log: readers don't block the writer
    con.execute(SCHEMA)
    return con


def save(result, config: dict, path=DB_PATH) -> int:
    with connect(path) as con:
        cur = con.execute(
            """INSERT INTO runs (created, scheduler, governor, replacement, disk_algorithm, processes, seed, workload,
                                 avg_waiting, total_time, energy_cpu, energy_mem, energy_disk, energy_total, avg_power, battery_hours)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (time.strftime("%Y-%m-%d %H:%M:%S"), config["scheduler"], config["governor"], config["replacement"],
             config["disk_algorithm"], config["processes"], config["seed"], config["workload"],
             result.cpu.avg_waiting, result.total_time_ms, result.energy_cpu_mj, result.energy_mem_mj,
             result.energy_disk_mj, result.energy_total_mj, result.avg_power_w, result.battery_hours))
        return cur.lastrowid


def all_runs(path=DB_PATH):
    with connect(path) as con:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute("SELECT * FROM runs ORDER BY id")]


def clear(path=DB_PATH):
    with connect(path) as con:
        con.execute("DELETE FROM runs")
