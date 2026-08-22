# Smart Learning Lab — Generic PDF Course Import V2

The PDF importer is intentionally **not tied to one PDF template**.

## Detection order

1. PDF bookmarks / native outline (`doc.get_toc()`)
2. Contents / Table of Contents pages
3. Numbered chapters/sections (`1`, `1.1`, `1.2`, `Chapter 1`, `Unit 1`, etc.)
4. Heading typography (bold/large headings)
5. Safe page-based fallback when a valid source boundary is available

## Course hierarchy

- Top-level PDF sections become modules where the PDF has a hierarchy.
- Child sections become lessons.
- Flat numbered TOCs become lessons in a `Course Content` module.
- Publisher-specific group headings can become modules with their bullet topics as lessons.

## Content preservation

- Lesson body is copied only from the uploaded PDF.
- Source page start/end are stored on every lesson.
- `content_blocks` are stored for predictable FE rendering.
- The original PDF is stored in GridFS.
- Missing TOC entries are never filled with generated/invented text.
- Incomplete sample PDFs therefore create only the lessons whose source content actually exists.

## Scanned PDFs

A scanned/image-only PDF is detected. The importer returns a clear OCR-required error instead of silently creating blank lessons. OCR can be added later as a separate deployment option.

## Tested sample types

- Tutorials Point-style Java tutorial with a detailed multi-page TOC.
- Think Java book with a native PDF outline and nested sections.
- Smart Learning Lab English Grammar study guide with a flat numbered contents page.
- One-page Smart Learning Lab certificate is rejected as a course source.
