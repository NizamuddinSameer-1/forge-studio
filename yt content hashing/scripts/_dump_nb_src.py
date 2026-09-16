"""Dump notebook cell sources to a text file."""
import json
import sys
from pathlib import Path

src_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
nb = json.loads(src_path.read_text(encoding="utf-8"))
parts = [f"cells: {len(nb['cells'])}\n"]
for i, c in enumerate(nb["cells"]):
    src = "".join(c.get("source", []))
    parts.append("=" * 80 + "\n")
    parts.append(
        f"CELL {i} ({c['cell_type']})  lines={src.count(chr(10))+1}  chars={len(src)}\n"
    )
    parts.append("-" * 80 + "\n")
    parts.append(src)
    parts.append("\n\n")
out_path.write_text("".join(parts), encoding="utf-8")
print(f"wrote {out_path} ({out_path.stat().st_size} bytes)")
