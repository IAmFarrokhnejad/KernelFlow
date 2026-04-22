# PROJECT_STATE

## Metadata
- Project: `KernelFlow vNext`
- Last updated: 2026-04-22
- Repo type: local-first image processing application

## Current state
- The original single-filter demo has been replaced with a studio-style architecture.
- The backend now exposes asset, preview, export, batch, history, and preset APIs on top of an operation registry.
- The frontend now provides editor, batch, and lab surfaces around a non-destructive pipeline model.
- Generated runtime artifacts are intentionally excluded from version control.

## Implemented product surfaces
- Asset library and multi-file import
- Editor workspace with before/after preview
- Pipeline inspector with reorder, duplicate, enable/disable, preview toggle, and dynamic parameter controls
- Selective targeting with region bounds, feathering, and generated masks
- Batch export queue using the current locked pipeline snapshot
- Lab mode with raster scan preview, histogram display, and quality metrics

## Open follow-ups
- Add richer direct-manipulation ROI handles in the viewer instead of numeric bounds only
- Add background job execution and cancellation beyond best-effort preview cancellation
- Add visual browser QA against the running dev servers
- Expand automated API coverage around invalid payloads and persistence edge cases
