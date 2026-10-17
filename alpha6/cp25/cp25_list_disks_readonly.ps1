# CP25: Windows native Get-Disk/Get-Partition inventory ONLY. No disk modifications.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$base = Split-Path -Parent $MyInvocation.MyCommand.Path
$out = Join-Path $base 'CP25_CARD_RESULTS'
if (-not (Test-Path -LiteralPath $out)) { New-Item -Path $out -ItemType Directory -ErrorAction Stop | Out-Null }
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$filename = Join-Path $out ('CP25_DISK_READONLY_' + $stamp + '.json')
if (Test-Path -LiteralPath $filename) { throw 'Refusing to overwrite existing report' }
# Get-Disk enumerates ALL Windows disks, including OS drives. This is NOT a
# recommendation to write to any of them, and does not test fake-card capacity.
$disks = @(Get-Disk | Sort-Object Number | ForEach-Object {
    $d = $_
    $parts = @(Get-Partition -DiskNumber $d.Number -ErrorAction SilentlyContinue | ForEach-Object {
        [ordered]@{ PartitionNumber = $_.PartitionNumber; SizeBytes = $_.Size; Type = [string]$_.Type }
    })
    [ordered]@{ DiskNumber = $d.Number; FriendlyName = [string]$d.FriendlyName;
        BusType = [string]$d.BusType; SizeBytes = $d.Size; PartitionStyle = [string]$d.PartitionStyle;
        IsBoot = [bool]$d.IsBoot; IsSystem = [bool]$d.IsSystem; IsReadOnly = [bool]$d.IsReadOnly;
        Partitions = $parts }
})
$report = [ordered]@{
    Format = 'R36OS_CP25_WINDOWS_DISK_INVENTORY_READONLY_V1'
    Status = 'INVENTORY_ONLY_NOT_A_FLASH_AUTHORIZATION'
    Disks = $disks
    SerialNumbersCollected = $false
    RawDiskOpened = $false
    CommandsUsed = @('Get-Disk', 'Get-Partition')
    AnyDiskWriteOperation = $false
    SpareCardUniqueIdentityVerified = $false
    SafeToFlash = $false
    OriginalSD1RebootsConfirmed = $false
    UBootSavedEnvironmentBackendConfirmed = $false
}
$json = ConvertTo-Json -InputObject $report -Depth 8
[IO.File]::WriteAllText($filename,$json + [Environment]::NewLine,[Text.UTF8Encoding]::new($false))
Write-Host 'Saved read-only inventory:' $filename
Write-Host 'PLEASE DOUBLE CHECK: disk numbers can change on reconnect.'