"""
Environment Configuration for IBKR Options Trader

🏗️ SHARED INFRASTRUCTURE PHILOSOPHY:
- Virtual Environment: One .venv/ for both dev/prod (same dependencies)
- TradeStation Dictionary: Same 'IBKR-TRADER' name (no strategy changes needed)  
- Core Application: Same code files with environment-aware configuration

🔄 SMART SEPARATION:
- Data Files: settings_dev.json vs settings_prod.json
- Client IDs: Dev (100-199) vs Prod (1-99) ranges
- Ports: Dev (7497 paper) vs Prod (7496 live)
- Logs: logs_dev/ vs logs_prod/ directories

⚙️ TRADING CONFIGURATION:
- Instrument Selection: Set SELECTED_INSTRUMENT to 'XSP' or 'SPX'
- Environment Control: Set ENVIRONMENT_OVERRIDE to 'development' or 'production'

⚠️ RECOMMENDED DEPLOYMENT:
For best results, use machine-specific local folders instead of shared Dropbox:
- Dev Machine: C:\Trading\IBKR_XSP_Trader_DEV\ (local copy)
- Prod Machine: C:\Trading\IBKR_XSP_Trader_PROD\ (local copy)
- Code Sharing: Git repo or Dropbox for source code only
See MIGRATION_TO_LOCAL_FOLDERS.md for complete setup instructions.

Author: Van Gothreaux
Date: November 2025
"""

# ============================================================================
# 🔧 ENVIRONMENT OVERRIDE - SET THIS MANUALLY FOR EACH DIRECTORY
# ============================================================================
# Set this to 'development' or 'production' to override automatic detection
# This is the primary method for determining environment
# 
# WORKFLOW: Use Git to manage separate dev/prod directories:
# - Development directory: Set to 'development' (this directory)
# - Production directory: Set to 'production' 
# - Use Git to sync code changes between directories
ENVIRONMENT_OVERRIDE = 'development'  # Change to 'production' in prod directory
# ============================================================================

# ============================================================================
# ⚙️ TRADING INSTRUMENT SELECTION - CONFIGURE THE TRADING INSTRUMENT
# ============================================================================
# Set this to either 'SPX' (full-size S&P 500) or 'XSP' (mini 1/10 size)
# This controls which instrument the application will trade
SELECTED_INSTRUMENT = 'XSP'  # Change to 'SPX' for full-size S&P 500 trading
# ============================================================================

import os
import socket
from pathlib import Path
from typing import Dict, Any


class Config:
    """
    Environment configuration implementing shared infrastructure philosophy
    
    Automatically detects environment and provides appropriate configuration
    while maintaining shared virtual environment and TradeStation dictionary.
    """
    
    def __init__(self):
        self.environment = self.detect_environment()
        
    def detect_environment(self) -> str:
        """
        Detect environment based on multiple methods (priority order):
        1. ENVIRONMENT_OVERRIDE variable at top of this file (primary method)
        2. Environment variable (TRADING_ENV=production|development)
        3. Computer hostname keywords (prod, dev, trading, test, etc.)
        4. Default to development (safe fallback)
        """
            
        # Method 1: Check ENVIRONMENT_OVERRIDE variable (primary)
        if ENVIRONMENT_OVERRIDE:
            return ENVIRONMENT_OVERRIDE.lower()
            
        # Method 2: Check environment variable
        env_override = os.getenv('TRADING_ENV')
        if env_override:
            return env_override.lower()
            
        # Method 3: Check computer hostname
        hostname = socket.gethostname().lower()
        production_keywords = ['trading', 'prod', 'live', 'trader']
        
        for keyword in production_keywords:
            if keyword in hostname:
                return 'production'
                
        # Default to development for safety
        return 'development'
    
    @property
    def is_production(self) -> bool:
        """True if running in production environment"""
        return self.environment == 'production'
    
    @property
    def is_development(self) -> bool:
        """True if running in development environment"""
        return self.environment == 'development'
    
    def get_config(self) -> Dict[str, Any]:
        """Get environment-specific configuration"""
        return ENV_CONFIG[self.environment]


# Environment-specific configurations
ENV_CONFIG = {
    'development': {
        # Connection settings (SEPARATED: Different ranges/ports per environment)
        'client_id_start': 100,           # Dev range: 100-199 (no conflicts with prod)
        'client_id_end': 199,
        'ibkr_port': 7497,                # Paper trading port (dev safety)
        'host': '127.0.0.1',
        'auto_connect': False,            # Manual connection for development safety
        
        # File paths (SEPARATED: Environment-specific data files)
        'settings_file': 'settings_dev.json',    # Dev-only settings
        'positions_file': 'positions_dev.json',  # Dev-only positions
        'log_dir': 'logs_dev',                   # Dev-only logs
        'log_prefix': 'DEV_',
        
        # Logging
        'log_level': 'DEBUG',             # More verbose logging
        'console_log_level': 'INFO',
        
        # Trading safety
        'paper_trading_only': True,       # Force paper trading
        'max_order_size': 1,              # Limit order sizes in dev
        'enable_live_orders': False,      # Block live orders
        
        # UI settings
        'window_title_prefix': '[DEV]',
        'border_color': '#FF0000',        # Red border for dev
        'theme_accent': '#FF4444',
        
        # TradeStation (SHARED: Same dictionary name for both environments)
        'tradestation_dict_name': 'IBKR-TRADER',  # SHARED: No strategy changes needed!
        'ts_auto_connect': False,         # Manual TS connection in dev
        
        # Feature flags
        'enable_auto_trading': False,     # Disable automation in dev
        'enable_order_chasing': True,     # Allow for testing
        'show_debug_info': True,
    },
    'production': {
        # Connection settings (SEPARATED: Different ranges/ports per environment)
        'client_id_start': 1,             # Prod range: 1-99 (no conflicts with dev)
        'client_id_end': 99,
        'ibkr_port': 7496,                # Live trading port (production)
        'host': '127.0.0.1',
        'auto_connect': True,             # Auto-connect for live trading
        
        # File paths (SEPARATED: Environment-specific data files)  
        'settings_file': 'settings_prod.json',   # Prod-only settings
        'positions_file': 'positions_prod.json', # Prod-only positions
        'log_dir': 'logs_prod',                  # Prod-only logs
        'log_prefix': 'PROD_',
        
        # Logging
        'log_level': 'INFO',              # Less verbose
        'console_log_level': 'INFO',
        
        # Trading safety
        'paper_trading_only': False,      # Allow live trading
        'max_order_size': 10,             # Higher limits
        'enable_live_orders': True,       # Allow live orders
        
        # UI settings
        'window_title_prefix': '[PROD]',
        'border_color': '#00FF00',        # Green border for prod
        'theme_accent': '#00AA00',
        
        # TradeStation (SHARED: Same dictionary name for both environments)
        'tradestation_dict_name': 'IBKR-TRADER',  # SHARED: No strategy changes needed!
        'ts_auto_connect': True,          # Auto-connect in production
        
        # Feature flags
        'enable_auto_trading': True,      # Enable automation
        'enable_order_chasing': True,     # Enable order chasing
        'show_debug_info': False,
    }
}

# 🏗️ SHARED INFRASTRUCTURE NOTES:
# - Virtual Environment (.venv/): SHARED between both environments
# - TradeStation Dictionary: SHARED name 'IBKR-TRADER' (no strategy changes)
# - Core Application Code: SHARED with environment-aware configuration
# - Data Files: SEPARATED per environment (settings, positions, logs)
# - Client IDs: SEPARATED ranges to prevent conflicts
# - This approach provides optimal separation with minimal complexity

# Global configuration instance
config = Config()
current_config = config.get_config()


def validate_environment() -> list[str]:
    """
    Validate environment setup and return list of issues
    Returns empty list if everything is OK
    """
    issues = []
    
    if config.is_production:
        # Production-specific validations
        
        # Check for trading approval flag
        if not Path('trading_approved.flag').exists():
            issues.append("❌ Missing trading_approved.flag file - create this file to confirm production trading approval")
            
        # Check for conflicting development processes (optional - requires psutil)
        try:
            import psutil
            current_pid = os.getpid()
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info['cmdline']
                    if cmdline and 'main.py' in ' '.join(cmdline):
                        if proc.info['pid'] != current_pid:
                            issues.append(f"❌ Another trading instance is running (PID: {proc.info['pid']})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            issues.append("⚠️ psutil not installed - cannot check for conflicting processes (optional feature)")
            
        # Check for development files in production environment
        dev_files = ['.env_dev', 'settings_dev.json', 'positions_dev.json']
        for dev_file in dev_files:
            if Path(dev_file).exists():
                issues.append(f"⚠️  Development file {dev_file} found in production environment")
                
    else:  # Development environment
        # Development-specific validations
        
        # Warn if production files exist
        prod_files = ['.env_prod', 'trading_approved.flag']
        for prod_file in prod_files:
            if Path(prod_file).exists():
                issues.append(f"⚠️  Production file {prod_file} found in development environment")
    
    # Check for shared folder deployment (affects both environments)
    current_path = Path.cwd().as_posix().lower()
    shared_folder_indicators = ['dropbox', 'onedrive', 'googledrive', 'icloud', 'sync']
    
    if any(indicator in current_path for indicator in shared_folder_indicators):
        issues.append("⚠️  Running from shared/cloud folder - consider using machine-specific local folders")
        issues.append("   📖 See MIGRATION_TO_LOCAL_FOLDERS.md for recommended setup")
        issues.append(f"   📂 Current path: {Path.cwd()}")
    
    return issues


def create_environment_marker(env_type: str) -> None:
    """
    Create environment marker file
    NOTE: With ENVIRONMENT_OVERRIDE variable, this is less needed but kept for compatibility
    """
    if env_type == 'production':
        Path('.env_prod').touch()
        if Path('.env_dev').exists():
            Path('.env_dev').unlink()
        print(f"⚠️  Note: ENVIRONMENT_OVERRIDE variable is set to '{ENVIRONMENT_OVERRIDE}'")
        print("   Update the variable at the top of config.py for primary control")
    elif env_type == 'development':
        Path('.env_dev').touch()
        if Path('.env_prod').exists():
            Path('.env_prod').unlink()
        print(f"⚠️  Note: ENVIRONMENT_OVERRIDE variable is set to '{ENVIRONMENT_OVERRIDE}'")
        print("   Update the variable at the top of config.py for primary control")


def get_selected_instrument() -> str:
    """Get the currently selected trading instrument"""
    return SELECTED_INSTRUMENT


def get_environment_info() -> str:
    """Get formatted environment information string"""
    info_lines = [
        f"🔧 Environment: {config.environment.upper()}",
        f"📈 Instrument: {SELECTED_INSTRUMENT}",
        f"⚙️  Override Variable: {ENVIRONMENT_OVERRIDE}",
        f"🖥️  Hostname: {socket.gethostname()}",
        f"📁 Settings: {current_config['settings_file']}",
        f"📊 Positions: {current_config['positions_file']}",
        f"🔌 Port: {current_config['ibkr_port']}",
        f"🆔 Client ID Start: {current_config['client_id_start']}",
        f"📡 TradeStation Dict: {current_config['tradestation_dict_name']}"
    ]
    
    if config.is_production:
        info_lines.append("🚨 LIVE TRADING ENVIRONMENT")
    else:
        info_lines.append("🧪 DEVELOPMENT ENVIRONMENT")
        
    return '\n'.join(info_lines)


if __name__ == "__main__":
    # CLI interface for environment management
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'info':
            print(get_environment_info())
            issues = validate_environment()
            if issues:
                print("\n⚠️  Issues found:")
                for issue in issues:
                    print(f"   {issue}")
            else:
                print("\n✅ Environment validation passed")
                
        elif command == 'set':
            if len(sys.argv) > 2:
                env_type = sys.argv[2].lower()
                if env_type in ['dev', 'development']:
                    create_environment_marker('development')
                    print("✅ Environment set to DEVELOPMENT")
                elif env_type in ['prod', 'production']:
                    create_environment_marker('production')
                    print("✅ Environment set to PRODUCTION")
                else:
                    print("❌ Invalid environment. Use 'dev' or 'prod'")
            else:
                print("❌ Usage: python config.py set <dev|prod>")
                
        elif command == 'approve':
            if config.is_production:
                Path('trading_approved.flag').touch()
                print("✅ Production trading approved")
            else:
                print("❌ Not in production environment")
                
        else:
            print("❌ Unknown command")
            print("Usage: python config.py <info|set|approve>")
    else:
        print(get_environment_info())