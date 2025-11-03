# FM Reloaded Trusted Store - Submission Guide

This guide explains how to submit your Football Manager 2026 mod to the FM Reloaded Trusted Store for inclusion in the mod browser.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Store Format](#store-format)
4. [Submission Methods](#submission-methods)
5. [Validation Requirements](#validation-requirements)
6. [Approval Process](#approval-process)
7. [Updating Your Mod](#updating-your-mod)
8. [Store Repository Structure](#store-repository-structure)

---

## Overview

The FM Reloaded Trusted Store is a curated collection of mods that users can browse and install directly from the FM Reloaded Mod Manager. Having your mod in the store:

- Makes it discoverable to thousands of FM players
- Provides automatic update notifications to users
- Ensures your mod meets quality standards
- Simplifies installation for end-users

**Store Repository**: `https://github.com/jo13310/FM_Reloaded_Trusted_Store`

---

## Prerequisites

Before submitting, ensure your mod meets these requirements:

### Required

1. **GitHub Repository**: Your mod must be hosted on GitHub
2. **Valid manifest.json**: Must conform to the FM Reloaded format
3. **README.md**: Clear installation and usage instructions
4. **LICENSE file**: Open-source or permissive license
5. **Tagged Release**: At least one GitHub release with your mod as an asset (ZIP preferred; single-file assets must provide a manifest URL)

### Recommended

1. **changelog.md**: Document version history
2. **Screenshots**: Visual preview of your mod
3. **Semantic Versioning**: Use X.Y.Z format (e.g., 1.0.0, 2.1.3)
4. **Testing**: Verify your mod works on Windows and/or macOS

---

## Store Format

The FM Reloaded Store uses a single `mods.json` file containing all available mods.

### Mod Entry Format

Each mod in the store is represented as a JSON object:

```json
{
  "name": "Your Mod Name",
  "version": "1.0.0",
  "type": "ui",
  "author": "YourName",
  "description": "Brief description of what your mod does",
  "homepage": "https://github.com/yourname/your-mod",
  "download": {
    "type": "github_release",
    "repo": "yourname/your-mod",
    "asset": "your-mod.zip",
    "tag_prefix": "v"
  },
  "changelog_url": "https://github.com/yourname/your-mod/blob/main/changelog.md",
  "downloads": 0,
  "date_added": "2025-01-15",
  "last_updated": "2025-01-15",
  "dependencies": [],
  "conflicts": [],
  "compatibility": {
    "fm_version": "26.0.0",
    "min_loader_version": "0.5.0"
  }
}
```

### Field Descriptions

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Mod display name (must match manifest.json) |
| `version` | Yes | Latest version (semantic versioning) |
| `type` | Yes | Mod category: ui, bundle, camera, skins, graphics, tactics, database, ruleset, editor-data, audio, misc |
| `author` | Yes | Mod creator name |
| `description` | Yes | 1-2 sentence summary (max 200 chars) |
| `homepage` | Yes | GitHub repository URL |
| `download` | Yes | Download descriptor (see below) |
| `changelog_url` | No | Link to changelog or release notes |
| `downloads` | No | Download count (maintained by store admin) |
| `date_added` | No | Date added to store (YYYY-MM-DD) |
| `last_updated` | No | Date of last update (YYYY-MM-DD) |
| `dependencies` | No | List of required mods |
| `conflicts` | No | List of incompatible mods |
| `compatibility` | No | Version requirements |
| `manifest_url` | Conditional | Required when the release asset is not a `.zip` |
| `install_notes` | No | Optional short hint about destination (e.g. `BepInEx/plugins`) |

### `download` object

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | Currently only `github_release` is supported |
| `repo` | Yes | Repository in `owner/name` form |
| `asset` | Yes | Exact asset filename (`your-mod.zip`, `Plugin.dll`, etc.) |
| `tag_prefix` | No | Prefix applied to the manifest version (`v` by default) |
| `tag` | No | Override tag when releases do not match semantic versioning |
| `latest` | No | Set to `true` to always follow `releases/latest` |

> **Packaging rules**
>
> - Release ZIP files must contain `manifest.json` at the root together with the folder/file structure referenced by the `files` array.  
> - For single-file assets (for example `YourMod.dll`), publish `manifest.json` in your repository and set `manifest_url` to the raw file. The Mod Manager downloads the asset, stages it in the `source` location defined by the manifest, then copies it to the `target_subpath` (such as `BepInEx/plugins/YourMod.dll`).

---

## Submission Methods

### Method 1: Using FM Reloaded (Easiest)

1. **Open FM Reloaded Mod Manager**
2. **Click "Submit Mod"** (bottom right button)
3. **Fill in the submission form**:
   - GitHub Repository URL
   - Mod Name
   - Author Name
   - Mod Type
   - Description
   - Contact Info (optional)
4. **Click "Submit Mod"**
5. Your submission is sent to the maintainer via Discord
6. The maintainer will review and add your mod

**Advantages**:
- Simple, no GitHub knowledge required
- Automatic submission to Discord channel
- Form validation

### Method 2: GitHub Pull Request (Advanced)

1. **Fork the FM Reloaded Trusted Store repository**
2. **Clone your fork**:
   ```bash
   git clone https://github.com/jo13310/FM_Reloaded_Trusted_Store.git
   cd FM_Reloaded_Trusted_Store
   ```

3. **Edit `mods.json`**:
   - Add your mod entry to the `"mods"` array
   - Follow the format exactly
   - Ensure valid JSON (use a validator)

4. **Commit your changes**:
   ```bash
   git add mods.json
   git commit -m "Add [Your Mod Name] v1.0.0"
   git push origin main
   ```

5. **Create a Pull Request**:
   - Go to the store repository on GitHub
   - Click "New Pull Request"
   - Select your fork
   - Fill in the PR template
   - Submit for review

**Advantages**:
- Full control over your entry
- See exactly what's being submitted
- Track review comments on GitHub

---

## Validation Requirements

Your submission will be validated against these criteria:

### 1. Repository Checks

- [ ] GitHub repository is public and accessible
- [ ] Repository contains a valid `manifest.json`
- [ ] Repository has at least one tagged release
- [ ] Release includes a `.zip` file of the mod

### 2. Manifest Validation

- [ ] `manifest.json` is valid JSON (no syntax errors)
- [ ] All required fields are present
- [ ] Version follows semantic versioning (X.Y.Z)
- [ ] File paths in `files` array are correct
- [ ] Platform specifications are valid

### 3. Quality Checks

- [ ] README.md exists and is properly formatted
- [ ] Description is clear and concise
- [ ] License is specified and appropriate
- [ ] Mod has been tested and works correctly

### 4. Store Entry Validation

- [ ] `name` matches manifest.json
- [ ] `version` is the latest release
- [ ] `download.asset` references an existing release asset
- [ ] `manifest_url` is set when the asset is not a `.zip`
- [ ] `homepage` is a valid GitHub URL
- [ ] No duplicate entries (same mod name)

### Automated Validation

The store repository includes automated validation:

```bash
# Run locally before submitting
python validate_mods.py
```

This script checks:
- JSON syntax
- Required fields
- URL validity
- Duplicate detection
- Version format

---

## Approval Process

### Timeline

1. **Submission**: Submit via Discord or PR
2. **Initial Review**: 1-3 days
3. **Testing** (if needed): 1-2 days
4. **Approval & Merge**: 1 day
5. **Store Update**: Immediate (automatic)

**Total**: Usually 3-7 days

### Review Criteria

Your mod will be reviewed for:

1. **Functionality**: Does it work as described?
2. **Quality**: Is the code/content well-made?
3. **Safety**: No malicious code or inappropriate content
4. **Compatibility**: Works with FM26 and FM Reloaded
5. **Documentation**: Clear README and manifest

### Possible Outcomes

- **Approved**: Mod added to store immediately
- **Changes Requested**: Minor fixes needed (you'll be notified)
- **Rejected**: Doesn't meet requirements (rare, with explanation)

### Notification

You'll be notified via:
- Discord message (if submitted via app)
- GitHub PR comments (if submitted via PR)
- Email (if provided)

---

## Updating Your Mod

When you release a new version:

### Option 1: Automated (Preferred)

If your mod is already in the store, the maintainer will periodically check for updates:

1. Create a new GitHub release with updated version tag
2. Upload the new `.zip` file
3. Update your README/changelog
4. Store will be updated within 7 days

### Option 2: Manual Update Request

Submit an update request:

1. **Via Discord**: Use "Submit Mod" button again with new version
2. **Via PR**: Update your entry in `mods.json` and submit PR

Include in your request:
- Mod name
- Old version → New version
- Link to new release
- Brief changelog

### Version Increment Guidelines

- **Patch (1.0.X)**: Bug fixes, minor tweaks
- **Minor (1.X.0)**: New features, backwards compatible
- **Major (X.0.0)**: Breaking changes, major overhaul

---

## Store Repository Structure

Understanding the store repository helps with submissions:

```
FM-Reloaded-Store/
├── mods.json                 # Main store index
├── README.md                 # Store documentation
├── SUBMISSION_TEMPLATE.md    # PR template
├── scripts/
│   ├── validate_mods.py      # Validation script
│   └── update_downloads.py   # Download counter
├── .github/
│   ├── workflows/
│   │   ├── validate-pr.yml   # Auto-validation on PR
│   │   └── update-stats.yml  # Daily stats update
│   └── PULL_REQUEST_TEMPLATE.md
└── images/                   # Optional screenshots
```

### mods.json Structure

```json
{
  "version": "1.0.0",
  "last_updated": "2025-01-15T12:00:00Z",
  "mod_count": 42,
  "mods": [
    {
      "name": "Mod 1",
      "version": "1.0.0",
      ...
    },
    {
      "name": "Mod 2",
      "version": "2.1.0",
      ...
    }
  ]
}
```

---

## Best Practices

### Before Submitting

1. **Test thoroughly** on your target platform(s)
2. **Use semantic versioning** consistently
3. **Write clear documentation**
4. **Choose an appropriate license**
5. **Tag your releases** properly

### During Submission

1. **Fill all required fields** accurately
2. **Use descriptive commit messages**
3. **Verify your release asset** exists and matches the `download.asset` entry
4. **Check for duplicates** (search existing mods)
5. **Provide contact info** for follow-up

### After Approval

1. **Monitor user feedback** (GitHub issues)
2. **Release updates** when FM26 updates
3. **Keep your README** up-to-date
4. **Respond to bug reports** promptly
5. **Credit contributors** and assets

---

## Common Issues

### Submission Rejected

**Reason**: Invalid `manifest.json`
**Solution**: Validate JSON syntax, ensure all required fields present

**Reason**: Broken download link
**Solution**: Verify the release asset name in GitHub matches `download.asset` (and `latest`/`tag` settings)

**Reason**: Duplicate mod name
**Solution**: Choose a unique name or coordinate with existing mod author

- Ensure the release is **public**, not a draft
- Example direct asset download link with tagged release:
  ```
  https://github.com/user/repo/releases/download/v1.0.0/mod.zip
  ```
- Latest-channel releases must use the exact asset name:
  ```
  https://github.com/user/repo/releases/latest/download/Plugin.dll
  ```
- Do not link to the release page itself.

### Version Mismatch

- Store version must match your latest release tag
- Update both `mods.json` entry and GitHub release

---

## Examples

### Example 1: Simple Submission

GitHub repo: `https://github.com/modder/simple-ui-mod`

**mods.json entry**:
```json
{
  "name": "Simple UI Enhancement",
  "version": "1.0.0",
  "type": "ui",
  "author": "Modder123",
  "description": "Clean and simple UI improvements for better visibility",
  "homepage": "https://github.com/modder/simple-ui-mod",
  "download": {
    "type": "github_release",
    "repo": "modder/simple-ui-mod",
    "asset": "simple-ui-mod.zip",
    "tag_prefix": "v"
  },
  "install_notes": "Replaces ui-panelids_assets_all.bundle inside the FM data folder."
}
```

### Example 2: Advanced Submission with Dependencies

GitHub repo: `https://github.com/graphicsteam/mega-logo-pack`

**mods.json entry**:
```json
{
  "name": "Mega Logo Pack 2026",
  "version": "2.0.1",
  "type": "graphics",
  "author": "GraphicsTeam",
  "description": "Complete logo pack for all European leagues with 4K quality badges",
  "homepage": "https://github.com/graphicsteam/mega-logo-pack",
  "download": {
    "type": "github_release",
    "repo": "graphicsteam/mega-logo-pack",
    "asset": "mega-logo-pack.zip",
    "tag": "release-2026"
  },
  "install_notes": "Extracts logos into Documents/Sports Interactive/Football Manager 2026/graphics/logos/premier-league/.",
  "changelog_url": "https://github.com/graphicsteam/mega-logo-pack/blob/main/CHANGELOG.md",
  "downloads": 1543,
  "date_added": "2025-01-01",
  "last_updated": "2025-01-15",
  "dependencies": [],
  "conflicts": ["Other-Logo-Pack"],
  "compatibility": {
    "fm_version": "26.0.0",
    "min_loader_version": "0.5.0"
  }
}
```

### Example 3: BepInEx Plugin (single DLL)

GitHub repo: `https://github.com/examplemods/fm-pov-camera`

**mods.json entry**:
```json
{
  "name": "Example POV Camera",
  "version": "1.0.3",
  "type": "misc",
  "author": "ExampleMods",
  "description": "First-person match camera controlled by hotkeys",
  "homepage": "https://github.com/examplemods/fm-pov-camera",
  "download": {
    "type": "github_release",
    "repo": "examplemods/fm-pov-camera",
    "asset": "ExamplePovCamera.dll",
    "latest": true
  },
  "manifest_url": "https://raw.githubusercontent.com/examplemods/fm-pov-camera/main/manifest.json",
  "install_notes": "Copies ExamplePovCamera.dll to BepInEx/plugins/."
}
```

---

## Support

Need help with your submission?

- **Discord**: Join the FM Reloaded community server
- **GitHub Issues**: [Open an issue](../../issues)
- **Email**: Contact the store maintainer
- **Wiki**: [Store documentation](../../wiki)

---

## License

Mods submitted to the FM Reloaded Trusted Store must use an open-source or permissive license. Recommended licenses:

- **CC BY-SA 4.0** (Creative Commons Attribution-ShareAlike)
- **MIT License**
- **Apache 2.0**
- **GPL v3** (if you want to enforce open-source derivatives)

---

## Checklist

Before submitting, ensure you have:

- [ ] Public GitHub repository
- [ ] Valid `manifest.json` in repository
- [ ] README.md with installation instructions
- [ ] LICENSE file
- [ ] At least one tagged release
- [ ] Release includes a ZIP package or a single asset plus `manifest_url`
- [ ] Tested on Windows and/or macOS
- [ ] Descriptive mod description
- [ ] changelog.md (recommended)
- [ ] Screenshots (recommended)

---

Thank you for contributing to the FM Reloaded mod ecosystem! Your mods make Football Manager better for everyone. ⚽
