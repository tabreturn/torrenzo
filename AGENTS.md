# AGENT NOTES

- README.md is canonical; skim it before changes and for details.
- Keep this file concise; do not duplicate README.

## Repository Snapshot

- Python CLI (`torrenzo.py`) orchestrates render jobs that transform Markdown briefs and module files into PDFs/HTML via the `torrenzo_engine` pipeline and renderer registry.
- Content sources live under `assessments/` (briefs and assets) and `modules/` (module content, activities, references, assets); outputs land in `build/` (cleared each run). Demo/sample content is checked in under `demo_*`; non-demo keeps base names. `sample_build/` shows demo outputs.
- `outline.md` provides YAML metadata injected via Dataview-style tags.
- No automated tests or linters; validation is manual.

## Setup & Dependencies

- Python 3.10+; `pip install -r requirements.txt` (use a venv if present).
- Node 18+ with `npm`; `npm install` for `md-to-pdf` (PDF only; HTML renderers are pure Python).
- Run from repo root: `python torrenzo.py [other-root]` to target another subject directory. Obsidian vault config included.

## Tagging (current behavior)

- Dataview-style inline tags only: `` `=[[outline]].path.to.value` ``.
- SLO Dataview LIST block supported (LIST without id slo[x] ... FLATTEN ...).
- Parent paths (e.g., `` `=[[outline]].assessment.a1` ``) auto-render as HTML tables; SLO code lists render `<ul>` of full descriptions (no bold codes).
- Assessment metatable: `` `=[[outline]].assessment.<id>.metatable` `` outputs the formatted assessment table.

## Directory Layout & Naming

- `torrenzo.py`: CLI entry; builds tag map from `outline.md`, registers renderers, constructs job specs, and runs the pipeline.
- `torrenzo_engine/`: renderer registry and pipeline execution; renderers include `md_to_pdf`, `md_to_html`, `bib_to_html`.
- `assessments/assessment_<n>/ass_<n>_brief.md` → PDF (assets alongside); `demo_assessment_*` variants checked in.
- `modules/module_<n>/mod_<n>_content.md`, `mod_<n>_activities.md`, `mod_<n>_resources.bib` → HTML (assets alongside); `demo_module_*` variants checked in.
- `modules/style/style.css` is inlined into module HTML; output HTML is body-only for LMS pasting.
- `assessments/style/` is copied alongside each brief; `logo.svg` injected into the PDF header; swap to change branding.
- `references.bib` contains global BibTeX sources.
- File naming must match the expected patterns (`ass_*_brief.md`, `mod_*_content.md`, `mod_*_activities.md`, `mod_*_resources.bib`) or files are skipped.

## Testing & Validation

- No automated suite; run `python torrenzo.py` to rebuild and inspect `build/` artifacts. PDF generation requires Node/npm (`npx`).

## Extensibility

- Plugin-style renderers; register new renderer names and job specs for additional targets (e.g., `.docx` → HTML, Marp `.md` → PDF, extended Markdown widgets).
