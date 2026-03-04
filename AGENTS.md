# AGENT NOTES


## Repository Snapshot

- Python-based tooling centered around `torrenzo.py`, which transforms Markdown briefs and module activities into PDFs and simple LMS HTML.
- Content sources live under `assessments/` (briefs) and `modules/` (module activities and assets).
- No tests or lint pipelines are defined; the repo focuses on content processing rather than a traditional application/service stack.


## Setup & Dependencies

- Requires Python 3 with `PyYAML` (installed via `requirements.txt`).
- No Node.js/npm installation is required; PDFs render via the Python `markdown_pdf` package bundled in requirements.
- Run `pip install -r requirements.txt` before executing scripts.
- Agent to use local env if one exists in torrenzo root.


## Directory Layout & Naming

- `torrenzo.py`: now the CLI/orchestration entry point; it loads configs, extends context, and delegates work to the `torrenzo_engine` pipeline instead of directly converting files.
- `torrenzo_engine/`: contains the new renderer registry and pipeline that discover render jobs and execute plugin renderers.
- `torrenzo_engine/renderers/`: each renderer (e.g., `md_to_pdf`, `md_to_html`, `bib_to_html`) lives here and returns success diagnostics.
- `outline.yaml`: metadata describing subject learning outcomes; tags from this file are injected into generated HTML via `{{subject_learning_outcomes}}`.
- `assessments/`: contains `ass_<n>_brief.md` files. Each brief is rendered to PDF in `build/`.
- `modules/`: includes `mod_<n>_activities.md` files. Each activity is converted to LMS-ready HTML fragments.
- `build/`: generated output. The pipeline recreates this directory on each run, so treat it as ephemeral.


## Code Patterns & Conventions

- The CLI now loads job specs and contexts, then feeds them to the renderer-based pipeline: jobs describe an input glob, output path, renderer name, and optional metadata injection.
- Renderers are registered with `RendererRegistry`; each renderer is responsible for reading its input, producing output under `build/`, and returning a success flag plus human-readable diagnostics.
- Markdown processing remains regex- and state-machine-driven:
  - Inline formatting uses `inline_format` with regex replacements for **bold**, *italic*, `code`, and `{{tag}}` placeholders.
  - Paragraph/list/code block detection happens line-by-line in `convert_markdown_to_lms_html`, with explicit flush helpers.
- Image references are turned into `<img>` tags; all text is HTML-escaped before structured markup is inserted.
- Naming uses `snake_case` for functions and constant-style uppercase for regex/patterns (`BRIEF_PATTERN`, `IMAGE_RE`).


## Testing & Validation Approach

- No automated test suite; validation is manual.
- Run the build command and inspect `build/` for PDFs/HTMLs. If `npx` is missing or the Markdown filename patterns aren’t matched, the pipeline exits with clear errors.


## Gotchas & Notes

- If `npx` is unavailable, `ensure_npx_available` raises and nothing is generated; install Node.js/NPM to resolve.
- Briefs only process when files match `ass_*_brief.md`, and activities require `mod_*_activities.md`. Files outside those patterns are ignored.
- `prepare_build_dir` wipes the entire `build/` directory on every run—do not store persistent files there between builds.
- The script now wires through the renderer registry; new outputs are added by registering new renderer names and job specs.
- The pipeline requires at least one matching job; otherwise, it exits with an informative SystemExit that references the configured job patterns.

