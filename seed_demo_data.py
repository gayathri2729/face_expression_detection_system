"""
seed_demo_data.py
Creates realistic sample sessions for the demo user if none exist.
"""

from datetime import datetime, timedelta
import json
from app import app, db, User, SessionRecord

with app.app_context():
    demo = User.query.filter_by(username="demo").first()
    if demo and SessionRecord.query.filter_by(user_id=demo.id).count() == 0:
        # Sample 1: Focused / Happy work session
        now = datetime.now()
        s1_start = now - timedelta(hours=3, minutes=15)
        s1_end = s1_start + timedelta(minutes=18, seconds=45)
        dist1 = {"happy": 68.4, "neutral": 22.1, "surprise": 6.5, "sad": 1.5, "angry": 0.8, "fear": 0.4, "disgust": 0.3}
        
        # Build timeline
        timeline1 = []
        for i in range(25):
            t = (s1_start + timedelta(seconds=i*45)).strftime("%H:%M:%S")
            timeline1.append({
                "time": t,
                "dominant": "happy" if i % 4 != 0 else "neutral",
                "happy": 65.0 + (i % 5)*2,
                "neutral": 20.0 + (i % 3)*2,
                "sad": 2.0, "angry": 1.0, "surprise": 5.0, "fear": 1.0, "disgust": 0.5
            })

        log1 = [{"timestamp": item["time"], "faces": [{"dominant": item["dominant"], "emotions": item}]} for item in timeline1]

        rec1 = SessionRecord(
            id="s1a8b9c0",
            user_id=demo.id,
            title="UI Project Code Review",
            category="Work",
            notes="Morning code review and sprint planning session. Great positive engagement.",
            start_time=s1_start,
            end_time=s1_end,
            dominant="happy",
            mood_text="😊 High Positivity — Enthusiastic, joyful, and engaged throughout the sprint review.",
            positive_pct=74.9,
            negative_pct=3.0,
            total_frames=185,
            stress_alert=False,
            distribution_json=json.dumps(dist1),
            emotion_log_json=json.dumps(log1),
            snapshots_json=json.dumps([])
        )

        # Sample 2: Study Focus session
        s2_start = now - timedelta(days=1, hours=4)
        s2_end = s2_start + timedelta(minutes=24, seconds=10)
        dist2 = {"neutral": 72.8, "sad": 11.2, "happy": 8.5, "angry": 4.1, "surprise": 2.2, "fear": 0.8, "disgust": 0.4}
        
        timeline2 = []
        for i in range(30):
            t = (s2_start + timedelta(seconds=i*48)).strftime("%H:%M:%S")
            timeline2.append({
                "time": t,
                "dominant": "neutral",
                "neutral": 70.0 + (i % 4)*1.5,
                "happy": 8.0, "sad": 10.0, "angry": 4.0, "surprise": 2.0, "fear": 1.0, "disgust": 0.5
            })
        log2 = [{"timestamp": item["time"], "faces": [{"dominant": item["dominant"], "emotions": item}]} for item in timeline2]

        rec2 = SessionRecord(
            id="s2d3e4f5",
            user_id=demo.id,
            title="Deep Learning Architecture Study",
            category="Study",
            notes="Intense technical reading session on CNNs and facial landmark detectors.",
            start_time=s2_start,
            end_time=s2_end,
            dominant="neutral",
            mood_text="😐 Composed & Focused — Calm, attentive, and neutral composure during study time.",
            positive_pct=10.7,
            negative_pct=16.5,
            total_frames=240,
            stress_alert=False,
            distribution_json=json.dumps(dist2),
            emotion_log_json=json.dumps(log2),
            snapshots_json=json.dumps([])
        )

        db.session.add(rec1)
        db.session.add(rec2)
        db.session.commit()
        print("Seeded 2 sample sessions for demo user successfully!")
