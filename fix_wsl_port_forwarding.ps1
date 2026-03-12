# PowerShell script to forward WSL port 8675 to Windows
# Run this as Administrator

# Remove existing rule if it exists
netsh interface portproxy delete v4tov4 listenport=8675 listenaddress=0.0.0.0 2>$null

# Get WSL IP address
$wslIp = (wsl hostname -I).Trim().Split()[0]

Write-Host "WSL IP Address: $wslIp"
Write-Host "Forwarding Windows port 8675 to WSL port 8675..."

# Forward Windows port 8675 to WSL port 8675
netsh interface portproxy add v4tov4 listenport=8675 listenaddress=0.0.0.0 connectport=8675 connectaddress=$wslIp

# Show current port proxy rules
Write-Host "`nCurrent port forwarding rules:"
netsh interface portproxy show all

Write-Host "`n✅ Port forwarding configured!"
Write-Host "You can now access the server at:"
Write-Host "  - http://localhost:8675 (from Windows)"
Write-Host "  - http://192.168.0.94:8675 (from other devices on your network)"

