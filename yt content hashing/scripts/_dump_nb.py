"""Dump all cell outputs/errors from a notebook (debug helper, not shipped)."""
import json
import sys

nb = json.load(open(sys.argv[1], encoding="utf-8"))
for i, c in enumerate(nb["cells"]):
    header = f"===== CELL {i + 1} ({c['cell_type']}) ====="
    print(header)
    for o in c.get("outputs", []):
        ot = o.get("output_type")
        if ot == "stream":
            print("".join(o.get("text", []))[:4000])
        elif ot == "error":
            print("ERROR:", o.get("ename"), o.get("evalue"))
            print("\n".join(o.get("traceback", []))[:4000])
        elif ot in ("execute_result", "display_data"):
            d = o.get("data", {})
            print("".join(d.get("text/plain", []))[:2000])
