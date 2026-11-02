# Gera o executável (PyInstaller) e o instalador (Inno Setup).
# Uso: .\build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$versao = python -c "import baixa; print(baixa.__version__)"
$repositorio = python -c "import baixa; print(baixa.REPOSITORIO)"
Write-Host "== baixa $versao ($repositorio) =="

if (-not (Test-Path build\baixa.ico)) { python build\gerar_icone.py }
python build\gerar_versao_exe.py | Out-Null

# O antivírus às vezes trava arquivos do build anterior. Renomear funciona mesmo assim:
# tira a pasta do caminho e tenta apagar as sobras antigas sem interromper o build.
if (Test-Path dist\BaixaYoutube) {
    New-Item -ItemType Directory -Force build\tmp\lixo | Out-Null
    Move-Item dist\BaixaYoutube "build\tmp\lixo\BaixaYoutube-$(Get-Date -Format yyyyMMddHHmmss)"
}
Get-ChildItem build\tmp\lixo -Directory -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }

Write-Host "== PyInstaller =="
python -m PyInstaller build\BaixaYoutube.spec --noconfirm --distpath dist --workpath build\tmp
if ($LASTEXITCODE) { throw "PyInstaller falhou" }

$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 não encontrado. Instale com: winget install JRSoftware.InnoSetup" }

Write-Host "== Inno Setup =="
& $iscc /Q "/DVersao=$versao" "/DRepositorio=$repositorio" instalador\baixa.iss
if ($LASTEXITCODE) { throw "Inno Setup falhou" }

Write-Host "`nPronto:"
Write-Host "  Executável: dist\BaixaYoutube\BaixaYoutube.exe"
Write-Host "  Instalador: dist\BaixaYoutube-Setup-$versao.exe"
