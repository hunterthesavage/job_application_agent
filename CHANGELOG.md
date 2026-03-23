# Changelog

All notable changes to this project will be tracked here.

## 1.0.0 - 2026-03-23

Initial stable local-first milestone.

### Added
- SQLite-first local storage as the primary source of truth
- Source trust and source registry tracking
- Discovery-state tracking for net new versus rediscovered roles
- Run telemetry and Last Run Monitor
- Preferred-location handling aligned across setup, settings, and pipeline
- New Roles sorting with a saved default sort setting
- Reset App / Remove All Data flow

### Changed
- Pipeline now owns live Run Inputs
- Settings navigation simplified by removing Search Criteria as a separate tab
- Busy-state labels use human-readable wording
- Last Run Monitor is collapsed by default

### Notes
- Versioning now follows MAJOR.MINOR.PATCH
- Use 1.0.x for small fixes, 1.x.0 for meaningful feature slices, and 2.0.0+ for major architectural shifts
