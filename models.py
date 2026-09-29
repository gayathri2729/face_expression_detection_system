"""
models.py
Database models for FaceIQ using Flask-SQLAlchemy and Flask-Login.
Provides User authentication, Session records, and User preferences.
"""

from datetime import datetime
import json
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), default='')
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    avatar = db.Column(db.String(255), default='🎭')
    bio = db.Column(db.String(255), default='FaceIQ AI Emotion Explorer')

    # Relationships
    sessions = db.relationship('SessionRecord', backref='user', lazy=True, cascade='all, delete-orphan')
    setting = db.relationship('UserSetting', backref='user', uselist=False, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name or self.username,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'avatar': self.avatar or '🎭',
            'bio': self.bio or '',
            'session_count': len(self.sessions)
        }


class SessionRecord(db.Model):
    __tablename__ = 'session_records'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    title = db.Column(db.String(120), default='Emotion Detection Session')
    category = db.Column(db.String(50), default='General')  # e.g., Focus, Meeting, Gaming, Relax, General
    notes = db.Column(db.Text, default='')
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    dominant = db.Column(db.String(30), default='neutral')
    mood_text = db.Column(db.String(255), default='')
    positive_pct = db.Column(db.Float, default=0.0)
    negative_pct = db.Column(db.Float, default=0.0)
    total_frames = db.Column(db.Integer, default=0)
    stress_alert = db.Column(db.Boolean, default=False)
    
    # Serialized fields
    distribution_json = db.Column(db.Text, default='{}')
    emotion_log_json = db.Column(db.Text, default='[]')
    snapshots_json = db.Column(db.Text, default='[]')

    @property
    def duration_seconds(self):
        if self.start_time and self.end_time:
            return max(0, int((self.end_time - self.start_time).total_seconds()))
        return 0

    @property
    def formatted_duration(self):
        secs = self.duration_seconds
        m = secs // 60
        s = secs % 60
        return f"{m}m {s}s" if m > 0 else f"{s}s"

    def get_distribution(self):
        try:
            return json.loads(self.distribution_json or '{}')
        except Exception:
            return {}

    def set_distribution(self, data):
        self.distribution_json = json.dumps(data)

    def get_emotion_log(self):
        try:
            return json.loads(self.emotion_log_json or '[]')
        except Exception:
            return []

    def set_emotion_log(self, data):
        self.emotion_log_json = json.dumps(data)

    def get_snapshots(self):
        try:
            return json.loads(self.snapshots_json or '[]')
        except Exception:
            return []

    def set_snapshots(self, data):
        self.snapshots_json = json.dumps(data)

    def to_dict(self):
        dist = self.get_distribution()
        snapshots = self.get_snapshots()
        log = self.get_emotion_log()
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'category': self.category,
            'notes': self.notes,
            'start_time': self.start_time.isoformat() if self.start_time else '',
            'end_time': self.end_time.isoformat() if self.end_time else '',
            'duration_seconds': self.duration_seconds,
            'formatted_duration': self.formatted_duration,
            'dominant': self.dominant or 'neutral',
            'mood_text': self.mood_text or '',
            'positive_pct': round(self.positive_pct or 0.0, 1),
            'negative_pct': round(self.negative_pct or 0.0, 1),
            'total_frames': self.total_frames or len(log),
            'stress_alert': bool(self.stress_alert),
            'distribution': dist,
            'snapshots': snapshots,
            'emotion_log_count': len(log)
        }


class UserSetting(db.Model):
    __tablename__ = 'user_settings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    sound_alerts = db.Column(db.Boolean, default=True)
    stress_threshold = db.Column(db.Integer, default=50)  # percentage
    camera_index = db.Column(db.Integer, default=0)
    theme = db.Column(db.String(20), default='dark')
    face_smoothing = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'sound_alerts': self.sound_alerts,
            'stress_threshold': self.stress_threshold,
            'camera_index': self.camera_index,
            'theme': self.theme,
            'face_smoothing': self.face_smoothing
        }
