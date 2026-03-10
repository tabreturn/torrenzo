# Torrenzo

*Lightweight publishing pipeline for digital learning content*

![banner](README_banner.png)

---

## What Does It Do?

Torrenzo traverses structured learning content directories and generates LMS-ready HTML module pages and PDF assessment briefs from Markdown, BibTeX, and other source material.

Torrenzo currently performs the following transformations:

| Input                                         | Output |
|-----------------------------------------------|--------|
| `assessments/assessment_<n>/ass_<n>_brief.md` | PDF    |
| `modules/module_<n>/mod_<n>_content.md`       | HTML   |
| `modules/module_<n>/mod_<n>_content.docx`     | HTML   |
| `modules/module_<n>/mod_<n>_activities.md`    | HTML   |
| `modules/module_<n>/mod_<n>_activities.docx`  | HTML   |

See [sample_build](sample_build) for example output artefacts generated from the demo content.

### Yeah, But Why?

Torrenzo keeps learning content **portable, readable, and version-controlled**.

Instead of authoring material directly in a learning management system (LMS), content is written in plain-text formats such as Markdown and BibTeX. This approach enables:

- **Consistent metadata** defined once and reused everywhere (e.g., learning outcomes or assessment details)
- **Version control** using Git and other standard tools
- **Clear separation** of content and presentation
- **Editor independence** so you can write with any tool (Obsidian, VS Code, Vim, even MS Word?)
- **Machine-readable materials** that automation tools and AI can analyse and update
- **Extensible components** for reusable interface elements across multiple pages
- **Adaptable open-source tooling** to extend or customise for *your* publishing workflow

---

## Usage

1. Ensure to install [prerequisites](#prerequisites).
2. [Populate subject content](#populating-content) (`outline.md`, `assessments/`, and `modules/`).
3. Run Torrenzo from the repository root using `python torrenzo.py`

By default, Torrenzo scans the current directory. To target another workspace, use: `python torrenzo.py ../other-subject`

Torrenzo outputs everything (HTML, PDF, etc.) to the `build/` directory (which is cleared at the start of each run).

> 💡 Torrenzo supports writing, organising, and navigating content in [Obsidian](https://obsidian.md), and includes an `.obsidian` configuration so that you can simply point a new vault at your Torrenzo project.


> 💡 Use `python torrenzo.py --optimize-assets` to optimise assets. This feature requires SVGO for SVG (provided via `npm install`). PNG optimisation requires `pngquant` or `oxipng` installed on your system.

---

## Configuration & Tags

Use `outline.md` as the single source of metadata, formatted in YAML. Use [Dataview-style](https://blacksmithgu.github.io/obsidian-dataview) tags in content, for example `` `=[[outline]].assessment.a1.weighting` `` or `` `=[[outline]].slo.a` ``

Starter keys in `outline.md` define your subject metadata and automatically populate across all content via tags/placeholders.

- **Subject:**  
  `subject.code`, `subject.title`, `subject.descriptor`
- **SLOs:**  
  Map under `slo` with codes (e.g., `slo.a`)
- **Assessments:**  
  Produce a full metadata table using `assessment.a1` or `assessment.a2`, etc.

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

## Repository Architecture

Torrenzo provides a ready-to-use structure for a single subject. The project is intentionally filesystem-driven: file names and directory structure determine how Torrenzo processes content.

Any `demo_`-prefixed items are included for illustration. You can delete them if you wish; otherwise they build normally and appear in the `build/` output.

```text
subject-root/
├── assessments/        # assessment briefs → PDF
│   ├── demo_assessment_1/
│   │   ├── ass_1_brief.md
│   │   └── assets/
│   ├── assessment_<n>/
│   │   ├── ass_<n>_brief.md
│   │   └── assets/
│   └── ...
├── modules/            # module content → HTML
│   ├── demo_module_1/
│   │   ├── mod_1_content.[md|docx]
│   │   ├── mod_1_activities.[md|docx]
│   │   └── assets/
│   ├── module_<n>/
│   │   ├── mod_<n>_content.[md|docx]
│   │   ├── mod_<n>_activities.[md|docx]
│   │   └── assets/
│   └── ...
├── build/              # generated output
├── outline.md          # subject configuration (YAML)
├── references.bib      # global references (BibTeX)
└── torrenzo.py         # run to build
```

### Populating Content

Subject content lives in two directories -- `assessments/` and `modules/`. Torrenzo relies on strict naming conventions in these directories to locate and process files.

- **Define global metadata** in `outline.md` (using YAML). Torrenzo injects these values wherever placeholders such as `` `=[[outline]].subject.title` `` appear in source Markdown files.

- **Define assessment briefs** in `assessments/assessment_<n>/ass_<n>_brief.md`. Place any assets the brief references (images, etc.) in the adjacent `assets/` directory.

- **Store reference sources** in `references.bib`. This file uses *BibTeX format*; in-text citations use the `@refname` syntax. Torrenzo renders the corresponding references at the bottom of the page.

- **Organise module files** using the same pattern under `modules/module_<n>/`. Each module contains:
  - `mod_<n>_content.[md|docx]` -- primary module content page(s)
  - `mod_<n>_activities.[md|docx]` -- activity page(s)
  - `assets/` -- supporting files (images, etc.) used within the module

> 💡 For multiple content or activity pages, add a suffix to the file name. For example: `mod_01_content_01.md`, `mod_01_content_02.md`, or `mod_01_activities_foo.md`, `mod_01_activities_bar.md`

During the build process, Torrenzo reads metadata from `outline.md` (SLOs, etc.) and converts source content into:

- PDF assessment briefs
- LMS-ready HTML module pages (including separate activity pages)

Torrenzo writes all output to `build/`. Module assets copy to `build/modules_html/assets`

When processing demo inputs, Torrenzo adds a `demo_` filename prefix to both HTML outputs and their asset filenames/paths. For non-demo inputs, it keeps the original base names. Torrenzo clears and regenerates the `build/` directory on each run.

### Module Styling

An optional global stylesheet lives at `modules/style/style.css`. Its rules inline into HTML output so styling survives LMS copy-paste without requiring additional stylesheets in the target LMS.

### Assessment Branding

Universal assessment branding assets live in `assessments/style/`. On each run, the build injects `logo.svg` into the PDF header. Replace `logo.svg` (must be an SVG) to use a different logo, and configure styling and header/footer elements via the `style.css` and `config.js`

---

## Technical Stuff

This section is intended for developers and contributors.

### Transformers

Torrenzo uses a plugin-style architecture with an extensible set of transformers:

| Transformer                                 | Conversion      |
|---------------------------------------------|-----------------|
| `torrenzo_engine/renderers/bib_to_html.py`  | BibTeX → HTML   |
| `torrenzo_engine/renderers/docx_to_html.py` | MS Word → HTML  |
| `torrenzo_engine/renderers/md_to_html.py`   | Markdown → HTML |
| `torrenzo_engine/renderers/md_to_pdf.py`    | Markdown → PDF  |

Torrenzo supports additional transformers without modifying the core pipeline. Developers should extend it to new targets (e.g., Marp slides) without expanding the CLI driver. Potential candidates include:

- Marp `.md` → PDF (slide decks)
- Extended Markdown features for module pages (accordions, navigation tabs, and other LMS-specific markup)
- Really, the limit is your imagination and whatever an LMS can handle ...

### Common Cartridge

Preliminary investigation into **[Common Cartridge](https://www.1edtech.org/standards/cc)** suggests it can effectively bulk-populate new subjects, though it is likely less useful for ongoing maintenance where individual components change more sporadically and 'manual' updates remain manageable. The [common_cartridge_WIP](common_cartridge_WIP) directory contains exploratory work to understand the format and generate new cartridges that may later integrate into the build process.

---

## To-Do

- [x] Match Obsidian (Dataview) tag syntax to better support WYSIWYG-style editing workflows
- [x] Improve assessment brief templates (page numbers, versioning in headers, etc.)
- [x] Refine CSS styles for assessment briefs
- [x] Capture and expose build diagnostics (missing placeholders, logo assets, etc.)
- [x] Add asset optimisation step for images (pngquant/oxipng for PNG, svgo for SVG)
- [ ] **Fix MS Word transformer tags?** (Do they function? Should the placeholder/tag syntax change?)
- [ ] **Fix MS Word transformer styles?** (Do they function?)
- [ ] **Include MS Word sample template** (with Word styles that approximate the LMS styling?)
- [ ] Add Image sizing support in Markdown (perhaps follow https://marpit.marp.app/image-syntax)
- [ ] Add support for common page elements (e.g., tabbed navigation components) -- via YAML metadata in header of Markdown?
- [ ] Build to `.imscc` (Common Cartridge) format for bulk populating subjects (see [common_cartidge_WIP](common_cartidge_WIP)), otherwise
- [ ] ... Implement a batch LMS content importer (via Tampermonkey or similar)?
- [ ] Configure GitHub Actions to publish cross-platform CLI packages (Windows/macOS/Linux)
- [ ] ... and add one-click executable runner to the above?
- [ ] Devise mechanism to flag what is new build content (versus what won't need updating in LMS)
- [ ] ... and on the above, best to add meta/commented timestamp to built items.
- [ ] ...

### 'Maybe' Goals

- [ ] Consolidate on a single runtime stack (Python or Node)
- [ ] Add support for Marp slide decks
- [ ] Build an Obsidian extension/plugin to streamline authoring workflows (configuration, build commands, etc.)
- [ ] ...

