## Pull Values From the Outline

- **`` `=[[outline]].path` ``** <span style="color:#888">backtick form; renders the value at that outline path (e.g. `` `=[[outline]].subject.code` ``). Live-previews in Obsidian.</span>
- **`[[outline]].path`** <span style="color:#888">bare form; same result but won't live-preview in Obsidian. Parent paths (e.g. `[[outline]].assessment.a1`) render as a metadata table.</span>
- **`outline.assessment.<id>`** (parent) <span style="color:#888">metadata table of all fields.</span>
- **`outline.assessment.<id>.<field>`** (`.title`, `.weighting`, `.total_marks`, `.submission`, `.assessment`) <span style="color:#888">plain string.</span>
- **`outline.assessment.<id>.metatable`** <span style="color:#888">formatted metadata table.</span>
- **`outline.slo`** (no code) <span style="color:#888">full list of all outcomes.</span>
- **`outline.slo.<code>`** <span style="color:#888">single outcome with code and description.</span>
- **`outline.subject.code`** / **`outline.subject.title`** <span style="color:#888">plain string.</span>

## Link to Things

- **`[[includes|file]]`** <span style="color:#888">inlined file content from `includes/` (e.g. `[[includes|referencing.md]]`).</span>
- **`[[target]]`** <span style="color:#888">link with auto-derived label (e.g. `[[assessment_01]]`).</span>
- **`[[target|label]]`** <span style="color:#888">link with custom label (e.g. `[[mod_02_02_mangoes|See mangoes]]`).</span>

## Page Layout & Components

- **`[[component.module-navigation]]`** <span style="color:#888">tabbed nav links to sibling sub-modules.</span>
- **`[[component.page-break]]`** <span style="color:#888">page break.</span>
- **`[[component.page-spacer]]`** <span style="color:#888">vertical spacer (also auto-appended).</span>
- **`[[component.under-construction]]`** <span style="color:#888">🚧 banner.</span>
- **`[[component.under-construction|Custom msg]]`** <span style="color:#888">🚧 banner with custom message.</span>
- **`[[component.video|path/to/file]]`** <span style="color:#888">responsive 16:9 video player.</span>

## CC Export Sections

- **`[[cc-section]]`** (on heading) <span style="color:#888">section shown below PDF in CC export.</span>
- **`[[cc-section|hide-in-pdf]]`** <span style="color:#888">section hidden from PDF, kept in HTML/CC.</span>

## Markdown Extensions

- **`![alt|css:directives](img.png)`** <span style="color:#888">image with custom CSS styling.</span>
- **`--`** / **`---`** <span style="color:#888">en-dash / em-dash.</span>
- **`<<metadata_table>>`** (PDF only) <span style="color:#888">metadata table from front matter.</span>
- **`[@key]`** / **`[@k1; @k2]`** <span style="color:#888">inline citation with numbered references list.</span>
