# Torrenzo

*Lightweight publishing pipeline for digital learning content*

Traverses structured subject directories and outputs LMS-ready HTML content and PDF assessment briefs from Markdown, BibTeX, and other source material.

Torrenzo currently performs the following transformations:

| Input                                         | Output |
|-----------------------------------------------|--------|
| `assessments/assessment_<n>/ass_<n>_brief.md` | PDF    |
| `modules/module_<n>/mod_<n>_content.md`       | HTML   |
| `modules/module_<n>/mod_<n>_activities.md`    | HTML   |
| `modules/module_<n>/mod_<n>_resources.bib`    | HTML   |

An `outline.yaml` provides the project/subject configuration:

- **`subject_descriptor`** -- A short overview of the subject: its aims, key concepts, and the knowledge and skills students will gain.
- **`slo > code: <n>`** -- Subject Learning Outcomes; the specific knowledge, skills, and capabilities students should demonstrate upon successful completion.
- **`assessment_metadata`** -- High-level submission requirements, including format, length, SLOs, and weighting.

---

## Usage

1. Ensure [prerequisites](#prerequisites) are installed.
2. [Populate subject content](#populating-content) (`outline.yaml`, `assessments/`, and `modules/`).
3. Run Torrenzo from the repository root:

```bash
python torrenzo.py
```

By default, Torrenzo scans the current directory. To target another workspace:

```bash
python torrenzo.py ../other-subject
```

All outputs (HTML, PDF, etc.) are written to the `build/` directory, which is cleared at the start of each run.

---

## Prerequisites

- **Python 3.10+**
- Dependencies installed via: `pip install -r requirements.txt`
- A terminal (`cd` to the repository root); relative paths are resolved from there

*(There is opportunity to add a GUI in future.)*

---

## Repository architecture

```text
subject-root/
├── outline.yaml        # subject configuration
├── assessments/        # assessment briefs → PDF
│   ├── assessment_1/
│   │   ├── ass_1_brief.md
│   │   └── assets/
│   ├── ...
│   └── assessment_n/
│       ├── ass_n_brief.md
│       └── assets/
├── modules/            # module content → HTML
│   ├── module_1/
│   │   ├── mod_1_content.md
│   │   ├── mod_1_activities.md
│   │   ├── mod_1_resources.bib
│   │   └── assets/
│   ├── ...
│   └── module_n/
│       ├── mod_n_content.md
│       ├── mod_n_activities.md
│       ├── mod_n_resources.bib
│       └── assets/
├── torrenzo.py         # run to build
└── build/              # generated output
```

### Populating content

Subject content is organised into two directories -- `assessments/` and `modules/` -- following strict naming conventions that Torrenzo uses to locate and process files.

**`outline.yaml`** is the metadata source for all generated outputs. Among other data, it must define:

- `subject_descriptor` -- a short overview of the subject
- `slo` -- Subject Learning Outcomes, each identified by a code (a, b, c, etc.)
- `assessment_metadata` -- submission requirements per assessment (format, length, weighting, SLOs, etc.)

Torrenzo injects these values wherever placeholders such as `{{subject_descriptor}}` appear in source Markdown files. The CSS in `assessments/style.css` controls the styling of generated PDF briefs.

**Assessment briefs** are placed in `assessments/assessment_<n>/ass_<n>_brief.md`. Any assets the brief references (images, etc.) go in the adjacent `assets/` directory.

**Module files** follow the same pattern under `modules/module_<n>/`:

- `mod_<n>_content.md` -- primary module content
- `mod_<n>_activities.md` -- activity pages
- `mod_<n>_resources.bib` -- reference list in BibTeX format
- `assets/` -- supporting files referenced by the module

During the build process, Torrenzo injects `outline.yaml` metadata (SLOs, etc.) and transforms content into PDF assessment briefs, LMS-ready HTML module pages (including separate activity pages), and HTML resource lists -- all output to `build/`. Note that `build/` deletes its contents to recreate them entirely on every run.

---

## Transformers

Torrenzo uses a plugin-style architecture with an extensible set of transformers:

| Transformer                                | Conversion      |
|--------------------------------------------|-----------------|
| `torrenzo_engine/renderers/bib_to_html.py` | BibTeX → HTML   |
| `torrenzo_engine/renderers/md_to_html.py`  | Markdown → HTML |
| `torrenzo_engine/renderers/md_to_pdf.py`   | Markdown → PDF  |

Torrenzo can accommodate additional transformers without touching the core pipeline. This makes it amenable to extending with new targets (e.g., Marp slides, DOCX, quizzes) without inflating the CLI driver. Potential candidates include:

- `.docx` → HTML (via predefined Word stylesheets for consistent visual output and semantic structure)
- Marp `.md` → PDF (slide decks)
- Extended Markdown features for module pages (accordions, nav tabs, etc.)

---

## TODO

- [ ] Refine CSS styles for assessment briefs
- [ ] Improve brief templates (page numbers, versioning in headers, etc.)
- [ ] Capture and expose build diagnostics (missing placeholders, missing assets, invalid front matter, failed conversions)
- [ ] ...

### 'Maybe' goals

- [ ] Build a GUI (desktop or web interface)
- [ ] Add support for Word documents (via semantic styles)
- [ ] Add support for Marp slide decks
- [ ] Implement batch LMS content importer (via Tampermonkey or similar)
- [ ] ...

