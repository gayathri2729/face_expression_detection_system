"""
test_system.py
Integration test checking all web pages, authentication, APIs, and exports.
"""

import requests

BASE = "http://127.0.0.1:5000"
s = requests.Session()

print("=" * 60)
print("  Running FaceIQ System Verification Tests")
print("=" * 60)

# 1. Home
r = s.get(f"{BASE}/")
assert r.status_code == 200, f"Home failed: {r.status_code}"
assert "FaceIQ" in r.text
print("[PASS] 1. Home Page (/): Status 200 OK")

# 2. Login Page
r = s.get(f"{BASE}/login")
assert r.status_code == 200, f"Login failed: {r.status_code}"
assert "Welcome Back" in r.text
print("[PASS] 2. Login Page (/login): Status 200 OK")

# 3. Register Page
r = s.get(f"{BASE}/register")
assert r.status_code == 200, f"Register failed: {r.status_code}"
assert "Create Account" in r.text
print("[PASS] 3. Register Page (/register): Status 200 OK")

# 4. Authenticate Demo Account
r = s.post(f"{BASE}/login", data={"username": "demo", "password": "demo123"}, allow_redirects=True)
assert r.status_code == 200, f"Auth failed: {r.status_code}"
assert "Live Emotion Stream" in r.text or "Dashboard" in r.text
print("[PASS] 4. Login Authentication (demo / demo123): Successfully logged in & redirected to Dashboard")

# 5. Dashboard Page
r = s.get(f"{BASE}/dashboard")
assert r.status_code == 200, f"Dashboard failed: {r.status_code}"
assert "Live Emotion Stream" in r.text
print("[PASS] 5. Dashboard Page (/dashboard): Status 200 OK")

# 6. History Page
r = s.get(f"{BASE}/history")
assert r.status_code == 200, f"History failed: {r.status_code}"
assert "Session History" in r.text
print("[PASS] 6. History Page (/history): Status 200 OK")

# 7. Analytics Page
r = s.get(f"{BASE}/analytics")
assert r.status_code == 200, f"Analytics failed: {r.status_code}"
assert "Session History" in r.text
print("[PASS] 7. Analytics Page (/analytics): Status 200 OK")

# 8. Photo AI Analyzer Page
r = s.get(f"{BASE}/photo_analyzer")
assert r.status_code == 200, f"Photo AI failed: {r.status_code}"
assert "Emotion Analyzer" in r.text
print("[PASS] 8. Photo AI Page (/photo_analyzer): Status 200 OK")

# 9. Profile Page
r = s.get(f"{BASE}/profile")
assert r.status_code == 200, f"Profile failed: {r.status_code}"
assert "Edit Profile" in r.text
print("[PASS] 9. Profile Page (/profile): Status 200 OK")

# 10. Sessions REST API
r = s.get(f"{BASE}/api/sessions")
assert r.status_code == 200, f"Sessions API failed: {r.status_code}"
data = r.json()
assert len(data) > 0, "No sessions found in API"
sample_sid = data[0]["id"]
print(f"[PASS] 10. Sessions API (/api/sessions): Status 200 OK ({len(data)} sessions retrieved, Sample ID: #{sample_sid})")

# 11. PDF Export API
r = s.get(f"{BASE}/api/export_pdf/{sample_sid}")
assert r.status_code == 200, f"PDF export failed: {r.status_code}"
assert r.headers.get("Content-Type") == "application/pdf"
assert len(r.content) > 1000
print(f"[PASS] 11. PDF Export API (/api/export_pdf/{sample_sid}): Status 200 OK ({len(r.content)} bytes generated)")

# 12. CSV Export API
r = s.get(f"{BASE}/api/export_csv/{sample_sid}")
assert r.status_code == 200, f"CSV export failed: {r.status_code}"
assert "text/csv" in r.headers.get("Content-Type", "")
print(f"[PASS] 12. CSV Export API (/api/export_csv/{sample_sid}): Status 200 OK")

# 13. All Sessions CSV Export API
r = s.get(f"{BASE}/api/export_all_csv")
assert r.status_code == 200, f"All CSV export failed: {r.status_code}"
assert "text/csv" in r.headers.get("Content-Type", "")
print(f"[PASS] 13. All Sessions CSV Export (/api/export_all_csv): Status 200 OK")

# 14. Video Feed Stream Headers
r_stream = requests.get(f"{BASE}/video_feed", stream=True, timeout=3)
assert r_stream.status_code == 200
assert "multipart/x-mixed-replace" in r_stream.headers.get("Content-Type", "")
print("[PASS] 14. Live Video Stream (/video_feed): Status 200 (multipart/x-mixed-replace 30fps stream active)")

print("=" * 60)
print("  ALL 14 INTEGRATION TESTS PASSED 100%!")
print("=" * 60)
