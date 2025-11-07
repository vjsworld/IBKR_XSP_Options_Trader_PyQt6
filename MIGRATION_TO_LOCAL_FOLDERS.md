# Project Structure Migration Guide

## Current Issue: Dropbox Shared Folder

You're currently running both development and production environments from the same Dropbox folder:
```
📁 d:\Dropbox\VRB Share\IBKR XSP Option Trader1 (PyQt6)\
```

This creates several problems:
- File conflicts when both machines access same data files
- Configuration changes sync instantly between environments  
- No isolation between development and production data
- Risk of untested code affecting production

## Recommended Solution: Machine-Specific Local Copies

### Setup Instructions

#### Step 1: Create Local Directories
```powershell
# On Development Machine:
mkdir C:\Trading\IBKR_XSP_Trader_DEV
cd C:\Trading\IBKR_XSP_Trader_DEV

# On Production Machine:  
mkdir C:\Trading\IBKR_XSP_Trader_PROD
cd C:\Trading\IBKR_XSP_Trader_PROD
```

#### Step 2: Copy Code Files (Both Machines)
Copy these files from Dropbox to local directory:
```
✅ main.py
✅ config.py  
✅ requirements.txt
✅ README.md
✅ *.md (documentation files)
```

#### Step 3: Create Local Virtual Environments
```powershell
# On each machine:
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

#### Step 4: Initialize Environment-Specific Files
```powershell
# These files will be created locally, NOT synced:
python config.py info          # Creates initial environment detection
# App will auto-create: settings_dev.json, settings_prod.json, positions_*.json, logs_*/
```

### Ongoing Workflow

#### For Code Changes:
1. **Develop** in local DEV folder: `C:\Trading\IBKR_XSP_Trader_DEV\`
2. **Test** thoroughly in development environment
3. **Copy** tested files to Dropbox: `\Dropbox\VRB Share\IBKR_XSP_Trader_Source\`  
4. **Deploy** from Dropbox to production: `C:\Trading\IBKR_XSP_Trader_PROD\`

#### Alternative: Git Repository (Recommended)
- Initialize Git repo in Dropbox folder
- Each machine clones/pulls from repo
- Use proper version control workflow:
  ```bash
  git add . && git commit -m "feature: new trading logic"
  git push origin main
  # On other machine:
  git pull origin main
  ```

### File Organization

#### SHARED (via Dropbox/Git):
- `main.py` - Core application  
- `config.py` - Environment configuration
- `requirements.txt` - Dependencies
- `README.md` - Documentation
- `*.md` - All documentation files

#### LOCAL ONLY (never sync):
- `.venv/` - Virtual environments (recreated on each machine)
- `settings_*.json` - Environment-specific settings
- `positions_*.json` - Position tracking files  
- `logs_*/` - Log directories
- `trading_approved.flag` - Production approval (prod machine only)
- `__pycache__/` - Python cache files

### Migration Commands

#### Development Machine:
```powershell
# 1. Create local development folder
mkdir C:\Trading\IBKR_XSP_Trader_DEV
cd C:\Trading\IBKR_XSP_Trader_DEV

# 2. Copy code files (not data files)
copy "d:\Dropbox\VRB Share\IBKR XSP Option Trader1 (PyQt6)\main.py" .
copy "d:\Dropbox\VRB Share\IBKR XSP Option Trader1 (PyQt6)\config.py" .
copy "d:\Dropbox\VRB Share\IBKR XSP Option Trader1 (PyQt6)\requirements.txt" .
copy "d:\Dropbox\VRB Share\IBKR XSP Option Trader1 (PyQt6)\*.md" .

# 3. Setup virtual environment
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 4. Test development environment
python config.py info
python -c "import main; print('✅ Development setup complete')"
```

#### Production Machine:
```powershell
# 1. Create local production folder  
mkdir C:\Trading\IBKR_XSP_Trader_PROD
cd C:\Trading\IBKR_XSP_Trader_PROD

# 2. Copy code files from Dropbox
copy "d:\Dropbox\VRB Share\IBKR XSP Option Trader1 (PyQt6)\main.py" .
copy "d:\Dropbox\VRB Share\IBKR XSP Option Trader1 (PyQt6)\config.py" .
copy "d:\Dropbox\VRB Share\IBKR XSP Option Trader1 (PyQt6)\requirements.txt" .

# 3. Setup virtual environment
python -m venv .venv  
.venv\Scripts\activate
pip install -r requirements.txt

# 4. Create production approval
echo "PRODUCTION APPROVED" > trading_approved.flag

# 5. Test production environment
$env:TRADING_ENV="production"
python config.py info
python -c "import main; print('✅ Production setup complete')"
```

### Benefits After Migration

✅ **Data Isolation**: Each machine has its own settings/positions/logs
✅ **No File Conflicts**: No simultaneous access to same data files  
✅ **Environment Safety**: Development changes don't immediately affect production
✅ **Independent Operation**: Machines can run simultaneously without interference
✅ **Proper Testing**: Can fully test in dev before deploying to prod
✅ **Version Control**: Can use Git for proper code management
✅ **Backup Safety**: Local data files aren't accidentally overwritten by sync

### Current Shared Infrastructure Still Works

The environment system we built still functions perfectly:
- ✅ Same TradeStation dictionary name ('IBKR-TRADER') 
- ✅ Same virtual environment setup process
- ✅ Same core application code
- ✅ Environment auto-detection and separation
- ✅ All safety features and validation

The only change is **where** the files live - locally instead of in shared Dropbox folder.