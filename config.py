"""
Environment Configuration for IBKR XSP Options Trader
Automatically detects and configures development vs production environments

Author: Van Gothreaux
Date: November 2025
"""

import os
import socket
from pathlib import Path
from typing import Dict, Any


class Config:
    """Environment configuration class"""
    
    def __init__(self):
        self.environment = self.detect_environment()
        
    def detect_environment(self) -> str:
        """
        Detect environment based on multiple methods:
        1. Environment file (.env_prod)
        2. Computer hostname
        3. Environment variable
        """
        
        # Method 1: Check for environment file (highest priority)
        if Path('.env_prod').exists():
            return 'production'
        if Path('.env_dev').exists():
            return 'development'
            
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
        # Connection settings
        'client_id_start': 100,           # Different client IDs to avoid conflicts
        'port': 7497,                     # Paper trading port
        'host': '127.0.0.1',
        'auto_connect': False,            # Manual connection for safety
        
        # File paths (separate from production)
        'settings_file': 'settings_dev.json',
        'positions_file': 'positions_dev.json',
        'log_dir': 'logs/dev',
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
        
        # TradeStation
        'ts_dict_name': 'IBKR-TRADER-DEV', # Different dictionary name
        'ts_auto_connect': False,         # Manual TS connection in dev
        
        # Feature flags
        'enable_auto_trading': False,     # Disable automation in dev
        'enable_order_chasing': True,     # Allow for testing
        'show_debug_info': True,
    },
    'production': {
        # Connection settings
        'client_id_start': 1,             # Production client IDs
        'port': 7497,                     # Usually paper, but configurable
        'host': '127.0.0.1',
        'auto_connect': True,             # Auto-connect for trading
        
        # File paths
        'settings_file': 'settings.json',
        'positions_file': 'positions.json',
        'log_dir': 'logs/prod',
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
        
        # TradeStation
        'ts_dict_name': 'IBKR-TRADER',    # Production dictionary name
        'ts_auto_connect': True,          # Auto-connect in production
        
        # Feature flags
        'enable_auto_trading': True,      # Enable automation
        'enable_order_chasing': True,     # Enable order chasing
        'show_debug_info': False,
    }
}

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
            
        # Check for conflicting development processes
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
            issues.append("⚠️  psutil not available - cannot check for conflicting processes")
            
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
    
    return issues


def create_environment_marker(env_type: str) -> None:
    """Create environment marker file"""
    if env_type == 'production':
        Path('.env_prod').touch()
        if Path('.env_dev').exists():
            Path('.env_dev').unlink()
    elif env_type == 'development':
        Path('.env_dev').touch()
        if Path('.env_prod').exists():
            Path('.env_prod').unlink()


def get_environment_info() -> str:
    """Get formatted environment information string"""
    info = [
        f"🔧 Environment: {config.environment.upper()}",
        f"🖥️  Hostname: {socket.gethostname()}",
        f"📁 Settings: {current_config['settings_file']}",
        f"📊 Positions: {current_config['positions_file']}",
        f"🔌 Port: {current_config['port']}",
        f"🆔 Client ID Start: {current_config['client_id_start']}",
        f"📡 TradeStation Dict: {current_config['ts_dict_name']}",
    ]
    
    if config.is_production:
        info.append("🚨 LIVE TRADING ENVIRONMENT")
    else:
        info.append("🧪 DEVELOPMENT ENVIRONMENT")
        
    return '\n'.join(info)


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