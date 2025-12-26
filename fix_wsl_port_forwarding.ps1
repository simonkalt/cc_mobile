# PowerShell script to forward WSL port 8000 to Windows
# Run this as Administrator

# Remove existing rule if it exists
netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0 2>$null

# Get WSL IP address
$wslIp = (wsl hostname -I).Trim().Split()[0]

Write-Host "WSL IP Address: $wslIp"
Write-Host "Forwarding Windows port 8000 to WSL port 8000..."

# Forward Windows port 8000 to WSL port 8000
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=$wslIp

# Show current port proxy rules
Write-Host "`nCurrent port forwarding rules:"
netsh interface portproxy show all

Write-Host "`n✅ Port forwarding configured!"
Write-Host "You can now access the server at:"
Write-Host "  - http://localhost:8000 (from Windows)"
Write-Host "  - http://192.168.0.94:8000 (from other devices on your network)"

