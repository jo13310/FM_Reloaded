# FM Reloaded Mod Manager

<div align="center">

<p align="center">
  <img src="src/assets/fm_reloaded.png" alt="FM Reloaded Mod Manager logo" width="600" />
</p>

[![License](https://img.shields.io/badge/license-CC%20BY--SA%204.0-blue.svg)](https://creativecommons.org/licenses/by-sa/4.0/)
[![Version](https://img.shields.io/badge/version-0.6.0-green.svg)]()
[![Discord](https://img.shields.io/badge/Discord-Join%20Us-7289da?logo=discord&logoColor=white)]()

**An enhanced, cross-platform mod manager for Football Manager 2026**

[Features](#features) • [Installation](#installation) • [Usage](#usage) • [Mod Store](#mod-store) • [BepInEx](#bepinex) • [Modders](#for-modders)

</div>

---

## Overview

FM Reloaded Mod Manager is a powerful, user-friendly tool for managing your Football Manager 2026 mods. Built with cross-platform support for Windows and macOS, it simplifies the process of installing, organizing, and updating mods.

**Forked from [FM_Reloaded_26](https://github.com/justinlevinedotme/FMMLoader-26)** by Justin Levine & FM Match Lab Team
**Enhanced by GerKo** with mod store, BepInEx support, and Discord integration

---

## Features

### Core Features
- **Cross-Platform**: Runs on Windows and macOS
- **Automatic FM Folder Detection**: Finds your FM installation automatically
- **Easy Mod Import**: Drag & drop .zip files or folders
- **Instant Enable/Disable**: One-click mod management with immediate apply
- **Automatic Backups**: Creates `.bck` backups alongside original files for easy restoration
- **Load Order Control**: Organize mod priority with last-write-wins system
- **Conflict Manager**: Detects overlapping files before applying
- **Restore Points**: One-click rollback to previous states
- **Type-Aware Installation**:
  - UI/Bundles → Game data folder
  - Camera/Plugins → BepInEx/plugins (requires BepInEx)
  - Tactics → Documents/Sports Interactive/FM26/tactics
  - Graphics → Documents/Sports Interactive/FM26/graphics (auto-routing for kits, faces, logos)
  - Database → Documents/Sports Interactive/FM26/editor data

### Enhanced Features (New!)
- **Mod Store Browser**: Browse and install mods directly from a trusted repository
- **Automatic Update Checking**: See when your mods have updates available
- **BepInEx Manager**: Install and configure BepInEx with one click
- **Discord Integration**: Report bugs and submit mods directly to Discord
- **Mod Template Generator**: Create properly formatted mod templates
- **Version Comparison**: Smart semantic versioning to track updates

---

## Installation

### Windows
1. Download `FM_Reloaded.exe` from [Releases](../../releases)
2. Run as Administrator
3. Windows Defender may show a warning - click "More Info" → "Run Anyway"

### macOS
1. Download `FM_Reloaded.zip` from [Releases](../../releases)
2. Unzip and drag to `Applications` folder
3. Control+Click → "Open" to bypass Gatekeeper
4. If prompted, go to System Preferences → Privacy & Security → "Open Anyway"

---

## Usage

### Quick Start

1. **Detect Your FM Installation**
   - Click "Detect" button or use `Ctrl+D` (`Cmd+D` on Mac)
   - The app will automatically find your FM data folder
   - If auto-detection fails, click "Set…" to manually select:
     - **Windows (Steam)**: `C:\Program Files (x86)\Steam\steamapps\common\Football Manager 26\fm_Data\StreamingAssets\aa\StandaloneWindows64`
     - **macOS (Steam)**: `~/Library/Application Support/Steam/steamapps/common/Football Manager 26/fm.app/Contents/Resources/Data/StreamingAssets/aa/StandaloneOSX`

2. **Install Mods**
   - **From File**: Click "Import Mod…" → Select .zip or folder
   - **From Store**: Go to "Mod Store" tab → Browse → Click "Install Selected"

3. **Manage Mods**
   - **Enable**: Select mod → Click "Enable" (immediately installs files and creates backups)
   - **Disable**: Select mod → Click "Disable" (immediately removes files and restores backups)
   - **Change Load Order**: Select mod → Click "Up (Order)" or "Down (Order)"
   - **Delete**: Select mod → Click "Delete" (automatically disables first, then removes mod)

4. **Check for Updates**
   - Mods with updates show "⬆" in the Update column
   - Visit the Mod Store tab to download the latest version

---

## Mod Store

The Mod Store allows you to browse and install mods from a curated, trusted repository.

### Features
- Browse all available mods
- Search by name, author, or type
- View mod details (description, version, author)
- One-click installation
- Automatic update notifications

### Using the Mod Store

1. Open the **Mod Store** tab
2. Browse available mods or use the search box
3. Click on a mod to see details
4. Click "Install Selected" to download and install
5. The mod will be automatically imported and added to your mod list

### Configuration

To use a custom mod store repository, you can configure the store URL in the config file:
- Located at `%APPDATA%/FM_Reloaded_26/config.json` (Windows) or `~/Library/Application Support/FM_Reloaded_26/config.json` (macOS)
- Set `"store_url"` to your repository's `mods.json` URL

---

## BepInEx

BepInEx is a plugin framework for Unity games like Football Manager. Use it to load code mods and plugins.

### Installation

1. Open the **BepInEx** tab
2. Click "Install BepInEx"
3. The app will extract and install BepInEx from the included archive
4. Installation status will update automatically

### Configuration

- **Enable/Disable Console**: Check/uncheck "Enable Console Logging"
  - Enabled: Shows a console window with debug information
  - Disabled (default): No console window
- **Edit Config**: Click "Open BepInEx Config File" to manually edit settings
- **View Logs**: Click "View Latest Log" to check for errors

### Troubleshooting

- **BepInEx not working?**
  1. Check "View Latest Log" for errors
  2. Ensure FM26 is closed before installing
  3. Try running FM26 as Administrator

- **Console not showing/hiding?**
  1. Close FM26 completely
  2. Toggle the console setting
  3. Restart FM26

---

## Discord Integration

### Report Bugs

1. Click "Report Bug" in the footer
2. Describe the issue
3. Optionally provide your email for follow-up
4. Click "Send Report"
5. Logs are automatically attached

### Submit Mods

1. Click "Submit Mod" in the footer
2. Enter your mod's GitHub repository URL
3. Fill in mod details (name, author, description, type)
4. Click "Submit Mod"
5. The maintainer will review and add it to the store

### Configuration

Discord webhooks must be configured before you can use bug reporting and mod submission features:

1. Go to **Settings** → **Preferences…**
2. Enter your Discord webhook URLs:
   - **Error Report Webhook**: For the ERROR-REPORT channel
   - **Mod Submission Webhook**: For the ADD-MOD channel
3. Get webhook URLs from your Discord server:
   - Server Settings → Integrations → Webhooks → New Webhook
   - Copy the Webhook URL
4. Click "Save"

---

## Configuration & Settings

### Preferences Dialog

Access via **Settings** → **Preferences…**

Configure:
- **Mod Store URL**: URL to the mods.json file (default: FM Reloaded Trusted Store)
- **Discord Error Report Webhook**: Webhook URL for bug reports
- **Discord Mod Submission Webhook**: Webhook URL for mod submissions
- **Auto-check for updates**: Automatically check for app updates on startup

### Where Discord Webhooks Are Used

**Error Report Webhook** (ERROR-REPORT channel):
- Sends bug reports from "Report Bug" button
- Includes app logs and BepInEx logs
- User description and contact info

**Mod Submission Webhook** (ADD-MOD channel):
- Sends mod submissions from "Submit Mod" button
- Includes GitHub repo URL and mod details
- Used by maintainer to add mods to store

### App Updates

The mod manager can automatically check for new releases:

1. **Auto-check on startup**: Enabled by default in Settings
2. **Manual check**: Go to **Help** → **Check for Updates…**
3. **Update notification**: Shows release notes and download link
4. **Download**: Opens your browser to the latest release

---

## For Modders

### Creating a Mod

1. **Generate a Template**
   - Go to Actions → "Generate Mod Template…"
   - Fill in mod details
   - Choose a save location
   - A template with `manifest.json` and `README.md` will be created

2. **Manifest Format**

```json
{
  "name": "Your Mod Name",
  "version": "1.0.0",
  "type": "ui|graphics|tactics|database|camera|misc",
  "author": "Your Name",
  "homepage": "https://github.com/yourname/your-mod",
  "description": "Brief description of your mod",
  "files": [
    {
      "source": "your_mod_file.bundle",
      "target_subpath": "target_file.bundle",
      "platform": "windows|mac|all"
    }
  ]
}
```

**Supported Mod Types:**
- `ui` - UI modifications (bundles in game data folder)
- `graphics` - Graphics packs (kits, faces, logos)
- `tactics` - Tactic files (.fmf)
- `database` - Database/editor files (.dbc, .lnc, .edt)
- `camera` - Camera plugins (BepInEx .dll files)
- `misc` - Other modifications

3. **Required Fields**
   - `name`: Mod display name
   - `version`: Semantic version (e.g., "1.0.0")
   - `type`: Mod category
   - `author`: Your name or handle
   - `files`: Array of files to install

4. **Optional Fields**
   - `description`: Detailed description
   - `homepage`: Website or GitHub URL
   - `dependencies`: List of required mods
   - `conflicts`: List of incompatible mods
   - `compatibility`: Version requirements

### Submitting to the Store

See [STORE_SUBMISSION.md](STORE_SUBMISSION.md) for detailed instructions on how to submit your mod to the FM Reloaded Trusted Store.

### Modder Resources

- [MODDER_GUIDE.md](MODDER_GUIDE.md) - Complete guide to creating mods
- [STORE_SUBMISSION.md](STORE_SUBMISSION.md) - How to submit mods to the store
- [Example Mods](example%20mods/) - Sample mods to learn from

---

## Technical Details

### Project Structure

```
FM_Reloaded/
├── src/
│   ├── fm26_mod_manager_gui.py    # Main GUI application
│   ├── FM_Reloaded_26.py             # Backend mod management
│   ├── mod_store_api.py           # Mod store integration
│   ├── discord_webhook.py         # Discord integration
│   ├── bepinex_manager.py         # BepInEx management
│   ├── requirements.txt           # Python dependencies
│   └── assets/                    # Icons and images
├── example mods/                  # Sample mods
├── BepInEx_Patched_Win_*.rar     # BepInEx installer
└── .github/                       # Documentation
```

### Data Storage

Configuration and mod data are stored in:
- **Windows**: `%APPDATA%\FM_Reloaded_26\`
- **macOS**: `~/Library/Application Support/FM_Reloaded_26/`

Contains:
- `config.json` - App configuration
- `mods/` - Installed mods
- `backups/` - Legacy backup storage
- `restore_points/` - Timestamped snapshots
- `logs/` - Activity logs

**Note**: Backups are now stored alongside original files with `.bck` extension (e.g., `gamemodules_assets_match.bundle.bck`) for easier restoration and transparency.

### Backup System

The mod manager uses an intelligent backup system to protect your game files:

**How it works:**
1. **Enable Mod**: When you enable a mod that replaces a game file, the original is automatically backed up:
   - Example: `gamemodules_assets_match.bundle` → `gamemodules_assets_match.bundle.bck`
   - Backup created only if it doesn't exist (preserves original game file)
   - Stored in the same directory as the original for transparency

2. **Disable Mod**: When you disable a mod:
   - Modded file is removed
   - Original file is restored from `.bck` backup
   - `.bck` file is kept for future enable/disable cycles

3. **Delete Mod**: When you delete a mod:
   - Mod is automatically disabled first (removes files, restores originals)
   - `.bck` backups are cleaned up after successful restore
   - If restore fails, backups are preserved for safety

**Manual Restoration:**
If you need to manually restore a file, simply:
1. Delete the modded file (e.g., `gamemodules_assets_match.bundle`)
2. Rename the backup (e.g., `gamemodules_assets_match.bundle.bck` → `gamemodules_assets_match.bundle`)

### Dependencies

- Python 3.x
- Tkinter (included with Python)
- rarfile (for BepInEx installation)
- tkinterdnd2 (optional, for drag-and-drop)

---

## Credits

### Original Authors
- **Justin Levine** ([justinlevine.me](https://justinlevine.me)) - Original FM_Reloaded_26 creator
- **FM Match Lab Team** ([fmmatchlab.co.uk](https://fmmatchlab.co.uk/)) - Support and presentation

### Enhanced Version
- **GerKo** - Mod store, BepInEx support, Discord integration, UI enhancements

### Example Mod Contributors
- **knap** - Beta Tactics example
- **bassyboy** - UI Speedster example

---

## License

This project is licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**.

You are free to:
- **Share** - Copy and redistribute the material
- **Adapt** - Remix, transform, and build upon the material

Under the following terms:
- **Attribution** - You must give appropriate credit
- **ShareAlike** - If you remix, transform, or build upon the material, you must distribute your contributions under the same license

See [LICENSE](LICENSE) for full details.

---

## Support

- **Issues**: [GitHub Issues](../../issues)
- **Discord**: [Join our Discord](#) (link to be added)
- **Wiki**: [Documentation Wiki](../../wiki)

---

## Changelog

### v0.6.0 (Latest Release)
- **Instant Apply**: Enable/Disable buttons now apply changes immediately (no separate Apply button needed)
- **Improved Backup System**: Backups stored alongside originals with `.bck` extension for transparency
- **Camera Mod Support**: Full support for BepInEx camera plugins (ArthurRay, TorojoH, Brululul)
- **Enhanced Security**: Improved file deletion validation and path traversal protection
- **Database Mod Support**: Real name fixes and licensing file management (NameFix FM26)
- **Automatic Cleanup on Delete**: Safely removes plugin files and restores backups when deleting mods
- **Shared Path Routing**: Proper routing for database mods in `shared/data/database/` directory
- **Direct Download Support**: Added support for direct file URLs in mod store
- **Bug Fixes**:
  - Fixed lambda closure bug causing "Install failed: None" errors
  - Fixed camera mod installation missing config_target parameter
  - Fixed security validation using wrong game root directory
  - Fixed deletion not cleaning up enabled plugins properly

### v0.5.0 (Enhanced Release)
- **Mod Store Integration**: Browse, search, and install mods directly from app
- **Automatic Update Checking**: See when mods have updates available
- **BepInEx Manager**: One-click installation and configuration
- **Discord Integration**: Bug reporting and mod submission via webhooks
- **Settings Dialog**: Configure store URL, Discord webhooks, and preferences
- **App Auto-Update**: Check for new app versions (manual or automatic)
- **Mod Template Generator**: Create properly formatted mod templates
- **Tabbed Interface**: My Mods, Mod Store, and BepInEx tabs
- **Enhanced Credits**: Proper attribution to original authors and GerKo
- **Improved Version Comparison**: Smart semantic versioning
- **Store Repository**: Created FM_Reloaded_Trusted_Store with validation
- **Help Menu**: Manifest help, update checking, and about dialog

### v0.4.0 (Original Release)
- Cross-platform GUI (Windows/macOS)
- Mod import from .zip or folders
- Enable/disable mods with load order control
- Conflict detection and resolution
- Restore points and rollback
- Type-aware installation (UI, graphics, tactics)

---

Made with ❤️ for the Football Manager community

> ⚠️ **Warning:** This project is still a work in progress. Verify everything for yourself before use—I’m not responsible if anything goes wrong.
