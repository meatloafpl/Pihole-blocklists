$HOME_GATEWAY  = ""
$EXPECTED_DNS  = ""
# These are the default install paths for Tailscale on Windows; adjust if you installed it somewhere else.
$TAILSCALE_EXE = "C:\Program Files\Tailscale\tailscale.exe"
$TAILSCALE_IPN = "C:\Program Files\Tailscale\tailscale-ipn.exe"
$COOLDOWN_FILE = "C:\Scripts\tailscale-last-run.tmp"
$COOLDOWN_SECS = 30

# Cooldown — if last run was less than 30s ago, exit immediately
if (Test-Path $COOLDOWN_FILE) {
    $lastRun = (Get-Item $COOLDOWN_FILE).LastWriteTime
    if ((New-TimeSpan -Start $lastRun -End (Get-Date)).TotalSeconds -lt $COOLDOWN_SECS) {
        exit 0
    }
}
Set-Content $COOLDOWN_FILE -Value (Get-Date) -ErrorAction SilentlyContinue

# If Tailscale is already connected, exit immediately
$tsStatus = (& $TAILSCALE_EXE status 2>&1) -join "`n"
if ($tsStatus -notmatch "stopped" -and $tsStatus -notmatch "NoState") {
    exit 0
}

function Show-Error($msg) {
    $escaped = $msg -replace "'", "''"
    Start-Process powershell.exe -ArgumentList @(
        "-NoExit",
        "-Command",
        "Write-Host '=== TAILSCALE AUTOSTART - ERROR ===' -ForegroundColor Red; Write-Host '$escaped' -ForegroundColor Yellow; Write-Host ''; Write-Host 'Press Enter to close...' -ForegroundColor Gray; Read-Host"
    ) -WindowStyle Normal
    exit 1
}

Write-Host "Waiting for DHCP..." -ForegroundColor Cyan
Start-Sleep -Seconds 2

$activeGateway = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
    Where-Object { $_.NextHop -ne "0.0.0.0" } |
    Where-Object { (Get-NetAdapter -InterfaceIndex $_.InterfaceIndex -ErrorAction SilentlyContinue).Status -eq "Up" } |
    Sort-Object { $_.RouteMetric + $_.InterfaceMetric } |
    Select-Object -First 1

Write-Host "Default gateway: $($activeGateway.NextHop)" -ForegroundColor White

$homeRoute = if ($activeGateway.NextHop -eq $HOME_GATEWAY) { $activeGateway } else { $null }

if ($homeRoute) {
    $dnsServers = Get-DnsClientServerAddress `
        -InterfaceIndex $homeRoute.InterfaceIndex `
        -AddressFamily IPv4 |
        Select-Object -ExpandProperty ServerAddresses
    if ($dnsServers -notcontains $EXPECTED_DNS) {
        Show-Error "Home network detected, but DNS does not point to Pi-hole!`nCurrent DNS: $($dnsServers -join ', ')`nExpected:    $EXPECTED_DNS"
    }
    Write-Host "Home network — Tailscale will not start." -ForegroundColor Green
    Start-Sleep -Seconds 2
    exit 0
}

Write-Host "External network — starting Tailscale..." -ForegroundColor Yellow

try {
    Start-Service -Name "Tailscale" -ErrorAction Stop
    & $TAILSCALE_EXE up 2>&1 | Out-Null

    # Metric swap — gives Tailscale routing priority over the active physical interface.
    # This prevents VPNs like GlobalProtect (PANGP Virtual Ethernet Adapter) from
    # hijacking DNS and traffic by holding a lower metric than Tailscale.
    # Tailscale is set to (current metric - 1) so it takes priority without
    # touching other interfaces or risking metric conflicts.
    $activeInterface = (Get-NetAdapter -InterfaceIndex $activeGateway.InterfaceIndex).Name
    $currentMetric = (Get-NetIPInterface -InterfaceIndex $activeGateway.InterfaceIndex -AddressFamily IPv4).InterfaceMetric
    $tailscaleMetric = $currentMetric - 1
    Write-Host "Setting metrics: Tailscale=$tailscaleMetric, $activeInterface=$currentMetric (unchanged)" -ForegroundColor Gray
    & "C:\Windows\System32\netsh.exe" interface ip set interface "Tailscale" metric=$tailscaleMetric | Out-Null

    # Launch GUI only if not already running.
    # Using Start-Job so tailscale-ipn.exe has no parent console to attach to.
    $ipnRunning = Get-Process -Name "tailscale-ipn" -ErrorAction SilentlyContinue
    if (-not $ipnRunning) {
        $ipn = $TAILSCALE_IPN
        Start-Job -ScriptBlock { Start-Process $using:ipn } | Out-Null
    }

    Write-Host "Tailscale started." -ForegroundColor Green
    Start-Sleep -Seconds 2
    exit 0
} catch {
    Show-Error "Failed to start Tailscale.`n$($_.Exception.Message)"
}