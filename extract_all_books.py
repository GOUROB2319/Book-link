from pathlib import Path
import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
OUT_JSON = ROOT / "nctb_all_books_links_structured.json"
REPORT_JSON = ROOT / "nctb_all_books_extraction_report.json"
BASE_URL = "https://nctb.gov.bd"


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
    text = text.replace(" ,", ",").replace(" .", ".")
    return text


def is_serial_text(text: str) -> bool:
    t = clean_text(text)
    if not t:
        return False
    return bool(re.fullmatch(r"[0-9০-৯]+[\.।:]?", t))


def abs_url(href: str) -> str:
    href = (href or "").strip()
    if not href:
        return ""
    return urljoin(BASE_URL, href)


def classify_link_source(url: str) -> str:
    host = (urlparse(url).netloc or "").lower()
    if "drive.google.com" in host:
        return "google_drive"
    if "nctb.gov.bd" in host:
        return "nctb"
    if host:
        return host
    return "unknown"


def is_probable_download(url: str) -> bool:
    u = url.lower()
    if any(k in u for k in ["drive.google.com", ".pdf", "download", "/pages/files/"]):
        return True
    return False


def parse_page_meta(page_title: str, source_name: str):
    text = clean_text(f"{page_title} {source_name}")

    year = None
    m = re.search(r"(20[0-9]{2}|২০১[0-9]|২০২[0-9])", text)
    if m:
        year = m.group(1)

    level = None
    level_keys = [
        "প্রাক-প্রাথমিক",
        "প্রাক প্রাথমিক",
        "প্রাথমিক",
        "মাধ্যমিক",
        "উচ্চ মাধ্যমিক",
        "দাখিল",
        "ইবতেদায়ি",
        "ইবতেদায়ি",
        "কারিগরি",
        "ভোকেশনাল",
        "এসএসসি",
        "ক্ষুদ্র নৃ",
    ]
    for k in level_keys:
        if k in text:
            level = k
            break

    class_name = None
    class_pattern = (
        r"([০-৯0-9]+(?:ম|য়|য়|ষ্ঠ|র্থ)?\s*শ্রেণি(?:র)?"
        r"|নবম\s*[ও\-]\s*দশম\s*শ্রেণি"
        r"|একাদশ[\-–]?দ্বাদশ\s*শ্রেণি)"
    )
    class_match = re.search(class_pattern, text)
    if class_match:
        class_name = clean_text(class_match.group(1))

    page_version_hint = None
    if "ইংরেজি" in text or "English" in text:
        page_version_hint = "english"
    elif "বাংলা" in text:
        page_version_hint = "bangla"

    return {
        "year_hint": year,
        "level_hint": level,
        "class_hint": class_name,
        "page_version_hint": page_version_hint,
    }


def extract_table_rows(table):
    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        parsed_cells = []
        for c in cells:
            ctext = clean_text(c.get_text(" ", strip=True))
            anchors = []
            for a in c.find_all("a"):
                href = clean_text(a.get("href", ""))
                if not href:
                    continue
                anchors.append(
                    {
                        "href": abs_url(href),
                        "anchor_text": clean_text(a.get_text(" ", strip=True)),
                    }
                )
            parsed_cells.append({"text": ctext, "anchors": anchors})
        rows.append(parsed_cells)
    return rows


def likely_header_row(cells):
    texts = [c["text"] for c in cells]
    joined = " | ".join(texts)
    header_keys = ["ক্রমিক", "পাঠ্যপুস্তক", "নাম", "ভার্সন", "পিডিএফ", "pdf", "ডাউনলোড"]
    return any(k.lower() in joined.lower() for k in header_keys)


def pick_book_name(cells, col_headers):
    for idx, header in enumerate(col_headers):
        h = header.lower()
        if any(k in h for k in ["পাঠ্যপুস্তক", "নাম", "subject", "book"]):
            if idx < len(cells):
                t = clean_text(cells[idx]["text"])
                if t and not is_serial_text(t):
                    return t

    for c in cells:
        t = clean_text(c["text"])
        if not t:
            continue
        if is_serial_text(t):
            continue
        if t in {"বাংলা ভার্সন", "ইংরেজি ভার্সন", "পিডিএফ ফাইল", "PDF"}:
            continue
        return t
    return ""


def language_from_header(header_text: str, cell_text: str) -> str:
    h = (header_text or "") + " " + (cell_text or "")
    h_lower = h.lower()
    if "বাংলা" in h:
        return "bangla"
    if "ইংরেজি" in h or "english" in h_lower:
        return "english"
    return "unknown"


def main():
    all_records = []
    source_stats = {
        "total_html_files": 0,
        "files_with_widget": 0,
        "files_with_extracted_rows": 0,
        "files_with_download_links": 0,
        "rows_total": 0,
        "rows_with_links": 0,
    }

    html_files = sorted(ROOT.rglob("*.html"))
    source_stats["total_html_files"] = len(html_files)

    for path in html_files:
        rel_path = str(path.relative_to(ROOT)).replace("\\", "/")
        parent_year = path.parent.name if path.parent.name.isdigit() else None

        try:
            raw = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        soup = BeautifulSoup(raw, "html.parser")
        widget = soup.select_one("div.title-with-image-content-widget")
        if not widget:
            continue
        source_stats["files_with_widget"] += 1

        h2 = widget.find("h2")
        page_title = clean_text(h2.get_text(" ", strip=True)) if h2 else clean_text(path.stem)
        canonical = ""
        canon_tag = soup.find("link", rel="canonical")
        if canon_tag:
            canonical = clean_text(canon_tag.get("href", ""))

        meta = parse_page_meta(page_title, path.name)
        page_rows_extracted = 0
        page_has_download = False

        for t_index, table in enumerate(widget.find_all("table"), start=1):
            rows = extract_table_rows(table)
            if len(rows) <= 1:
                continue

            if rows and likely_header_row(rows[0]):
                headers = [clean_text(c["text"]) for c in rows[0]]
                data_rows = rows[1:]
            else:
                headers = [f"col_{i + 1}" for i in range(max(len(r) for r in rows))]
                data_rows = rows

            for r_index, cells in enumerate(data_rows, start=1):
                row_text = clean_text(" | ".join(c["text"] for c in cells if c["text"]))
                if not row_text and not any(c["anchors"] for c in cells):
                    continue

                book_name = pick_book_name(cells, headers)
                if not book_name:
                    continue

                links = []
                serial_value = clean_text(cells[0]["text"]) if cells and is_serial_text(cells[0]["text"]) else ""

                for i, c in enumerate(cells):
                    header = headers[i] if i < len(headers) else f"col_{i + 1}"
                    cell_text = c["text"]
                    for a in c["anchors"]:
                        url = a["href"]
                        probable = is_probable_download(url)
                        links.append(
                            {
                                "url": url,
                                "source": classify_link_source(url),
                                "column_header": clean_text(header),
                                "language_version": language_from_header(header, cell_text),
                                "anchor_text": clean_text(a["anchor_text"]),
                                "is_probable_download": probable,
                            }
                        )
                        if probable:
                            page_has_download = True

                keep = bool(links)
                if not keep and headers and any(k in " ".join(headers) for k in ["পাঠ্যপুস্তক", "নাম", "ভার্সন", "পিডিএফ"]):
                    keep = True
                if not keep:
                    continue

                all_records.append(
                    {
                        "source_file": rel_path,
                        "source_canonical_url": canonical,
                        "source_page_title": page_title,
                        "source_table_index": t_index,
                        "source_row_index": r_index,
                        "year": parent_year,
                        "year_hint": meta["year_hint"],
                        "level": meta["level_hint"],
                        "class": meta["class_hint"],
                        "book_name": book_name,
                        "subject": book_name,
                        "page_version_hint": meta["page_version_hint"],
                        "serial": serial_value,
                        "download_links": links,
                        "other_info": {
                            "table_headers": headers,
                            "row_text": row_text,
                        },
                    }
                )
                source_stats["rows_total"] += 1
                if links:
                    source_stats["rows_with_links"] += 1
                page_rows_extracted += 1

        if page_rows_extracted:
            source_stats["files_with_extracted_rows"] += 1

    files_with_dl = {
        r["source_file"]
        for r in all_records
        if any(l.get("is_probable_download") for l in r["download_links"])
    }
    source_stats["files_with_download_links"] = len(files_with_dl)

    unique_links = set()
    for r in all_records:
        for l in r["download_links"]:
            if l.get("url"):
                unique_links.add(l["url"])

    output = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": str(ROOT),
        "summary": {
            **source_stats,
            "total_records": len(all_records),
            "total_unique_links": len(unique_links),
        },
        "records": all_records,
    }

    report = {
        "generated_at_utc": output["generated_at_utc"],
        "summary": output["summary"],
        "sample_first_5_records": all_records[:5],
        "notes": [
            "Rows are extracted from content tables inside title-with-image-content-widget.",
            "Non-content navigation menu links are ignored.",
            "Rows without direct links are preserved when they are part of textbook tables.",
        ],
    }

    OUT_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote: {OUT_JSON.name}")
    print(f"Wrote: {REPORT_JSON.name}")
    print(json.dumps(output["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
