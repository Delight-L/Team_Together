param(
    [string]$ChromePath = 'C:\Program Files\Google\Chrome\Application\chrome.exe',
    [ValidateRange(1,4)][int]$Scale = 2
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $projectRoot 'docs\architecture\system_architecture.svg'
$output = Join-Path $projectRoot 'docs\architecture\system_architecture.png'
if (-not (Test-Path -LiteralPath $ChromePath)) { throw "Chrome not found: $ChromePath" }
if (-not (Test-Path -LiteralPath $source)) { throw "SVG not found: $source" }
$profile = Join-Path $projectRoot '.tmp\architecture-chrome-profile'
New-Item -ItemType Directory -Path $profile -Force | Out-Null
$sourceUri = ([System.Uri]$source).AbsoluteUri
$arguments = @(
    '--headless=new', '--disable-gpu', '--hide-scrollbars',
    '--no-first-run', '--no-default-browser-check',
    "--user-data-dir=`"$profile`"", "--force-device-scale-factor=$Scale",
    '--window-size=1920,1080', "--screenshot=`"$output`"", $sourceUri
)
$process = Start-Process -FilePath $ChromePath -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "Chrome rendering failed: $($process.ExitCode)" }
if (-not (Test-Path -LiteralPath $output)) { throw 'PNG was not generated.' }
Write-Output "Generated: $output"
