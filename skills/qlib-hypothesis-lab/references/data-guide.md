# Existing data and environment

Read this when using an environment for the first time, when the data path is missing or when data loading fails. The current skill reads existing Qlib US daily data; it does not automatically prepare arbitrary data sources.

Use `uv run --locked` in the target project. Restore the locked environment with `uv sync --locked` when needed. Execution does not depend on a terminal's `base` indicator or manual virtual-environment activation.

Read the process's actual `QLIB_DATA_DIR`. If it is unset, check the user's existing environment configuration or ask for the dataset path. The application does not automatically load `.env`; use the user's path rather than the author's personal path. It must point to the Qlib provider directory containing `calendars`, `features` and `instruments`.

Perform the minimum check: the actual directory and required files exist, and required fields are readable. Avoid adding supplier audits or full membership-coverage gates. The universe uses historical `sp500.txt` intervals; `all.txt` describes imported price coverage and cannot replace historical membership.

The CLI uses `kernels=1` to avoid macOS/stdin multiprocessing startup issues. Keep existing data unchanged. Run artifacts are written to the project's ignored `runs/` directory.

For downloads, repairs or different data types, identify whether the request exceeds current authorization or tool support. A study using existing data does not implicitly authorize a whole-market download.

For the provider layout, snapshot retention and numerical reproduction limits, see the target repository's `docs/reproducibility.md`.
