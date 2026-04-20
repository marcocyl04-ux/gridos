# GridOS API Restructuring Plan

## Status: SCAFFOLDING COMPLETE (No Breaking Changes Yet)

This document tracks the ongoing restructuring to make GridOS more modular and AI-friendly.

## What Changed

### New Directory Structure
```
core/api/
├── __init__.py          # Exports all routers
├── agents.py            # /agent/* routes (chat, execute-graph, write)
├── grid.py              # /grid/* routes (cell, range, clear, format)
├── templates.py         # /templates/* routes (apply, create, list)
├── workbooks.py         # /workbook/* routes (create, load, save, share)
└── system.py            # /auth/*, /healthz, /cloud/status, /settings
```

### What Exists Now

**Phase 1: Scaffolding (COMPLETE)**
- ✅ Created `core/api/` package with 5 domain modules
- ✅ All route signatures documented with examples
- ✅ Endpoint models and schemas defined
- ✅ NO functionality moved yet (all endpoints return 501 Not Implemented)
- ✅ main.py still contains all working code (UNCHANGED)

**Phase 2: Migration (IN PROGRESS)**
- Routes will be migrated from `main.py` to domain modules
- Each module gets a dedicated implementation file
- Tests updated to use new structure
- No breaking changes to API consumers

**Phase 3: Integration**
- Update `main.py` to import and mount routers
- Verify all routes still work (same behavior, new location)
- Deploy with full API compatibility

## Why This Helps

### For Developers
- Find code by domain (agents, grid, templates) not by line number
- Each module is independently testable
- Clear separation of concerns

### For AIs
- Each router has docstrings with examples
- Consistent request/response models
- Easier to understand API surface
- Enables automated code generation (OpenAPI → client libs)

## How to Use Now (During Restructuring)

### All existing endpoints still work in `main.py`
Nothing breaks. The new structure is being built **in parallel**.

### To extend an endpoint
1. Find the route in the appropriate `core/api/*.py` module
2. Read the docstring and example
3. Implement the handler there (scaffolding functions return 501)
4. Test in isolation before integrating into main.py

### To understand the API
Read `core/api/agents.py`, `core/api/grid.py`, etc. The models and docstrings are the spec.

## Migration Checklist

- [ ] Agents routes migrated
  - [ ] `/agent/chat`
  - [ ] `/agent/execute-graph`
  - [ ] `/agent/write`
  - [ ] `/agent/write/graph`
  - [ ] `/agent/chat/chain`

- [ ] Grid routes migrated
  - [ ] `/grid/cell`
  - [ ] `/grid/range`
  - [ ] `/grid/read`
  - [ ] `/grid/clear`
  - [ ] `/grid/format`

- [ ] Template routes migrated
  - [ ] `/templates/available`
  - [ ] `/templates/apply/{id}`
  - [ ] `/templates/{id}`
  - [ ] `/templates/create`

- [ ] Workbook routes migrated
  - [ ] `/workbook/create`
  - [ ] `/workbook/{id}`
  - [ ] `/workbook/{id}/save`

- [ ] System routes migrated
  - [ ] `/healthz`
  - [ ] `/auth/whoami`
  - [ ] `/cloud/status`
  - [ ] `/settings/keys/save`

- [ ] Integration
  - [ ] main.py imports all routers
  - [ ] Tests pass
  - [ ] Deployment verification

## Safety Guarantees

1. **No endpoint changes** - All paths, methods, request/response shapes stay identical
2. **Backwards compatible** - Existing clients work without modification
3. **Staged migration** - One route family at a time, full testing between
4. **Git checkpoints** - Tag before each phase (`checkpoint-before-api-restructure` already saved)
5. **Rollback ready** - Can revert to checkpoint if issues arise

## Next Steps

1. **Agents module** - Move `/agent/*` routes to `core/api/agents.py`
2. **Grid module** - Move `/grid/*` routes to `core/api/grid.py`
3. **Templates module** - Move `/templates/*` routes to `core/api/templates.py`
4. **Integration** - Mount all routers in main.py
5. **Testing** - Verify all endpoints work identically

## Testing During Migration

```bash
# Before migration (baseline)
pytest test_integration.py -v
# Record response shapes and status codes

# After each module migration
pytest test_integration.py -v
# Compare with baseline - should be identical

# Deployment verification
curl https://gridos-dk0k.onrender.com/agent/chat -X POST
# Should work exactly as before
```

## Questions?

Refer to:
- `AI_GUIDE.md` - How to understand GridOS architecture
- `core/api/*.py` - Exact endpoint specifications
- `main.py` - Current working implementations (until migrated)
