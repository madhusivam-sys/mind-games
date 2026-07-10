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
    "api" { $env:PYTHONPATH = "src"; python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload }
    "dashboard" { $env:PYTHONPATH = "src"; python -m streamlit run src/dashboard/app.py }
    "pipeline" { python run_app.py test }
}
