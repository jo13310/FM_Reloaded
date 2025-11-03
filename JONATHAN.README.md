# JONATHAN'S SETUP GUIDE - FM Reloaded Mod Manager

## ✅ What Was Done

### Phase 1: Security Fixes ✅ COMPLETED
- Fixed all critical security vulnerabilities
- Added path traversal protection
- Implemented safe ZIP extraction (ZIP bomb protection)
- Added symlink detection in file operations
- Fixed bare exception handlers
- Added comprehensive security documentation

### Phase 2: Version Syncing (GitHub Actions) ✅ COMPLETED
- Created automatic version sync workflow (runs every 6 hours)
- Created validation workflows for mods.json
- Created download count validation workflow

### Phase 3: Download Tracking (Cloudflare Worker) ✅ COMPLETED
- Implemented secure server-side tracking
- NO GitHub tokens in app (secure!)
- Rate limiting built-in
- Bot protection via Cloudflare

---

## 🔧 WHAT YOU NEED TO DO

### Step 1: Setup Cloudflare Worker (One-Time, ~10 minutes)

#### 1.1 Create Cloudflare Account
1. Go to: https://dash.cloudflare.com/sign-up
2. Sign up for **FREE** account
3. Verify your email

#### 1.2 Create Worker
1. In Cloudflare dashboard, click **Workers & Pages**
2. Click **Create Worker**
3. Name it: `fm-reloaded-tracker`
4. Click **Deploy** (deploy the default code first)

#### 1.3 Upload Worker Code
1. Click **Edit Code** button
2. Delete all the default code
3. Open file: `FM_Reloaded_Trusted_Store/cloudflare-worker/worker.js`
4. Copy ALL the code
5. Paste into Cloudflare editor
6. Click **Save and Deploy**

#### 1.4 Configure Secrets
1. Click **Settings** tab
2. Click **Variables and Secrets**
3. Scroll to **Environment Variables**
4. Click **Add variable** → Select **Encrypt** (for secrets)

Add these 3 secrets:

| Variable Name | Value | Where to Get It |
|---------------|-------|-----------------|
| `GITHUB_TOKEN` | `ghp_xxxxx...` | See step 1.5 below |
| `GITHUB_OWNER` | `jo13310` | Your GitHub username |
| `GITHUB_REPO` | `FM_Reloaded_Trusted_Store` | Your repo name |

#### 1.5 Generate GitHub Token
1. Go to: https://github.com/settings/tokens/new
2. **Note**: `FM Reloaded Download Tracking`
3. **Expiration**: `No expiration` (or 1 year)
4. **Select scopes**: Check the box for `repo` (Full control of private repositories)
5. Click **Generate token**
6. **COPY THE TOKEN** (starts with `ghp_`) - you won't see it again!
7. Paste this token as `GITHUB_TOKEN` in Cloudflare (step 1.4)

#### 1.6 Enable Rate Limiting (OPTIONAL but recommended)
1. In Cloudflare, go to **Settings** → **Bindings**
2. Click **Add Binding**
3. Select **KV Namespace**
4. Variable name: `RATE_LIMIT_KV`
5. Click **Create a new namespace**
6. Namespace name: `fm-track-rate-limits`
7. Click **Save**

#### 1.7 Get Your Worker URL
Your worker URL will be:
```
https://fm-reloaded-tracker.{your-subdomain}.workers.dev
```

Example:
```
https://fm-reloaded-tracker.jonathan123.workers.dev
```

**IMPORTANT**: Copy this URL! You'll need it below.

#### 1.8 Update App with Your Worker URL
1. Open: `FM_Reloaded/src/mod_store_api.py`
2. Find line 434 (in `increment_download_count` method)
3. Change:
   ```python
   tracking_api_url = "https://fm-track.fmreloaded.workers.dev/download"
   ```
   To:
   ```python
   tracking_api_url = "https://YOUR-WORKER-URL-HERE.workers.dev/download"
   ```
4. Save file

---

### Step 2: Test Cloudflare Worker (5 minutes)

#### 2.1 Test with curl (from command line)
```bash
curl -X POST https://YOUR-WORKER-URL.workers.dev/download \
  -H "Content-Type: application/json" \
  -d "{\"mod_name\":\"Test Mod\"}"
```

Expected response:
```json
{"success":true,"mod_name":"Test Mod"}
```

Or test with PowerShell:
```powershell
Invoke-RestMethod -Method Post -Uri "https://YOUR-WORKER-URL.workers.dev/download" -ContentType "application/json" -Body '{"mod_name":"Test Mod"}'
```

#### 2.2 Check Cloudflare Logs
1. Go to Cloudflare dashboard
2. Click on your worker: `fm-reloaded-tracker`
3. Click **Logs** tab (or **Real-time Logs**)
4. Run the test above again
5. You should see log entries appear in real-time

#### 2.3 Verify GitHub Commit
1. Go to: https://github.com/jo13310/FM_Reloaded_Trusted_Store
2. Click **Commits** (or check recent commits)
3. You should see: `Increment download count: Test Mod`
4. Check `mods.json` - downloads should be incremented

---

### Step 3: Enable GitHub Actions for Version Syncing (5 minutes)

#### 3.1 Add GitHub Token to Repository Secrets
1. Go to: https://github.com/jo13310/FM_Reloaded_Trusted_Store
2. Click **Settings** tab (at the top)
3. In left sidebar, click **Secrets and variables** → **Actions**
4. Click **New repository secret**
5. Name: `GITHUB_TOKEN`
6. Value: Paste the same token from step 1.5
7. Click **Add secret**

#### 3.2 Enable Workflows
1. Go to **Actions** tab
2. If workflows are disabled, click **I understand my workflows, go ahead and enable them**
3. You should see:
   - ✅ Sync Mod Versions
   - ✅ Validate Mods JSON
   - ✅ Validate Download Counts

#### 3.3 Test Version Sync Workflow
1. Click on **Sync Mod Versions** workflow
2. Click **Run workflow** button (top right)
3. Select `main` branch
4. Check **Dry run**: `true` (for testing)
5. Click **Run workflow**
6. Wait ~30 seconds
7. Click on the running workflow to see logs
8. Should show: "All mods are up to date" or list of updates found

#### 3.4 Schedule (Automatic)
The workflow is configured to run every 6 hours automatically. No action needed!

---

### Step 4: Build & Test FM Reloaded App (10 minutes)

#### 4.1 Build the Application
```bash
cd "C:\Program Files (x86)\Steam\steamapps\common\Football Manager 26\Mods\FM_Reloaded\src"
python -m PyInstaller --clean --noconfirm fm26_mod_manager.spec
```

Expected output:
```
Building EXE from EXE-00.toc completed successfully.
```

Executable location:
```
src/dist/FM_Reloaded.exe
```

#### 4.2 Test Download Tracking
1. Run `FM_Reloaded.exe`
2. Go to **Store** tab
3. Install any mod (e.g., Arthur's PoV Camera Mod)
4. Check Cloudflare logs - should see download event
5. Check GitHub commits - should see increment commit
6. Refresh store in app - download count should increase

---

### Step 5: Commit Your Changes (Git)

#### 5.1 Check What Changed
```bash
cd "C:\Program Files (x86)\Steam\steamapps\common\Football Manager 26\Mods\FM_Reloaded"
git status
```

#### 5.2 Stage Changes
```bash
git add .github/readme.md
git add MODDER_GUIDE.md
git add src/fm26_mod_manager_gui.py
git add src/mod_store_api.py
git add src/config.example.json
git add src/fm26_mod_manager.spec
git add .gitignore
git add JONATHAN.README.md
```

#### 5.3 Commit
```bash
git commit -m "$(cat <<'EOF'
Security fixes and automated tracking implementation

- Fixed critical security vulnerabilities (path traversal, ZIP bombs, symlinks)
- Implemented secure download tracking via Cloudflare Worker (no user tokens!)
- Added automatic version syncing (GitHub Actions every 6 hours)
- Added validation workflows for data integrity
- Improved GUI modernization with ttkbootstrap
- Fixed syntax errors and indentation issues

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

#### 5.4 Push to GitHub
```bash
git push origin main
```

---

### Step 6: Setup Trusted Store Repository

#### 6.1 Commit Workflows
```bash
cd "C:\Program Files (x86)\Steam\steamapps\common\Football Manager 26\Mods\FM_Reloaded_Trusted_Store"
git add .github/workflows/
git add cloudflare-worker/
```

#### 6.2 Commit
```bash
git commit -m "$(cat <<'EOF'
Add automated version syncing and download tracking

- Automatic version detection (runs every 6 hours)
- Validation workflows for mods.json integrity
- Download count validation
- Cloudflare Worker for secure tracking

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

#### 6.3 Push
```bash
git push origin main
```

---

## 📋 CHECKLIST

Use this to track your progress:

### Cloudflare Worker Setup
- [ ] Created Cloudflare account
- [ ] Created worker: `fm-reloaded-tracker`
- [ ] Uploaded worker.js code
- [ ] Added GITHUB_TOKEN secret
- [ ] Added GITHUB_OWNER secret
- [ ] Added GITHUB_REPO secret
- [ ] (Optional) Enabled KV rate limiting
- [ ] Copied worker URL
- [ ] Updated mod_store_api.py with worker URL
- [ ] Tested with curl/PowerShell
- [ ] Verified GitHub commit created
- [ ] Checked Cloudflare logs

### GitHub Actions Setup
- [ ] Added GITHUB_TOKEN to repository secrets
- [ ] Enabled workflows in Actions tab
- [ ] Manually tested "Sync Mod Versions" workflow
- [ ] Verified workflows are scheduled (every 6 hours)

### Build & Test
- [ ] Built FM_Reloaded.exe successfully
- [ ] Tested app launches
- [ ] Tested mod installation
- [ ] Verified download tracking works
- [ ] Checked Cloudflare logs for tracking
- [ ] Verified GitHub commit for download increment

### Git Commits
- [ ] Committed FM_Reloaded changes
- [ ] Pushed to GitHub
- [ ] Committed Trusted_Store changes
- [ ] Pushed to GitHub

---

## 🎯 WHAT TO EXPECT AFTER SETUP

### Automatic Version Syncing
- **Frequency**: Every 6 hours
- **What it does**: Checks all mods for new releases on GitHub
- **Updates**: Automatically commits new versions to mods.json
- **Example**: When Arthur releases v1.2, it will be detected within 6 hours

### Download Tracking
- **When**: Every time a user installs a mod from the store
- **What happens**:
  1. App sends request to Cloudflare Worker
  2. Worker increments download count in mods.json
  3. Change committed to GitHub
  4. Download count visible in store immediately
- **Security**: No tokens in app, all handled server-side

### Validation
- **On every push**: mods.json is validated for correct structure
- **Download counts**: Never decrease, warnings for large jumps
- **Prevents**: Corrupted data, malformed JSON, invalid versions

---

## 🐛 TROUBLESHOOTING

### Cloudflare Worker Returns 500 Error
**Check:**
- Is GITHUB_TOKEN set correctly in Cloudflare secrets?
- Does the token have `repo` scope?
- Has the token expired?

**Fix:**
1. Go to Cloudflare → Worker → Settings → Variables
2. Re-add GITHUB_TOKEN secret
3. Test again

### Version Sync Not Working
**Check:**
- Is GITHUB_TOKEN added to repository secrets (not Cloudflare)?
- Are workflows enabled in Actions tab?

**Fix:**
1. Go to GitHub repo → Settings → Secrets → Actions
2. Add GITHUB_TOKEN
3. Go to Actions tab → Enable workflows

### Download Counts Not Incrementing
**Check Cloudflare Logs:**
1. Cloudflare dashboard → Worker → Logs
2. Install a mod from FM Reloaded
3. Look for errors in logs

**Common Issues:**
- Wrong worker URL in mod_store_api.py
- Rate limited (wait 1 hour)
- Network connectivity

### Build Fails with Syntax Errors
All syntax errors should be fixed, but if you see any:
```bash
python -m py_compile src/fm26_mod_manager_gui.py
```

This will show exact line number of syntax error.

---

## 📞 NEED HELP?

- **GitHub Issues**: https://github.com/jo13310/FM_Reloaded/issues
- **This README**: Read section carefully for your issue
- **Cloudflare Docs**: https://developers.cloudflare.com/workers/
- **GitHub Actions Docs**: https://docs.github.com/en/actions

---

## 🎉 YOU'RE DONE WHEN...

✅ Cloudflare Worker responds to test requests
✅ GitHub shows "Increment download count" commits
✅ FM_Reloaded.exe builds without errors
✅ Installing a mod from store increments download count
✅ Version sync workflow runs successfully
✅ All changes pushed to GitHub

**Congrats! Your mod manager is now automated and secure! 🎊**
