"""End-to-end check for Forge Studio.

Run the studio first, then:

    python tools/smoke_test.py            # assumes http://127.0.0.1:8000
    python tools/smoke_test.py 8010       # or a custom port

It drives the real HTTP surface: upload -> refuse-export-before-hash ->
hash job -> poll -> reuse-on-export -> staleness guard -> download.
Exits non-zero on the first failure.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

PORT = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("FORGE_PORT", "8000")
BASE = f"http://127.0.0.1:{PORT}"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "app", "uploads", "test_sample.mp4")
PROFILE = "SAFE"  # fastest profile; keeps the check under a couple of minutes


def post_json(path, payload):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def get_json(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.loads(r.read())


def upload(path):
    boundary = uuid.uuid4().hex
    with open(path, "rb") as f:
        content = f.read()
    name = os.path.basename(path)
    body = b"".join([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'.encode(),
        b"Content-Type: video/mp4\r\n\r\n",
        content,
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    req = urllib.request.Request(
        BASE + "/api/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def check(label, condition, detail=""):
    mark = "PASS" if condition else "FAIL"
    print(f"  [{mark}] {label}" + (f" - {detail}" if detail else ""), flush=True)
    if not condition:
        raise SystemExit(f"FAILED: {label}")


if not os.path.exists(SRC):
    raise SystemExit(f"Missing test video: {SRC}")

print(f"Forge Studio smoke test against {BASE}\n", flush=True)

print("1. upload")
meta = upload(SRC)
print(f"  {meta['filename']}  {meta['width']}x{meta['height']}  {meta['duration']}s  {meta['size_mb']}MB")

payload = {
    "filename": meta["filename"],
    "trim_start": 0.0,
    "trim_end": None,
    "crop": {"enabled": True, "x": 0, "y": 0, "width": 1080, "height": 1920},
    "color_grade": {"sharpen": 0.4, "brightness": 0.03, "contrast": 1.05,
                    "saturation": 1.1, "temperature": 0.05},
    "mask": {"enabled": False},
    "text_layers": [{
        "id": "t1", "text": "UNIQUE HOOK", "x": 40, "y": 120,
        "font_family": "Impact", "font_size": 64, "color": "#FFFFFF",
        "stroke_color": "#000000", "stroke_width": 4,
        "bg_enabled": False, "bg_color": "#000000", "bg_opacity": 0.6,
    }],
    "hashing": {"enabled": True, "profile": PROFILE, "seed": 42, "pad": True},
}

print("\n2. export before hashing must be refused")
code, body = post_json("/api/export", payload)
check("export refused with 409", code == 409, str(body.get("detail"))[:70])

print("\n3. run the hashing job")
code, job = post_json("/api/hash", payload)
check("hash job accepted", code == 200, str(job.get("detail"))[:70])
job_id = job["job_id"]
print(f"  job_id={job_id}")

print("\n4. poll")
seen, result, last_p = 0, None, "init"
deadline = time.time() + 900
while time.time() < deadline:
    st = get_json(f"/api/hash/{job_id}?since={seen}")
    for line in st["logs"]:
        print(f"  [{st['elapsed']:6.1f}s] {line}")
    if st.get("progress") != last_p:
        print(f"  [{st['elapsed']:6.1f}s] ...progress {st.get('progress')}%")
        last_p = st.get("progress")
    seen = st["log_total"]
    if st["status"] in ("done", "error"):
        result = st["result"]
        check("job finished without error", st["status"] == "done", str(st["error"])[:120])
        break
    time.sleep(1.0)
else:
    raise SystemExit("FAILED: job did not finish within 15 minutes")

print("\n5. hashing actually happened")
check("hashing applied", result["hashing_applied"] is True)
check("SHA-256 changed", result["hash_changed"] is True)
check("no temp name leaked into the filename", "temp_edit" not in result["file_name"],
      result["file_name"])
print(f"  {result['file_name']}  {result['width']}x{result['height']}  {result['size_mb']}MB")

print("\n6. export after hashing reuses the hashed file")
t0 = time.time()
code, exp = post_json("/api/export", payload)
check("export succeeded", code == 200, str(exp.get("detail"))[:70])
check("export reused the hashed render", exp.get("reused") is True)
check("same file returned", exp["file_name"] == result["file_name"])
print(f"  took {time.time() - t0:.2f}s")

print("\n7. changed settings require a re-hash")
changed = json.loads(json.dumps(payload))
changed["hashing"]["profile"] = "AGGRESSIVE"
code, body = post_json("/api/export", changed)
check("stale config refused with 409", code == 409, str(body.get("detail"))[:70])

print("\n8. download endpoint")
with urllib.request.urlopen(BASE + exp["download_url"], timeout=120) as r:
    blob = r.read()
check("download served the file", r.status == 200 and len(blob) > 1000,
      f"{len(blob) / 1024:.1f} KB")

print("\n" + "=" * 60)
print("ALL CHECKS PASSED")
print("=" * 60)
