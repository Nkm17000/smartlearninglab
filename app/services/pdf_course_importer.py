"""Generic PDF -> course importer.

Design goals:
- never depend on one publisher/template
- prefer the PDF's own outline/TOC when available
- otherwise detect headings from numbering + typography
- preserve every body page between lesson boundaries
- group hierarchical headings into modules/lessons
- keep source page ranges so the original PDF remains authoritative
- never invent missing text
"""
from __future__ import annotations

import io
import os
import re
import statistics
from dataclasses import dataclass
from typing import Any

import fitz  # PyMuPDF


BULLET_RE = re.compile(r"^\s*(?:[\u2022\u2023\u25E6\u25CF\u25AA\u25AB\u25A0]|[-*])\s+")
NUMBERED_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)(?:[.)])?\s*(.+?)\s*$")
CHAPTER_RE = re.compile(r"^\s*((?:chapter|unit|module|part|section)\s+\d+(?:\s*[:.-]\s*)?)(.+?)\s*$", re.I)


def norm(text: str) -> str:
    text = str(text or "").replace("\u00ad", "").replace("\ufeff", "")
    text = re.sub(r"\.{3,}", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def clean_line(text: str) -> str:
    text = str(text or "").replace("\x00", "").replace("\u00a0", " ")
    text = text.replace("\uf0b7", "•").replace("\uf0a7", "•")
    return re.sub(r"[ \t]+", " ", text).strip()


def strip_toc_dots(text: str) -> str:
    text = re.sub(r"\.{3,}[^\w]*\d+\s*$", "", text)
    text = re.sub(r"\s{2,}\d+\s*$", "", text)
    return text.strip(" .")


def heading_number(text: str):
    m = NUMBERED_RE.match(clean_line(text))
    return (m.group(1), m.group(2).strip()) if m else None


def heading_kind(text: str):
    s = clean_line(text)
    m = heading_number(s)
    if m:
        return "numbered", m[0], m[1]
    m = CHAPTER_RE.match(s)
    if m:
        prefix = m.group(1).strip()
        title = m.group(2).strip()
        return "chapter", prefix, title
    return None


def is_probable_heading(text: str, size: float, flags: int, body_size: float) -> bool:
    s = clean_line(text)
    if not s or len(s) > 140 or BULLET_RE.match(s):
        return False
    if heading_kind(s):
        return not s.endswith(("?", ";"))
    bold = bool(flags & 16)
    large = size >= body_size + 2.0
    words = s.split()
    if len(words) <= 10 and (bold and (large or size >= 13)):
        if s.endswith((".", ":", ";", "?")) and len(words) > 5:
            return False
        return True
    # Short all-caps headings are common in manuals.
    letters = re.sub(r"[^A-Za-z]", "", s)
    if letters and letters.upper() == letters and len(letters) >= 4 and len(words) <= 8:
        return True
    return False


def _line_records(doc: fitz.Document):
    records = []
    seq = 0
    for pno, page in enumerate(doc):
        page_dict = page.get_text("dict")
        for bidx, block in enumerate(page_dict.get("blocks", [])):
            if "lines" not in block:
                continue
            for lidx, line in enumerate(block.get("lines", [])):
                spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
                if not spans:
                    continue
                text = clean_line("".join(s.get("text", "") for s in spans))
                if not text:
                    continue
                sizes = [float(s.get("size", 0)) for s in spans]
                flags = max(int(s.get("flags", 0)) for s in spans)
                fonts = [str(s.get("font", "")) for s in spans]
                records.append({
                    "seq": seq,
                    "page": pno,
                    "block": bidx,
                    "line": lidx,
                    "text": text,
                    "size": max(sizes or [0]),
                    "flags": flags,
                    "fonts": fonts,
                    "bbox": line.get("bbox", [0, 0, 0, 0]),
                })
                seq += 1
    return records


def _repeated_chrome(records, page_count):
    """Identify repeated header/footer lines without assuming a publisher name."""
    counts = {}
    for r in records:
        if r["page"] == 0:
            continue
        y0, y1 = r["bbox"][1], r["bbox"][3]
        key = norm(r["text"])
        if not key or len(key) > 100:
            continue
        # Page headers and footers usually live in the top/bottom 12%.
        # Coordinates are page-local; use page height below when filtering.
        counts[key] = counts.get(key, 0) + 1
    # Conservative: repeated on >= 25% of pages and short enough to be chrome.
    threshold = max(3, int(page_count * 0.25))
    return {k for k, v in counts.items() if v >= threshold and len(k.split()) <= 12}


def _page_height(doc, pno):
    return float(doc[pno].rect.height)


def useful_records(doc):
    records = _line_records(doc)
    repeated = _repeated_chrome(records, len(doc))
    out = []
    for r in records:
        h = _page_height(doc, r["page"])
        y0, y1 = r["bbox"][1], r["bbox"][3]
        key = norm(r["text"])
        # Remove only repeated chrome in the page margins. A repeated body phrase is retained.
        margin = h * 0.11
        if key in repeated and (y0 < margin or y1 > h - margin):
            continue
        if re.fullmatch(r"(?:page\s*)?[ivxlcdm]+", key, re.I):
            continue
        if re.fullmatch(r"page\s+\d+", key, re.I):
            continue
        out.append(r)
    return out


def _outline_entries(doc: fitz.Document):
    toc = doc.get_toc(simple=True) or []
    out = []
    for level, title, page in toc:
        title = strip_toc_dots(clean_line(title))
        if not title or len(title) > 180:
            continue
        out.append({"level": int(level), "title": title, "page_hint": max(1, int(page or 1))})
    return out


def _contents_pages(records, doc):
    """Return only the actual TOC span, not later numbered exercises/questions."""
    by_page = {}
    for r in records:
        by_page.setdefault(r["page"], []).append(r)

    markers = []
    for pno, rows in by_page.items():
        joined = norm(" ".join(r["text"] for r in rows[:20]))
        if any(x in joined for x in ("table of contents", "contents", "course contents")):
            markers.append(pno)
    if markers:
        start = min(markers)
        pages = [start]
        # Continue only through immediately following pages that look like TOC pages.
        for pno in range(start + 1, min(len(doc), start + 20)):
            rows = by_page.get(pno, [])
            text = " ".join(r["text"] for r in rows)
            dotted = sum(1 for r in rows if "..." in r["text"] or ". . ." in r["text"])
            numbered = sum(1 for r in rows if re.match(r"^\s*\d+[.)]?\s*$", r["text"]) or heading_number(strip_toc_dots(r["text"])))
            upper = sum(1 for r in rows if r["text"].strip().isupper() and len(r["text"].split()) <= 12)
            if dotted >= 2 or (numbered >= 3 and upper >= 1):
                pages.append(pno)
            else:
                break
        return pages

    # No explicit marker: use dotted TOC pages only. This avoids practice-question pages.
    pages=[]
    for pno, rows in by_page.items():
        dotted=sum(1 for r in rows if "..." in r["text"] or ". . ." in r["text"])
        if dotted >= 3:
            pages.append(pno)
    return sorted(pages)


def _parse_text_contents(records, contents_pages):
    """Parse several TOC layouts, including split number/title/page columns."""
    by_page={}
    for r in records:
        by_page.setdefault(r["page"],[]).append(r)
    entries=[]
    current_group=None
    for pno in contents_pages:
        rows=by_page.get(pno,[])
        i=0
        while i<len(rows):
            r=rows[i]; raw=clean_line(r["text"])
            if not raw or norm(raw) in {"contents","table of contents","course contents"}:
                i+=1; continue

            # Split-column TOC: "1." on one line, title on next line, page number on next.
            if re.fullmatch(r"\d{1,3}[.)]?", raw) and i+1<len(rows):
                title_raw=clean_line(rows[i+1]["text"])
                page_hint=None
                mpage=re.search(r"(?:\.{3,}\s*|\s{2,})(\d+)\s*$", title_raw)
                if mpage:
                    page_hint=int(mpage.group(1))
                    title_raw=title_raw[:mpage.start()]
                title=strip_toc_dots(title_raw)
                j=i+2
                if j<len(rows) and re.fullmatch(r"\d+|[ivxlcdm]+", clean_line(rows[j]["text"]), re.I):
                    try: page_hint=int(rows[j]["text"])
                    except Exception: pass
                    j+=1
                if title and len(title)<=180:
                    entries.append({"level":1,"title":title,"number":re.sub(r"[.)]$","",raw),"group":current_group,"page_hint":page_hint})
                    i=j; continue

            # Normal single-line numbered TOC: "10. Topic ........ 42" or "10.Topic ... 42".
            num=heading_number(raw)
            if num:
                ph=None
                mpage=re.search(r"(?:\.{3,}\s*|\s{2,})(\d+)\s*$", raw)
                if mpage:
                    ph=int(mpage.group(1))
                title=num[1]
                if mpage:
                    title=raw[:mpage.start()].strip(" .")
                    title=re.sub(r"^\s*\d+(?:\.\d+)*[.)]?\s*", "", title).strip()
                else:
                    title=strip_toc_dots(title)
                if title and len(title)<=180 and not title.endswith("?"):
                    entries.append({"level":1,"title":title,"number":num[0],"group":current_group,"page_hint":ph})
                    i+=1; continue

            if BULLET_RE.match(raw):
                child=BULLET_RE.sub("",raw).strip()
                if child:
                    entries.append({"level":2,"title":child,"number":None,"group":current_group,"page_hint":None})
                i+=1; continue

            # Group/section headings in TOCs are commonly uppercase and/or bold.
            if (r["text"].strip().isupper() and len(raw.split())<=12) or (r["flags"] & 16 and r["size"]>=12 and len(raw.split())<=8):
                if not raw.lower().startswith(("about ","copyright ","prerequisite","how to ")):
                    current_group=strip_toc_dots(raw)
            i+=1

    unique=[]; seen=set()
    for e in entries:
        k=(e["level"],norm(e["title"]),norm(e.get("group")),e.get("number"))
        if k not in seen:
            seen.add(k); unique.append(e)
    return unique

def _heading_records(doc, records):
    body_sizes = [r["size"] for r in records if 8 <= r["size"] <= 14]
    body = statistics.median(body_sizes) if body_sizes else 10.0
    heads = []
    for r in records:
        if is_probable_heading(r["text"], r["size"], r["flags"], body):
            kind = heading_kind(r["text"])
            if kind:
                htype = kind[0]
            else:
                htype = "styled"
            heads.append({**r, "heading_type": htype})
    return heads


def _find_heading_position(headings, title, start_page=0, number=None):
    target = norm(strip_toc_dots(title))
    candidates = [h for h in headings if h["page"] >= start_page]
    # Prefer exact title, then numbered title, then containment.
    for h in candidates:
        hs = norm(h["text"])
        tail = re.sub(r"^\d+(?:\.\d+)*[.)]?\s*", "", hs)
        if number:
            n=norm(str(number))
            if hs.startswith(n) and (tail == target or tail.startswith(target + " ") or target.startswith(tail)):
                return h
        if hs == target or tail == target:
            return h
    for h in candidates:
        hs = norm(h["text"])
        tail = re.sub(r"^\d+(?:\.\d+)*[.)]?\s*", "", hs)
        if target and (tail.endswith(target) or target.endswith(tail) or tail.startswith(target + " ")) and len(tail) >= max(5, int(len(target)*0.55)):
            return h
    return None


def _build_from_outline(doc, records, outline):
    headings = _heading_records(doc, records)
    # Remove TOC headings by starting after the latest contents page.
    content_start = max(_contents_pages(records, doc) or [-1]) + 1
    modules = []
    # Outline may include level 1/2/3. Treat level 1 as module and deepest child as lesson.
    i = 0
    while i < len(outline):
        e = outline[i]
        if e["level"] > 1:
            # Orphan subsection becomes a module-less lesson later.
            i += 1; continue
        module_title = e["title"]
        children = []
        j = i + 1
        while j < len(outline) and outline[j]["level"] > e["level"]:
            children.append(outline[j]); j += 1
        if children:
            lessons = []
            for child in children:
                if child["level"] == e["level"] + 1:
                    lessons.append(child)
            if not lessons:
                lessons = [children[0]]
        else:
            lessons = [e]
        module = {"title": module_title, "description": "Source section from the uploaded PDF.", "lessons": []}
        for le in lessons:
            h = _find_heading_position(headings, le["title"], content_start)
            if not h:
                # Use the PDF outline destination directly when the visual heading
                # is not text-searchable (common in books with decorative chapter titles).
                ph = max(1, int(le.get("page_hint") or 1)) - 1
                h = next((x for x in headings if x["page"] >= max(content_start, ph-1) and (norm(le["title"]) in norm(x["text"]) or norm(x["text"]) in norm(le["title"]))), None)
                if not h and content_start <= ph < len(doc):
                    h = {"page": ph, "line": -1, "seq": None, "text": le["title"], "size": 0, "flags": 0, "bbox": [0,0,0,0]}
            module["lessons"].append({
                "title": le["title"],
                "source_level": le["level"],
                "source_number": re.match(r"^\d+(?:\.\d+)*", le["title"] or "").group(0) if re.match(r"^\d+(?:\.\d+)*", le["title"] or "") else None,
                "anchor": h,
                "group": module_title,
            })
        modules.append(module)
        i = j
    return modules, headings


def _build_from_text_toc(doc, records, toc_entries):
    headings = _heading_records(doc, records)
    toc_pages = _contents_pages(records, doc)
    content_start = max(toc_pages or [-1]) + 1

    has_groups = any(e.get("group") for e in toc_entries)
    has_bullet_children = any(e.get("level") == 2 and e.get("number") is None for e in toc_entries)

    if has_bullet_children or has_groups:
        groups=[]
        current_by_group={}
        for e in toc_entries:
            group=e.get("group") or "Course Content"
            if group not in current_by_group:
                current_by_group[group]={"title":group,"description":f"Topics from the uploaded PDF section: {group}.","lessons":[]}
                groups.append(current_by_group[group])
            current_by_group[group]["lessons"].append(e)
        modules=groups
    else:
        modules=[{"title":"Course Content","description":"Topics from the uploaded PDF.","lessons":list(toc_entries)}]

    # Derive a printed-page -> PDF-page offset where possible.
    first_ph = next((e.get("page_hint") for e in toc_entries if e.get("page_hint")), None)
    first_title = next((e for e in toc_entries if e.get("page_hint")), None)
    offset = None
    if first_ph is not None and first_title:
        # Search the first body title; if not present, use the first page after the TOC.
        h=_find_heading_position(headings, first_title["title"], content_start, first_title.get("number"))
        if h:
            offset=h["page"]+1-int(first_ph)
        else:
            first_body_page = next((p for p in range(content_start, len(doc)) if sum(len(r["text"]) for r in records if r["page"] == p) >= 200), content_start)
            offset=first_body_page-int(first_ph)

    for module in modules:
        for le in module["lessons"]:
            title=le["title"]; num=le.get("number")
            # When the PDF gives page numbers in its TOC, use those as the authoritative
            # boundary. This avoids confusing numbered exercises inside the body with TOC topics.
            if le.get("page_hint") is not None and offset is not None:
                pdf_page=int(le["page_hint"])+offset-1
                if content_start <= pdf_page < len(doc):
                    le["anchor"]={"page":pdf_page,"line":-1,"seq":None,"text":title,"size":0,"flags":0,"bbox":[0,0,0,0]}
                else:
                    le["anchor"]=None
            else:
                le["anchor"]=_find_heading_position(headings,title,content_start,number=num)
            le["group"]=module["title"]
    return modules, headings

def _fallback_modules(doc, records):
    headings = _heading_records(doc, records)
    content_start = max(_contents_pages(records, doc) or [-1]) + 1
    heads = [h for h in headings if h["page"] >= content_start]
    # Prefer hierarchical numbering.
    numbered = []
    for h in heads:
        n = heading_kind(h["text"])
        if n and n[0] == "numbered":
            depth = len(n[1].split("."))
            numbered.append((h, n[1], n[2], depth))
    if numbered:
        top_depth = min(x[3] for x in numbered)
        tops = [x for x in numbered if x[3] == top_depth]
        modules=[]
        for idx, top in enumerate(tops):
            start_num=top[1]
            children=[x for x in numbered if x[1].startswith(start_num+".") and x[3] == top_depth+1]
            lessons=children or [top]
            modules.append({"title": top[2], "description":"Source chapter from the uploaded PDF.", "lessons":[{"title":x[2],"source_level":x[3],"source_number":x[1],"anchor":x[0],"group":top[2]} for x in lessons]})
        return modules, headings
    # Last resort: each strong heading becomes a lesson, grouped by page ranges.
    strong=[h for h in heads if h["size"] >= (statistics.median([x["size"] for x in heads]) if heads else 10)]
    if not strong:
        # Never lose content: page chunks of 5 pages.
        strong=[]
        for p in range(content_start, len(doc), 5):
            strong.append({"page":p,"line":0,"text":f"Pages {p+1}-{min(len(doc),p+5)}","bbox":[0,0,0,0]})
    return [{"title":"Course Content","description":"Content extracted from the uploaded PDF.","lessons":[{"title":h["text"],"source_level":1,"source_number":None,"anchor":h,"group":"Course Content"} for h in strong]}], headings


def _clean_content_lines(rows):
    out=[]
    for r in rows:
        s=clean_line(r["text"])
        if not s:
            if out and out[-1] != "": out.append("")
            continue
        out.append(s)
    while out and out[0]=="": out.pop(0)
    while out and out[-1]=="": out.pop()
    return out


def _extract_content(doc, records, start, end):
    start_seq = start.get("seq") if start else None
    end_seq = end.get("seq") if end else None
    rows=[]
    for r in records:
        if start_seq is not None and r.get("seq",0) < start_seq:
            continue
        if end_seq is not None and r.get("seq",0) >= end_seq:
            continue
        rows.append(r)
    lines=_clean_content_lines(rows)
    if lines and start and norm(lines[0]) == norm(start["text"]):
        lines=lines[1:]
    return "\n".join(lines).strip()

def _content_blocks(content):
    """Convert extracted text to neutral blocks; FE can render these without knowing PDF templates."""
    lines=content.splitlines()
    blocks=[]; buf=[]; i=0
    def flush_para():
        nonlocal buf
        if buf:
            txt=" ".join(x.strip() for x in buf).strip()
            if txt: blocks.append({"type":"paragraph","text":txt})
            buf=[]
    while i<len(lines):
        s=lines[i].strip()
        if not s:
            flush_para(); i+=1; continue
        if BULLET_RE.match(s):
            flush_para(); items=[]
            while i<len(lines) and BULLET_RE.match(lines[i].strip()):
                items.append(BULLET_RE.sub("",lines[i].strip()).strip()); i+=1
            blocks.append({"type":"bullets","items":items}); continue
        if re.match(r"^\s*\d+[.)]\s+",s):
            flush_para(); items=[]
            while i<len(lines) and re.match(r"^\s*\d+[.)]\s+",lines[i].strip()):
                items.append(re.sub(r"^\s*\d+[.)]\s+","",lines[i].strip())); i+=1
            blocks.append({"type":"numbered","items":items}); continue
        if re.match(r"^(example|exam tip|note|warning|important)\s*:",s,re.I):
            flush_para(); label,rest=s.split(":",1); blocks.append({"type":"callout","label":label.strip(),"text":rest.strip()}); i+=1; continue
        # Markdown-like headings occasionally survive extraction.
        if len(s)<=90 and (heading_kind(s) or (s.endswith(":") and len(s.split())<=8)):
            flush_para(); blocks.append({"type":"subheading","text":s}); i+=1; continue
        buf.append(s); i+=1
    flush_para()
    return blocks


def build_course_from_pdf(data: bytes, filename: str):
    doc=fitz.open(stream=data, filetype="pdf")
    if len(doc)==0:
        raise ValueError("The PDF contains no pages.")
    records=useful_records(doc)
    text_len=sum(len(r["text"]) for r in records)
    joined=norm(" ".join(r["text"] for r in records[:80]))
    if len(doc) <= 2 and ("certificate of completion" in joined or "certificate" in joined) and text_len < 2000:
        return {"status":"not_course","reason":"This PDF appears to be a certificate or single-page document, not a course source.","page_count":len(doc)}
    if text_len < 80:
        # A scanned PDF may have no text. We still return a diagnostic so the UI can tell the admin why it cannot create text lessons.
        return {"status":"needs_ocr","reason":"This PDF appears to be scanned/image-only. OCR is required to turn page images into editable lesson text.","page_count":len(doc)}

    outline=_outline_entries(doc)
    if outline:
        modules, headings=_build_from_outline(doc,records,outline)
        strategy="pdf-outline"
    else:
        toc_pages=_contents_pages(records,doc)
        toc_entries=_parse_text_contents(records,toc_pages)
        if toc_entries:
            modules, headings=_build_from_text_toc(doc,records,toc_entries)
            strategy="pdf-contents"
        else:
            modules, headings=_fallback_modules(doc,records)
            strategy="typography-fallback"

    detected_lesson_count = sum(len(m.get("lessons", [])) for m in modules)
    # Flatten lesson anchors and order by PDF location.
    lesson_items=[]
    for mi,m in enumerate(modules):
        for li,l in enumerate(m.get("lessons",[])):
            anchor=l.get("anchor") or l.get("page_anchor")
            if anchor:
                lesson_items.append((mi,li,anchor))
    lesson_items.sort(key=lambda x:(x[2]["page"], x[2].get("seq") if x[2].get("seq") is not None else x[2].get("line",-1)))

    # Content is page-range based first, with line precision when two lessons share a page.
    for idx,(mi,li,anchor) in enumerate(lesson_items):
        next_anchor=lesson_items[idx+1][2] if idx+1<len(lesson_items) else None
        start_page=anchor["page"]
        # A page-only anchor owns the whole page. If the next anchor is also page-only,
        # stop before its page; if the next anchor is a real heading on that page,
        # include the page and cut at its sequence position.
        if next_anchor:
            end_page = next_anchor["page"] if next_anchor.get("seq") is not None else next_anchor["page"]-1
        else:
            end_page=len(doc)-1
        start_seq=anchor.get("seq")
        end_seq=next_anchor.get("seq") if next_anchor and next_anchor.get("seq") is not None and next_anchor["page"]==end_page else None

        rows=[]
        for r in records:
            if r["page"] < start_page or r["page"] > end_page:
                continue
            if r["page"] == start_page and start_seq is not None and r.get("seq",0) < start_seq:
                continue
            if next_anchor and r["page"] == end_page and end_seq is not None and r.get("seq",0) >= end_seq:
                continue
            rows.append(r)
        content="\n".join(_clean_content_lines(rows)).strip()
        if anchor.get("seq") is not None:
            # Heading line itself should not be repeated as lesson body.
            lines=content.splitlines()
            if lines and norm(lines[0])==norm(anchor.get("text","")):
                content="\n".join(lines[1:]).strip()

        l=modules[mi]["lessons"][li]
        l["content"]=content
        l["content_blocks"]=_content_blocks(content)
        l["source_pages"]=list(range(start_page+1,end_page+2))
        l["source_page_start"]=start_page+1
        l["source_page_end"]=end_page+1
        l["content_source"]="pdf" if content else "toc_only"

    # Remove TOC-only entries when their detailed body is not present in the uploaded PDF.
    # This prevents blank lessons and makes incomplete sample PDFs safe to import.
    for m in modules:
        m["lessons"]=[l for l in m.get("lessons",[]) if l.get("content") or l.get("source_page_start")]

    # Unanchored lessons: preserve them as drafts rather than stealing another chapter's content.
    for m in modules:
        clean_lessons=[]
        for l in m.get("lessons",[]):
            l.pop("anchor",None); l.pop("page_anchor",None)
            l.setdefault("content","")
            l.setdefault("content_blocks",_content_blocks(l.get("content","")))
            l.setdefault("source_pages",[])
            l.setdefault("source_page_start",None)
            l.setdefault("source_page_end",None)
            l.setdefault("content_source","pdf" if l.get("content") else "toc_only")
            clean_lessons.append(l)
        m["lessons"]=clean_lessons

    # Reject obvious non-course documents such as certificates.
    total_lessons=sum(len(m.get("lessons",[])) for m in modules)
    with_content=sum(1 for m in modules for l in m.get("lessons",[]) if len(l.get("content", "").split())>=8)
    if total_lessons<=1 and len(doc)<=2 and text_len<800:
        return {"status":"not_course","reason":"The uploaded PDF does not contain enough structured educational content to create a course.","page_count":len(doc)}

    title=os.path.splitext(os.path.basename(filename))[0].replace("_"," ").replace("-"," ").strip().title()
    # Prefer first strong title on first few pages.
    for r in records[:80]:
        if r["page"]<=2 and r["size"]>=16 and len(r["text"].split())<=14 and norm(r["text"]) not in {"contents","table of contents"}:
            title=r["text"]; break

    missing_topics=max(0, detected_lesson_count - sum(len(m.get("lessons",[])) for m in modules))
    return {
        "status":"ok",
        "title":title,
        "page_count":len(doc),
        "source_topic_count":detected_lesson_count,
        "strategy":strategy,
        "modules":modules,
        "lesson_count":total_lessons,
        "lessons_with_content":with_content,
        "missing_topics":missing_topics,
        "text_length":text_len,
        "has_outline":bool(outline),
        "toc_pages":[p+1 for p in _contents_pages(records,doc)],
    }
