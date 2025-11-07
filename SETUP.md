# TVer Downloader - Tauri App Setup Guide

Complete guide to set up and run the TVer Downloader desktop application.

## Prerequisites

### 1. Install Rust
```bash
# macOS/Linux
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# After installation, restart your terminal or run:
source $HOME/.cargo/env
```

### 2. Install Node.js
Download from https://nodejs.org/ (LTS version recommended) or use a version manager:
```bash
# Using homebrew on macOS
brew install node

# Or using nvm
nvm install --lts
```

### 3. Install Tauri CLI
```bash
npm install -g @tauri-apps/cli
```

### 4. Install System Dependencies (macOS)
```bash
xcode-select --install
```

### 5. Ensure Python 3 and yt-dlp are installed
```bash
# Check Python
python3 --version

# Install/upgrade yt-dlp
brew install yt-dlp
# or
pip3 install -U yt-dlp
```

## Project Setup

### 1. Create Project Structure
```bash
mkdir tver-downloader-app
cd tver-downloader-app
```

### 2. Initialize npm project
```bash
npm init -y
```

### 3. Create File Structure
```
tver-downloader-app/
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── src-tauri/
│   ├── src/
│   │   ├── main.rs
│   │   └── build.rs
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   └── icons/
├── python/
│   └── tver_downloader.py
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
└── postcss.config.js
```

### 4. Copy Files
Copy all the files I provided into their respective locations:
- Frontend files go in `src/`
- Rust backend files go in `src-tauri/src/`
- Your Python script goes in `python/`
- Config files in root

### 5. Create Missing Files

**src-tauri/src/build.rs:**
```rust
fn main() {
    tauri_build::build()
}
```

**postcss.config.js:**
```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

**tsconfig.node.json:**
```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

### 6. Install Dependencies
```bash
# Install npm dependencies
npm install

# This will install all packages from package.json including:
# - React, React DOM
# - Tauri API
# - Vite and TypeScript
# - TailwindCSS
# - Lucide React (icons)
```

### 7. Update Python Script for App Integration

Your Python script needs minor modifications to work with the app. Add these command-line argument handlers:

```python
# Add at the end of tver_downloader.py, before if __name__ == "__main__":

def fetch_episodes_only(series_url: str):
    """Fetch episodes and output as JSON for the app"""
    downloader = TVerDownloader(debug=False)
    episodes = downloader.get_episode_urls(series_url)
    import json
    print(json.dumps(episodes))

# Modify main() to support new flags:
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', '-d', action='store_true')
    parser.add_argument('--fetch-episodes', help='Fetch episodes for a series URL')
    parser.add_argument('--config', help='Config file path')
    
    args = parser.parse_args()
    
    if args.fetch_episodes:
        fetch_episodes_only(args.fetch_episodes)
        return
    
    downloader = TVerDownloader(
        config_path=args.config if args.config else "config.json",
        debug=args.debug
    )
    downloader.run()
```

### 8. Create App Icons

Tauri needs icons in specific sizes. You can generate them from a single PNG:

```bash
# Create src-tauri/icons directory
mkdir -p src-tauri/icons

# Use an icon generator or create manually
# Required sizes: 32x32, 128x128, 128x128@2x, icon.icns (macOS), icon.ico (Windows)
```

Or use a placeholder for now - the app will work without custom icons.

## Running the App

### Development Mode
```bash
# Start the development server
npm run tauri dev
```

This will:
1. Start Vite dev server (React frontend)
2. Compile Rust backend
3. Launch the application window
4. Enable hot-reload for frontend changes

### Build Production App
```bash
# Build the final application
npm run tauri build
```

The built app will be in: `src-tauri/target/release/bundle/`

## Usage

### First Run
1. **Check VPN**: Click "Check VPN" to verify Japanese IP connection
2. **Add Series**: Click "Add Series" button
3. **Configure Series**:
   - Enter series name
   - Paste TVer series URL
   - Set include patterns (e.g., `＃, #, 第`)
   - Set exclude patterns (e.g., `予告, ダイジェスト, 解説放送版`)
4. **Download**: Enable series checkboxes and click "Download Episodes"

### Settings
- **Download Path**: Where episodes are saved
- **Archive File**: Tracks downloaded episodes
- **Debug Mode**: Enable verbose logging

### Download Logs
Watch real-time progress as episodes download.

## Troubleshooting

### "Python3 not found"
The app needs Python 3 installed:
```bash
# macOS
brew install python3

# Verify
which python3
```

### "yt-dlp not found"
Install yt-dlp:
```bash
brew install yt-dlp
# or
pip3 install yt-dlp
```

### "Rust compiler not found"
Reinstall Rust:
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

### Build fails
```bash
# Clean and rebuild
cd src-tauri
cargo clean
cd ..
npm run tauri build
```

### App won't start in dev mode
```bash
# Kill any existing processes
pkill -f tauri
pkill -f vite

# Try again
npm run tauri dev
```

## Development Tips

### Frontend Only Development
You can develop the UI without Tauri:
```bash
npm run dev
```
Then open http://localhost:5173 (Tauri commands won't work, but you can design the UI)

### Hot Reload
Changes to React components will hot-reload automatically. Rust changes require recompilation (automatic in dev mode).

### Debugging
- Frontend: Use browser DevTools (Cmd+Option+I in dev mode)
- Backend: Check terminal output where you ran `npm run tauri dev`

## Next Steps

Once working, you can add:
- **Scheduling**: Cron-like functionality to auto-download
- **Notifications**: Desktop notifications when downloads complete
- **System Tray**: Minimize to tray, background operation
- **Update Checker**: Auto-update functionality via Tauri
- **Multi-language**: i18n support for Japanese UI

## File Locations

### macOS
- Config: `~/Library/Application Support/com.tver.downloader/config.json`
- Downloads: `~/Library/Application Support/com.tver.downloader/downloads/`
- Archive: `~/Library/Application Support/com.tver.downloader/downloads/downloaded.txt`

### Windows
- Config: `%APPDATA%\com.tver.downloader\config.json`

### Linux
- Config: `~/.config/com.tver.downloader/config.json`