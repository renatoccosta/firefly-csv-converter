# AGENTS.md

## Overview
- This repository contains small Python 3.11+ converters that transform bank and brokerage exports into CSV files suitable for Firefly III import workflows.
- The codebase is intentionally simple: each converter lives in its own module under `src/firefly_csv_converter/` and exposes a small CLI-oriented `main()` plus parsing and CSV writing helpers.
- Poetry is the source of truth for dependency management, virtual environment management, package execution, and test execution in this project.
- Use the globally installed `poetry` binary. Do not create or bootstrap a project-local Poetry installation.

## Project Layout
- `src/firefly_csv_converter/convert_bb_cp.py`: converts Banco do Brasil checking account CSV exports.
- `src/firefly_csv_converter/convert_bb_lc.py`: extracts BB LC/LCI/LCA statement rows from plain text.
- `src/firefly_csv_converter/convert_ourocard_ofx.py`: converts Ourocard OFX files using `ofxparse`.
- `src/firefly_csv_converter/convert_rico_xlsx_csv.py`: converts Rico account spreadsheets using `pandas` and `openpyxl`.
- `tests/`: pytest coverage for each converter, mostly focused on parser behavior and output formatting.
- `samples/`: real example inputs used by tests and useful for manual verification.

## Environment And Tooling
- Python requirement: `>=3.11`.
- Runtime dependencies: `pandas`, `openpyxl`, `ofxparse`.
- Test dependencies: `pytest`, `pytest-cov`.
- Poetry should be used as the primary project tool for:
  - installing dependencies
  - managing the virtual environment
  - running tests
  - running project entry points
- Preferred workflow:
  - `poetry install`
  - `poetry run pytest -v`
- Prefer `poetry run <command>` over invoking tools from the system interpreter directly.
- Use the global Poetry installation already available in the environment when present, for example `poetry --version`.

## Working Conventions
- Preserve the current module-per-bank structure. New converters should normally be added as new modules instead of folding unrelated logic into existing files.
- Keep parsing logic in small pure functions where possible. The current test suite imports functions like `parse_csv`, `parse_input`, and `process_csv` directly.
- Maintain Portuguese field names and source-specific naming where they reflect the input format. Output formatting conventions already vary by converter and should only be normalized with explicit intent.
- Prefer using `Path` for filesystem arguments and keep command-line entrypoints minimal.
- Avoid adding heavy abstraction layers. This repository is small and benefits from direct, readable data-cleaning code.

## Testing Guidance
- When changing a converter, run the targeted test first:
  - `poetry run pytest tests/test_convert_bb_cp.py -v`
  - `poetry run pytest tests/test_convert_bb_lcilca.py -v`
  - `poetry run pytest tests/test_convert_ourocard_ofx.py -v`
  - `poetry run pytest tests/test_convert_rico_xlsx_csv.py -v`
- Then run the full suite.
- Full suite command: `poetry run pytest -v`
- Use files in `samples/` for manual spot checks before introducing new fixtures unless the scenario cannot be represented by the existing samples.
- Do not make versioned tests depend on files from `samples-local/`. That directory is not versioned and should be treated only as local parser-building input or for manual validation.
- For parsers based on non-versioned sources such as PDFs in `samples-local/`, create synthetic fixtures in the tests that mimic the relevant layout, coordinates, colors, and text patterns with fictitious data.
- Test fixtures and assertions must not hardcode personal data from real documents. Always anonymize names, identifiers, account numbers, and similar fields in versioned tests.
- Be careful with formatting assertions:
  - decimal separator is often `,`
  - CSV delimiter is sometimes `;`
  - some outputs quote all fields, others rely on default writer behavior
  - date formats differ by converter according to test expectations

## CLI And Entry Points
- Declared console scripts in `pyproject.toml`:
  - `convert-bb-cp`
  - `convert-bb-lc`
  - `convert-ourocard-ofx`
  - `convert-rico-xlsx-csv`
- Each CLI currently expects exactly two positional arguments: input path and output path.
- Prefer running entry points through Poetry during development, for example `poetry run convert-bb-cp ...`.
- If you change CLI behavior, update both `README.md` and the relevant tests.

## Known Repository Realities
- The `README.md` still mentions shell commands like `./convert_bb_cp`, but the packaging configuration defines console scripts with hyphenated names. Prefer the `pyproject.toml` entry points as the source of truth unless you are explicitly fixing the documentation.
- `pytest.ini` only sets `pythonpath = .`; imports in tests currently mix `src.firefly_csv_converter...` and `firefly_csv_converter...`. Be cautious when changing package layout or test invocation assumptions.
- `poetry install` may occasionally have trouble installing the current project in editable mode on some environments, but `poetry run pytest` can still work. Treat Poetry as the required workflow unless the user explicitly asks to debug Poetry itself.
- There is no `Makefile`, no CI config checked into the current workspace snapshot, and no existing `AGENTS.md` before this file.

## When Editing
- Update or add tests with behavior changes. This project relies on tests as the clearest specification for parsing rules.
- Keep sample-driven expectations stable unless the user requested a format change.
- Do not remove user changes in unrelated files.
- If local test tools are missing, state that explicitly in your final handoff instead of claiming validation.
