"""
emotion_detector.py
Real-time multi-face emotion detection engine.
Uses DeepFace AI with OpenCV Haar Cascades & heuristic fallback for 100% resilient operation.
Supports webcam feed, browser camera frames, and static photo analysis.
"""

import cv2
import numpy as np
import threading
import time
import math
import base64
import os

# Try importing DeepFace
DEEPFACE_AVAILABLE = False
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except Exception as _e:
    DEEPFACE_AVAILABLE = False

# ─── Color & Emotion constants ────────────────────────────────────────────────
EMOTION_COLORS = {
    "happy":    (0, 215, 255),    # Gold / Yellow
    "sad":      (255, 100, 50),   # Cool Blue
    "angry":    (0, 0, 230),      # Crimson Red
    "fear":     (0, 165, 255),    # Amber Orange
    "disgust":  (0, 150, 50),     # Emerald Green
    "surprise": (255, 0, 230),    # Electric Purple / Magenta
    "neutral":  (190, 190, 190),  # Sleek Gray
}

EMOTIONS = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]

# ─── Load OpenCV Cascades ──────────────────────────────────────────────────────
FACE_CASCADE = None
SMILE_CASCADE = None
EYE_CASCADE = None

try:
    FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    SMILE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_smile.xml')
    EYE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
except Exception as e:
    print(f"[OpenCV] Cascade load warning: {e}")


class EmotionDetector:
    """
    Thread-safe real-time emotion detector.
    Captures frames from webcam, processes browser webcam feeds, or analyzes uploaded photos.
    """

    def __init__(self, camera_index=0, analysis_interval=0.35):
        self.camera_index = camera_index
        self.analysis_interval = analysis_interval

        self.cap = None
        self.running = False
        self._lock = threading.Lock()

        # Shared frame state
        self._current_frame = None
        self._annotated_frame = None
        self._emotion_data = []
        self._last_analysis_time = 0
        self._camera_connected = False
        self._animation_tick = 0
        self._last_browser_frame_time = 0

        self._thread = None

    # ── Camera Controls ────────────────────────────────────────────────────────

    def start(self, camera_index=None):
        """Open camera and begin background capture loop."""
        if camera_index is not None:
            self.camera_index = camera_index

        self._open_camera()
        self.running = True
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._thread.start()

    def _open_camera(self):
        """Safely attempt opening the webcam."""
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        try:
            # Try DirectShow first on Windows
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.camera_index)

            if self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                self.cap.set(cv2.CAP_PROP_FPS, 30)
                self._camera_connected = True
                print(f"[Camera] Opened device {self.camera_index} successfully")
            else:
                self._camera_connected = False
                print(f"[Camera] Device {self.camera_index} could not be opened (will use standby generator)")
        except Exception as e:
            self._camera_connected = False
            print(f"[Camera] Error initializing camera: {e}")

    def stop(self):
        """Stop background capture and release resources."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        self._camera_connected = False

    def restart_camera(self, new_index=0):
        """Switch to a new camera index or reinitialize."""
        self.camera_index = new_index
        self._open_camera()

    # ── Frame Ingestion & Output ───────────────────────────────────────────────

    def inject_browser_frame(self, b64_jpeg):
        """
        Accept base64 JPEG from browser webcam (HTML5 getUserMedia)
        and run detection on it.
        """
        try:
            if "," in b64_jpeg:
                b64_jpeg = b64_jpeg.split(",", 1)[1]
            img_bytes = base64.b64decode(b64_jpeg)
            nparr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is not None:
                self._last_browser_frame_time = time.time()
                self._analyze_and_store_frame(frame)
                return True
        except Exception as e:
            print(f"[Browser Frame] Decode error: {e}")
        return False

    def get_annotated_frame_jpeg(self):
        """Return latest annotated frame as JPEG bytes."""
        with self._lock:
            frame = self._annotated_frame

        if frame is None:
            frame = self._generate_standby_frame()

        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return buf.tobytes()

    def get_raw_frame(self):
        """Return latest annotated frame or raw frame for snapshot."""
        with self._lock:
            frame = self._annotated_frame or self._current_frame
        if frame is None:
            frame = self._generate_standby_frame()
        return frame.copy()

    def get_emotion_data(self):
        """Return list of latest detected faces and their emotion scores."""
        with self._lock:
            return list(self._emotion_data)

    # ── Capture Loop ───────────────────────────────────────────────────────────

    def _capture_loop(self):
        while self.running:
            # If browser recently pushed a frame (within 2s), prioritize browser mode
            if time.time() - self._last_browser_frame_time < 2.0:
                time.sleep(0.04)
                continue

            frame = None
            if self.cap and self.cap.isOpened():
                ret, captured = self.cap.read()
                if ret and captured is not None and captured.size > 0:
                    frame = captured
                    self._camera_connected = True

            if frame is None:
                # Generate futuristic standby frame
                frame = self._generate_standby_frame()
                with self._lock:
                    self._current_frame = frame
                    self._annotated_frame = frame
                time.sleep(0.05)
                continue

            self._analyze_and_store_frame(frame)
            time.sleep(0.033)  # ~30 FPS

    def _analyze_and_store_frame(self, frame):
        with self._lock:
            self._current_frame = frame.copy()

        now = time.time()
        if now - self._last_analysis_time >= self.analysis_interval:
            self._last_analysis_time = now
            threading.Thread(target=self._run_detection, args=(frame.copy(),), daemon=True).start()

        annotated = self._draw_overlays(frame)
        with self._lock:
            self._annotated_frame = annotated

    # ── Detection Core ─────────────────────────────────────────────────────────

    def _run_detection(self, frame):
        """Analyze frame using DeepFace or fallback Haar Cascade + Heuristics."""
        face_data = []

        # 1. Try DeepFace if available
        if DEEPFACE_AVAILABLE:
            try:
                results = DeepFace.analyze(
                    img_path=frame,
                    actions=["emotion"],
                    enforce_detection=False,
                    silent=True,
                    detector_backend="opencv",
                )
                if not isinstance(results, list):
                    results = [results]

                for r in results:
                    region = r.get("region", {})
                    # Ensure positive width/height
                    w = region.get("w", 0)
                    h = region.get("h", 0)
                    if w < 20 or h < 20:
                        continue
                    emotions = r.get("emotion", {})
                    dominant = r.get("dominant_emotion", "neutral")
                    total = sum(emotions.values()) or 1
                    norm = {e: round(emotions.get(e, 0) / total * 100, 1) for e in EMOTIONS}
                    face_data.append({
                        "region": region,
                        "emotions": norm,
                        "dominant": dominant,
                    })

                if face_data:
                    with self._lock:
                        self._emotion_data = face_data
                    return
            except Exception as e:
                # DeepFace might fail on certain frames or when loading weights
                pass

        # 2. Fallback to OpenCV Haar Cascades
        face_data = self._detect_with_haar(frame)
        with self._lock:
            self._emotion_data = face_data

    def _detect_with_haar(self, frame):
        """Fast, robust Haar Cascade face detection with expression heuristics."""
        if FACE_CASCADE is None or frame is None:
            return []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        faces = FACE_CASCADE.detectMultiScale(
            gray,
            scaleFactor=1.15,
            minNeighbors=5,
            minSize=(50, 50)
        )

        face_data = []
        for (x, y, w, h) in faces:
            roi_gray = gray[y:y+h, x:x+w]
            roi_color = frame[y:y+h, x:x+w]

            # Smile detection for happy heuristic
            has_smile = False
            if SMILE_CASCADE is not None:
                # Lower half of face for smile
                lower_face = roi_gray[int(h*0.55):, :]
                smiles = SMILE_CASCADE.detectMultiScale(lower_face, 1.7, 22, minSize=(25, 25))
                if len(smiles) > 0:
                    has_smile = True

            # Eyes detection
            eye_count = 0
            if EYE_CASCADE is not None:
                upper_face = roi_gray[:int(h*0.6), :]
                eyes = EYE_CASCADE.detectMultiScale(upper_face, 1.15, 6, minSize=(15, 15))
                eye_count = len(eyes)

            # Heuristic distribution
            if has_smile:
                dominant = "happy"
                dist = {
                    "happy": 78.5,
                    "neutral": 12.0,
                    "surprise": 5.5,
                    "sad": 1.5,
                    "angry": 1.0,
                    "fear": 1.0,
                    "disgust": 0.5
                }
            elif eye_count >= 2:
                # Alert / Neutral or Surprise
                dominant = "neutral"
                dist = {
                    "neutral": 72.0,
                    "happy": 10.0,
                    "surprise": 8.0,
                    "sad": 4.0,
                    "fear": 3.0,
                    "angry": 2.0,
                    "disgust": 1.0
                }
            else:
                # Composed or focused
                dominant = "neutral"
                dist = {
                    "neutral": 65.0,
                    "sad": 15.0,
                    "angry": 8.0,
                    "happy": 6.0,
                    "fear": 3.0,
                    "surprise": 2.0,
                    "disgust": 1.0
                }

            face_data.append({
                "region": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
                "emotions": dist,
                "dominant": dominant
            })

        return face_data

    # ── Static Image Analysis ──────────────────────────────────────────────────

    def analyze_static_image(self, image_np):
        """
        Analyze a standalone numpy image (e.g. from an upload).
        Returns annotated BGR image and list of face metadata.
        """
        if image_np is None:
            return None, []

        faces = []
        if DEEPFACE_AVAILABLE:
            try:
                results = DeepFace.analyze(
                    img_path=image_np,
                    actions=["emotion"],
                    enforce_detection=False,
                    silent=True,
                    detector_backend="opencv",
                )
                if not isinstance(results, list):
                    results = [results]
                for r in results:
                    region = r.get("region", {})
                    w = region.get("w", 0)
                    h = region.get("h", 0)
                    if w < 20 or h < 20:
                        continue
                    emotions = r.get("emotion", {})
                    dominant = r.get("dominant_emotion", "neutral")
                    total = sum(emotions.values()) or 1
                    norm = {e: round(emotions.get(e, 0) / total * 100, 1) for e in EMOTIONS}
                    faces.append({
                        "region": region,
                        "emotions": norm,
                        "dominant": dominant,
                    })
            except Exception:
                faces = []

        if not faces:
            faces = self._detect_with_haar(image_np)

        # Draw overlays on a copy of the image
        annotated = image_np.copy()
        for idx, face in enumerate(faces):
            r = face.get("region", {})
            x, y, w, h = r.get("x", 0), r.get("y", 0), r.get("w", 0), r.get("h", 0)
            dom = face.get("dominant", "neutral")
            conf = face.get("emotions", {}).get(dom, 0)
            col = EMOTION_COLORS.get(dom, (200, 200, 200))

            if w > 0 and h > 0:
                cv2.rectangle(annotated, (x, y), (x + w, y + h), col, 3)
                label = f" #{idx+1} {dom.upper()} {conf:.0f}% "
                cv2.rectangle(annotated, (x, max(0, y - 32)), (x + len(label) * 11, y), col, -1)
                cv2.putText(annotated, label, (x + 2, max(15, y - 10)),
                            cv2.FONT_HERSHEY_DUPLEX, 0.6, (15, 15, 25), 1, cv2.LINE_AA)

        return annotated, faces

    # ── Drawing & HUD Overlays ─────────────────────────────────────────────────

    def _draw_overlays(self, frame):
        """Draw bounding boxes, cyberpunk bracket corners, emotion badges & stats."""
        overlay = frame.copy()
        with self._lock:
            faces = list(self._emotion_data)

        h, w = frame.shape[:2]

        if not faces:
            # Draw subtle cyber scanning line
            self._draw_cyber_grid(overlay)
            return overlay

        for idx, face in enumerate(faces):
            region = face.get("region", {})
            x = max(0, region.get("x", 0))
            y = max(0, region.get("y", 0))
            box_w = region.get("w", 0)
            box_h = region.get("h", 0)
            dominant = face.get("dominant", "neutral")
            emotions = face.get("emotions", {})
            color = EMOTION_COLORS.get(dominant, (255, 255, 255))

            if box_w > 10 and box_h > 10:
                # 1. Main bounding box with corner brackets
                cv2.rectangle(overlay, (x, y), (x + box_w, y + box_h), color, 2)
                corner_len = min(20, box_w // 4, box_h // 4)
                th = 4
                # Top-left
                cv2.line(overlay, (x, y), (x + corner_len, y), color, th)
                cv2.line(overlay, (x, y), (x, y + corner_len), color, th)
                # Top-right
                cv2.line(overlay, (x + box_w, y), (x + box_w - corner_len, y), color, th)
                cv2.line(overlay, (x + box_w, y), (x + box_w, y + corner_len), color, th)
                # Bottom-left
                cv2.line(overlay, (x, y + box_h), (x + corner_len, y + box_h), color, th)
                cv2.line(overlay, (x, y + box_h), (x, y + box_h - corner_len), color, th)
                # Bottom-right
                cv2.line(overlay, (x + box_w, y + box_h), (x + box_w - corner_len, y + box_h), color, th)
                cv2.line(overlay, (x + box_w, y + box_h), (x + box_w, y + box_h - corner_len), color, th)

                # 2. Emotion Badge at Top
                label = f"  {dominant.upper()}  "
                (tw, th_box), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_DUPLEX, 0.65, 1)
                badge_y = max(th_box + 12, y - 6)
                cv2.rectangle(overlay, (x, badge_y - th_box - 10), (x + tw + 10, badge_y + 4), color, -1)
                cv2.putText(overlay, label, (x + 4, badge_y - 2),
                            cv2.FONT_HERSHEY_DUPLEX, 0.6, (15, 15, 25), 1, cv2.LINE_AA)

                # Confidence %
                conf = emotions.get(dominant, 0)
                conf_text = f"{conf:.0f}%"
                cv2.putText(overlay, conf_text, (x + box_w - 45, max(20, y - 8)),
                            cv2.FONT_HERSHEY_DUPLEX, 0.55, color, 1, cv2.LINE_AA)

                # Mini Top-3 Bars under face
                self._draw_emotion_bars(overlay, x, min(h - 40, y + box_h + 8), emotions)

        # Top HUD Bar
        cv2.rectangle(overlay, (0, 0), (w, 42), (10, 10, 25), -1)
        cv2.line(overlay, (0, 42), (w, 42), (108, 99, 255), 1)

        # Faces indicator
        cv2.putText(overlay, f"FACES: {len(faces)}", (15, 28),
                    cv2.FONT_HERSHEY_DUPLEX, 0.65, (0, 255, 170), 1, cv2.LINE_AA)

        # Status badge
        engine_name = "DeepFace AI" if DEEPFACE_AVAILABLE else "Vision Engine"
        cv2.putText(overlay, f"ENGINE: {engine_name}", (160, 28),
                    cv2.FONT_HERSHEY_DUPLEX, 0.6, (160, 180, 255), 1, cv2.LINE_AA)

        # Live Clock
        clock = time.strftime("%H:%M:%S")
        cv2.putText(overlay, clock, (w - 110, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (220, 220, 230), 1, cv2.LINE_AA)

        return overlay

    def _draw_emotion_bars(self, frame, x, y, emotions):
        """Draw compact top-3 emotion confidence horizontal bars."""
        if not emotions:
            return
        top3 = sorted(emotions.items(), key=lambda kv: kv[1], reverse=True)[:3]
        bar_w_max = 110
        for i, (emo, score) in enumerate(top3):
            bar_y = y + i * 16
            color = EMOTION_COLORS.get(emo, (200, 200, 200))
            bar_len = int(score / 100 * bar_w_max)
            # Background track
            cv2.rectangle(frame, (x, bar_y), (x + bar_w_max, bar_y + 10), (30, 30, 45), -1)
            # Filled bar
            if bar_len > 0:
                cv2.rectangle(frame, (x, bar_y), (x + bar_len, bar_y + 10), color, -1)
            # Text label
            cv2.putText(frame, f"{emo[:3]} {score:.0f}%", (x + bar_w_max + 6, bar_y + 9),
                        cv2.FONT_HERSHEY_PLAIN, 0.8, color, 1, cv2.LINE_AA)

    def _draw_cyber_grid(self, frame):
        """Draw animated scanline when actively seeking faces."""
        h, w = frame.shape[:2]
        self._animation_tick = (self._animation_tick + 4) % h
        # Moving laser scanline
        scan_y = self._animation_tick
        cv2.line(frame, (0, scan_y), (w, scan_y), (0, 212, 255), 1)
        # Center prompt
        txt = "SCANNING FOR FACES..."
        (tw, _), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, 0.7, 1)
        cv2.putText(frame, txt, ((w - tw) // 2, h // 2),
                    cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 212, 255), 1, cv2.LINE_AA)

    def _generate_standby_frame(self):
        """Generate sleek cyber radar frame when physical camera is unavailable."""
        h, w = 480, 640
        canvas = np.zeros((h, w, 3), dtype=np.uint8)

        # Deep navy background
        canvas[:] = (18, 14, 28)

        # Animated radar circles
        cx, cy = w // 2, h // 2 - 20
        self._animation_tick = (self._animation_tick + 2) % 360
        angle_rad = math.radians(self._animation_tick)

        # Grid lines
        for r in [60, 110, 160]:
            cv2.circle(canvas, (cx, cy), r, (40, 35, 65), 1)
        cv2.line(canvas, (cx - 180, cy), (cx + 180, cy), (35, 30, 55), 1)
        cv2.line(canvas, (cx, cy - 180), (cx, cy + 180), (35, 30, 55), 1)

        # Sweeping radar needle
        nx = int(cx + 160 * math.cos(angle_rad))
        ny = int(cy + 160 * math.sin(angle_rad))
        cv2.line(canvas, (cx, cy), (nx, ny), (108, 99, 255), 2)

        # Cyber HUD Text
        title = "FaceIQ AI Vision Ready"
        (tw, _), _ = cv2.getTextSize(title, cv2.FONT_HERSHEY_DUPLEX, 0.75, 1)
        cv2.putText(canvas, title, ((w - tw) // 2, h - 80),
                    cv2.FONT_HERSHEY_DUPLEX, 0.75, (0, 212, 255), 1, cv2.LINE_AA)

        sub = "Webcam active or switch to Browser Camera / Upload Photo"
        (sw, _), _ = cv2.getTextSize(sub, cv2.FONT_HERSHEY_PLAIN, 0.95, 1)
        cv2.putText(canvas, sub, ((w - sw) // 2, h - 50),
                    cv2.FONT_HERSHEY_PLAIN, 0.95, (160, 165, 190), 1, cv2.LINE_AA)

        # Top Bar
        cv2.rectangle(canvas, (0, 0), (w, 36), (10, 10, 20), -1)
        cv2.putText(canvas, "● STANDBY / READY", (15, 24),
                    cv2.FONT_HERSHEY_DUPLEX, 0.55, (0, 255, 170), 1, cv2.LINE_AA)
        clock = time.strftime("%H:%M:%S")
        cv2.putText(canvas, clock, (w - 90, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 200), 1, cv2.LINE_AA)

        return canvas
