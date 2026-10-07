param([string]$Python = 'C:\ProgramData\anaconda3\envs\analysis1\python.exe')
$ErrorActionPreference = 'Stop'
$env:OMP_NUM_THREADS = '1'
foreach ($testDirectory in @('Analysis1','Analysis2','Analysis3','.')) {
    Push-Location (Join-Path $PSScriptRoot $testDirectory)
    try {
        & $Python -m pytest tests -q -p no:cacheprovider -W error::FutureWarning
        if ($LASTEXITCODE -ne 0) { throw "Tests failed: $testDirectory" }
    } finally { Pop-Location }
}
