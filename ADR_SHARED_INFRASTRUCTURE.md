# Architecture Decision Record: Shared Infrastructure Philosophy

## Status: ✅ ACCEPTED
**Date**: November 7, 2025  
**Decision Makers**: Project Team  
**Status**: Implemented and Documented  

## Context

During implementation of development/production environment separation for the IBKR XSP Option Trader, we needed to decide how to handle infrastructure components like virtual environments and TradeStation GlobalDictionary integration.

## Decision

**SHARED INFRASTRUCTURE PHILOSOPHY**: Separate what affects runtime behavior, share what can be shared safely.

### What We Share (Same for Both Environments)

1. **Virtual Environment (`.venv/`)**
   - Same Python packages and versions for both environments
   - No conflicts since both use identical dependencies
   - Simpler maintenance and updates

2. **TradeStation GlobalDictionary Name (`'IBKR-TRADER'`)**
   - Both environments connect to same dictionary name
   - No need to modify TradeStation strategies
   - Separation achieved through different client IDs

3. **Core Application Code**
   - Same `main.py`, `config.py`, and source files
   - Environment-aware configuration without code duplication

### What We Separate (Different per Environment)

1. **Runtime Configuration**
   - Client ID ranges: Dev (100-199) vs Prod (1-99)
   - IBKR ports: Dev (7497 paper) vs Prod (7496 live)
   - Connection settings and safety features

2. **Data Files**
   - Settings: `settings_dev.json` vs `settings_prod.json`
   - Positions: `positions_dev.json` vs `positions_prod.json`
   - Logs: `logs_dev/` vs `logs_prod/` directories

3. **Safety & Approval Systems**
   - Production requires explicit approval
   - Different visual indicators and warnings
   - Environment-specific order limits and validations

## Rationale

### Benefits of Shared Infrastructure

- **Simplicity**: One virtual environment to maintain, not two
- **Consistency**: Same package versions prevent environment drift
- **Efficiency**: No duplication of 100MB+ virtual environment
- **TradeStation Integration**: No strategy modifications needed
- **Deployment**: Easier synchronization between environments

### Benefits of Separated Data

- **Safety**: Complete isolation of trading data and settings
- **Flexibility**: Different configurations per environment
- **Conflict Prevention**: No chance of mixing dev/prod data
- **Auditing**: Clear separation for compliance and tracking

### Why Not Full Separation?

We considered completely separate environments but rejected it because:
- **Overkill**: Same Python dependencies don't need separation
- **Complexity**: Managing two virtual environments adds overhead  
- **Deployment Risk**: Version mismatches between environments
- **TradeStation**: Would require duplicate strategy setup

## Implementation

### File Structure
```
Project/
├── .venv/                     # SHARED: Virtual environment
├── main.py                    # SHARED: Application code
├── config.py                  # SHARED: Environment configuration
├── settings_dev.json          # SEPARATED: Dev settings
├── settings_prod.json         # SEPARATED: Prod settings  
├── positions_dev.json         # SEPARATED: Dev positions
├── positions_prod.json        # SEPARATED: Prod positions
├── logs_dev/                  # SEPARATED: Dev logs
└── logs_prod/                 # SEPARATED: Prod logs
```

### Environment Detection
1. Environment files (`.env_dev`, `.env_prod`) - explicit override
2. Environment variable (`TRADING_ENV=development|production`)
3. Hostname keywords (`prod`, `dev`, `trading`, `test`, etc.)
4. Default to development (safe fallback)

### TradeStation Integration
Both environments use `'IBKR-TRADER'` GlobalDictionary:
- No strategy code changes needed
- Separation via different client ID ranges
- Same COM interface for both environments

## Consequences

### Positive
✅ **Simplified Management**: One virtual environment to maintain  
✅ **No Strategy Changes**: Same TradeStation GlobalDictionary name  
✅ **Complete Data Isolation**: Safe separation where it matters  
✅ **Easy Deployment**: No dependency synchronization issues  
✅ **Consistent Dependencies**: No version drift between environments  

### Negative  
⚠️ **Dependency Conflicts**: If dev needs different packages (rare)  
⚠️ **Testing Isolation**: Both environments share same package versions  

### Mitigation
- Document any dev-only dependencies clearly
- Use feature flags for development-specific code paths
- Regular testing in both environments to catch issues

## Compliance

This decision must be maintained in:
- ✅ All documentation (ENVIRONMENT_GUIDE.md, IMPLEMENTATION_SUMMARY.md)
- ✅ Copilot instructions for future AI assistance  
- ✅ Code comments and configuration files
- ✅ Deployment scripts and tooling

## Review

This decision should be reviewed if:
- Dependencies diverge significantly between environments
- TradeStation integration requirements change
- Security requirements demand complete isolation
- Performance issues arise from shared infrastructure

---

**Future Contributors**: Please maintain this shared infrastructure philosophy. Do not create separate virtual environments or TradeStation dictionaries unless there is a compelling technical reason documented in a new ADR.