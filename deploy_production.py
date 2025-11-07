"""
Production Deployment Helper for IBKR XSP Option Trader

This script helps set up and deploy the production environment safely.
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime


def print_header(title):
    """Print a formatted header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_step(step_num, description):
    """Print a numbered step"""
    print(f"\n[STEP {step_num}] {description}")


def confirm_action(message):
    """Ask for user confirmation"""
    response = input(f"\n{message} (y/N): ").strip().lower()
    return response in ['y', 'yes']


def run_command(command, description):
    """Run a command and return the result"""
    print(f"  Running: {command}")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✅ Success: {description}")
            return True, result.stdout
        else:
            print(f"  ❌ Failed: {description}")
            print(f"     Error: {result.stderr}")
            return False, result.stderr
    except Exception as e:
        print(f"  ❌ Exception: {e}")
        return False, str(e)


def check_prerequisites():
    """Check if system is ready for production deployment"""
    print_step(1, "Checking Prerequisites")
    
    issues = []
    
    # Check if main.py exists
    if not Path("main.py").exists():
        issues.append("main.py not found - ensure you're in the correct directory")
    
    # Check if config.py exists
    if not Path("config.py").exists():
        issues.append("config.py not found - environment system not installed")
    
    # Check Python version
    if sys.version_info < (3, 8):
        issues.append(f"Python {sys.version} is too old - requires Python 3.8+")
    
    # Check current environment
    try:
        success, output = run_command("python config.py info", "environment check")
        if "PRODUCTION" in output:
            print("  ⚠️  Already in production environment")
        elif "DEVELOPMENT" in output:
            print("  ✅ Currently in development environment")
        else:
            issues.append("Cannot determine current environment")
    except:
        issues.append("Cannot run environment check")
    
    if issues:
        print("\n❌ Prerequisites check failed:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    
    print("  ✅ All prerequisites met")
    return True


def backup_current_settings():
    """Backup current settings before deployment"""
    print_step(2, "Backing Up Current Settings")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(f"backup_{timestamp}")
    backup_dir.mkdir(exist_ok=True)
    
    files_to_backup = [
        "settings.json",
        "settings_dev.json", 
        "settings_prod.json",
        "positions.json",
        "positions_dev.json",
        "positions_prod.json"
    ]
    
    backed_up = []
    for file in files_to_backup:
        if Path(file).exists():
            try:
                shutil.copy2(file, backup_dir / file)
                backed_up.append(file)
                print(f"  ✅ Backed up: {file}")
            except Exception as e:
                print(f"  ⚠️  Failed to backup {file}: {e}")
    
    if backed_up:
        print(f"\n  📁 Backup created in: {backup_dir}")
        print(f"  📄 Files backed up: {len(backed_up)}")
        return str(backup_dir)
    else:
        print("  ℹ️  No existing settings files to backup")
        return None


def setup_production_environment():
    """Set up production environment files"""
    print_step(3, "Setting Up Production Environment")
    
    # Force production environment
    print("  Creating production environment marker...")
    Path(".env_prod").write_text(
        "# This file forces PRODUCTION environment\n"
        "# CAUTION: Live trading environment\n"
        "# Ensure all settings are verified before use\n"
        f"# Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    print("  ✅ Created .env_prod file")
    
    # Remove development marker if it exists
    if Path(".env_dev").exists():
        Path(".env_dev").unlink()
        print("  🗑️  Removed .env_dev file")
    
    # Verify environment
    success, output = run_command("python config.py info", "environment verification")
    if success and "PRODUCTION" in output:
        print("  ✅ Production environment confirmed")
        return True
    else:
        print("  ❌ Failed to set production environment")
        return False


def create_production_settings():
    """Create production-specific settings"""
    print_step(4, "Creating Production Settings")
    
    # Default production settings
    prod_settings = {
        "host": "127.0.0.1",
        "port": 7496,  # Live trading port
        "client_id": 1,
        "strikes_above": 10,
        "strikes_below": 10,
        "chain_refresh_interval": 3600,
        "chain_drift_threshold": 5,
        "ts_strikes_above": 6,
        "ts_strikes_below": 6,
        "ts_chain_drift_threshold": 3,
        "show_all_gd_communications": False,
        "es_to_cash_offset": 0.0,
        "last_offset_update_time": 0,
        "strategy_enabled": False,  # Safety: disabled by default
        "vix_threshold": 20.0,
        "time_stop": 60,
        "target_delta": 30,
        "max_risk": 500,
        "trade_qty": 1,
        "position_size_mode": "fixed",
        "straddle_enabled": False,  # Safety: disabled by default
        "straddle_frequency": 60,
        "confirm_ema_length": 9,
        "confirm_z_period": 30,
        "confirm_z_threshold": 1.5,
        "trade_ema_length": 9,
        "trade_z_period": 30,
        "trade_z_threshold": 1.5
    }
    
    settings_file = "settings_prod.json"
    
    if Path(settings_file).exists():
        if confirm_action(f"Production settings file {settings_file} already exists. Overwrite?"):
            Path(settings_file).write_text(json.dumps(prod_settings, indent=2))
            print(f"  ✅ Overwrote {settings_file}")
        else:
            print(f"  ⏩ Kept existing {settings_file}")
    else:
        Path(settings_file).write_text(json.dumps(prod_settings, indent=2))
        print(f"  ✅ Created {settings_file}")
    
    # Create empty production positions file
    positions_file = "positions_prod.json"
    if not Path(positions_file).exists():
        Path(positions_file).write_text("{}")
        print(f"  ✅ Created empty {positions_file}")
    
    return True


def verify_production_setup():
    """Verify production environment is correctly configured"""
    print_step(5, "Verifying Production Setup")
    
    checks = []
    
    # Check environment detection
    success, output = run_command("python config.py info", "environment info")
    if success and "PRODUCTION" in output:
        checks.append(("Environment Detection", True, "Production environment detected"))
        
        # Parse output for details
        for line in output.split('\n'):
            if "Port:" in line:
                port = line.split(':')[1].strip()
                if port == "7496":
                    checks.append(("IBKR Port", True, f"Live trading port ({port})"))
                else:
                    checks.append(("IBKR Port", False, f"Wrong port ({port}) - should be 7496"))
            
            elif "Client ID Start:" in line:
                client_id = line.split(':')[1].strip()
                if client_id == "1":
                    checks.append(("Client ID", True, f"Production range starts at {client_id}"))
                else:
                    checks.append(("Client ID", False, f"Wrong client ID start ({client_id})"))
            
            elif "TradeStation Dict:" in line:
                dict_name = line.split(':')[1].strip()
                if "PROD" in dict_name:
                    checks.append(("TradeStation", True, f"Production dictionary ({dict_name})"))
                else:
                    checks.append(("TradeStation", False, f"Wrong dictionary ({dict_name})"))
    else:
        checks.append(("Environment Detection", False, "Production environment not detected"))
    
    # Check production files
    prod_files = ["settings_prod.json", "positions_prod.json", ".env_prod"]
    for file in prod_files:
        if Path(file).exists():
            checks.append((f"File {file}", True, "Exists"))
        else:
            checks.append((f"File {file}", False, "Missing"))
    
    # Print results
    print("\n  Verification Results:")
    all_passed = True
    for check_name, passed, message in checks:
        status = "✅" if passed else "❌"
        print(f"    {status} {check_name}: {message}")
        if not passed:
            all_passed = False
    
    return all_passed


def show_deployment_summary():
    """Show summary and next steps"""
    print_header("Deployment Complete")
    
    print("🎉 Production environment has been set up successfully!")
    print(f"\nNext Steps:")
    print("1. Review production settings in settings_prod.json")
    print("2. Configure IBKR TWS/Gateway for live trading (port 7496)")
    print("3. Update TradeStation with IBKR-TRADER-PROD dictionary")
    print("4. Test connection: python main.py")
    print("5. Approve production mode: python config.py approve")
    
    print(f"\n⚠️  Important Reminders:")
    print("• This is now a LIVE TRADING environment")
    print("• All orders will execute with real money")
    print("• Verify all settings before trading")
    print("• Monitor logs for any issues")
    
    print(f"\n📚 For detailed information:")
    print("• Read ENVIRONMENT_GUIDE.md")
    print("• Run 'python config.py info' to check status")


def main():
    """Main deployment process"""
    print_header("IBKR XSP Option Trader - Production Deployment")
    
    print("This script will set up a production environment for live trading.")
    print("⚠️  WARNING: Production environment involves real money and live trading!")
    
    if not confirm_action("Are you sure you want to proceed with production deployment?"):
        print("\n❌ Deployment cancelled by user")
        return
    
    try:
        # Check prerequisites
        if not check_prerequisites():
            print("\n❌ Deployment aborted due to prerequisite failures")
            return
        
        # Backup current settings
        backup_dir = backup_current_settings()
        
        # Set up production environment
        if not setup_production_environment():
            print("\n❌ Failed to set up production environment")
            return
        
        # Create production settings
        if not create_production_settings():
            print("\n❌ Failed to create production settings")
            return
        
        # Verify setup
        if not verify_production_setup():
            print("\n⚠️  Production setup has issues - please review before proceeding")
        
        # Show summary
        show_deployment_summary()
        
        if backup_dir:
            print(f"\n📁 Original files backed up to: {backup_dir}")
    
    except KeyboardInterrupt:
        print("\n\n❌ Deployment cancelled by user (Ctrl+C)")
    except Exception as e:
        print(f"\n❌ Deployment failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()