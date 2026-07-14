from __future__ import annotations

import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
BACKEND_PACKAGES = {
    "api",
    "backtest",
    "features",
    "ingestion",
    "integrations",
    "journal",
    "labels",
    "models",
    "rules",
    "services",
    "utils",
}


def test_every_backend_module_imports() -> None:
    failures: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        relative = path.relative_to(SRC)
        if relative.parts[0] not in BACKEND_PACKAGES or path.name == "__init__.py":
            continue
        module_name = ".".join(relative.with_suffix("").parts)
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - assertion reports the module and error
            failures.append(f"{module_name}: {type(exc).__name__}: {exc}")
    assert not failures, "Backend import failures:\n" + "\n".join(failures)


def test_only_one_market_router_implementation_exists() -> None:
    route_files = sorted(path.name for path in (SRC / "api").glob("routes_market*.py"))
    assert route_files == ["routes_market.py"]


def test_retired_rule_modules_are_removed() -> None:
    assert not (SRC / "rules" / "confluence_engine.py").exists()
    assert not (SRC / "rules" / "trap_detector.py").exists()
