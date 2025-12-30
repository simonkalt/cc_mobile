# How to Revert WSL Extension to Previous Version

## Current Version
- **Installed**: `ms-vscode-remote.remote-wsl-0.81.8`

## Method 1: Via Cursor UI (Easiest)

1. **Open Extensions Panel**
   - Press `Ctrl+Shift+X` or click the Extensions icon

2. **Find WSL Extension**
   - Search for "Remote - WSL"
   - Look for `ms-vscode-remote.remote-wsl`

3. **Install Previous Version**
   - Click the **gear icon** (⚙️) next to the extension
   - Select **"Install Another Version..."**
   - Choose an older version from the dropdown list
   - Common stable versions to try:
     - `0.80.0` (if available)
     - `0.79.0`
     - `0.78.0`
     - `0.77.0`

4. **Disable Auto-Updates** (Optional)
   - After installing, click the gear icon again
   - Select **"Disable Auto Updating"** to prevent future updates

## Method 2: Manual VSIX Installation

1. **Download Previous Version**
   - Visit: https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-wsl
   - Click "Version History" to see all versions
   - Download the `.vsix` file for your desired version

2. **Uninstall Current Version**
   - In Extensions panel, click gear icon → "Uninstall"

3. **Install from VSIX**
   - In Extensions panel, click the three dots (⋯) menu
   - Select "Install from VSIX..."
   - Choose the downloaded `.vsix` file

## Recommended Versions to Try

If version 0.81.8 is causing issues, try these stable versions:
- **0.80.0** - Recent stable release
- **0.79.0** - Previous stable release
- **0.77.0** - Older stable release

## Troubleshooting

If you can't find "Install Another Version" option:
- Make sure you're looking at the installed extension (not the marketplace listing)
- Try uninstalling first, then use Method 2
- Check Cursor's extension compatibility (some VS Code extensions may have limited version history in Cursor)

