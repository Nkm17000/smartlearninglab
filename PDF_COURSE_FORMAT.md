# PDF → Course Authoring Standard

Use this format whenever an AI or content author creates a PDF that will be uploaded to Smart Learning Lab.

## 1. Required structure

1. **Cover page**
   - Course title
   - Optional subtitle
   - Target exam / audience

2. **Table of Contents**
   - Use the heading `Contents` or `Table of Contents`.
   - List every topic in the exact learning order.
   - Use one numbered topic per line:

```text
1. Topic One
2. Topic Two
3. Topic Three
```

   - Dotted leaders are optional:

```text
1. Topic One ........ 3
2. Topic Two ........ 5
```

3. **Course body**
   - Start each topic with the exact same numbered heading used in the TOC.
   - Keep one topic as one lesson.

```text
1. Topic One
<complete content for Topic One>

2. Topic Two
<complete content for Topic Two>
```

## 2. One topic = one lesson

Do not merge multiple TOC topics into one lesson. Do not create extra topics that are not in the PDF.

The importer uses the TOC as the source of truth for:
- topic names
- lesson names
- order
- chapter boundaries

## 3. Content requirements

Each topic should contain its complete source material:
- explanations
- definitions
- rules
- examples
- tables
- bullet points
- formulas
- code examples
- exercises
- exam tips

Do not put the complete course content only at the end of the PDF.

## 4. Avoid these problems

- Do not create a TOC containing chapters whose body pages are missing.
- Do not use headings in the body that differ significantly from the TOC.
- Do not use numbered question lists that look like chapter headings outside a clearly named practice section.
- Do not generate a TOC-only PDF when the intention is to create a full course.
- Avoid scanned/image-only PDFs unless OCR is available.

## 5. Recommended AI prompt

Create a complete educational PDF using the following rules:

> Create a full course PDF. Start with a cover page and a `Table of Contents`. List every topic in learning order using numbered headings (`1.`, `2.`, `3.`...). For every TOC topic, include the complete topic body later in the PDF using the exact same numbered heading and title. Do not omit any topic. Do not place topic content only in the final pages. Keep one topic equal to one lesson. Preserve explanations, examples, rules, tables, exercises, code and important notes. Ensure the TOC and body headings match exactly. The PDF must contain the complete body for every topic listed in the TOC.

## 6. Example

```text
COURSE TITLE: English Grammar for SSC & CAT

TABLE OF CONTENTS
1. Parts of Speech
2. Nouns
3. Pronouns
4. Adjectives
5. Verbs

1. Parts of Speech
Complete content...
Examples...
Exercises...

2. Nouns
Complete content...
Examples...
Exercises...

3. Pronouns
Complete content...
Examples...
Exercises...
```

This format is optimized for automatic PDF → Course extraction and lesson navigation.
