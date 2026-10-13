param(
 [ValidateSet('scan','status','export','watch')][string]$Command='scan',
 [int]$Interval=60,
 [string]$Python='C:\ProgramData\anaconda3\envs\analysis1\python.exe'
)
$ErrorActionPreference='Stop'
$analysis3Args=@((Join-Path $PSScriptRoot 'run_analysis3.py'),$Command)
if($Command -eq 'watch'){$analysis3Args+=@('--interval',"$Interval")}
& $Python @analysis3Args
if($LASTEXITCODE -ne 0){throw "Analysis3 failed ($LASTEXITCODE)"}
