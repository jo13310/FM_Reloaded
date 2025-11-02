## 🧩 For Modders: Packaging Mods for FM Reloaded

FM Reloaded supports a range of Football Manager 2026 mod types — from UI and bundle edits to graphics and tactics packs — and handles installation automatically based on your manifest.
This section explains how to structure and package your mods so they're compatible with FM Reloaded.

---

### ⚙️ Supported Mod Types

| Type         | Description                                                          | Typical Files                          | Destination                                          |
| ------------ | -------------------------------------------------------------------- | -------------------------------------- | ---------------------------------------------------- |
| **ui**       | UI bundles that replace interface panels, menus, or in-game overlays | `.bundle`                              | Game directory → `StreamingAssets/aa/Standalone...`  |
| **bundle**   | Core game assets (graphics, shaders, lighting, etc.)                 | `.bundle`                              | Game directory → `StreamingAssets/aa/Standalone...`  |
| **tactics**  | Custom tactics that appear under "Load Tactic"                       | `.fmf`                                 | User folder → `Football Manager 26/tactics/`         |
| **graphics** | Logo, kit, and face packs                                            | `logos/`, `kits/`, or `faces/` folders | User folder → `Football Manager 26/graphics/<type>/` |
| **misc**     | Configs, XMLs, or scripts that don't fit other categories            | `.xml`, `.txt`, etc.                   | User folder → `Football Manager 26/`                 |

FM Reloaded automatically detects where each mod type belongs and installs it in the correct directory for both Windows and macOS.

---

### 📁 Directory Structure

Your mod folder (or `.zip`) should have this simple structure:

```
MyMod/
│
├─ manifest.json            <-- REQUIRED
├─ my_mod_file.bundle       <-- or .fmf, .xml, etc.
├─ logos/                   <-- (optional) subfolders for graphics
│   ├─ clubs/
│   ├─ nations/
│   └─ config.xml
└─ README.txt               <-- optional
```

When compressed, it should look like:

```
MyMod.zip
 ├─ manifest.json
 ├─ logos/
 └─ ...
```

⚠️ **Important:** `manifest.json` must be in the *root* of the mod folder or ZIP.
FM Reloaded will reject any archive without it.

---

### 🧾 Example Manifest Format

Each mod needs a `manifest.json` file that tells FM Reloaded what it is and where files go.

```json
{
  "name": "UI Speedster",
  "version": "1.0.0",
  "type": "ui",
  "author": "BassyBoy",
  "homepage": "https://discord.gg/qXbfmkVXth",
  "description": "Streamlined interface overhaul for FM26.",
  "files": [
    { "source": "ui-panelids_assets_all.bundle", "target_subpath": "ui-panelids_assets_all.bundle", "platform": "mac" },
    { "source": "ui-panelids_assets_all.bundle", "target_subpath": "ui-panelids_assets_all.bundle", "platform": "windows" }
  ]
}
```

---

### 🔧 Manifest Field Reference

| Field           | Required   | Description                                            |
| --------------- | ---------- | ------------------------------------------------------ |
| **name**        | ✅          | Display name of the mod                                |
| **version**     | ✅          | Version number (e.g., `"1.0.0"`)                       |
| **type**        | ✅          | One of: `ui`, `bundle`, `tactics`, `graphics`, `misc`  |
| **author**      | ✅          | Mod creator name                                       |
| **homepage**    | ⛔ Optional | URL or Discord link for your mod                       |
| **description** | ⛔ Optional | Short summary shown in the app                         |
| **files**       | ✅          | List of `{ source, target_subpath, platform }` objects |
| **platform**    | ⛔ Optional | `"windows"`, `"mac"`, or omitted for both              |

---

### 🧠 Platform & File Handling Notes

* **FM Reloaded** automatically merges folders (e.g., `graphics/logos`) and backs up existing files before overwriting.
* `.bundle` files in **UI** or **bundle** types replace the originals in the FM game directory.
* **Graphics**, **faces**, and **kits** mods get installed into subfolders inside the `graphics/` directory (auto-created if missing).
* You can include platform-specific entries for Mac and Windows if your bundle names differ.

---

### 📦 Packaging and Testing

1. Make sure your mod folder includes a valid `manifest.json`.
2. Zip the entire folder (not just the files inside it).
3. Test importing via FM Reloaded:

   * Drag-and-drop your ZIP into the app window, or
   * Click **Import Mod…** and select your archive.
4. FM Reloaded will unpack it, verify the manifest, and install it automatically.
5. The mod will now appear in your list, ready to enable or disable.

---

### 🧰 Example Mods Included

The repository includes sample mods for reference under `/example mods`:

```
example mods/
 ├─ KNAP's Beta Tactics.zip
 ├─ Logopack.zip
 └─ UI Speedster.zip
```

Each demonstrates one of the supported mod types with working manifests and structures.

---

### 📘 Additional Resources

For more detailed information:
- **[MODDER_GUIDE.md](../../MODDER_GUIDE.md)** - Complete modding guide
- **[STORE_SUBMISSION.md](../../STORE_SUBMISSION.md)** - How to submit to FM Reloaded Trusted Store
- **Mod Template Generator** - Available in the app under Actions → Generate Mod Template

---

### 🌐 Submitting to the Mod Store

Want your mod available for easy installation by all FM Reloaded users?

1. **Host on GitHub** with a valid `manifest.json`
2. **Create a release** with your mod as a `.zip` asset
3. **Submit via app**: Click "Submit Mod" in FM Reloaded footer, or
4. **Submit via PR**: Fork the [FM_Reloaded_Trusted_Store](https://github.com/jo13310/FM_Reloaded_Trusted_Store) and submit a pull request

See [STORE_SUBMISSION.md](../../STORE_SUBMISSION.md) for detailed submission guidelines.
