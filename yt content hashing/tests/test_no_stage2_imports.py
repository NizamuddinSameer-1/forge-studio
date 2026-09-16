import ast
from pathlib import Path


def test_package_has_no_stage2_module():
    root = Path(__file__).resolve().parents[1] / "v7_pipeline"
    assert not (root / "stage2.py").exists()


def test_no_forbidden_imports():
    root = Path(__file__).resolve().parents[1] / "v7_pipeline"
    forbidden = {"stage2", "meta_data_hashing"}
    for py in root.glob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    assert n.name.split(".")[0] not in forbidden
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden
