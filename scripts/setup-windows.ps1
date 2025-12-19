py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements\windows.txt
Write-Host "✅ Done. Activate later with: .\.venv\Scripts\Activate.ps1"
