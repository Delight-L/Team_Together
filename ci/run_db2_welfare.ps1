param(
    [string]$PythonPath = "",
    [ValidateRange(1,100000)][int]$MaxPages,
    [ValidateRange(1,100000)][int]$MaxDetails,
    [ValidateRange(1,100)][int]$Rows = 100
)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $PythonPath) { $PythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $PythonPath)) { throw "Python executable missing: $PythonPath" }
$logDir = Join-Path $projectRoot 'runtime\db2_logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$logStamp = (Get-Date -Format 'yyyy-MM-dd_HHmmss') + '_' + [guid]::NewGuid().ToString('N').Substring(0,8)
$logFile = Join-Path $logDir ($logStamp + '.log')
$outFile = Join-Path $logDir ($logStamp + '.out.log')
Set-Location -LiteralPath $projectRoot
# UTF-8 로그. 원천 API 예외/URL은 Python에서 출력하지 않는다.
$env:PYTHONIOENCODING = 'utf-8'
$collector = Join-Path $projectRoot 'collect_db2.py'
$collectorArgs = "`"$collector`" collect --rows $Rows"
if ($MaxPages) { $collectorArgs += " --max-pages $MaxPages" }
if ($MaxDetails) { $collectorArgs += " --max-details $MaxDetails" }
$process = Start-Process -FilePath $PythonPath -ArgumentList $collectorArgs -WorkingDirectory $projectRoot -WindowStyle Hidden -Wait -PassThru -RedirectStandardError $logFile -RedirectStandardOutput $outFile
exit $process.ExitCode
