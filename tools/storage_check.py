"""Safety-focused test for the storage endpoints.

Deliberately does NOT exercise the bulk-delete path against the real folders -
that would destroy the user's files. Instead it verifies the guards, the age
filter (using a cutoff that matches nothing), single-file delete, and that every
pre-existing file is still present afterwards.
"""
import json
import os
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8021"
ROOT = r"C:\Users\lenovo\OneDrive\Desktop\Custom editing software"
UPLOADS = os.path.join(ROOT, "app", "uploads")
OUTPUTS = os.path.join(ROOT, "app", "outputs")

FAILURES = []


def check(label, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))
    if not cond:
        FAILURES.append(label)


def req(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method=method)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def snapshot():
    out = {}
    for d in (UPLOADS, OUTPUTS):
        out[d] = sorted(f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f)))
    return out


print("STORAGE ENDPOINT TEST\n")

before = snapshot()
print(f"pre-existing: {len(before[UPLOADS])} uploads, {len(before[OUTPUTS])} outputs")

# --- create throwaway files to delete -------------------------------------
probe_a = os.path.join(UPLOADS, "zz_storage_probe_a.mp4")
probe_b = os.path.join(OUTPUTS, "zz_storage_probe_b.mp4")
for p in (probe_a, probe_b):
    with open(p, "wb") as f:
        f.write(b"\0" * (512 * 1024))   # 0.5 MB

print("\n1. GET /api/storage lists both folders")
code, data = req("GET", "/api/storage")
check("200", code == 200, str(code))
names_up = [i["name"] for i in data["uploads"]]
names_out = [i["name"] for i in data["outputs"]]
check("probe upload listed", "zz_storage_probe_a.mp4" in names_up)
check("probe output listed", "zz_storage_probe_b.mp4" in names_out)
check("totals present", isinstance(data["uploads_total_mb"], (int, float)),
      f"uploads {data['uploads_total_mb']} MB, outputs {data['outputs_total_mb']} MB")
print(f"   totals: uploads {data['uploads_total_mb']} MB / outputs {data['outputs_total_mb']} MB")
print(f"   in_use: {data['in_use']}")

print("\n2. path traversal must be rejected")
for bad in ["../requirements.txt", "..%2Frequirements.txt", "sub/dir.mp4", "..\\win.ini"]:
    code, body = req("DELETE", f"/api/storage/uploads/{bad}")
    check(f"rejected {bad!r}", code in (400, 404), f"HTTP {code}")

print("\n3. unknown kind must be rejected")
code, body = req("DELETE", "/api/storage/secrets/x.mp4")
check("rejected kind=secrets", code == 400, f"HTTP {code} {body.get('detail')}")
code, body = req("POST", "/api/storage/clear", {"kind": "secrets", "older_than_hours": 0})
check("rejected clear kind=secrets", code == 400, f"HTTP {code}")

print("\n4. clear with an age filter that matches nothing deletes nothing")
# 200000 hours ~= 22 years; no file is that old, so everything is skipped.
code, body = req("POST", "/api/storage/clear", {"kind": "all", "older_than_hours": 200000})
check("200", code == 200, str(code))
check("deleted nothing", body.get("deleted_count") == 0, f"deleted_count={body.get('deleted_count')}")
check("skipped everything", body.get("skipped_count", 0) >= 2, f"skipped={body.get('skipped_count')}")
print(f"   deleted={body.get('deleted_count')} skipped={body.get('skipped_count')} freed={body.get('freed_mb')} MB")
mid = snapshot()
check("uploads unchanged by the filtered clear", mid[UPLOADS] == sorted(before[UPLOADS] + ["zz_storage_probe_a.mp4"]))
check("outputs unchanged by the filtered clear", mid[OUTPUTS] == sorted(before[OUTPUTS] + ["zz_storage_probe_b.mp4"]))

print("\n5. delete one file")
code, body = req("DELETE", "/api/storage/uploads/zz_storage_probe_a.mp4")
check("200", code == 200, str(code))
check("freed about 0.5 MB", abs(body.get("freed_mb", 0) - 0.5) < 0.05, f"freed {body.get('freed_mb')} MB")
check("file gone from disk", not os.path.exists(probe_a))

print("\n6. deleting a missing file gives 404")
code, body = req("DELETE", "/api/storage/uploads/zz_storage_probe_a.mp4")
check("404", code == 404, f"HTTP {code}")

print("\n7. clean up the remaining probe")
code, body = req("DELETE", "/api/storage/outputs/zz_storage_probe_b.mp4")
check("200", code == 200, str(code))
check("file gone", not os.path.exists(probe_b))

print("\n8. every pre-existing file must still be here")
after = snapshot()
check("uploads intact", after[UPLOADS] == before[UPLOADS],
      f"{len(after[UPLOADS])} vs {len(before[UPLOADS])}")
check("outputs intact", after[OUTPUTS] == before[OUTPUTS],
      f"{len(after[OUTPUTS])} vs {len(before[OUTPUTS])}")
for d in (UPLOADS, OUTPUTS):
    for f in before[d]:
        if f not in after[d]:
            print(f"   !! LOST: {f}")

print("\n" + "=" * 58)
print("ALL STORAGE CHECKS PASSED" if not FAILURES else f"FAILURES: {FAILURES}")
print("=" * 58)
if FAILURES:
    raise SystemExit(1)
