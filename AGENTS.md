# AGENT NOTES

## Repository Snapshot

- Python CLI (`torrenzo.py`) orchestrates render jobs that transform Markdown briefs and module files into PDFs/HTML via the `torrenzo_engine` pipeline and renderer registry.
- Content sources live under `assessments/` (briefs and assets) and `modules/` (module content, activities, references, assets); outputs land in `build/`.
- No automated tests or linters; validation is manual.

## Setup & Dependencies

- Python 3.10+ with requirements from `requirements.txt` (includes `PyYAML`, `markdown_pdf`, etc.).
- Node 18+ with `npm`; run `npm install` for `md-to-pdf` used in PDF rendering.
- Use a local virtualenv if present in the repo root.

## Usage & Build Behavior

- Run from repo root: `python torrenzo.py` (optionally `python torrenzo.py <other-root>` to target a different subject directory).
- All outputs write to `build/`, which is cleared at the start of each run.

## Directory Layout & Naming

- `torrenzo.py`: CLI entry; builds tag map from `outline.yaml`, registers renderers, constructs job specs, and runs the pipeline.
- `torrenzo_engine/`: renderer registry and pipeline execution.
- `torrenzo_engine/renderers/`: individual renderers (`md_to_pdf`, `md_to_html`, `bib_to_html`).
- `outline.yaml`: subject metadata (subject info, descriptor, SLOs, assessments) injected into renders via tags like `{{slo}}`, `{{slo|<code>}}`, and `{{ assessment|<id>|... }}`.
- `assessments/assessment_<n>/ass_<n>_brief.md`: briefs → PDF (assets alongside).
- `modules/module_<n>/mod_<n>_content.md`: module content → HTML.
- `modules/module_<n>/mod_<n>_activities.md`: activities → HTML.
- `modules/module_<n>/mod_<n>_resources.bib`: references → HTML.
- `build/`: generated output; ephemeral.

## Code Patterns & Conventions

- Job specs define input globs, output dirs/exts/naming, renderer key, and optional context.
- Renderers are registered by name; registry returns a renderer factory, invoked per job.
- Inline formatting/tag replacement occurs in renderer implementations; HTML is escaped before markup insertion.
- Naming uses `snake_case` functions and constant-style uppercase for patterns/regex.

## Testing & Validation Approach

- No automated suite; run the build (`python torrenzo.py`) and inspect `build/` artifacts.

## Gotchas & Notes

- `build/` is wiped each run (`prepare_build_dir`).
- PDF rendering depends on Node/npm for `md-to-pdf`; failure to have `npx`/Node halts PDF generation.
- File naming must match the expected patterns (`ass_*_brief.md`, `mod_*_content.md`, `mod_*_activities.md`, `mod_*_resources.bib`) or files are skipped.
- New outputs require registering renderer names and adding job specs.
