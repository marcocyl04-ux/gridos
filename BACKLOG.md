# GridOS Product Backlog

## UI / UX

### Menubar AI button visibility at half-screen widths
- **Problem:** At half-screen widths (~960px), the "Ask GridOS" button in the menubar requires horizontal scrolling to access
- **Attempted in Session 2:** Tried to address as part of responsive fixes, but caused regressions and was reverted
- **Next approach:** Pin the "Ask GridOS" button to the right edge so it's always visible, or restructure menubar to collapse less-important items at narrow widths
- **Status:** Needs revisit with different approach

### Sidebar backdrop at narrow widths
- **Problem:** Sidebar backdrop at half-screen dims the grid unnecessarily since sidebar isn't truly modal — the grid is still interactive but looks locked
- **Attempted in Session 2:** Tried removing backdrop below 1100px width, but this broke sidebar open/close behavior (JS/CSS breakpoint mismatch)
- **Next approach:** Remove backdrop below a width threshold without breaking sidebar open/close behavior. Ensure JS and CSS breakpoints stay synchronized
- **Status:** Needs revisit with careful testing at all widths before merging

### Landing page API key banner false positive
- **Problem:** Landing page shows "No API keys configured" banner even when keys exist in landing.html's detection logic
- **Attempted in Session 2:** Tried to fix detection using `configured_providers` array, but the banner was still showing incorrectly
- **Note:** Workbook page (`renderModelSelect()`) has correct detection — landing.html uses distinct logic that needs its own fix
- **Status:** Needs dedicated fix for landing.html detection logic

### Composer button tooltips not appearing
- **Problem:** Native browser tooltips not appearing on Selection / Whole sheet / Chain buttons despite title attributes being present
- **Attempted in Session 2:** Verified title attributes exist in DOM and no obvious CSS blocking (`pointer-events: none` not applied)
- **Next approach:** Something is blocking native tooltip rendering. Needs in-browser debugging to identify cause. Consider custom tooltip component rather than native `title` attributes for better control and styling
- **Status:** Needs debugging session with DevTools to identify root cause

---

## Session History

### Phase 1.5 Session 2 (Reverted)
**Date:** 2026-04-20
**Commit Range:** `23646f3` through `7a2ea69` (all reverted)

**Attempted:**
- API key banner detection fix using `configured_providers` array
- Sidebar backdrop removal at narrow widths (<= 1100px)
- Responsive menubar improvements

**Regressions introduced:**
- Sidebar wouldn't open at half-screen widths (JS/CSS breakpoint mismatch)
- Banner became undismissable / still showed when keys configured
- Tooltips still non-functional

**Action:** Hard reset to `2adefd6` — all Session 2 UX work removed from master.

**Lessons:**
- Any sidebar breakpoint changes must update BOTH CSS media queries AND JS width checks
- Responsive features need testing at multiple widths before merge
- Consider custom tooltip component vs native `title` attributes
