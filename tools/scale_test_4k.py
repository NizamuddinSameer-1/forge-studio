"""Realistic scale test: a 4K (3840x2160) source through the full hash flow.

Uses the video already sitting in app/uploads, crops it to 9:16 (the user's
actual workflow) and runs the default BALANCED profile.
"""
import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8016"
SOURCE = "1789241102_New_Project_7__1F9A111_.mp4"

# Centre 9:16 slice out of 3840x2160 (even width, centred).
CROP_W, CROP_H = 1214, 2160
CROP_X = (3840 - CROP_W) // 2


def post_json(path, payload, timeout=300):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def get_json(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.loads(r.read())


payload = {
    "filename": SOURCE,
    "trim_start": 0.0,
    "trim_end": None,
    "crop": {"enabled": True, "x": CROP_X, "y": 0, "width": CROP_W, "height": CROP_H},
    "color_grade": {"sharpen": 0.3, "brightness": 0.02, "contrast": 1.04,
                    "saturation": 1.08, "temperature": 0.04},
    "mask": {"enabled": True, "x": 60, "y": 60, "width": 240, "height": 110, "blur": 24},
    "text_layers": [{
        "id": "t1", "text": "WATCH TILL END", "x": 60, "y": 180,
        "font_family": "Impact", "font_size": 88, "color": "#FFFFFF",
        "stroke_color": "#000000", "stroke_width": 5,
        "bg_enabled": False, "bg_color": "#000000", "bg_opacity": 0.6,
    }],
    "hashing": {"enabled": True, "profile": "BALANCED", "seed": 1234, "pad": True},
}

print("4K SCALE TEST")
print(f"  source : {SOURCE} (3840x2160, 6.46s, 33.9 MB)")
print(f"  crop   : {CROP_W}x{CROP_H} at x={CROP_X} (9:16 centre slice)")
print(f"  profile: BALANCED (the default) + mask + text overlay\n", flush=True)

code, body = post_json("/api/export", payload)
print(f"export before hashing -> HTTP {code} (expected 409)")
assert code == 409, body

t_start = time.time()
code, job = post_json("/api/hash", payload)
assert code == 200, job
job_id = job["job_id"]
print(f"hash job started: {job_id}\n", flush=True)

seen, last_p, result = 0, "init", None
milestones = []
while True:
    st = get_json(f"/api/hash/{job_id}?since={seen}")
    for line in st["logs"]:
        print(f"  [{st['elapsed']:7.1f}s] {line}", flush=True)
    if st.get("progress") != last_p:
        last_p = st.get("progress")
        if last_p is not None:
            milestones.append((round(st["elapsed"], 1), last_p))
    seen = st["log_total"]
    if st["status"] in ("done", "error"):
        result = st["result"]
        print(f"\n  status={st['status']}  stage={st['stage']}  elapsed={st['elapsed']}s", flush=True)
        if st["error"]:
            print(f"  ERROR: {st['error']}", flush=True)
        break
    time.sleep(2.0)

wall = time.time() - t_start
if not result:
    raise SystemExit("no result")

print("\nRESULT")
for k in ("file_name", "profile_used", "hashing_applied", "hash_changed",
          "width", "height", "duration", "size_mb"):
    print(f"  {k:16} = {result[k]}")
print(f"  source_hash      = {result['source_hash'][:24]}...")
print(f"  output_hash      = {result['output_hash'][:24]}...")
print(f"  wall clock       = {wall:.1f}s for a 6.5s 4K clip")
print(f"  progress samples = {len(milestones)} (first {milestones[:3]}, last {milestones[-2:]})")

assert result["hashing_applied"] is True
assert result["hash_changed"] is True, "hash did not change"
assert "temp_edit" not in result["file_name"]

print("\nexport after hashing")
t0 = time.time()
code, exp = post_json("/api/export", payload)
print(f"  HTTP {code}  reused={exp.get('reused')}  in {time.time()-t0:.2f}s")
assert code == 200 and exp["reused"] is True

print(f"\nSCALE TEST PASSED - {wall:.0f}s wall clock, {len(milestones)} progress updates")
