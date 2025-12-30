# WSL Permissions Guide - Running Scripts on Windows Filesystems

## The Problem

When files are on a Windows drive mounted in WSL (`/mnt/t/`, `/mnt/c/`, etc.), Linux permissions don't work the same way. The filesystem is controlled by Windows, not Linux.

## Solutions

### Solution 1: Run Script Directly (Easiest)

Even if `chmod` fails, you can still run the script:

```bash
# Method 1: Use bash explicitly
bash start.sh

# Method 2: Use sh
sh start.sh

# Method 3: If permissions show as executable, try:
./start.sh
```

### Solution 2: Copy to Linux Filesystem

Copy the script to your Linux home directory where permissions work:

```bash
# Copy to home directory
cp start.sh ~/start.sh

# Make it executable (this will work on Linux filesystem)
chmod +x ~/start.sh

# Run it
~/start.sh
```

### Solution 3: Use sudo (Usually Not Needed)

If you really need to change permissions (rarely works on Windows filesystems):

```bash
sudo chmod +x start.sh
```

**Note:** This usually won't work on `/mnt/` drives because Windows controls the permissions.

### Solution 4: Change Permissions in Windows

1. Right-click `start.sh` in Windows File Explorer
2. Properties → Security tab
3. Edit permissions to allow execution
4. Or run PowerShell as Admin:
   ```powershell
   icacls "T:\Python\cc_mobile\start.sh" /grant Everyone:F
   ```

## For Your Specific Case

Since `start.sh` contains:
```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Just run it directly:
```bash
bash start.sh
```

Or create a Linux-native version:
```bash
# Copy to Linux filesystem
cp start.sh ~/start_cc_mobile.sh
chmod +x ~/start_cc_mobile.sh

# Create a symlink or alias for convenience
alias start-server='cd /mnt/t/Python/cc_mobile && bash start.sh'
```

## Understanding WSL Filesystem Permissions

- **Windows filesystems** (`/mnt/c/`, `/mnt/t/`): Permissions controlled by Windows
- **Linux filesystems** (`/home/`, `/tmp/`, `/usr/`): Permissions controlled by Linux

For scripts you run frequently, consider:
1. Keeping them on Linux filesystem (`~/scripts/`)
2. Using aliases in `~/.bashrc`
3. Running with `bash script.sh` instead of `./script.sh`

