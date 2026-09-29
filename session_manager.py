"""
session_manager.py
Manages real-time emotion detection sessions.
Integrates in-memory high-frequency logging with SQLite database persistence via SessionRecord.
"""

import json
import os
import uuid
from datetime import datetime
import threading

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")


class SessionManager:
    def __init__(self, db_instance=None, session_model=None):
        os.makedirs(DATA_DIR, exist_ok=True)
        self._lock = threading.Lock()
        self.db = db_instance
        self.SessionRecord = session_model
        self._sessions = self._load_sessions_json()
        self._active_session = None

    def set_db(self, db_instance, session_model):
        """Set SQLAlchemy database instance and SessionRecord model."""
        self.db = db_instance
        self.SessionRecord = session_model

    # ── Session Lifecycle ──────────────────────────────────────────────────────

    def start_session(self, user_id=None, title="Emotion Session", category="General", notes=""):
        """Create and activate a new session. Returns session_id."""
        sid = str(uuid.uuid4())[:8]
        start_dt = datetime.now()
        session = {
            "id": sid,
            "user_id": user_id,
            "title": title or "Emotion Session",
            "category": category or "General",
            "notes": notes or "",
            "start_time": start_dt.isoformat(),
            "end_time": None,
            "emotion_log": [],
            "snapshots": [],
            "summary": None,
        }
        with self._lock:
            self._active_session = session
            self._sessions[sid] = session
            self._save_sessions_json()

        # Save initial record to DB if available
        if self.db and self.SessionRecord:
            try:
                rec = self.SessionRecord(
                    id=sid,
                    user_id=user_id,
                    title=session["title"],
                    category=session["category"],
                    notes=session["notes"],
                    start_time=start_dt,
                    dominant="neutral"
                )
                self.db.session.add(rec)
                self.db.session.commit()
            except Exception as e:
                print(f"[SessionManager] DB start error: {e}")
                try:
                    self.db.session.rollback()
                except Exception:
                    pass

        return sid

    def stop_session(self):
        """Stop active session, compute statistics, and persist."""
        with self._lock:
            if not self._active_session:
                return None
            sid = self._active_session["id"]
            end_dt = datetime.now()
            self._active_session["end_time"] = end_dt.isoformat()
            summary = self._compute_summary(self._active_session["emotion_log"])
            self._active_session["summary"] = summary
            completed = dict(self._active_session)
            self._sessions[sid] = completed
            self._active_session = None
            self._save_sessions_json()

        # Update DB record
        if self.db and self.SessionRecord:
            try:
                rec = self.SessionRecord.query.get(sid)
                if rec:
                    rec.end_time = end_dt
                    rec.dominant = summary.get("dominant", "neutral")
                    rec.mood_text = summary.get("mood_text", "")
                    rec.positive_pct = summary.get("positive_pct", 0.0)
                    rec.negative_pct = summary.get("negative_pct", 0.0)
                    rec.total_frames = summary.get("total_frames", len(completed.get("emotion_log", [])))
                    rec.stress_alert = summary.get("stress_alert", False)
                    rec.set_distribution(summary.get("distribution", {}))
                    rec.set_emotion_log(completed.get("emotion_log", []))
                    rec.set_snapshots(completed.get("snapshots", []))
                    self.db.session.commit()
            except Exception as e:
                print(f"[SessionManager] DB save error: {e}")
                try:
                    self.db.session.rollback()
                except Exception:
                    pass

        return completed

    def log_emotion(self, emotion_data: list):
        """Append emotion snapshot to active session log in memory."""
        with self._lock:
            if not self._active_session:
                return
            entry = {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "faces": emotion_data,
            }
            self._active_session["emotion_log"].append(entry)

    def add_snapshot(self, filename: str):
        """Register a snapshot filename in the active session."""
        with self._lock:
            if self._active_session:
                self._active_session["snapshots"].append(filename)
                self._save_sessions_json()

    def get_session(self, session_id: str):
        """Get session dict by ID from DB or memory/JSON."""
        # 1. Try DB first
        if self.db and self.SessionRecord:
            try:
                rec = self.SessionRecord.query.get(session_id)
                if rec:
                    d = rec.to_dict()
                    d["emotion_log"] = rec.get_emotion_log()
                    d["summary"] = {
                        "dominant": rec.dominant,
                        "distribution": rec.get_distribution(),
                        "mood_text": rec.mood_text,
                        "positive_pct": rec.positive_pct,
                        "negative_pct": rec.negative_pct,
                        "total_frames": rec.total_frames,
                        "stress_alert": rec.stress_alert
                    }
                    return d
            except Exception as e:
                print(f"[SessionManager] DB get error: {e}")

        # 2. Fallback to memory/JSON
        with self._lock:
            return dict(self._sessions.get(session_id, {}))

    def list_sessions(self, user_id=None):
        """Return list of all sessions, optionally filtered by user_id."""
        if self.db and self.SessionRecord:
            try:
                query = self.SessionRecord.query
                if user_id is not None:
                    query = query.filter_by(user_id=user_id)
                recs = query.order_by(self.SessionRecord.start_time.desc()).all()
                res = []
                for r in recs:
                    item = r.to_dict()
                    item["summary"] = {
                        "dominant": r.dominant,
                        "distribution": r.get_distribution(),
                        "mood_text": r.mood_text,
                        "positive_pct": r.positive_pct,
                        "negative_pct": r.negative_pct,
                        "total_frames": r.total_frames,
                    }
                    res.append(item)
                return res
            except Exception as e:
                print(f"[SessionManager] DB list error: {e}")

        with self._lock:
            sessions = list(self._sessions.values())
            if user_id is not None:
                sessions = [s for s in sessions if s.get("user_id") == user_id]
        return sorted(sessions, key=lambda s: s.get("start_time", ""), reverse=True)

    def delete_session(self, session_id: str):
        """Delete session by ID."""
        deleted = False
        if self.db and self.SessionRecord:
            try:
                rec = self.SessionRecord.query.get(session_id)
                if rec:
                    self.db.session.delete(rec)
                    self.db.session.commit()
                    deleted = True
            except Exception as e:
                print(f"[SessionManager] DB delete error: {e}")
                try:
                    self.db.session.rollback()
                except Exception:
                    pass

        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                self._save_sessions_json()
                deleted = True

        return deleted

    def is_active(self):
        return self._active_session is not None

    def active_session_id(self):
        return self._active_session.get("id") if self._active_session else None

    # ── Summary Computation ───────────────────────────────────────────────────

    def _compute_summary(self, emotion_log):
        if not emotion_log:
            return {
                "dominant": "neutral",
                "distribution": {"neutral": 100.0},
                "mood_text": "No data recorded during session.",
                "positive_pct": 0.0,
                "negative_pct": 0.0,
                "total_frames": 0,
                "stress_alert": False
            }

        totals = {}
        count = 0
        for entry in emotion_log:
            for face in entry.get("faces", []):
                emos = face.get("emotions", {})
                for e, v in emos.items():
                    totals[e] = totals.get(e, 0) + v
                count += 1

        if not count:
            return {
                "dominant": "neutral",
                "distribution": {"neutral": 100.0},
                "mood_text": "No faces detected in this session.",
                "positive_pct": 0.0,
                "negative_pct": 0.0,
                "total_frames": 0,
                "stress_alert": False
            }

        dist = {e: round(v / count, 1) for e, v in totals.items()}
        dominant = max(dist, key=dist.get) if dist else "neutral"

        negative = dist.get("angry", 0) + dist.get("fear", 0) + dist.get("sad", 0) + dist.get("disgust", 0)
        positive = dist.get("happy", 0) + dist.get("surprise", 0)
        stress_alert = bool(negative > 45.0)

        if positive > 50:
            mood_text = "😊 High Positivity — Enthusiastic, joyful, and engaged!"
        elif positive > 30:
            mood_text = "🙂 Balanced & Positive — Generally upbeat and responsive."
        elif negative > 50:
            mood_text = "😟 High Stress Alert — Notable tension detected. Relaxation recommended."
        elif dist.get("neutral", 0) > 60:
            mood_text = "😐 Composed & Focused — Calm, attentive, and neutral composure."
        else:
            mood_text = f"✨ Varied Expressions — Dominant emotion observed: {dominant.capitalize()}."

        return {
            "dominant": dominant,
            "distribution": dist,
            "mood_text": mood_text,
            "negative_pct": round(negative, 1),
            "positive_pct": round(positive, 1),
            "total_frames": count,
            "stress_alert": stress_alert
        }

    def _load_sessions_json(self):
        if os.path.exists(SESSIONS_FILE):
            try:
                with open(SESSIONS_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_sessions_json(self):
        try:
            with open(SESSIONS_FILE, "w") as f:
                json.dump(self._sessions, f, indent=2)
        except Exception as e:
            print(f"[SessionManager] JSON save error: {e}")
