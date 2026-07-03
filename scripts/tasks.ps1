param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("install", "test", "lint", "typecheck", "api", "dashboard", "pipeline")]
    [string]$Task
)

$ErrorActionPreference = "Stop"

switch ($Task) {
    "install" { python -m pip install -r requirements.txt }
    "test" { python -m pytest }
    "lint" { python -m ruff check src }
    "typecheck" { python -m mypy src }
    "api" { python -m uvicorn bazaar_mind_games.api.main:app --host 0.0.0.0 --port 8000 --reload }
    "dashboard" { python -m streamlit run src/bazaar_mind_games/dashboard/app.py }
    "pipeline" { python -m bazaar_mind_games.research.pipeline }
}
