param(
    [ValidateSet('initialize','analysis1','analysis2','analysis3','scan','watch','export','status')]
    [string]$Command = 'scan',
    [string]$Period,
    [string]$Month,
    [int]$Interval = 60,
    [string]$Python = 'C:\ProgramData\anaconda3\envs\analysis1\python.exe'
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Python)) { throw "Python not found: $Python" }
if (-not $env:OMP_NUM_THREADS) { $env:OMP_NUM_THREADS = '1' }
$runnerArgs = @((Join-Path $PSScriptRoot 'run_db1.py'), $Command)
if ($Period) { $runnerArgs += @('--period', $Period) }
if ($Month) { $runnerArgs += @('--month', $Month) }
if ($Command -eq 'watch') { $runnerArgs += @('--interval', "$Interval") }
Push-Location $PSScriptRoot
try {
    & $Python @runnerArgs
    if ($LASTEXITCODE -ne 0) { throw "DB1 command failed ($LASTEXITCODE)" }
} finally { Pop-Location }
