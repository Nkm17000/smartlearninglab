# PDF Import + Learning Navigation Fix

## What was fixed

- `Contents` and `Table of Contents` pages are detected even when they do not use dotted leaders.
- Numbered topics such as `1. Parts of Speech` are parsed as the source lesson list.
- The importer starts reading lesson content only after the TOC, so TOC entries are never stored as lesson content.
- Each topic is mapped to the exact body section until the next topic heading.
- Topics can span multiple PDF pages.
- Practice headings with short suffixes (for example `25. Practice Set A — SSC Grammar`) are matched to their TOC entry.
- Missing topic body content is marked `toc_only`; it is never invented.
- Source page ranges are stored on imported lessons.

## Student UX

- Lesson navigation is derived from the published course curriculum every time a lesson opens.
- Previous/Next therefore works even when the learner entered the lesson from another screen.
- The final lesson alone shows `Course Complete`.
- Intermediate lessons always show `Next Lesson`.
- Students can expand `Course Outline` inside the lesson and jump directly to another lesson without leaving the learning screen.
