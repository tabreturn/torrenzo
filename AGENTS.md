# AGENT NOTES

## Repository Snapshot

- Python CLI (`torrenzo.py`) orchestrates render jobs that transform Markdown briefs and module files into PDFs/HTML via the `torrenzo_engine` pipeline and renderer registry.
- Content sources live under `assessments/` (briefs and assets) and `modules/` (module content, activities, references, assets); outputs land in `build/`.
- Demo/sample content is checked in under `assessments/demo_assessment_*` and `modules/demo_module_*`; user-created `assessment_*` / `module_*` are gitignored but still built.
- Outputs land in `build/`; demo inputs produce filenames prefixed with `demo_`, others keep their base names.
- No automated tests or linters; validation is manual.

## Setup & Dependencies

- Python 3.10+ with requirements from `requirements.txt` (includes `PyYAML`, `premailer`, etc.).
- Node 18+ with `npm`; run `npm install` for `md-to-pdf` used in PDF rendering (PDF only; HTML renderers are pure-Python + pip deps).
- Use a local virtualenv if present in the repo root.

## Usage & Build Behavior

- Run from repo root: `python torrenzo.py` (optionally `python torrenzo.py <other-root>` to target a different subject directory).
- All outputs write to `build/`, which is cleared at the start of each run. Demo inputs keep `demo_` prefixes in output filenames; non-demo inputs do not.

## Tagging (current behavior)

- **Only Dataview-style inline tags are supported**: `` `=[[outline]].path.to.value` `` and the SLO dataview block (LIST without id slo[x] ... FLATTEN ...).
- Parent paths (e.g., `` `=[[outline]].assessment.a1` ``) auto-render as HTML tables for their child fields. Lists of SLO codes render as `<ul>` of full descriptions (no bold codes).
- Assessment metatable: `` `=[[outline]].assessment.<id>.metatable` `` outputs the formatted assessment table.

## Directory Layout & Naming

- `torrenzo.py`: CLI entry; builds tag map from `outline.md` YAML, registers renderers, constructs job specs, and runs the pipeline.
- `torrenzo_engine/`: renderer registry and pipeline execution.
- `torrenzo_engine/renderers/`: individual renderers (`md_to_pdf`, `md_to_html`, `bib_to_html`).
- `outline.md`: subject metadata (subject info, descriptor, SLOs, assessments) injected into renders via Dataview-style tags.
- `assessments/demo_assessment_<n>/ass_<n>_brief.md`: demo briefs → PDF (assets alongside).
- `assessments/assessment_<n>/ass_<n>_brief.md`: user briefs → PDF (gitignored by default unless demo-prefixed).
- `modules/demo_module_<n>/mod_<n>_content.md`: demo module content → HTML.
- `modules/demo_module_<n>/mod_<n>_activities.md`: demo activities → HTML.
- `modules/demo_module_<n>/mod_<n>_resources.bib`: demo references → HTML.
- `modules/module_<n>/...`: user modules (gitignored) also built; they output without the `demo_` prefix.
- `modules/style/style.css`: optional global stylesheet inlined into module HTML; legacy attributes stripped; output HTML is body-only for LMS pasting.
- `build/`: generated output; ephemeral.
- Branding: `assessments/style/` is copied alongside each brief; `logo.svg` is injected into the PDF header via `assessments/style/config.js` at build time—swap that file to change the header logo.

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
