# Environment Configuration Guide

This guide explains how to use the development/production environment separation system in the IBKR XSP Option Trader application.

## Overview

The application now supports automatic environment detection and configuration separation, allowing you to run development and production versions simultaneously on different computers without conflicts.

## Environment Detection

The system automatically detects the environment using multiple methods (in order of priority):

1. **Environment Files**: 
   - `.env_prod` file = Production environment
   - `.env_dev` file = Development environment

2. **Environment Variable**: 
   - `TRADING_ENV=production` or `TRADING_ENV=development`

3. **Hostname Keywords**:
   - Hostnames containing "prod", "trading", "live" = Production
   - Hostnames containing "dev", "test", "laptop" = Development
   - All other hostnames = Development (safe default)

## Environment Configurations

### Development Environment
- **Window Title**: `[DEV]` prefix with green border
- **Client ID Range**: 100-199 (no conflicts with production)
- **IBKR Port**: 7497 (paper trading)
- **Settings File**: `settings_dev.json`
- **Positions File**: `positions_dev.json`
- **Log Directory**: `logs_dev/`
- **TradeStation Dict**: `IBKR-TRADER-DEV`
- **Safety Checks**: Disabled for development flexibility

### Production Environment
- **Window Title**: `[PROD]` prefix with red border
- **Client ID Range**: 1-99
- **IBKR Port**: 7496 (live trading)
- **Settings File**: `settings_prod.json`
- **Positions File**: `positions_prod.json`
- **Log Directory**: `logs_prod/`
- **TradeStation Dict**: `IBKR-TRADER-PROD`
- **Safety Checks**: Enabled with approval requirements

## Usage Commands

### Check Current Environment
```bash
python config.py info
```

### Manual Environment Override
```bash
# Set to production (requires approval)
python config.py set production

# Set to development
python config.py set development
```

### Production Environment Approval
```bash
# After verifying production setup
python config.py approve
```

## Setup for Different Computers

### Development Computer Setup
1. Ensure hostname contains "dev", "test", or "laptop", OR
2. Create `.env_dev` file in the project directory, OR
3. Set environment variable: `set TRADING_ENV=development`

### Production Computer Setup
1. Ensure hostname contains "prod", "trading", or "live", OR
2. Create `.env_prod` file in the project directory, OR
3. Set environment variable: `set TRADING_ENV=production`

### Manual Override Files
Create these files in the project directory for explicit environment control:

**Development Override** (`.env_dev`):
```
# This file forces DEVELOPMENT environment
# Remove this file to use automatic detection
```

**Production Override** (`.env_prod`):
```
# This file forces PRODUCTION environment
# CAUTION: Live trading environment
# Ensure all settings are verified before use
```

## Safety Features

### Production Safety Checks
- **Approval Requirement**: Production mode requires explicit approval
- **Conflict Detection**: Prevents multiple instances on same computer
- **Visual Indicators**: Red border and [PROD] prefix on window
- **Order Size Limits**: Configurable maximum order sizes
- **Confirmation Dialogs**: Extra confirmations for live trading

### Development Flexibility
- **No Approval Required**: Start immediately
- **Higher Log Verbosity**: More detailed logging for debugging
- **Flexible Order Limits**: No artificial restrictions
- **Green Visual Indicators**: Clear development identification

## File Separation

Each environment maintains completely separate files while sharing common infrastructure:

```
Project Directory/
├── main.py                 # Main application
├── config.py              # Environment configuration
├── .venv/                 # SHARED: One virtual environment for both environments
├── settings_dev.json      # Development settings
├── settings_prod.json     # Production settings
├── positions_dev.json     # Development positions
├── positions_prod.json    # Production positions
├── logs_dev/              # Development logs
├── logs_prod/             # Production logs
├── .env_dev               # Force development (optional)
└── .env_prod              # Force production (optional)
```

### Shared Infrastructure Philosophy

**SHARED COMPONENTS** (Same for both environments):
- **Virtual Environment (`.venv/`)**: Both environments use identical Python packages
- **TradeStation GlobalDictionary**: Both use `'IBKR-TRADER'` dictionary name
- **Core Application Code**: Same `main.py` and `config.py` files

**SEPARATED COMPONENTS** (Different per environment):
- **Configuration Files**: Separate settings and positions
- **Client ID Ranges**: Dev (100-199) vs Prod (1-99) 
- **IBKR Ports**: Dev (7497 paper) vs Prod (7496 live)
- **Log Directories**: Separate logging for each environment

This approach provides **clean separation where it matters** (runtime behavior, data isolation) while **sharing infrastructure where it makes sense** (dependencies, core code, TradeStation integration).

## TradeStation Integration

Each environment uses a different GlobalDictionary name:
- **Development**: `IBKR-TRADER-DEV`
- **Production**: `IBKR-TRADER-PROD`

This allows both environments to run simultaneously with TradeStation without conflicts.

## Best Practices

### For Development
1. Use a separate computer or virtual machine
2. Keep IBKR in paper trading mode (port 7497)
3. Use different TradeStation strategies for testing
4. Regular backups of development settings

### For Production
1. Verify all settings before going live
2. Use live IBKR account (port 7496) 
3. Run on dedicated trading computer
4. Monitor logs regularly for issues
5. Test new features in development first

### General Workflow
1. **Develop** on development environment
2. **Test** thoroughly with paper trading
3. **Deploy** to production environment
4. **Monitor** production logs and performance

## Troubleshooting

### Wrong Environment Detected
- Check hostname keywords
- Create explicit `.env_dev` or `.env_prod` file
- Use manual override: `python config.py set <environment>`

### File Permission Issues
- Ensure write access to project directory
- Run as administrator if needed on Windows

### IBKR Connection Issues
- Verify correct port (7497 for dev, 7496 for prod)
- Check client ID ranges don't overlap
- Ensure IBKR TWS/Gateway is configured correctly

### TradeStation Connection Issues
- Verify correct dictionary names in TradeStation
- Check that GlobalDictionary is enabled
- Ensure only one environment connects to each dictionary

## Support

For issues or questions:
1. Check the logs in the appropriate log directory
2. Run `python config.py info` to verify configuration
3. Review this guide for common solutions
4. Check the main application logs for detailed error information