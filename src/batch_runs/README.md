# `src/batch_runs/`

This folder is a legacy output location from the older repository layout, when Optuna results were written under `src/`.

## Current Status

- New Optuna studies are no longer written here.
- The active location is now `batch_runs/` at the repo root.
- Files in this folder are retained only as historical artifacts from earlier runs.

## Recommendation

Treat this folder as read-only unless you are explicitly inspecting an older run. New automation and replay scripts default to the repo-root `batch_runs/` tree.
