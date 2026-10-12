<#
로컬 PostgreSQL(team_together의 db1·db2 스키마)을 Oracle Cloud PostgreSQL로 옮깁니다.

사용 예 (프로젝트 루트의 PowerShell):
  powershell -ExecutionPolicy Bypass -File deploy\oracle\migrate_to_oracle.ps1 -RemoteHost 168.138.xxx.xxx

- 로컬 postgres 비밀번호와 원격 welfind_admin 비밀번호를 차례로 묻습니다(화면·파일에 남기지 않음).
- 다시 실행하면 원격의 db1·db2를 지우고 로컬 내용으로 다시 채웁니다(--clean).
- 마지막에 로컬과 원격의 테이블별 행 수를 비교합니다.
#>
param(
    [Parameter(Mandatory = $true)][string]$RemoteHost,
    [int]$RemotePort = 5432,
    [string]$RemoteUser = "welfind_admin",
    [string]$Database = "team_together",
    [string]$LocalHost = "127.0.0.1",
    [int]$LocalPort = 5432,
    [string]$LocalUser = "postgres",
    [string]$PgBin = "C:\Program Files\PostgreSQL\18\bin"
)
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$DumpDir = Join-Path $Root ".tmp"
New-Item -ItemType Directory -Force -Path $DumpDir | Out-Null
$DumpFile = Join-Path $DumpDir "team_together_db1_db2.dump"
$PgDump = Join-Path $PgBin "pg_dump.exe"
$PgRestore = Join-Path $PgBin "pg_restore.exe"
$Psql = Join-Path $PgBin "psql.exe"
foreach ($tool in @($PgDump, $PgRestore, $Psql)) {
    if (-not (Test-Path $tool)) { throw "$tool 이 없습니다. -PgBin 으로 PostgreSQL bin 폴더를 지정하세요." }
}

function Read-Secret([string]$Prompt) {
    $secure = Read-Host -AsSecureString $Prompt
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}
function Invoke-Checked([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$([IO.Path]::GetFileName($Exe)) 실패 (exit $LASTEXITCODE)" }
}

$localPassword = Read-Secret "로컬 $LocalUser 비밀번호"
$remotePassword = Read-Secret "원격 $RemoteUser 비밀번호"

try {
    Write-Host "[1/4] 로컬 db1·db2 덤프 -> $DumpFile"
    $env:PGPASSWORD = $localPassword; $env:PGSSLMODE = "prefer"
    Invoke-Checked $PgDump @("-h", $LocalHost, "-p", $LocalPort, "-U", $LocalUser, "-d", $Database,
        "-n", "db1", "-n", "db2", "--no-owner", "--no-privileges", "-Fc", "-f", $DumpFile)
    $localCounts = & $Psql -h $LocalHost -p $LocalPort -U $LocalUser -d $Database -At -f (Join-Path $PSScriptRoot "table_counts.sql")

    Write-Host "[2/4] 원격 복원 ($RemoteHost)"
    $env:PGPASSWORD = $remotePassword; $env:PGSSLMODE = "require"
    Invoke-Checked $PgRestore @("-h", $RemoteHost, "-p", $RemotePort, "-U", $RemoteUser, "-d", $Database,
        "--clean", "--if-exists", "--no-owner", "--no-privileges", "--single-transaction", $DumpFile)

    Write-Host "[3/4] 읽기 전용 계정 권한 설정"
    Invoke-Checked $Psql @("-h", $RemoteHost, "-p", $RemotePort, "-U", $RemoteUser, "-d", $Database,
        "-v", "ON_ERROR_STOP=1", "-q", "-f", (Join-Path $PSScriptRoot "grants.sql"))

    Write-Host "[4/4] 행 수 비교"
    $remoteCounts = & $Psql -h $RemoteHost -p $RemotePort -U $RemoteUser -d $Database -At -f (Join-Path $PSScriptRoot "table_counts.sql")
    $diff = Compare-Object @($localCounts) @($remoteCounts)
    if ($diff) {
        $diff | Format-Table -AutoSize
        throw "로컬과 원격의 행 수가 다릅니다."
    }
    Write-Host ("완료: 테이블 {0}개 행 수 일치" -f @($localCounts).Count) -ForegroundColor Green
}
finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:PGSSLMODE -ErrorAction SilentlyContinue
}
