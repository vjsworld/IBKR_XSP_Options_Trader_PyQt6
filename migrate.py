"""
Migration Helper Script for IBKR XSP Options Trader
Helps migrate from shared Dropbox folder to machine-specific local folders
"""

import os
import shutil
from pathlib import Path


def create_local_setup(environment: str = "development"):
    """
    Create local development or production setup
    
    Args:
        environment: "development" or "production"
    """
    
    if environment not in ["development", "production"]:
        print("❌ Environment must be 'development' or 'production'")
        return
    
    # Determine local path
    env_suffix = "DEV" if environment == "development" else "PROD"
    local_path = Path(f"C:/Trading/IBKR_XSP_Trader_{env_suffix}")
    
    print(f"🚀 Setting up {environment.upper()} environment")
    print(f"📂 Target folder: {local_path}")
    
    # Create directory
    local_path.mkdir(parents=True, exist_ok=True)
    print(f"✅ Created directory: {local_path}")
    
    # Files to copy (code only, not data)
    code_files = [
        "main.py",
        "config.py", 
        "requirements.txt",
        "README.md",
        "copilot-instructions.md"
    ]
    
    # Copy documentation files
    doc_files = list(Path(".").glob("*.md"))
    
    current_dir = Path.cwd()
    copied_files = []
    
    # Copy code files
    for file_name in code_files:
        source = current_dir / file_name
        dest = local_path / file_name
        
        if source.exists():
            shutil.copy2(source, dest)
            copied_files.append(file_name)
            print(f"✅ Copied: {file_name}")
        else:
            print(f"⚠️  Not found: {file_name}")
    
    # Copy all markdown documentation files
    for md_file in doc_files:
        if md_file.name not in code_files:  # Don't double-copy
            dest = local_path / md_file.name
            shutil.copy2(md_file, dest)
            copied_files.append(md_file.name)
            print(f"✅ Copied: {md_file.name}")
    
    print(f"\n📋 Migration Summary:")
    print(f"   📂 Local folder: {local_path}")
    print(f"   📄 Files copied: {len(copied_files)}")
    print(f"   🔧 Environment: {environment.upper()}")
    
    # Create setup instructions
    setup_file = local_path / "SETUP_INSTRUCTIONS.txt"
    with open(setup_file, 'w', encoding='utf-8') as f:
        f.write(f"""IBKR XSP Options Trader - {environment.upper()} Setup

📂 Local Environment Path: {local_path}

🚀 Next Steps:

1. Open terminal in this folder:
   cd "{local_path}"

2. Create virtual environment:
   python -m venv .venv

3. Activate virtual environment:
   .venv\\Scripts\\activate

4. Install dependencies:
   pip install -r requirements.txt

5. Test configuration:
   python config.py info

6. """ + ('Create production approval (PRODUCTION ONLY):' if environment == 'production' else 'Test development environment:') + """
   """ + ('echo "PRODUCTION APPROVED" > trading_approved.flag' if environment == 'production' else 'python -c "import main; print(\'✅ Development ready\')"') + """

🔄 Environment Configuration:
- This setup will auto-detect as {environment.upper()} environment
- Settings file: settings_{environment[:3]}.json (created automatically)
- Positions file: positions_{environment[:3]}.json (created automatically)  
- Log directory: logs_{environment[:3]}/ (created automatically)
- Client ID range: {'1-99' if environment == 'production' else '100-199'}
- IBKR port: {'7496 (live)' if environment == 'production' else '7497 (paper)'}

⚠️  Data Files:
- Settings, positions, and logs will be LOCAL to this machine
- No more file conflicts with other machines
- Safe to run simultaneously with other environments

📖 For complete instructions, see:
   MIGRATION_TO_LOCAL_FOLDERS.md
""")
    
    print(f"✅ Created setup instructions: {setup_file}")
    
    if environment == "production":
        print(f"\n🚨 PRODUCTION ENVIRONMENT NOTES:")
        print(f"   ⚠️  Remember to create trading approval flag:")
        print(f"       echo \"PRODUCTION APPROVED\" > trading_approved.flag")
        print(f"   ⚠️  This enables LIVE TRADING with real money")
        print(f"   ⚠️  Only do this after thorough testing")
    
    print(f"\n🎯 Ready! Navigate to {local_path} and follow SETUP_INSTRUCTIONS.txt")


if __name__ == "__main__":
    import sys
    
    print("🏗️  IBKR XSP Options Trader - Migration Helper")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        env = sys.argv[1].lower()
        if env in ["dev", "development"]:
            create_local_setup("development")
        elif env in ["prod", "production"]:
            create_local_setup("production") 
        else:
            print("❌ Usage: python migrate.py [development|production]")
            print("   Examples:")
            print("     python migrate.py development")
            print("     python migrate.py production")
    else:
        print("Select environment to set up:")
        print("1. Development (safe testing environment)")
        print("2. Production (live trading environment)")
        
        while True:
            choice = input("\nEnter choice (1/2): ").strip()
            if choice == "1":
                create_local_setup("development")
                break
            elif choice == "2":
                confirm = input("⚠️  Production setup enables LIVE TRADING. Are you sure? (yes/no): ")
                if confirm.lower() in ["yes", "y"]:
                    create_local_setup("production")
                    break
                else:
                    print("❌ Production setup cancelled")
                    break
            else:
                print("❌ Invalid choice. Please enter 1 or 2.")