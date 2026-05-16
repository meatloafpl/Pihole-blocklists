$HOME_GATEWAY    = ""
$EXPECTED_DNS    = ""
$TAILSCALE_EXE   = "C:\Path\To\tailscale.exe"

$tsStatus = & $TAILSCALE_EXE status 2>&1
if ($tsStatus -notmatch "stopped") {
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
    # Get physical interface name
    $physicalInterface = Get-NetAdapter -InterfaceIndex $activeGateway.InterfaceIndex | Select-Object -ExpandProperty Name

    Start-Service -Name "Tailscale" -ErrorAction Stop
    & $TAILSCALE_EXE up 2>&1 | Out-Null

    # Set Tailscale interface metric to highest priority
    & netsh interface ip set interface "Tailscale" metric=1 2>&1 | Out-Null

    # Lower priority of physical interface
    & netsh interface ip set interface "$physicalInterface" metric=5 2>&1 | Out-Null

    Start-Process "C:\Program Files\Tailscale\tailscale-ipn.exe"
    Write-Host "Tailscale started." -ForegroundColor Green
    Start-Sleep -Seconds 2
} catch {
    Show-Error "Failed to start Tailscale.`n$($_.Exception.Message)"
}