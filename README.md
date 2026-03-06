# Torrenzo

*Lightweight publishing pipeline for digital learning content*

---

## What Does It Do?

Traverses structured subject directories and outputs LMS-ready HTML content and PDF assessment briefs from Markdown, BibTeX, and other source material.

Torrenzo currently performs the following transformations:

| Input                                         | Output |
|-----------------------------------------------|--------|
| `assessments/assessment_<n>/ass_<n>_brief.md` | PDF    |
| `modules/module_<n>/mod_<n>_content.md`       | HTML   |
| `modules/module_<n>/mod_<n>_activities.md`    | HTML   |
| `modules/module_<n>/mod_<n>_resources.bib`    | HTML   |

---

## Configuration

An `outline.yaml` provides the project/subject configuration, which includes:

- **`subject` (with `id`, `title`)**  
  Basic subject identity used in rendered outputs.

- **`subject_descriptor`**  
  A short overview of the subject: its aims, key concepts, and laerning it covers.

- **`slo` (each with `id` and `description`)**  
  Subject Learning Outcomes; the specific knowledge, skills, and capabilities students.

- **`assessment` (each with an `id` and other values)**  
  Submission requirements, tagged in markdown using `{{ assessment|<id>|... }}` pattern.

---

## Usage

1. Ensure [prerequisites](#prerequisites) are installed.
2. [Populate subject content](#populating-content) (`outline.yaml`, `assessments/`, and `modules/`).
3. Run Torrenzo from the repository root using `python torrenzo.py`

By default, Torrenzo scans the current directory. To target another workspace use: `python3 torrenzo.py ../other-subject`

Torrenzo outputs everything (HTML, PDF, etc.) to the `build/` directory (which is cleared at the start of each run).

---

## Prerequisites

- **Python 3.10+**
- **Node 18+** with `npm`
- **Terminal environment** of your choice

### Working Directory
All relative paths assume execution from the repository root. Set your working directory using:
```bash
cd <repository-root>
```

### Python Setup
To create and activate a virtual environment, then install dependencies:
```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

### Node Setup
Required for PDF generation via `md-to-pdf`. To install Node dependencies locally:
```bash
npm install
```

---

## Repository architecture

Torrenzo provides a ready-to-use structure for a single subject.

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

- **Global metadata** is handled using the **`outline.yaml`**. Torrenzo injects these values wherever placeholders such as `{{subject_descriptor}}` appear in source Markdown files.

- **Assessment briefs** are defined using `assessments/assessment_<n>/ass_<n>_brief.md`. Any assets the brief references (images, etc.) go in its adjacent `assets/` directory.

- **Module files** follow a similar naming pattern (`modules/module_<n>/`), and comprise a --
  - `mod_<n>_content.md` -- for primary module content
  - `mod_<n>_activities.md` -- for activity page(s)
  - `mod_<n>_resources.bib` -- for references (in BibTeX format)
  - `assets/` -- holds and supporting files (images, etc.) that form part of each module

During the build process, Torrenzo injects `outline.yaml` metadata (SLOs, etc.) and transforms content into PDF assessment briefs, LMS-ready HTML module pages (including separate activity pages), and HTML resource lists -- all output to `build/`. Note that `build/` deletes its contents to recreate them entirely with each run.

### Assessment Branding

Universal assessment branding assets live in `assessments/style/`. On each run, the build injects `logo.svg` into the PDF header. Replace `logo.svg` (must be an SVG) to use a different logo, and configure styling and header/footer elements via the `style.css` and `config.js`.

---

## Technical Stuff

This section is intended for developers and contributors.

### Transformers

Torrenzo uses a plugin-style architecture with an extensible set of transformers:

| Transformer                                | Conversion      |
|--------------------------------------------|-----------------|
| `torrenzo_engine/renderers/bib_to_html.py` | BibTeX → HTML   |
| `torrenzo_engine/renderers/md_to_html.py`  | Markdown → HTML |
| `torrenzo_engine/renderers/md_to_pdf.py`   | Markdown → PDF  |

Torrenzo supports additional transformers without modifying the core pipeline. Developers should extend it to new targets (e.g., Marp slides or Word documents) without expanding the CLI driver. Potential candidates include:

- `.docx` → HTML (using predefined Word stylesheets to ensure consistent visual output and semantic structure)
- Marp `.md` → PDF (slide decks)
- Extended Markdown features for module pages (accordions, navigation tabs, and other LMS-specific markup)

---

## TODO

- [ ] Refine CSS styles for assessment briefs
- [x] Improve brief templates (page numbers, versioning in headers, etc.)
- [ ] Capture and expose build diagnostics (missing placeholders, missing assets, invalid front matter, failed conversions)
- [ ] ...

### 'Maybe' goals

- [ ] Build a GUI (desktop or web interface)
- [ ] Add support for Word documents (via semantic styles)
- [ ] Add support for Marp slide decks
- [ ] Implement batch LMS content importer (via Tampermonkey or similar)
- [ ] ...

