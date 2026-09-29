"""
app.py
FaceIQ – Professional Face Expression Detection & Emotion Analytics System.
Full Flask + SocketIO + SQLite web application with authentication, history, analytics, photo analyzer, and reports.
"""

import os
import sys
import time
import json
import base64
import io
import csv
import threading
from datetime import datetime, timedelta

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from flask import (
    Flask, render_template, Response, request,
    jsonify, redirect, url_for, flash, send_from_directory, send_file
)
from flask_socketio import SocketIO
from flask_cors import CORS
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)

from models import db, User, SessionRecord, UserSetting
from emotion_detector import EmotionDetector
from session_manager import SessionManager
from analytics import compute_distribution, compute_timeline, is_stress_alert, emotion_colors

# ─── Directories Setup ─────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SNAPSHOTS_DIR = os.path.join(BASE_DIR, "static", "snapshots")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SNAPSHOTS_DIR, exist_ok=True)

# ─── App Configuration ────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"] = "faceiq-secret-2024-super-safe-enterprise"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(DATA_DIR, 'faceiq.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload

CORS(app)
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ─── Login Manager ────────────────────────────────────────────────────────────
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to access FaceIQ."
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ─── Core Singletons ──────────────────────────────────────────────────────────
detector = EmotionDetector(camera_index=0, analysis_interval=0.35)
session_mgr = SessionManager()
detector.start()

# ─── Initialize DB & Seed Demo User ───────────────────────────────────────────
with app.app_context():
    db.create_all()
    session_mgr.set_db(db, SessionRecord)

    # Seed demo account if not exists
    demo_user = User.query.filter_by(username="demo").first()
    if not demo_user:
        demo_user = User(
            username="demo",
            email="demo@faceiq.ai",
            full_name="Demo User",
            avatar="🎭",
            bio="FaceIQ Explorer testing real-time emotion detection"
        )
        demo_user.set_password("demo123")
        db.session.add(demo_user)
        db.session.commit()

        # Add default settings
        setting = UserSetting(user_id=demo_user.id, sound_alerts=True, stress_threshold=50)
        db.session.add(setting)
        db.session.commit()
        print("[Database] Seeded demo user: demo / demo123")

# ─── Real-Time Emotion Push Thread ─────────────────────────────────────────────
_push_active = False
_push_thread = None

def _emotion_push_loop():
    """Broadcast latest emotion metrics to all connected clients."""
    global _push_active
    while _push_active:
        try:
            data = detector.get_emotion_data()
            if data:
                face_count = len(data)
                dominant = data[0].get("dominant", "neutral")
                emotions = data[0].get("emotions", {})
            else:
                face_count = 0
                dominant = "neutral"
                emotions = {e: 0.0 for e in ["angry","disgust","fear","happy","sad","surprise","neutral"]}

            # Log to active session
            if session_mgr.is_active():
                session_mgr.log_emotion(data)

            # Compute stress alert
            dist = compute_distribution([{"faces": data}] if data else [])
            stress = is_stress_alert(dist)

            payload = {
                "face_count": face_count,
                "dominant": dominant,
                "emotions": emotions,
                "all_faces": data,
                "stress_alert": stress,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }
            socketio.emit("emotion_update", payload)
        except Exception as e:
            pass
        time.sleep(0.3)

def _start_push():
    global _push_active, _push_thread
    _push_active = True
    _push_thread = threading.Thread(target=_emotion_push_loop, daemon=True)
    _push_thread.start()

_start_push()


# ─── Authentication Routes ─────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username_or_email = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        user = User.query.filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        ).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash(f"Welcome back, {user.full_name or user.username}!", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))
        else:
            flash("Invalid username or password. Please try again.", "error")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html")

        if User.query.filter_by(username=username).first():
            flash("Username already taken. Please choose another.", "error")
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash("Email address already registered. Please log in.", "error")
            return render_template("register.html")

        # Create user
        new_user = User(username=username, email=email, full_name=full_name, avatar="🎭")
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        # Create default user setting
        setting = UserSetting(user_id=new_user.id)
        db.session.add(setting)
        db.session.commit()

        login_user(new_user)
        flash("Account created successfully! Welcome to FaceIQ.", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out safely.", "info")
    return redirect(url_for("login"))


# ─── Main Pages ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/history")
@login_required
def history():
    sessions = session_mgr.list_sessions(user_id=current_user.id)
    # If no sessions for current user yet, show all sessions
    if not sessions:
        sessions = session_mgr.list_sessions()

    # Normalize session dicts — guarantee all template fields exist
    def _fmt_duration(secs):
        secs = secs or 0
        m = secs // 60
        s = secs % 60
        return f"{m}m {s}s" if m > 0 else f"{s}s"

    for s in sessions:
        s.setdefault("title", "Emotion Session")
        s.setdefault("category", "General")
        s.setdefault("notes", "")
        s.setdefault("dominant", "neutral")
        s.setdefault("mood_text", "")
        s.setdefault("start_time", "")
        s.setdefault("end_time", "")
        s.setdefault("positive_pct", 0.0)
        s.setdefault("negative_pct", 0.0)
        s.setdefault("total_frames", 0)
        s.setdefault("stress_alert", False)
        s.setdefault("snapshots", [])
        dur = s.get("duration_seconds") or 0
        s.setdefault("formatted_duration", _fmt_duration(dur))
        # Coerce pct to float
        s["positive_pct"] = round(float(s["positive_pct"] or 0), 1)
        s["negative_pct"] = round(float(s["negative_pct"] or 0), 1)

    # Calculate overall metrics
    total_seconds = sum(s.get("duration_seconds", 0) or 0 for s in sessions)
    m = total_seconds // 60
    s_rem = total_seconds % 60
    total_duration_str = f"{m}m {s_rem}s" if m > 0 else f"{s_rem}s"

    positives = [s.get("positive_pct", 0) for s in sessions]
    avg_positivity = round(sum(positives) / len(positives), 1) if positives else 0.0

    # Find most common mood
    mood_counts = {}
    for s in sessions:
        d = s.get("dominant", "neutral")
        mood_counts[d] = mood_counts.get(d, 0) + 1
    top_mood = max(mood_counts, key=mood_counts.get) if mood_counts else "neutral"

    return render_template(
        "history.html",
        sessions=sessions,
        total_duration_str=total_duration_str,
        avg_positivity=avg_positivity,
        top_mood=top_mood
    )


@app.route("/analytics")
@login_required
def analytics_page():
    sessions = session_mgr.list_sessions(user_id=current_user.id)
    if not sessions:
        sessions = session_mgr.list_sessions()
    return render_template("analytics.html", sessions=sessions)


@app.route("/photo_analyzer")
@login_required
def photo_analyzer():
    return render_template("photo_analyzer.html")


@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html")


# ─── Video Feed Route ──────────────────────────────────────────────────────────

def _gen_frames():
    while True:
        jpeg = detector.get_annotated_frame_jpeg()
        if jpeg:
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
        time.sleep(0.033)  # ~30 fps

@app.route("/video_feed")
def video_feed():
    return Response(_gen_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


# ─── Session REST APIs ─────────────────────────────────────────────────────────

@app.route("/api/start_session", methods=["POST"])
@login_required
def start_session():
    if session_mgr.is_active():
        return jsonify({
            "error": "Session already active",
            "session_id": session_mgr.active_session_id()
        }), 400

    data = request.get_json(silent=True) or {}
    title = data.get("title") or "Emotion Session"
    category = data.get("category") or "General"
    notes = data.get("notes") or ""

    sid = session_mgr.start_session(
        user_id=current_user.id,
        title=title,
        category=category,
        notes=notes
    )
    return jsonify({
        "session_id": sid,
        "title": title,
        "category": category,
        "started_at": datetime.now().isoformat()
    })


@app.route("/api/stop_session", methods=["POST"])
@login_required
def stop_session():
    session = session_mgr.stop_session()
    if not session:
        return jsonify({"error": "No active session"}), 400
    return jsonify(session)


@app.route("/api/sessions", methods=["GET"])
@login_required
def list_sessions():
    sessions = session_mgr.list_sessions(user_id=current_user.id)
    return jsonify(sessions)


@app.route("/api/session/<session_id>", methods=["GET", "DELETE"])
@login_required
def manage_session(session_id):
    if request.method == "DELETE":
        deleted = session_mgr.delete_session(session_id)
        if deleted:
            return jsonify({"success": True, "message": f"Session {session_id} deleted."})
        return jsonify({"error": "Session not found"}), 404

    session = session_mgr.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    log = session.get("emotion_log", [])
    distribution = compute_distribution(log)
    timeline = compute_timeline(log)
    stress = is_stress_alert(distribution)

    return jsonify({
        **session,
        "distribution": distribution,
        "timeline": timeline,
        "stress_alert": stress,
        "emotion_colors": emotion_colors(),
    })


# ─── Snapshot & Image APIs ────────────────────────────────────────────────────

@app.route("/api/snapshot", methods=["POST"])
def take_snapshot():
    import cv2
    frame = detector.get_raw_frame()
    if frame is None:
        return jsonify({"error": "No frame available"}), 503

    filename = f"snap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    filepath = os.path.join(SNAPSHOTS_DIR, filename)
    cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])

    session_mgr.add_snapshot(filename)
    return jsonify({"filename": filename, "url": f"/static/snapshots/{filename}"})


@app.route("/static/snapshots/<filename>")
def serve_snapshot(filename):
    return send_from_directory(SNAPSHOTS_DIR, filename)


@app.route("/api/snapshots", methods=["GET"])
def list_snapshots():
    files = []
    if os.path.exists(SNAPSHOTS_DIR):
        for f in sorted(os.listdir(SNAPSHOTS_DIR), reverse=True):
            if f.endswith((".jpg", ".png", ".webp")):
                files.append({"filename": f, "url": f"/static/snapshots/{f}"})
    return jsonify(files)


@app.route("/api/analyze_photo", methods=["POST"])
def analyze_photo():
    """Analyze uploaded photo for multi-face emotion recognition."""
    import cv2
    import numpy as np

    file = request.files.get("photo")
    if not file or file.filename == "":
        return jsonify({"error": "No image uploaded"}), 400

    try:
        file_bytes = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"error": "Invalid image file format"}), 400

        h, w = img.shape[:2]
        annotated, faces = detector.analyze_static_image(img)

        # Encode annotated image to base64 JPEG
        _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 92])
        b64_str = f"data:image/jpeg;base64,{base64.b64encode(buf).decode('utf-8')}"

        dominant_all = "neutral"
        if faces:
            dominant_all = faces[0].get("dominant", "neutral")

        return jsonify({
            "success": True,
            "face_count": len(faces),
            "dominant": dominant_all,
            "width": w,
            "height": h,
            "faces": faces,
            "annotated_image": b64_str
        })
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500


@app.route("/api/browser_frame", methods=["POST"])
def receive_browser_frame():
    """Receive frame sent from browser camera (HTML5 getUserMedia)."""
    data = request.get_json(silent=True) or {}
    frame_b64 = data.get("frame")
    if not frame_b64:
        return jsonify({"error": "No frame received"}), 400

    ok = detector.inject_browser_frame(frame_b64)
    return jsonify({"success": ok})


@app.route("/api/switch_camera", methods=["POST"])
@login_required
def switch_camera():
    data = request.get_json(silent=True) or {}
    cam_idx = int(data.get("camera_index", 0))
    detector.restart_camera(cam_idx)
    return jsonify({"success": True, "camera_index": cam_idx})


# ─── Profile & Settings APIs ──────────────────────────────────────────────────

@app.route("/api/profile", methods=["POST"])
@login_required
def update_profile():
    data = request.get_json(silent=True) or {}
    current_user.avatar = data.get("avatar") or current_user.avatar
    current_user.full_name = data.get("full_name", current_user.full_name)
    current_user.bio = data.get("bio", current_user.bio)
    db.session.commit()
    return jsonify({"success": True, "user": current_user.to_dict()})


@app.route("/api/change_password", methods=["POST"])
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    curr_pass = data.get("current_password", "")
    new_pass = data.get("new_password", "")

    if not current_user.check_password(curr_pass):
        return jsonify({"error": "Current password incorrect"}), 400
    if len(new_pass) < 6:
        return jsonify({"error": "New password must be at least 6 characters"}), 400

    current_user.set_password(new_pass)
    db.session.commit()
    return jsonify({"success": True, "message": "Password updated successfully"})


# ─── CSV Export APIs ──────────────────────────────────────────────────────────

@app.route("/api/export_csv/<session_id>")
def export_csv(session_id):
    """Export single session timeline emotion logs to CSV file."""
    session = session_mgr.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    log = session.get("emotion_log", [])
    output = io.StringIO()
    writer = csv.writer(output)

    # Headers
    writer.writerow([
        "Session ID", "Timestamp", "Face Index",
        "Dominant Emotion", "Happy %", "Neutral %",
        "Surprise %", "Sad %", "Angry %", "Fear %", "Disgust %"
    ])

    for entry in log:
        ts = entry.get("timestamp", "")
        for idx, face in enumerate(entry.get("faces", [])):
            dom = face.get("dominant", "")
            emos = face.get("emotions", {})
            writer.writerow([
                session_id,
                ts,
                idx + 1,
                dom,
                emos.get("happy", 0),
                emos.get("neutral", 0),
                emos.get("surprise", 0),
                emos.get("sad", 0),
                emos.get("angry", 0),
                emos.get("fear", 0),
                emos.get("disgust", 0),
            ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=session_{session_id}_data.csv"}
    )


@app.route("/api/export_all_csv")
@login_required
def export_all_csv():
    """Export summary of all recorded sessions to CSV file."""
    sessions = session_mgr.list_sessions(user_id=current_user.id)
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Session ID", "Title", "Category", "Start Time", "End Time",
        "Duration (sec)", "Dominant Emotion", "Positivity %", "Negativity %",
        "Total Frames", "Stress Alert", "Mood Text"
    ])

    for s in sessions:
        writer.writerow([
            s.get("id"),
            s.get("title", ""),
            s.get("category", "General"),
            s.get("start_time", ""),
            s.get("end_time", ""),
            s.get("duration_seconds", 0),
            s.get("dominant", "neutral"),
            s.get("positive_pct", 0),
            s.get("negative_pct", 0),
            s.get("total_frames", 0),
            "Yes" if s.get("stress_alert") else "No",
            s.get("mood_text", "")
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=faceiq_all_sessions.csv"}
    )


# ─── PDF Report Generation ────────────────────────────────────────────────────

def clean_pdf_text(text):
    if not text:
        return ""
    text = str(text)
    replacements = {
        "—": " - ",
        "–": " - ",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "•": "*",
        "…": "...",
        "😊": "",
        "😐": "",
        "😢": "",
        "😠": "",
        "😮": "",
        "😨": "",
        "🤢": ""
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    # Remove any character not encodable in latin-1
    return text.encode("latin-1", "ignore").decode("latin-1").strip()


@app.route("/api/export_pdf/<session_id>")
def export_pdf(session_id):
    from fpdf import FPDF

    session = session_mgr.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    log = session.get("emotion_log", [])
    distribution = compute_distribution(log)
    summary = session.get("summary", {})

    pdf = FPDF()
    pdf.add_page()

    # Dark background
    pdf.set_fill_color(15, 15, 35)
    pdf.rect(0, 0, 210, 297, "F")

    # Title
    pdf.set_text_color(0, 212, 255)
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(0, 15, "FaceIQ Emotion Intelligence Report", ln=True, align="C")

    # Subtitle & Session Metadata
    pdf.set_text_color(180, 180, 210)
    pdf.set_font("Helvetica", "", 10)
    category_text = clean_pdf_text(session.get("category", "General"))
    pdf.cell(0, 7, f"Session ID: #{session_id} | Category: {category_text}", ln=True, align="C")
    start_str = (session.get('start_time') or '')[:19].replace('T', ' ')
    end_str = (session.get('end_time') or '')[:19].replace('T', ' ')
    pdf.cell(0, 6, f"Period: {start_str} to {end_str}", ln=True, align="C")
    pdf.ln(6)

    # Mood Summary Box
    pdf.set_fill_color(25, 25, 55)
    pdf.rect(15, pdf.get_y(), 180, 24, "F")
    pdf.set_text_color(255, 215, 0)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(20, pdf.get_y() + 3)
    pdf.cell(0, 8, "Overall Session Mood:", ln=True)
    pdf.set_text_color(240, 240, 250)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_x(20)
    mood_desc = clean_pdf_text(summary.get("mood_text", session.get("mood_text", "Session completed.")))
    pdf.cell(0, 7, mood_desc, ln=True)
    pdf.ln(10)

    # Dominant Emotion Banner
    dom = clean_pdf_text(summary.get("dominant") or session.get("dominant") or "neutral").upper()
    pdf.set_text_color(108, 99, 255)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 9, f"Dominant Expression: {dom}", ln=True)
    pdf.ln(2)

    # Emotion Distribution Bars
    pdf.set_text_color(0, 255, 170)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 9, "Emotion Distribution Breakdown", ln=True)

    COLORS = {
        "happy": (255, 215, 0), "sad": (74, 144, 217), "angry": (231, 76, 60),
        "fear": (230, 126, 34), "disgust": (39, 174, 96),
        "surprise": (155, 89, 182), "neutral": (149, 165, 166),
    }

    for emo, pct in sorted(distribution.items(), key=lambda x: x[1], reverse=True):
        r, g, b = COLORS.get(emo, (180, 180, 180))
        bar_w = int(pct * 1.3)

        pdf.set_text_color(220, 220, 230)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(28, 7, clean_pdf_text(emo.capitalize()))

        x = pdf.get_x()
        y = pdf.get_y()
        pdf.set_fill_color(35, 35, 60)
        pdf.rect(x, y + 1, 130, 5, "F")
        pdf.set_fill_color(r, g, b)
        if bar_w > 0:
            pdf.rect(x, y + 1, min(130, bar_w), 5, "F")

        pdf.set_xy(x + 135, y)
        pdf.set_text_color(255, 215, 0)
        pdf.cell(20, 7, f"{pct:.1f}%", ln=True)

    pdf.ln(6)

    # Performance & Well-being Metrics
    pdf.set_text_color(0, 255, 170)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 9, "Key Metrics & Well-Being Summary", ln=True)
    pdf.set_text_color(210, 210, 220)
    pdf.set_font("Helvetica", "", 10)

    pos_pct = summary.get("positive_pct", session.get("positive_pct", 0))
    neg_pct = summary.get("negative_pct", session.get("negative_pct", 0))
    total_frames = summary.get("total_frames", len(log))

    pdf.cell(0, 6, f"- Total Video Frames Analyzed: {total_frames}", ln=True)
    pdf.cell(0, 6, f"- Positivity Score: {pos_pct:.1f}%", ln=True)
    pdf.cell(0, 6, f"- Tension / Stress Level: {neg_pct:.1f}%", ln=True)
    snapshots = session.get("snapshots", [])
    pdf.cell(0, 6, f"- Snapshots Recorded: {len(snapshots)}", ln=True)

    # Footer
    pdf.set_y(-22)
    pdf.set_text_color(120, 120, 150)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 10, "Generated by FaceIQ AI Vision & Emotion Intelligence Platform", align="C")

    pdf_bytes = bytes(pdf.output())
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"FaceIQ_Report_{session_id}.pdf"
    )


# ─── SocketIO Events ──────────────────────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    print(f"[SocketIO] Client connected: {request.sid}")

@socketio.on("disconnect")
def on_disconnect():
    print(f"[SocketIO] Client disconnected: {request.sid}")


# ─── Main Runner ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 65)
    print("  [FaceIQ] Real-Time Face Expression & Emotion Detection Platform")
    print("  Open in browser: http://localhost:5000")
    print("  Quick Demo Login: demo / demo123")
    print("=" * 65)
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
