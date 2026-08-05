$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
python -m pip install -r requirements.txt
python book-assembler.py
