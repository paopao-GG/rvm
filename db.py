#!/usr/bin/env python3
"""
RVM Database Module - Shared by portal and main script
SQLite database for user sessions, bottle types, and machine state
"""

import sqlite3
import threading
from datetime import datetime, timedelta
from contextlib import contextmanager

DB_PATH = "/home/raspi/rvm/rvm.db"

# Thread-local storage for connections
_local = threading.local()

@contextmanager
def get_db():
    """Get a database connection (thread-safe)."""
    if not hasattr(_local, 'conn'):
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    try:
        yield _local.conn
    except Exception:
        _local.conn.rollback()
        raise
    else:
        _local.conn.commit()


def init_db():
    """Initialize database tables."""
    with get_db() as conn:
        conn.executescript("""
            -- User sessions table
            CREATE TABLE IF NOT EXISTS users (
                mac TEXT PRIMARY KEY,
                accumulated_time INTEGER DEFAULT 0,  -- seconds
                wifi_active INTEGER DEFAULT 0,       -- boolean: 0 or 1
                session_started TEXT,                -- ISO timestamp when WiFi started
                last_seen TEXT                       -- ISO timestamp of last activity
            );

            -- Bottle types and time rewards
            CREATE TABLE IF NOT EXISTS bottles (
                bottle_type TEXT PRIMARY KEY,
                time_minutes INTEGER NOT NULL
            );

            -- Machine state (who is actively inserting bottles)
            CREATE TABLE IF NOT EXISTS machine_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),  -- only one row
                active_mac TEXT,                        -- MAC address currently using machine
                lock_started TEXT                       -- ISO timestamp when locked
            );

            -- Insert default bottle time values (based on P.E.T-O rate card)
            INSERT OR IGNORE INTO bottles (bottle_type, time_minutes) VALUES
                ('water_bottle-500mL', 5),
                ('water_bottle-350mL', 3.5),
                ('water_bottle-1L', 10),
                ('coke_2L', 20),
                ('coke_mismo', 3.2),
                ('pocari_350mL', 3.5),
                ('sprite_1.5L', 15),
                ('royal_1.5L', 15),
                ('natures_spring_1000ml', 10),
                ('coke_litro', 15);

            -- Initialize machine state
            INSERT OR IGNORE INTO machine_state (id, active_mac, lock_started)
                VALUES (1, NULL, NULL);
        """)


# ── User Session Functions ────────────────────────────────────────

def get_user(mac):
    """Get user by MAC address. Returns dict or None."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE mac = ?", (mac,)).fetchone()
        return dict(row) if row else None


def create_user(mac):
    """Create a new user with MAC address."""
    now = datetime.now().isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (mac, accumulated_time, wifi_active, last_seen) VALUES (?, 0, 0, ?)",
            (mac, now)
        )


def add_time_to_user(mac, minutes):
    """Add time to user's accumulated time.

    Minutes format: X.Y where X is whole minutes and Y is additional seconds
    Example: 3.2 = 3 minutes + 20 seconds = 200 seconds
    """
    now = datetime.now().isoformat()

    # Convert minutes to seconds: integer part as minutes, decimal part as seconds
    whole_minutes = int(minutes)
    decimal_part = minutes - whole_minutes
    additional_seconds = int(decimal_part * 100)  # .2 -> 20 seconds, .5 -> 50 seconds
    total_seconds = (whole_minutes * 60) + additional_seconds

    with get_db() as conn:
        # Ensure user exists
        conn.execute(
            "INSERT OR IGNORE INTO users (mac, accumulated_time, wifi_active, last_seen) VALUES (?, 0, 0, ?)",
            (mac, now)
        )
        # Add time
        conn.execute(
            "UPDATE users SET accumulated_time = accumulated_time + ?, last_seen = ? WHERE mac = ?",
            (total_seconds, now, mac)
        )


def start_wifi_session(mac):
    """Activate WiFi for user and start countdown."""
    now = datetime.now().isoformat()
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET wifi_active = 1, session_started = ?, last_seen = ? WHERE mac = ?",
            (now, now, mac)
        )


def stop_wifi_session(mac):
    """Deactivate WiFi for user."""
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET wifi_active = 0, accumulated_time = 0, session_started = NULL WHERE mac = ?",
            (mac,)
        )


def get_remaining_time(mac):
    """Get remaining WiFi time for user in seconds. Returns 0 if no time left or not active."""
    user = get_user(mac)
    if not user or not user['wifi_active'] or not user['session_started']:
        return 0

    session_start = datetime.fromisoformat(user['session_started'])
    elapsed = (datetime.now() - session_start).total_seconds()
    remaining = user['accumulated_time'] - elapsed

    return max(0, int(remaining))


def update_last_seen(mac):
    """Update user's last_seen timestamp."""
    now = datetime.now().isoformat()
    with get_db() as conn:
        conn.execute("UPDATE users SET last_seen = ? WHERE mac = ?", (now, mac))


def get_expired_users():
    """Get list of MACs with expired sessions (24 hours inactive or time ran out)."""
    expired = []
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()

    with get_db() as conn:
        # Users inactive for 24 hours
        rows = conn.execute(
            "SELECT mac FROM users WHERE last_seen < ? OR last_seen IS NULL",
            (cutoff,)
        ).fetchall()
        expired.extend([row['mac'] for row in rows])

        # Users with active WiFi but time ran out
        active_users = conn.execute(
            "SELECT mac FROM users WHERE wifi_active = 1"
        ).fetchall()

        for row in active_users:
            if get_remaining_time(row['mac']) <= 0:
                expired.append(row['mac'])

    return list(set(expired))  # Remove duplicates


# ── Machine State Functions ────────────────────────────────────────

def get_machine_state():
    """Get current machine state. Returns dict with active_mac and lock_started."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM machine_state WHERE id = 1").fetchone()
        return dict(row) if row else None


def lock_machine(mac):
    """Lock machine to a specific MAC address. Returns True if successful, False if already locked."""
    state = get_machine_state()

    # Check if already locked to someone else
    if state and state['active_mac'] and state['active_mac'] != mac:
        # Check if lock is stale (>5 minutes)
        if state['lock_started']:
            lock_time = datetime.fromisoformat(state['lock_started'])
            if (datetime.now() - lock_time).total_seconds() < 300:  # 5 minutes
                return False  # Still locked

    # Lock to this MAC
    now = datetime.now().isoformat()
    with get_db() as conn:
        conn.execute(
            "UPDATE machine_state SET active_mac = ?, lock_started = ? WHERE id = 1",
            (mac, now)
        )
    return True


def release_machine():
    """Release machine lock."""
    with get_db() as conn:
        conn.execute("UPDATE machine_state SET active_mac = NULL, lock_started = NULL WHERE id = 1")


def refresh_machine_lock(mac):
    """Refresh the machine lock timestamp (call after each scan)."""
    state = get_machine_state()
    if state and state['active_mac'] == mac:
        now = datetime.now().isoformat()
        with get_db() as conn:
            conn.execute(
                "UPDATE machine_state SET lock_started = ? WHERE id = 1",
                (now,)
            )


# ── Bottle Functions ───────────────────────────────────────────────

def get_bottle_time(bottle_type):
    """Get time reward for a bottle type in minutes. Returns 0 if unknown."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT time_minutes FROM bottles WHERE bottle_type = ?",
            (bottle_type,)
        ).fetchone()
        return row['time_minutes'] if row else 0


def get_all_bottles():
    """Get all bottle types and their time values."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM bottles ORDER BY time_minutes DESC").fetchall()
        return [dict(row) for row in rows]


# Initialize database on import
init_db()
