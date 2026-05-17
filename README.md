# Torrenzo

*Lightweight publishing pipeline for digital learning content*

---

![banner](README_banner.png)  
*Image: Editing a Torrenzo project using Obsidian for Markdown support. You can use any editor you prefer, including MS Word, with potential to support other formats in future.*

---

## What Does It Do?

Torrenzo traverses structured learning content directories and generates LMS-ready HTML module pages and PDF assessment briefs from Markdown, BibTeX, and other source material.

Torrenzo currently performs the following transformations:

| Input                                          | Output |
|------------------------------------------------|--------|
| `assessments/assessment_<n>/ass_<n>_brief.md`  | PDF    |
| `modules/module_<n>/mod_<n>_<seq>_<name>.md`   | HTML   |
| `modules/module_<n>/mod_<n>_<seq>_<name>.docx` | HTML   |

See the `demo/` directory for sample subject content, and `demo/build/` for example output artefacts.

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

## Usage: GUI

Torrenzo includes a desktop application for point-and-click builds.

![GUI](README_gui.png)
*Image: The Torrenzo GUI running on Linux. The GUI is available for Linux, macOS, and Windows.*

**Features:**

- **Directory picker** with history (remembers your subject folders)
- **Build options** as checkboxes: `--force`, `--clean`, `--optimize-assets`, `-cc`
- **Live build log** displayed in the window
- **Preview in Browser** button opens the build output for review

Launch the GUI using one of the following methods:

- Prebuilt binary from the Releases page: https://github.com/tabreturn/torrenzo/releases
- From source (repo root): `python -m torrenzo_gui` (ensure to install [prerequisites](#prerequisites) first)

> 💡 To start working on a Torrenzo project, it's easiest to [download the demo as a scaffold](https://download-directory.github.io/?url=https%3A%2F%2Fgithub.com%2Ftabreturn%2Ftorrenzo%2Ftree%2Fmain%2Fdemo), launch the GUI, and run a build to explore how everything works.

## Usage: Command-Line Interface (CLI)

1. Ensure to install [prerequisites](#prerequisites).
2. [Populate subject content](#populating-content) (`outline.md` or `outline.yaml`, `assessments/`, and `modules/`).
3. Run Torrenzo from the repository root, passing your subject directory:

```bash
python -m torrenzo /path/to/your-subject
```

`outline.[md|yaml]`, `assessments/`, `modules/`, and `build/` all resolve relative to the subject root. Torrenzo outputs everything (HTML, PDF, etc.) to `build/` inside the subject directory. Only files whose sources have changed since the last build are regenerated; orphaned outputs are removed automatically.

> 💡 Torrenzo supports writing, organising, and navigating content in [Obsidian](https://obsidian.md). The `demo/` subject includes an `.obsidian` configuration that you can copy to any working subject root -- then point a new vault at your subject directory to use it.

> 💡 Use `python -m torrenzo <subject> --optimize-assets` to optimise assets. SVG optimisation uses the system `scour` CLI tool (`pip install scour`). PNG optimisation requires `pngquant` or `oxipng` installed on your system.

> 💡 By default, Torrenzo skips files whose outputs are already newer than their sources. Use `--force` to rebuild everything regardless, or `--clean` to wipe `build/` first and then do a full rebuild.

> 💡 Each build writes (or appends to) `build/build-log.json` listing newly built files with timestamps. Use this to identify which files need updating in your LMS across multiple builds. Delete the log once you've uploaded everything to reset tracking.

---

## Configuration & Tags

Use `outline.[md|yaml]` as the single source of metadata, formatted in YAML. Use [Dataview-style](https://blacksmithgu.github.io/obsidian-dataview) tags in content, for example `` `=[[outline]].assessment.a1.weighting` `` or `` `=[[outline]].slo.a` ``

Starter keys in `outline.[md|yaml]` define your subject metadata and automatically populate across all content via tags/placeholders.

- **Subject:**  
  `subject.code`, `subject.title`, `subject.descriptor`
- **SLOs:**  
  Map under `slo` with codes (e.g., `slo.a`)
- **Assessments:**  
  Produce a full metadata table using `assessment.a1` or `assessment.a2`, etc.

### Components

Torrenzo includes built-in components for common page elements. Use the `component` tag prefix:

| Tag                                      | Description                                       |
|------------------------------------------|---------------------------------------------------|
| `` `=[[component.module-navigation]]` `` | Tabbed navigation linking to sibling module files |

Custom components live in `torrenzo/components/` and plug into the tag system via `build_component_tags()`.

---

## Prerequisites (to Run Torrenzo or Launch the GUI via CLI)

- **Python 3.10+**
- **Google Chrome or Chromium** (for PDF generation)
- **Terminal environment** of your choice

### Setup
Clone or download the Torrenzo repository. All setup commands run from the **Torrenzo repo root** -- subject content lives separately.

To create and activate a virtual environment, then install dependencies:
```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

> 💡 Running the GUI from the CLI is useful when you don't have administrative privileges on your computer (but already have Python).

> 💡 PDF generation uses your system's Chrome/Chromium. If Chrome is installed in a non-standard location, set the `PUPPETEER_EXECUTABLE_PATH` environment variable (e.g., `export PUPPETEER_EXECUTABLE_PATH=/path/to/chrome`).

---

## Populating Content

The tool is filesystem-driven: file names and directory structure determine how content is processed.

**Subject directory layout:**
```text
your-subject/
├── assessments/        # assessment briefs → PDF
│   ├── assessment_<n>/
│   │   ├── ass_<n>_brief.md
│   │   └── assets/
│   └── style/          # branding (logo.svg, style.css, config.js)
├── modules/            # module content → HTML
│   ├── module_00/      # overview / introductory content (landing page)
│   │   ├── mod_00_<seq>_<name>.[md|docx]
│   │   └── assets/
│   ├── module_<n>/
│   │   ├── mod_<n>_<seq>_<name>.[md|docx]
│   │   └── assets/
│   ├── style/          # stylesheet inlined into HTML output
│   └── references.bib  # subject-level BibTeX references
├── notes/              # lecturer-only notes (copied as-is, hidden in cartidge)
│   └── *.md (or any format)
├── build/              # generated output
│   └── lecturer_notes/ # notes output (retains original format)
└── outline.[md|yaml]   # subject configuration (YAML)
```

> 💡 To get started, you could simply duplicate the `demo/` subject, rename it, and use it as a starting point for developing new learning materials.

Subject content lives in two directories -- `assessments/` and `modules/`. Torrenzo relies on strict naming conventions in these directories to locate and process files.

- **Define global metadata** in `outline.[md|yaml]` (using YAML). Torrenzo injects these values wherever placeholders such as `` `=[[outline]].subject.title` `` appear in source Markdown files.

- **Define assessment briefs** in `assessments/assessment_<n>/ass_<n>_brief.md`. Place any assets the brief references (images, etc.) in the adjacent `assets/` directory.

- **Store reference sources** in `references.bib`. This file uses *BibTeX format*; in-text citations use the `@refname` syntax. Torrenzo renders the corresponding references at the bottom of the page.

- **Organise module files** using the same pattern under `modules/module_<n>/`. Each module contains:
  - `mod_<n>_<seq>_<name>.[md|docx]` -- module page(s) (content and activities)
  - `assets/` -- supporting files (images, etc.) used within the module

Use `modules/module_00/` for subject overview and introductory content (e.g., welcome page, student expectations, key documents). This typically serves as the landing page(s) content.

> 💡 Module files follow the pattern `mod_<module_num>_<seq>_<name>.<ext>`. For example: `mod_01_01_introduction.md`, `mod_01_02_oranges.md`, or `mod_01_03_activities.md`. Module folders accept an optional label suffix: `module_01_citrus_fruits/` becomes "Module 1 – Citrus Fruits" in the cartridge instead of "Module 1".

During the build process, Torrenzo reads metadata from `outline.[md|yaml]` (SLOs, etc.) and converts source content into:

- PDF assessment briefs
- LMS-ready HTML module pages (including separate activity pages)

Torrenzo writes all output to `build/`. Module assets copy to `build/modules_html/assets`

Torrenzo only rebuilds files whose source (or a shared dependency such as `outline.[md|yaml]` or the stylesheet) is newer than the existing output. Outputs for deleted or renamed source files are removed automatically. Each build output embeds a timestamp (code comments for plain-text formats; EXIF/etc. metadata for binary assets).

Use `--clean` to wipe `build/` and force a full rebuild, or `--force` to rebuild all files without clearing first.

### Lecturer Notes

Place lecturer-only materials (teaching notes, facilitation guides, answer keys) in `notes/`. Files are copied to `build/lecturer_notes/` retaining their original format -- no conversion applies (`.md` stays `.md`, `.docx` stays `.docx`, etc.). When exporting a Common Cartridge (via `--cc`), lecturer notes end up in the `.imscc` package under an **unpublished** module, hidden from students.

### Module Styling & Assessment Branding

An optional global stylesheet lives at `modules/style/style.css`. Its inlines CSS into HTML output so styling survives LMS copy-paste without requiring additional stylesheets in the target LMS.

Universal assessment branding assets live in `assessments/style/`. On each run, the build injects `logo.svg` into the PDF header. Replace `logo.svg` (must be an SVG) to use a different logo, and configure styling and header/footer elements via the `style.css` and `config.js`

> 💡 Each stylesheet and `config.js` includes a metadata block at the top (`Theme`, `Output`, `Version`, `Modified`). Update these when you customise styles, ensuring theming is easier to track across subjects.

---

## Technical Stuff

This section is intended for developers and contributors.

### Transformers

Torrenzo uses a plugin-style architecture with an extensible set of transformers:

| Transformer                                          | Conversion      |
|------------------------------------------------------|-----------------|
| `torrenzo/torrenzo_engine/renderers/bib_to_html.py`  | BibTeX → HTML   |
| `torrenzo/torrenzo_engine/renderers/docx_to_html.py` | MS Word → HTML  |
| `torrenzo/torrenzo_engine/renderers/md_to_html.py`   | Markdown → HTML |
| `torrenzo/torrenzo_engine/renderers/md_to_pdf.py`    | Markdown → PDF  |

> 💡 Note that MS Word is not a priority source format, so this has received the least attention. As a matter of personal preference, the Torrenzo contributor(s) do not spend time authoring content outside of Markdown.

Torrenzo supports additional transformers without modifying the core pipeline. Developers should extend it to new targets (e.g., Marp slides) without expanding the CLI driver. Potential candidates include:

- Marp `.md` → PDF (slide decks)
- Extended Markdown features for module pages (accordions, navigation tabs, and other LMS-specific markup)
- Really, the limit is your imagination and whatever an LMS can handle ...

### Common Cartridge (.imscc)

Pass `--cc` to generate an **IMS Common Cartridge** package alongside the normal build output. The `.imscc` file bundles all module pages as Canvas WikiPages (with inter-page navigation and asset paths rewritten to Canvas's `$WIKI_REFERENCE$` / `$IMS-CC-FILEBASE$` tokens).

**Importing into Canvas:**

1. Navigate to the target course and select **Settings → Import Course Content**.
2. Set *Content Type* to **Common Cartridge 1.x Package**, choose the `.imscc` file, and click **Import**.
3. Canvas will prompt you to select *All content* or *Specific content*. Importing all content populates:
  - **Modules** -- Grouped, numbered modules containing related pages; assessments appear in a separate *Assessments* module.
  - **Pages** -- All module pages appear as Wiki Pages; assign relevant `Module_00` page as the front page manually via **Pages → View All Pages → ⁝ → Use as Front Page**.
  - **Assignments** -- A submission point with its total marks, weighting, and rubric (parsed from the **last table** in the brief markdown).
  - **Files** -- assessment PDFs and image assets uploaded to course Files.
- **Lecturer Notes** -- Lecturer-only materials set to `unpublished` (hidden from students); notes retain their original format.

Additionally, any heading in the brief tagged with `[[cc-section]]` (at any level) is rendered below the linked PDF, with its full branch of sub-sections and content included.

---

## To-Do

- [x] Match Obsidian (Dataview) tag syntax to better support WYSIWYG-style editing workflows
- [x] Improve assessment brief templates (page numbers, versioning in headers, etc.)
- [x] Refine CSS styles for assessment briefs
- [x] Capture and expose build diagnostics (missing placeholders, logo assets, etc.)
- [x] Add asset optimisation step for images (PNG: pngquant, oxipng; SVG: scour)
- [x] Include MS Word sample template with styles approximating LMS formatting
- [x] Devise mechanism to flag new build content vs LMS-stable content (see `build/build-log.json`)
- [x] Add metadata timestamp to built items
- [x] Add support for common page elements (e.g., tabbed navigation components)
- [x] Configure GitHub Actions to publish cross-platform CLI packages (Windows/macOS/Linux)
- [x] Consolidate on a single runtime stack (Python or Node)
- [x] Add GUI desktop application

## Stretch Goals

- [x] Build export to `.imscc` (Common Cartridge) format for bulk LMS subject import
- [ ] Add support for Marp slide decks
- [ ] Evaluate Markdown image sizing support (e.g., Marpit image syntax: https://marpit.marp.app/image-syntax)

