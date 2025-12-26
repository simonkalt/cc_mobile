# Fix WSL Port Forwarding for Local Development

## The Problem

Your server is running in WSL on port 8000, but Windows isn't forwarding that port, so:
- ❌ `http://localhost:8000` from Windows doesn't work
- ❌ `http://192.168.0.94:8000` from other devices doesn't work
- ✅ `http://localhost:8000` from WSL works (server is running there)

## Solution: Port Forwarding

WSL runs in a virtual network, so Windows needs to forward port 8000 from Windows to WSL.

## Quick Fix (PowerShell as Admin)

1. **Open PowerShell as Administrator**
   - Right-click PowerShell → "Run as Administrator"

2. **Run the port forwarding script:**
   ```powershell
   cd T:\Python\cc_mobile
   .\fix_wsl_port_forwarding.ps1
   ```

3. **Or run manually:**
   ```powershell
   # Get WSL IP
   $wslIp = (wsl hostname -I).Trim().Split()[0]
   
   # Forward port
   netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=$wslIp
   
   # Verify
   netsh interface portproxy show all
   ```

## Manual Steps

### Step 1: Find WSL IP Address

From WSL terminal:
```bash
hostname -I
# Or
ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1
```

### Step 2: Forward Port (PowerShell as Admin)

```powershell
# Replace WSL_IP with the IP from step 1 (e.g., 172.17.136.190)
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=WSL_IP
```

### Step 3: Verify Port Forwarding

```powershell
netsh interface portproxy show all
```

You should see:
```
Listen on ipv4:             Connect to ipv4:
Address         Port        Address         Port
--------------- ----------  --------------- ----------
0.0.0.0         8000        172.17.136.190  8000
```

### Step 4: Test Connection

From Windows:
```bash
curl http://localhost:8000
```

From Android device:
```
http://192.168.0.94:8000
```

## Windows Firewall

Make sure Windows Firewall allows port 8000:

**PowerShell (as Admin):**
```powershell
New-NetFirewallRule -DisplayName "WSL FastAPI Port 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

## Persistent Port Forwarding

The port forwarding resets when WSL restarts. To make it persistent:

### Option 1: Create a Startup Script

Create `C:\Users\YourName\wsl-port-forward.ps1`:
```powershell
$wslIp = (wsl hostname -I).Trim().Split()[0]
netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0 2>$null
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=$wslIp
```

Add to Windows Task Scheduler to run on startup (as Admin).

### Option 2: Use WSL Port Forwarding Script

Create a script that runs when WSL starts. Add to `~/.bashrc` in WSL:
```bash
# Port forwarding helper (runs on WSL startup)
if [ -z "$WSL_PORT_FORWARDED" ]; then
    export WSL_PORT_FORWARDED=1
    # This would need to run on Windows side, so better to use PowerShell script
fi
```

## Alternative: Run Server on Windows Directly

If port forwarding is too complicated, you can run the server directly on Windows:

1. Install Python on Windows
2. Create venv on Windows (not WSL)
3. Install dependencies
4. Run server from Windows

But this won't work for WeasyPrint (needs Linux libraries).

## Troubleshooting

### "Port already in use"
```powershell
# Remove existing rule
netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0
```

### "Access denied"
- Run PowerShell as Administrator
- Check Windows Firewall settings

### Port forwarding works but still can't connect
- Verify server is running: `wsl bash -c "curl http://localhost:8000"`
- Check Windows Firewall
- Try `http://127.0.0.1:8000` instead of `localhost`

### Port forwarding resets after restart
- WSL IP changes on restart
- Re-run the port forwarding script
- Or set up persistent forwarding (see above)

## Verify Everything Works

1. **Server running in WSL:**
   ```bash
   wsl bash -c "curl http://localhost:8000"
   ```

2. **Port forwarding configured:**
   ```powershell
   netsh interface portproxy show all
   ```

3. **Accessible from Windows:**
   ```bash
   curl http://localhost:8000
   ```

4. **Accessible from Android:**
   ```
   http://192.168.0.94:8000/docs
   ```

