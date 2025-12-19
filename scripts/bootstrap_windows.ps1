python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements/windows.txt

pre-commit install
pre-commit install --hook-type pre-push

Write-Host "✅ Python env ready: .venv"
