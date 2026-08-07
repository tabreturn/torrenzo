# AGENT NOTES

- README.md is canonical; skim it before changes and for details.
- Keep this file concise; do not duplicate README.

## Repository Snapshot

- Python package (`torrenzo/`) with entry point `torrenzo/__main__.py`; run as `python -m torrenzo <subject>`.
- `torrenzo/torrenzo_engine/` contains the renderer registry and pipeline.
- Subject content (e.g. `demo/`) has `outline.md`, `assessments/`, `modules/`, `notes/`, and `build/` -- all resolved relative to the subject root passed as the CLI argument. `build/` is not wiped on each run; only stale files are rebuilt and orphans are pruned.
- `demo/` is a self-contained sample subject checked into this repo.
- No automated tests or linters; validation is manual.

## Setup & Dependencies

- Python 3.10+; `pip install -r requirements.txt` (use a venv if present). Key deps: `pypdf` (PDF metadata), `Pillow` (PNG metadata), `pyppeteer` (PDF via Chromium); all pure Python.
- Google Chrome or Chromium required for PDF generation; set `PUPPETEER_EXECUTABLE_PATH` if Chrome is not on PATH.
- Run as `python -m torrenzo <subject-root>` from the repo root. `requirements.txt` lives here; subject content lives elsewhere. Obsidian vault config included.

## Tagging (current behavior)

- Dataview-style inline tags only: `` `=[[outline]].path.to.value` ``.
- Bare tag form also supported: `[[outline]].path.to.value` (no backticks/equals).
- Components use the bare form: `[[component.module-navigation]]` (no backticks/equals).
- SLO Dataview LIST block supported (LIST without id slo[x] ... FLATTEN ...).
- Parent paths (e.g., `` `=[[outline]].assessment.a1` ``) auto-render as HTML tables; SLO code lists render `<ul>` of full descriptions (no bold codes).

## Directory Layout & Naming

- `torrenzo/__main__.py`: CLI entry; builds tag map from `outline.md`, registers renderers, constructs job specs, and runs the pipeline.
- `torrenzo/torrenzo_engine/`: renderer registry and pipeline execution; renderers include `md_to_pdf`, `md_to_html`, `bib_to_html`.
- Subject: `assessments/assessment_<n>/ass_<n>_brief.md` → PDF; `modules/module_<n>/mod_<n>_<seq>_<name>.[md|docx]` → HTML; `notes/**/*` → `build/lecturer_notes/` (copied as-is, no conversion).
- `modules/style/style.css` is inlined into module HTML; output HTML is body-only for LMS pasting.
- `assessments/style/` is copied alongside each brief; `logo.svg` injected into the PDF header; swap to change branding.
- `modules/references.bib` contains subject-level BibTeX sources.
- File naming must match the expected patterns (`ass_*_brief.md`, `mod_*_*_*.md`, `mod_*_*_*.docx`) or files are skipped.

## Incremental Builds & Timestamps

- Default run skips files whose output is newer than the source and all shared deps (`outline.md`, stylesheet, bib) -- mtime comparison via `torrenzo_engine/build_stamp.py`.
- `--force` rebuilds all files without clearing `build/`; `--clean` wipes `build/` first then rebuilds all.
- `--watch` does an initial incremental build then polls source files (1 s interval, skips `build/`) and re-runs an incremental build whenever changes are detected; Ctrl+C stops it.
- `--live` implies `--watch`; additionally starts a localhost HTTP server (`torrenzo_engine/live_server.py`) that serves `build/`, injects an SSE-based reload script into HTML responses, and pushes reload events to all connected browsers after each rebuild. Port is auto-assigned; URL printed to stdout. GUI `--watch` checkbox passes `--live`, parses the URL from stdout, and uses it for the Preview button.
- Orphaned outputs (source deleted/renamed) are pruned automatically after each run; empty directories are removed.
- Diagnostics report "N file(s) up-to-date, skipped", "N file(s) newly built", and "N orphaned file(s) removed" at the end of each run.
- Timestamp embedding per format:
  - **HTML**: `<!-- built: <ISO-8601>  source: <filename> -->` prepended
  - **PDF**: timestamp in visible page header; `Producer`/`Subject`/`Keywords` written to PDF document properties via `pypdf`
  - **SVG**: XML comment inserted after XML declaration
  - **PNG**: `Comment` tEXt chunk written via `Pillow`; falls back to plain copy if Pillow unavailable
  - **Other assets**: plain `shutil.copy2`, no metadata added

## Cache-Busting (`--cache-bust`)

- `--cache-bust [TAG]` appends `_TAG` before the file extension of every asset copied to `build/` and rewrites corresponding `src`/`href` references in HTML output.
- Omit `TAG` for an auto-generated daily stamp (`vYYYYMMDD`): `--cache-bust` → `_v20260619`.
- Provide a custom tag: `--cache-bust cb` → `_cb`.
- Affects **module assets** (`modules/*/assets/`), **HTML module pages**, **CC cartridge** (both module and assessment assets), and **lecturer notes** (`notes/**/*`).
- Assessment PDFs are unaffected (they reference local files, not Canvas-served URLs).
- Designed to work around Canvas caching issues where previously uploaded images stop rendering after re-import.
- GUI exposes a `--cache-bust` checkbox with an optional tag text field.

## Testing & Validation

- No automated suite; run `python -m torrenzo <subject>` to rebuild and inspect `build/` artifacts.

## Extensibility

- Plugin-style renderers; register new renderer names and job specs for additional targets (e.g., `.docx` → HTML, Marp `.md` → PDF, extended Markdown widgets).
- `--cc` exports Common Cartridge; lecturer notes included as unpublished module hidden from students. CC import overwrites (not additive).
