"""Does the HASHING step preserve a freeform crop?

Runs the real /api/hash flow with deliberately non-9:16 crops on a 1280x720
source and measures the dimensions of the hashed output.
"""
import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8020"
SOURCE = "crop_probe.mp4"   # 1280x720 landscape


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


def hash_with_crop(label, crop, expect_ratio):
    payload = {
        "filename": SOURCE,
        "trim_start": 0.0,
        "trim_end": None,
        "crop": crop,
        "hashing": {"enabled": True, "profile": "SAFE", "seed": 5, "pad": False},
    }
    print(f"\n--- {label} ---")
    print(f"  crop asked for : {crop['width']}x{crop['height']} "
          f"(aspect {crop['width'] / crop['height']:.3f}) at +{crop['x']}+{crop['y']}")

    code, job = post_json("/api/hash", payload)
    if code != 200:
        print(f"  could not start job: HTTP {code} {job}")
        return None
    job_id = job["job_id"]

    seen = 0
    while True:
        st = get_json(f"/api/hash/{job_id}?since={seen}")
        seen = st["log_total"]
        if st["status"] in ("done", "error"):
            if st["error"]:
                print(f"  ERROR: {st['error']}")
                return None
            break
        time.sleep(1.5)

    r = st["result"]
    out_w, out_h = r["width"], r["height"]
    out_ratio = out_w / out_h if out_h else 0
    print(f"  hashed output  : {out_w}x{out_h} (aspect {out_ratio:.3f})")
    print(f"  file           : {r['file_name']}")

    match = abs(out_ratio - expect_ratio) < 0.02
    print(f"  {'OK   ' if match else 'WRONG'} aspect {'preserved' if match else 'CHANGED'}"
          f" (expected ~{expect_ratio:.3f}, got {out_ratio:.3f})")
    return match


results = []

# 3:1 landscape - nothing like 9:16
results.append(hash_with_crop(
    "wide 3:1 freeform crop",
    {"enabled": True, "x": 190, "y": 210, "width": 900, "height": 300},
    3.0))

# 1:3 tall freeform crop - portrait but not 9:16
results.append(hash_with_crop(
    "tall 1:3 freeform crop",
    {"enabled": True, "x": 490, "y": 60, "width": 300, "height": 600},
    0.5))

# a genuine 9:16 crop, for reference
results.append(hash_with_crop(
    "9:16 reference crop",
    {"enabled": True, "x": 440, "y": 0, "width": 405, "height": 720},
    0.5625))

print("\n" + "=" * 62)
print(f"aspect preserved in {sum(1 for r in results if r)}/{len(results)} cases")
print("=" * 62)
