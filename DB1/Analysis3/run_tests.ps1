param([string]$Python='C:\ProgramData\anaconda3\envs\analysis1\python.exe')
$ErrorActionPreference='Stop'
Push-Location $PSScriptRoot
try {
 & $Python -m pytest tests -q -p no:cacheprovider -W error::FutureWarning
 if($LASTEXITCODE -ne 0){throw 'Analysis3 tests failed'}
} finally {Pop-Location}
