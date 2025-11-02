# FM Reloaded Modder's Guide

Complete guide to creating, packaging, and distributing mods for Football Manager 2026 using FM Reloaded Mod Manager.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Manifest Format](#manifest-format)
3. [Mod Types](#mod-types)
4. [File Structure](#file-structure)
5. [Platform Support](#platform-support)
6. [Testing Your Mod](#testing-your-mod)
7. [Packaging & Distribution](#packaging--distribution)
8. [Submitting to the Store](#submitting-to-the-store)
9. [Best Practices](#best-practices)
10. [Examples](#examples)

---

## Getting Started

### Using the Template Generator

The easiest way to start is using the built-in template generator:

1. Open FM Reloaded Mod Manager
2. Go to **Actions** → **Generate Mod Template…**
3. Fill in your mod details:
   - **Mod Name**: Display name for your mod
   - **Version**: Start with "1.0.0" (use semantic versioning)
   - **Author**: Your name or handle
   - **Mod Type**: Select from ui, graphics, tactics, database, or misc
   - **Description**: Brief summary of what your mod does
   - **Homepage**: (Optional) Your GitHub repo or website
4. Choose a save location
5. Click "Generate Template"

This creates a folder with:
- `manifest.json` - Mod configuration file
- `README.md` - Template readme for your mod

### Manual Setup

If you prefer to create the structure manually:

```
your-mod-name/
├── manifest.json          # Required: Mod configuration
├── README.md             # Recommended: Mod documentation
├── LICENSE               # Recommended: License information
├── changelog.md          # Optional: Version history
└── [your mod files]      # Your actual mod files
```

---

## Manifest Format

The `manifest.json` file is the core of every mod. It tells FM Reloaded how to install your mod.

### Minimum Required Manifest

```json
{
  "name": "My First Mod",
  "version": "1.0.0",
  "type": "ui",
  "author": "YourName",
  "files": [
    {
      "source": "my-mod-file.bundle",
      "target_subpath": "ui-panelids_assets_all.bundle"
    }
  ]
}
```

### Complete Manifest Example

```json
{
  "name": "FM26 Enhanced UI Pack",
  "version": "2.1.0",
  "type": "ui",
  "author": "ModderName",
  "homepage": "https://github.com/yourname/fm26-ui-pack",
  "description": "A comprehensive UI enhancement pack that improves visibility and usability",
  "license": "CC BY-SA 4.0",
  "compatibility": {
    "fm_version": "26.0.0",
    "min_loader_version": "0.5.0"
  },
  "dependencies": [],
  "conflicts": ["OtherUIModName"],
  "load_after": ["BaseUIFramework"],
  "files": [
    {
      "source": "ui-enhanced-windows.bundle",
      "target_subpath": "ui-panelids_assets_all.bundle",
      "platform": "windows"
    },
    {
      "source": "ui-enhanced-mac.bundle",
      "target_subpath": "ui-panelids_assets_all.bundle",
      "platform": "mac"
    }
  ]
}
```

### Field Descriptions

> **Packaging basics**  
> • Ship the manifest at the root of your release ZIP. The Mod Manager unpacks the archive first, then applies each entry in `files`.  
> • For single-file releases (for example a BepInEx DLL), publish the asset alongside a raw `manifest.json` in your repository. The trusted store references both; the manager stages the downloaded asset into the `source` path defined in the manifest before copying it to the `target_subpath`.

#### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Display name of your mod (shown in mod list) |
| `version` | string | Semantic version (e.g., "1.0.0", "2.1.3") |
| `type` | string | Mod category: `ui`, `graphics`, `tactics`, `database`, `misc` |
| `author` | string | Your name, handle, or team name |
| `files` | array | List of file installation instructions |

#### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `description` | string | Detailed explanation of what your mod does |
| `homepage` | string | URL to your mod's website, GitHub repo, or Discord |
| `license` | string | License type (e.g., "CC BY-SA 4.0", "MIT") |
| `compatibility` | object | Version requirements |
| `dependencies` | array | List of required mods |
| `conflicts` | array | List of incompatible mods |
| `load_after` | array | Mods that should load before this one |

### File Objects

Each item in the `files` array describes how to install one file:

```json
{
  "source": "path/to/file/in/your/mod.bundle",
  "target_subpath": "where/to/install/in/fm.bundle",
  "platform": "windows|mac|all"
}
```

**Fields**:
- `source` (required): Path to the file within your mod folder
- `target_subpath` (required): Destination relative to the FM install or Documents tree
- `platform` (optional): Platform-specific overrides
  - `"windows"` - Windows only
  - `"mac"` - macOS only
  - Omit or `"all"` to apply on every platform

**Common destinations**

| Destination | Use case | Example |
|-------------|----------|---------|
| `ui-*/…` | Game bundles in `StreamingAssets/aa/Standalone…` | `ui-panelids_assets_all.bundle` |
| `BepInEx/plugins/…` | Managed plugins | `BepInEx/plugins/ArthurRayPovMod.dll` |
| `graphics/...` | Logos, kits, faces in Documents | `graphics/logos/premier-league/` |
| `tactics/...` | Tactic `.fmf` files in Documents | `tactics/4-3-3-attacking.fmf` |

```json
{
  "name": "Camera POV",
  "type": "misc",
  "files": [
    {
      "source": "plugins/CameraPov.dll",
      "target_subpath": "BepInEx/plugins/CameraPov.dll"
    }
  ]
}
```

To copy a complete directory tree, point `source` at the folder and end both paths with `/`:

```json
{
  "source": "logos/",
  "target_subpath": "graphics/logos/premier-league/"
}
```

### Install/Enable lifecycle

Imported mods are stored in the FM Reloaded workspace (`%APPDATA%/FM_Reloaded_26/mods/` on Windows, `~/Library/Application Support/FM_Reloaded_26/mods/` on macOS). Enabling a mod reads the manifest and copies each entry in `files` to the proper destination:

- Paths beginning with `BepInEx/` are written to the Football Manager installation folder (for example `C:\Program Files (x86)\Steam\steamapps\common\Football Manager 26\BepInEx\plugins`).
- Graphics and tactics entries are routed to the Sports Interactive Documents directory.
- UI/bundle overrides land under `fm_Data/StreamingAssets/aa/Standalone…`.

Disabling a mod removes the installed files but keeps the copy in the workspace so you can re-enable it later.

---

## Mod Types

FM Reloaded supports different mod types, each with specific installation behavior:

### UI / Bundle Mods (`"type": "ui"`)

- **Install Location**: Game data folder (StandaloneWindows64 / StandaloneOSX)
- **Common Files**: `.bundle` files
- **Examples**: Interface tweaks, custom panels, skin modifications

```json
{
  "type": "ui",
  "files": [
    {
      "source": "ui-customization.bundle",
      "target_subpath": "ui-panelids_assets_all.bundle",
      "platform": "windows"
    }
  ]
}
```

### Graphics Mods (`"type": "graphics"`)

- **Install Location**: `Documents/Sports Interactive/Football Manager 26/graphics/`
- **Auto-routing**: FM Reloaded automatically detects and routes to:
  - `graphics/kits/` - Kit packs
  - `graphics/faces/` - Face packs / portraits
  - `graphics/logos/` - Logo packs / badges
- **Common Files**: `.png`, `.xml` (config)

```json
{
  "type": "graphics",
  "files": [
    {
      "source": "team-logos/",
      "target_subpath": "logos/premier-league/"
    }
  ]
}
```

### Tactics Mods (`"type": "tactics"`)

- **Install Location**: `Documents/Sports Interactive/Football Manager 26/tactics/`
- **Common Files**: `.fmf`, `.xml`

```json
{
  "type": "tactics",
  "files": [
    {
      "source": "4-3-3-attacking.fmf",
      "target_subpath": "my-tactics/"
    }
  ]
}
```

### Database Mods (`"type": "database"`)

- **Install Location**: Game data folder
- **Common Files**: `.db`, `.dbc`

### Misc Mods (`"type": "misc"`)

- **Install Location**: User data folder
- **Use for**: Editor files, custom tools, utilities

---

## File Structure

### Single-Platform Mods

```
your-mod/
├── manifest.json
├── README.md
└── mod-file.bundle
```

Manifest:
```json
{
  "files": [
    {
      "source": "mod-file.bundle",
      "target_subpath": "target-file.bundle"
    }
  ]
}
```

### Multi-Platform Mods

```
your-mod/
├── manifest.json
├── README.md
├── windows/
│   └── mod-windows.bundle
└── mac/
    └── mod-mac.bundle
```

Manifest:
```json
{
  "files": [
    {
      "source": "windows/mod-windows.bundle",
      "target_subpath": "target-file.bundle",
      "platform": "windows"
    },
    {
      "source": "mac/mod-mac.bundle",
      "target_subpath": "target-file.bundle",
      "platform": "mac"
    }
  ]
}
```

### Graphics Packs with Multiple Folders

```
your-graphics-mod/
├── manifest.json
├── README.md
├── kits/
│   ├── premier-league/
│   └── la-liga/
└── logos/
    ├── premier-league/
    └── la-liga/
```

Manifest:
```json
{
  "type": "graphics",
  "files": [
    {
      "source": "kits/",
      "target_subpath": "kits/"
    },
    {
      "source": "logos/",
      "target_subpath": "logos/"
    }
  ]
}
```

---

## Platform Support

### Platform Detection

FM Reloaded automatically detects the user's platform and only installs files marked for that platform.

### Cross-Platform Best Practices

1. **Test on both platforms** if possible
2. **Use platform-specific files** only when necessary
3. **Document platform differences** in your README
4. **Name files clearly**: `mod-windows.bundle`, `mod-mac.bundle`

### Bundle Format Differences

- Windows bundles are often different from macOS bundles
- FM's Unity version may compile assets differently per platform
- Always specify `platform` when files differ

---

## Testing Your Mod

### Local Testing

1. **Create your mod folder** with `manifest.json`
2. **Open FM Reloaded Mod Manager**
3. **Import your mod**:
   - Click "Import Mod…"
   - Select your mod folder (not a .zip)
4. **Enable and Apply**:
   - Enable your mod
   - Click "Apply Order" (F5)
5. **Launch FM26** and check your changes

### Testing Checklist

- [ ] Manifest validates (no JSON errors)
- [ ] All source files exist in mod folder
- [ ] Mod installs without errors
- [ ] Changes appear in FM26
- [ ] No conflicts with other mods
- [ ] Backup/restore works correctly

### Debugging

If your mod doesn't work:

1. **Check the log** (`Open Logs Folder` button)
2. **Verify paths** in manifest.json
3. **Check file permissions**
4. **Look for conflicts** (Conflicts… button)
5. **Test with only your mod enabled**

Common issues:
- Incorrect `target_subpath`
- Missing files
- Wrong file format (.bundle vs .xml)
- Platform mismatch

---

## Packaging & Distribution

### Creating a Release

1. **Organize your files**:
   ```
   your-mod-v1.0.0/
   ├── manifest.json
   ├── README.md
   ├── LICENSE
   ├── changelog.md
   └── [mod files]
   ```

2. **Version your release**:
   - Use semantic versioning: `MAJOR.MINOR.PATCH`
   - Update `manifest.json` version
   - Document changes in `changelog.md`

3. **Create a .zip archive**:
   - Zip the entire mod folder
   - Name it `your-mod-v1.0.0.zip`
   - Ensure `manifest.json` is at the root of the zip

### Distribution Options

#### GitHub Releases
1. Create a GitHub repository
2. Tag your release (e.g., `v1.0.0`)
3. Upload the .zip file as a release asset
4. Add release notes

#### Direct Download
- Host the .zip on your website
- Share via Discord, forums, etc.

#### FM Reloaded Store
- Submit to the official FM Reloaded Trusted Store
- See [STORE_SUBMISSION.md](STORE_SUBMISSION.md)

---

## Submitting to the Store

### Prerequisites

1. **GitHub Repository**: Your mod must be hosted on GitHub
2. **Valid Manifest**: Must follow the format specified here
3. **README**: Include installation and usage instructions
4. **License**: Clearly state your mod's license
5. **Testing**: Ensure your mod works correctly

### Submission Process

#### Option 1: Using FM Reloaded (Recommended)

1. Open FM Reloaded Mod Manager
2. Click "Submit Mod" in the footer
3. Fill in the form:
   - GitHub Repository URL
   - Mod Name
   - Author
   - Mod Type
   - Description
   - Contact info (optional)
4. Click "Submit Mod"
5. Your submission is sent to the maintainer's Discord

#### Option 2: Manual Submission

See [STORE_SUBMISSION.md](STORE_SUBMISSION.md) for the GitHub PR process.

### Store Requirements

- **manifest.json** must be valid and complete
- **README.md** with clear installation instructions
- **LICENSE** file (recommended: CC BY-SA 4.0)
- **changelog.md** for version tracking
- **download_url** pointing to a stable release
- **Version format**: Semantic versioning (X.Y.Z)

---

## Best Practices

### Manifest
- Use semantic versioning consistently
- Include a detailed description
- Specify dependencies and conflicts
- Document compatibility requirements

### File Organization
- Keep source files organized in logical folders
- Use clear, descriptive file names
- Separate platform-specific files
- Include example screenshots

### Documentation
- Write a comprehensive README
- Explain installation and usage
- Document known issues
- Credit contributors and assets

### Versioning
- **1.0.0**: Initial release
- **1.1.0**: New features (backwards compatible)
- **1.0.1**: Bug fixes
- **2.0.0**: Breaking changes

### Testing
- Test on both Windows and macOS when possible
- Check compatibility with popular mods
- Verify uninstall/rollback works
- Test with different FM versions

### Licensing
- Choose a permissive license (CC BY-SA 4.0, MIT, Apache)
- Respect asset licenses (logos, faces, etc.)
- Credit original creators
- Clearly state usage rights

---

## Examples

### Example 1: Simple UI Mod

```json
{
  "name": "Compact Player Stats",
  "version": "1.0.0",
  "type": "ui",
  "author": "ExampleModder",
  "description": "Makes player stat panels more compact for better overview",
  "homepage": "https://github.com/examplemodder/compact-stats",
  "files": [
    {
      "source": "compact-stats.bundle",
      "target_subpath": "ui-panelids_assets_all.bundle"
    }
  ]
}
```

### Example 2: Graphics Pack with Dependencies

```json
{
  "name": "Premier League Megapack 2026",
  "version": "2.0.1",
  "type": "graphics",
  "author": "GraphicsTeam",
  "description": "Complete kit, logo, and face pack for Premier League teams",
  "homepage": "https://github.com/graphicsteam/pl-megapack",
  "license": "CC BY-SA 4.0",
  "compatibility": {
    "fm_version": "26.0.0"
  },
  "dependencies": [],
  "conflicts": ["Other-PL-Logopack"],
  "files": [
    {
      "source": "kits/",
      "target_subpath": "kits/england/"
    },
    {
      "source": "logos/",
      "target_subpath": "logos/england/"
    },
    {
      "source": "faces/",
      "target_subpath": "faces/premier-league/"
    }
  ]
}
```

### Example 3: Multi-Platform Tactics

```json
{
  "name": "Tiki-Taka Master",
  "version": "1.2.0",
  "type": "tactics",
  "author": "TacticsGuru",
  "description": "Possession-based 4-3-3 with high pressing",
  "homepage": "https://discord.gg/tacticsgroup",
  "files": [
    {
      "source": "tiki-taka-4-3-3.fmf",
      "target_subpath": "Tiki-Taka Master/4-3-3-possession.fmf"
    },
    {
      "source": "tiki-taka-instructions.xml",
      "target_subpath": "Tiki-Taka Master/instructions.xml"
    }
  ]
}
```

---

## Resources

- [FM Reloaded README](README.md) - User guide
- [STORE_SUBMISSION.md](STORE_SUBMISSION.md) - Store submission guide
- [Example Mods](example%20mods/) - Sample mods to study
- [JSON Validator](https://jsonlint.com/) - Validate your manifest.json

---

## Support

Need help creating your mod?

- **GitHub Issues**: [Report issues](../../issues)
- **Discord**: Join the FM Reloaded community
- **Wiki**: [Community mod creation guides](../../wiki)

---

## License

This guide is part of FM Reloaded Mod Manager, licensed under CC BY-SA 4.0.

---

Happy modding! 🎮
