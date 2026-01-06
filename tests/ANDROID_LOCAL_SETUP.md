# Android App - Local Development Setup

## The Problem

When your Android app tries to connect to `http://localhost:8000`, it's looking for a server **on the Android device itself**, not your Windows/WSL machine.

## Solution: Use Your Windows Machine's IP Address

### Step 1: Find Your Windows Machine's IP Address

**Option A: From Windows Command Prompt**
```cmd
ipconfig
```
Look for "IPv4 Address" under your active network adapter (usually Wi-Fi or Ethernet).

**Option B: From WSL**
```bash
# Get Windows host IP (from WSL perspective)
cat /etc/resolv.conf | grep nameserver | awk '{print $2}'
```

**Option C: From Windows PowerShell**
```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike "*Loopback*"} | Select-Object IPAddress
```

### Step 2: Update Your Android App Configuration

Change your API base URL from:
```javascript
const API_BASE_URL = 'http://localhost:8000';  // ❌ Won't work
```

To:
```javascript
const API_BASE_URL = 'http://YOUR_WINDOWS_IP:8000';  // ✅ Works!
// Example: http://192.168.1.100:8000
```

### Step 3: Ensure Server is Accessible

Your server is already configured with `--host 0.0.0.0`, which means it listens on all interfaces. This is correct!

### Step 4: Check Windows Firewall

Make sure Windows Firewall allows connections on port 8000:

**Windows Firewall:**
1. Open "Windows Defender Firewall"
2. Click "Advanced settings"
3. Click "Inbound Rules" → "New Rule"
4. Select "Port" → Next
5. Select "TCP" and enter port `8000`
6. Select "Allow the connection"
7. Apply to all profiles
8. Name it "FastAPI Development"

**Or use PowerShell (Run as Admin):**
```powershell
New-NetFirewallRule -DisplayName "FastAPI Dev Port 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

### Step 5: Verify Server is Reachable

From your Android device (or emulator), test:
```bash
# Replace with your Windows IP
curl http://YOUR_WINDOWS_IP:8000
```

Or open in a browser on your Android device:
```
http://YOUR_WINDOWS_IP:8000/docs
```

## Common IP Addresses

- **192.168.x.x** - Most home networks
- **10.0.x.x** - Some corporate networks
- **172.16.x.x - 172.31.x.x** - Some networks

## For Android Emulator

If you're using Android Emulator:
- **Android Emulator (API 10+)**: Use `10.0.2.2` instead of `localhost`
- **Android Emulator (older)**: Use `10.0.2.2`
- **Physical Device**: Use your Windows machine's actual IP

```javascript
// For Android Emulator
const API_BASE_URL = __DEV__ 
  ? 'http://10.0.2.2:8000'  // Android emulator
  : 'https://your-render-api.onrender.com';  // Production
```

## Troubleshooting

### "Network request failed"
- ✅ Check Windows IP address is correct
- ✅ Verify server is running (`http://localhost:8000/docs` works in Windows browser)
- ✅ Check Windows Firewall allows port 8000
- ✅ Ensure Android device and Windows machine are on same network
- ✅ Try `http://YOUR_IP:8000/docs` in Android browser first

### "Connection refused"
- Server might not be listening on `0.0.0.0`
- Check server logs for binding errors
- Verify port 8000 is not in use by another app

### CORS Errors
- CORS is configured for web browsers, not mobile apps
- Mobile apps don't enforce CORS the same way
- If you see CORS errors, check server CORS configuration includes your IP

## Quick Test

1. **Find your IP:**
   ```bash
   # Windows CMD
   ipconfig | findstr IPv4
   ```

2. **Test from Android browser:**
   ```
   http://YOUR_IP:8000/docs
   ```

3. **Update app config:**
   ```javascript
   const API_BASE_URL = 'http://YOUR_IP:8000';
   ```

4. **Restart your app**

## MongoDB Connection

MongoDB connection issues are separate from network connectivity. If MongoDB works on Render but not locally:

1. **Check MongoDB Atlas IP Whitelist:**
   - Go to MongoDB Atlas → Network Access
   - Add your Windows machine's public IP
   - Or temporarily allow `0.0.0.0/0` for development (not recommended for production)

2. **Check MongoDB URI in `.env`:**
   ```env
   MONGODB_URI=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/...
   ```

3. **Test MongoDB connection:**
   ```bash
   # From WSL
   python -c "from app.db.mongodb import get_database; print(get_database())"
   ```

