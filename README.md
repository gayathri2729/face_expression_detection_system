# FaceIQ — Real-World Face Expression Detection System

## Quick Start

### Step 1 — Install Dependencies
Double-click `install.bat` or run in terminal:
```
python -m pip install -r requirements.txt
```

### Step 2 — Launch the App
Double-click `start.bat` or run:
```
python app.py
```

### Step 3 — Open in Browser
```
http://localhost:5000
```

---

## Project Structure

```
face expression/
├── app.py                  ← Flask app (main server)
├── emotion_detector.py     ← DeepFace + OpenCV emotion engine
├── session_manager.py      ← Session storage & management
├── analytics.py            ← Stats, charts data, mood analysis
├── requirements.txt        ← Python dependencies
├── install.bat             ← First-time install script
├── start.bat               ← App launcher
├── data/
│   └── sessions.json       ← Persisted session history (auto-created)
├── static/
│   ├── css/style.css       ← Glassmorphic dark-mode design
│   ├── js/main.js          ← Dashboard SocketIO client
│   ├── js/charts.js        ← Chart.js helpers
│   └── snapshots/          ← Captured frame images
└── templates/
    ├── index.html          ← Landing page
    ├── dashboard.html      ← Live detection dashboard
    └── analytics.html      ← Session analytics & reports
```

---

## Features

| Feature | Details |
|---|---|
| 🎭 7-Emotion AI | DeepFace detects: happy, sad, angry, fear, disgust, surprise, neutral |
| 👥 Multi-Face | Simultaneous detection for multiple people |
| 📡 Live Stream | 30fps MJPEG webcam feed with annotated overlays |
| 📊 Live Chart | Rolling 30-point emotion timeline chart |
| 🚨 Stress Alert | Banner when negative emotions > 50% |
| 📸 Snapshots | Capture & download annotated frames |
| 📄 PDF Report | Professional mood report exported as PDF |
| 🗂 History | All sessions saved to `data/sessions.json` |
| 🌓 Theme | Dark/Light mode toggle |

---

## Requirements
- Python 3.9+
- Webcam connected & allowed in browser
- Internet on first run (DeepFace downloads ~200MB model weights)

---

## Notes
- First-time emotion analysis may take 3-5 seconds as models load
- Session data persists across restarts in `data/sessions.json`
- Snapshots saved to `static/snapshots/` folder
