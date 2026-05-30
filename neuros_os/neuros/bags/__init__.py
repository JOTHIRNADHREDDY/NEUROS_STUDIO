"""
neuros.bags
===========
Phase 2 — Bag File Manager.

Record, replay, and analyze NEUROS Neural Bus data bags.
SQLite-backed storage for zero-dependency persistence.

Usage
-----
    from neuros.bags import BagRecorder, BagPlayer, BagAnalyzer

    # Record topics to a bag file
    recorder = BagRecorder(bus, "session_001.neuros.bag")
    recorder.add_topic("/robot/sensor/#")      # wildcard
    recorder.add_topic("/robot/cmd/velocity")
    recorder.start()
    # ... robot runs ...
    recorder.stop()

    # Analyze a bag
    analyzer = BagAnalyzer("session_001.neuros.bag")
    print(analyzer.info())
    # → {duration: 120.5s, messages: 24680, topics: [...]}

    # Export to CSV
    analyzer.export_csv("/robot/sensor/imu/accel", "imu_data.csv")

    # Replay a bag
    player = BagPlayer(bus, "session_001.neuros.bag")
    player.play(speed=1.0)  # 1x realtime

    # CLI:
    neuros bag record --topics "/robot/sensor/#" -o session.bag
    neuros bag info session.bag
    neuros bag export session.bag --topic /robot/sensor/imu/accel -o data.csv
    neuros bag play session.bag --speed 2.0
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from neuros.bus.bus import NeuralBus

logger = logging.getLogger("neuros.bags")


# ── Bag Schema ────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bag_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL    NOT NULL,
    topic     TEXT    NOT NULL,
    data      TEXT    NOT NULL,
    seq       INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_messages_topic ON messages(topic);
CREATE INDEX IF NOT EXISTS idx_messages_time  ON messages(timestamp);
"""


# ── Bag Recorder ──────────────────────────────────────────────────────────

class BagRecorder:
    """
    Record Neural Bus messages to a .neuros.bag file (SQLite).

    Parameters
    ----------
    bus       : NeuralBus instance to record from
    path      : output bag file path
    overwrite : if True, overwrite existing bag file
    """

    def __init__(
        self,
        bus: "NeuralBus",
        path: str,
        *,
        overwrite: bool = False,
        buffer_size: int = 100,
    ) -> None:
        self._bus = bus
        self._path = str(path)
        self._overwrite = overwrite
        self._buffer_size = buffer_size
        self._topics: List[str] = []
        self._subscriptions: list = []  # Store actual Subscription objects
        self._running = False
        self._db: Optional[sqlite3.Connection] = None
        self._buffer: List[Tuple[float, str, str, int]] = []
        self._lock = threading.Lock()
        self._flush_thread: Optional[threading.Thread] = None
        self._msg_count = 0
        self._start_time = 0.0

    def add_topic(self, topic: str) -> "BagRecorder":
        """Add a topic pattern to record (supports wildcards)."""
        self._topics.append(topic)
        return self

    def start(self) -> "BagRecorder":
        """Start recording."""
        if self._running:
            return self

        # Create/open database
        p = Path(self._path)
        if p.exists() and self._overwrite:
            p.unlink()
        p.parent.mkdir(parents=True, exist_ok=True)

        self._db = sqlite3.connect(self._path, check_same_thread=False)
        self._db.executescript(_SCHEMA)

        self._start_time = time.time()
        self._msg_count = 0

        # Write metadata
        meta = {
            "start_time": self._start_time,
            "topics": json.dumps(self._topics),
            "version": "1.0",
            "format": "neuros.bag.v1",
        }
        for k, v in meta.items():
            self._db.execute(
                "INSERT OR REPLACE INTO bag_meta (key, value) VALUES (?, ?)",
                (k, str(v))
            )
        self._db.commit()

        # Subscribe to topics — store Subscription objects for proper cleanup
        for topic in self._topics:
            sub_id = f"bag_recorder_{topic}"
            sub = self._bus.subscribe(topic, self._on_message, node_id=sub_id)
            self._subscriptions.append(sub)

        # Start flush thread
        self._running = True
        self._flush_thread = threading.Thread(
            target=self._flush_loop,
            name="neuros-bag-flush",
            daemon=True,
        )
        self._flush_thread.start()

        logger.info("[BAG] Recording started → %s (%d topics)", self._path, len(self._topics))
        return self

    def stop(self) -> dict:
        """Stop recording and finalize the bag file. Returns summary."""
        self._running = False

        # Unsubscribe — pass actual Subscription objects (not strings)
        for sub in self._subscriptions:
            try:
                self._bus.unsubscribe(sub)
            except Exception:
                pass
        self._subscriptions.clear()

        # Flush remaining buffer
        self._flush_buffer()

        # Write end metadata
        end_time = time.time()
        duration = end_time - self._start_time

        if self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO bag_meta (key, value) VALUES (?, ?)",
                ("end_time", str(end_time))
            )
            self._db.execute(
                "INSERT OR REPLACE INTO bag_meta (key, value) VALUES (?, ?)",
                ("duration", str(duration))
            )
            self._db.execute(
                "INSERT OR REPLACE INTO bag_meta (key, value) VALUES (?, ?)",
                ("message_count", str(self._msg_count))
            )
            self._db.commit()
            self._db.close()
            self._db = None

        if self._flush_thread:
            self._flush_thread.join(timeout=2.0)

        summary = {
            "path": self._path,
            "duration_s": round(duration, 2),
            "messages": self._msg_count,
            "topics": self._topics,
            "size_bytes": Path(self._path).stat().st_size if Path(self._path).exists() else 0,
        }
        logger.info("[BAG] Recording stopped — %d messages in %.1fs", self._msg_count, duration)
        return summary

    def _on_message(self, msg) -> None:
        """Callback for bus messages."""
        entry = (
            time.time(),
            str(msg.topic),
            json.dumps(msg.data) if not isinstance(msg.data, str) else msg.data,
            getattr(msg, 'seq', 0),
        )
        with self._lock:
            self._buffer.append(entry)
            self._msg_count += 1
            if len(self._buffer) >= self._buffer_size:
                self._flush_buffer()

    def _flush_buffer(self) -> None:
        """Write buffered messages to SQLite."""
        with self._lock:
            if not self._buffer or not self._db:
                return
            batch = self._buffer[:]
            self._buffer.clear()

        try:
            self._db.executemany(
                "INSERT INTO messages (timestamp, topic, data, seq) VALUES (?, ?, ?, ?)",
                batch
            )
            self._db.commit()
        except Exception as e:
            logger.error("[BAG] Flush error: %s", e)

    def _flush_loop(self) -> None:
        """Periodic flush thread."""
        while self._running:
            time.sleep(0.5)
            self._flush_buffer()

    @property
    def message_count(self) -> int:
        return self._msg_count

    def status(self) -> dict:
        return {
            "recording": self._running,
            "path": self._path,
            "messages": self._msg_count,
            "topics": self._topics,
            "elapsed_s": round(time.time() - self._start_time, 1) if self._running else 0,
        }


# ── Bag Player ────────────────────────────────────────────────────────────

class BagPlayer:
    """
    Replay a .neuros.bag file through the Neural Bus.

    Parameters
    ----------
    bus   : NeuralBus to publish replayed messages into
    path  : path to the bag file
    """

    def __init__(self, bus: "NeuralBus", path: str) -> None:
        self._bus = bus
        self._path = str(path)
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._progress: float = 0.0
        self._total_messages: int = 0
        self._played_messages: int = 0
        self._speed: float = 1.0

    def play(
        self,
        speed: float = 1.0,
        *,
        topics: Optional[List[str]] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        loop: bool = False,
        blocking: bool = False,
    ) -> "BagPlayer":
        """
        Start replaying the bag.

        Parameters
        ----------
        speed      : playback speed multiplier (1.0 = realtime, 2.0 = 2x, 0.5 = half)
        topics     : filter to specific topics (None = all)
        start_time : start from this absolute timestamp
        end_time   : stop at this absolute timestamp
        loop       : repeat when finished
        blocking   : if True, block until playback completes
        """
        self._speed = speed
        self._running = True
        self._paused = False
        self._played_messages = 0

        self._thread = threading.Thread(
            target=self._play_loop,
            args=(speed, topics, start_time, end_time, loop),
            name="neuros-bag-player",
            daemon=True,
        )
        self._thread.start()

        if blocking:
            self._thread.join()

        return self

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _play_loop(self, speed, topics, start_time, end_time, loop) -> None:
        """Main playback loop."""
        from neuros.bus.message import Message

        while self._running:
            db = sqlite3.connect(self._path)

            # Build query
            query = "SELECT timestamp, topic, data, seq FROM messages"
            conditions = []
            params: list = []

            if topics:
                placeholders = ','.join('?' for _ in topics)
                conditions.append(f"topic IN ({placeholders})")
                params.extend(topics)
            if start_time:
                conditions.append("timestamp >= ?")
                params.append(start_time)
            if end_time:
                conditions.append("timestamp <= ?")
                params.append(end_time)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY timestamp ASC"

            # Count total for progress tracking
            count_row = db.execute(
                "SELECT COUNT(*) FROM messages" +
                (" WHERE " + " AND ".join(conditions) if conditions else ""),
                params[:len(conditions)]
            ).fetchone()
            self._total_messages = count_row[0] if count_row else 0

            if self._total_messages == 0:
                db.close()
                logger.warning("[BAG] No messages to play from %s", self._path)
                break

            logger.info("[BAG] Playing %d messages at %.1fx speed", self._total_messages, speed)

            # Stream rows via cursor iteration (not fetchall) to avoid OOM
            cursor = db.execute(query, params)
            prev_ts = None
            for i, (ts, topic, data, seq) in enumerate(cursor):
                if prev_ts is None:
                    prev_ts = ts
                if not self._running:
                    break

                while self._paused and self._running:
                    time.sleep(0.05)

                # Delay to match original timing
                dt = (ts - prev_ts) / speed if speed > 0 else 0
                if dt > 0:
                    time.sleep(dt)
                prev_ts = ts

                # Publish to bus
                try:
                    msg_data = json.loads(data) if data.startswith('{') or data.startswith('[') else data
                except (json.JSONDecodeError, ValueError):
                    msg_data = data

                self._bus.publish(Message(topic=topic, data=msg_data))
                self._played_messages = i + 1
                self._progress = (i + 1) / self._total_messages if self._total_messages else 0

            db.close()

            if not loop:
                break

        self._running = False
        logger.info("[BAG] Playback complete — %d messages", self._played_messages)

    @property
    def progress(self) -> float:
        return self._progress

    def status(self) -> dict:
        return {
            "playing": self._running,
            "paused": self._paused,
            "speed": self._speed,
            "progress": round(self._progress, 3),
            "played": self._played_messages,
            "total": self._total_messages,
            "path": self._path,
        }


# ── Bag Analyzer ──────────────────────────────────────────────────────────

class BagAnalyzer:
    """
    Analyze a .neuros.bag file.

    Parameters
    ----------
    path : path to the bag file
    """

    def __init__(self, path: str) -> None:
        self._path = str(path)
        if not Path(path).exists():
            raise FileNotFoundError(f"Bag file not found: {path}")

    def info(self) -> dict:
        """Get bag metadata and statistics."""
        db = sqlite3.connect(self._path)

        # Read metadata
        meta = {}
        try:
            for row in db.execute("SELECT key, value FROM bag_meta"):
                meta[row[0]] = row[1]
        except sqlite3.OperationalError:
            pass

        # Count messages
        total = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

        # Time range
        time_range = db.execute(
            "SELECT MIN(timestamp), MAX(timestamp) FROM messages"
        ).fetchone()
        start_t = time_range[0] or 0
        end_t = time_range[1] or 0
        duration = end_t - start_t

        # Topics
        topics = []
        for row in db.execute(
            "SELECT topic, COUNT(*), MIN(timestamp), MAX(timestamp) FROM messages GROUP BY topic"
        ):
            topic_duration = (row[3] - row[2]) if row[3] and row[2] else 0
            hz = row[1] / topic_duration if topic_duration > 0 else 0
            topics.append({
                "topic": row[0],
                "count": row[1],
                "hz": round(hz, 1),
                "first_time": row[2],
                "last_time": row[3],
            })

        db.close()

        # File size
        size = Path(self._path).stat().st_size

        return {
            "path": self._path,
            "size_bytes": size,
            "size_human": _human_size(size),
            "duration_s": round(duration, 2),
            "total_messages": total,
            "topics": topics,
            "topic_count": len(topics),
            "start_time": start_t,
            "end_time": end_t,
            "meta": meta,
        }

    def get_messages(
        self,
        topic: Optional[str] = None,
        *,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 1000,
    ) -> List[dict]:
        """
        Read messages from the bag.

        Parameters
        ----------
        topic      : filter by topic (None = all)
        start_time : filter by start time
        end_time   : filter by end time
        limit      : max messages to return
        """
        db = sqlite3.connect(self._path)
        query = "SELECT timestamp, topic, data, seq FROM messages"
        conditions = []
        params: list = []

        if topic:
            conditions.append("topic = ?")
            params.append(topic)
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY timestamp ASC LIMIT ?"
        params.append(limit)

        rows = db.execute(query, params).fetchall()
        db.close()

        messages = []
        for ts, top, data, seq in rows:
            try:
                parsed = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                parsed = data
            messages.append({
                "timestamp": ts,
                "topic": top,
                "data": parsed,
                "seq": seq,
            })
        return messages

    def export_csv(self, topic: str, output_path: str, *,
                   delimiter: str = ",") -> int:
        """
        Export messages for a topic to CSV.
        Returns count of exported messages.
        """
        messages = self.get_messages(topic, limit=1_000_000)
        if not messages:
            logger.warning("[BAG] No messages for topic '%s'", topic)
            return 0

        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        # Collect all data keys
        all_keys: list = []
        for msg in messages:
            if isinstance(msg["data"], dict):
                for k in msg["data"]:
                    if k not in all_keys:
                        all_keys.append(k)

        with open(p, 'w', encoding='utf-8') as f:
            # Header
            header = ["timestamp", "seq"]
            if all_keys:
                header.extend(all_keys)
            else:
                header.append("data")
            f.write(delimiter.join(header) + '\n')

            # Rows
            for msg in messages:
                row = [str(msg["timestamp"]), str(msg["seq"])]
                if all_keys and isinstance(msg["data"], dict):
                    for k in all_keys:
                        row.append(str(msg["data"].get(k, "")))
                else:
                    row.append(str(msg["data"]))
                f.write(delimiter.join(row) + '\n')

        logger.info("[BAG] Exported %d messages to %s", len(messages), output_path)
        return len(messages)

    def topics(self) -> List[str]:
        """List all topics in the bag."""
        db = sqlite3.connect(self._path)
        topics = [row[0] for row in db.execute("SELECT DISTINCT topic FROM messages")]
        db.close()
        return topics

    def message_count(self, topic: Optional[str] = None) -> int:
        """Count messages, optionally filtered by topic."""
        db = sqlite3.connect(self._path)
        if topic:
            count = db.execute("SELECT COUNT(*) FROM messages WHERE topic = ?", (topic,)).fetchone()[0]
        else:
            count = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        db.close()
        return count


def _human_size(size: int) -> str:
    """Convert bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


__all__ = [
    "BagRecorder",
    "BagPlayer",
    "BagAnalyzer",
]
