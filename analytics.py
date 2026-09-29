"""
analytics.py
Compute analytics and generate timeline / distribution data from session logs.
"""

from collections import defaultdict

EMOTIONS = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]

EMOTION_COLORS = {
    "happy":    "#FFD700",
    "sad":      "#4A90D9",
    "angry":    "#E74C3C",
    "fear":     "#E67E22",
    "disgust":  "#27AE60",
    "surprise": "#9B59B6",
    "neutral":  "#95A5A6",
}


def compute_distribution(emotion_log: list) -> dict:
    """
    Returns {emotion: avg_percentage} across all log entries.
    """
    totals = defaultdict(float)
    count = 0

    for entry in emotion_log:
        for face in entry.get("faces", []):
            emos = face.get("emotions", {})
            for e in EMOTIONS:
                totals[e] += emos.get(e, 0)
            count += 1

    if count == 0:
        return {e: 0.0 for e in EMOTIONS}

    return {e: round(totals[e] / count, 1) for e in EMOTIONS}


def compute_timeline(emotion_log: list, max_points: int = 60) -> dict:
    """
    Returns Chart.js friendly timeline data.
    {
        labels: [timestamps],
        datasets: [{label: emotion, data: [values], borderColor: color}]
    }
    """
    if not emotion_log:
        return {"labels": [], "datasets": []}

    # Downsample if needed
    step = max(1, len(emotion_log) // max_points)
    sampled = emotion_log[::step]

    labels = []
    series = defaultdict(list)

    for entry in sampled:
        ts = entry.get("timestamp", "")
        # Keep only HH:MM:SS
        time_label = ts[11:19] if len(ts) >= 19 else ts
        labels.append(time_label)

        # Average across faces
        face_list = entry.get("faces", [])
        if face_list:
            avg = {}
            for e in EMOTIONS:
                avg[e] = round(sum(f.get("emotions", {}).get(e, 0) for f in face_list) / len(face_list), 1)
        else:
            avg = {e: 0.0 for e in EMOTIONS}

        for e in EMOTIONS:
            series[e].append(avg[e])

    datasets = []
    for e in EMOTIONS:
        datasets.append({
            "label": e.capitalize(),
            "data": series[e],
            "borderColor": EMOTION_COLORS[e],
            "backgroundColor": EMOTION_COLORS[e] + "33",
            "tension": 0.4,
            "fill": False,
            "pointRadius": 2,
        })

    return {"labels": labels, "datasets": datasets}


def is_stress_alert(distribution: dict, threshold: float = 50.0) -> bool:
    """Returns True if cumulative negative emotions exceed threshold %."""
    neg = distribution.get("angry", 0) + distribution.get("fear", 0) \
        + distribution.get("sad", 0) + distribution.get("disgust", 0)
    return neg > threshold


def emotion_colors():
    return EMOTION_COLORS
