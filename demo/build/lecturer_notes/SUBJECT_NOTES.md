# Instructor Notes

This document offers suggestions for running the subject. It is not processed by Torrenzo. 

Torrenzo will ignore everything in `notes`.

## Delivery Overview

FRU101 runs across a single learning block with four modules. The landing page (`module_00`) introduces the subject, expectations, and key documents. Module 1 (the only one populated in this demo) uses citrus fruits as a lens for observation and cataloguing.

| Week | Module | Focus |
|------|--------|-------|
| 0 | Welcome | Subject intro, expectations, key docs |
| 1 | 1.1--1.2 | Observation skills; the orange as a case study |
| 2 | 1.3--1.4 | Lemons and comparative notes; learning resources & activities |

Assessment 1 (Seasonal Fruit Catalogue) is due at the end of Module 4.

## Session Structure

Each week's facilitated session (3 hours) might follow this rhythm:

1. **Opening (20 min)** -- Recap previous module; surface questions; preview this week's focus.
2. **Content discussion (40 min)** -- Walk through the module pages together. Invite students to share observations from the readings. Use the orange/lemon examples as prompts.
3. **Hands-on activity (60 min)** -- Students work individually or in pairs on observation and catalogue-writing exercises (see below).
4. **Share-back (30 min)** -- A few students share draft catalogue entries. Group discusses what worked, what surprised them, what to revise.
5. **Assessment check-in (20 min)** -- Review progress toward Assessment 1. Clarify brief requirements. Flag upcoming deadlines.
6. **Close (10 min)** -- Summarise key takeaways. Preview next module. Assign pre-reading.

## In-Class Activities

### Module 1: Observation Warm-Up

Bring a few actual citrus fruits to class (or ask students to bring one). Give everyone 10 minutes to write a paragraph describing the fruit in front of them -- appearance, scent, texture, even sound when peeled. No phones, no Googling. Compare descriptions: what did different people notice? What vocabulary emerged?

### Module 1: Mini Catalogue Entry

Supply three high-quality fruit photographs (or use the demo assets). Each student writes a 4--6 sentence catalogue entry for one fruit, pairing the image with descriptive text. Swap with a neighbour and give feedback using two questions:

- What does the description tell you that the image alone cannot?
- Is there anything the image shows that the description missed?

### Module 1: Sensory Vocabulary Builder

On a whiteboard or shared doc, build a class word bank: columns for appearance, scent, texture, flavour, and sound. Students contribute terms as they encounter them in readings or during observation exercises. Return to this bank throughout the module -- it grows into a shared resource.

## Assessment Support

Module 1 activities build toward Assessment 1. By the end of the module, students should have:

- Practised close observation of at least two fruits.
- Written draft catalogue entries with images.
- Received peer feedback on one entry.
- Reviewed the Assessment 1 brief and understood the submission format (ZIP with README).

Remind students that Assessment 1 is playful -- the goal is careful observation and clear description, not formal academic referencing. Encourage them to cite image sources in captions and acknowledge borrowed descriptors.

## Using the LMS Pages

The HTML pages in `build/modules_html/` are body-only snippets for pasting into your LMS. Each page includes:

- **Tabbed navigation** -- links to sibling pages within the same module.
- **Stamped build metadata** -- a comment at the top showing build date and source file.
- **Inlined CSS** -- styling travels with the content; no separate stylesheet needed in the LMS.

Only rebuild and repaste pages that have changed. Torrenzo's incremental build tells you which files are newly built vs. up-to-date.

## Extending the Subject

To add Module 2 (say, Tropical Fruits):

```bash
mkdir modules/module_02
mkdir modules/module_02/assets
```

Create pages following `mod_02_01_<name>.md`, etc. Add entries to `outline.md` for new SLOs or assessments as needed. Run the build -- new pages appear in `build/modules_html/` automatically.

