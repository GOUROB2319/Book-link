from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup

ROOT = Path(r"c:\Users\GourobSaha\OneDrive - Gourob Saha\Downloads\Book-link")

BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
BASE_URL = "https://nctb.gov.bd"


def norm_space(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def bn_to_en_digits(text: str) -> str:
    return text.translate(BN_DIGITS)


def extract_year_label(filename: str) -> str:
    m = re.search(r"([০-৯]{4}(?:-[০-৯]{2})?)", filename)
    return bn_to_en_digits(m.group(1)) if m else "unknown"


def infer_stream(filename: str) -> str:
    keys = [
        ("উচ্চ মাধ্যমিক", "উচ্চ মাধ্যমিক"),
        ("মাধ্যমিক", "মাধ্যমিক"),
        ("প্রাথমিক", "প্রাথমিক"),
        ("দাখিল", "দাখিল"),
        ("কারিগরি", "কারিগরি"),
        ("ইবতেদায়ি", "ইবতেদায়ি"),
        ("ক্ষুদ্র নৃ-গোষ্ঠী", "ক্ষুদ্র নৃ-গোষ্ঠী"),
        ("ক্ষুদ্র নৃগোষ্ঠি", "ক্ষুদ্র নৃ-গোষ্ঠী"),
        ("ক্ষুদ্র নৃগোষ্ঠির", "ক্ষুদ্র নৃ-গোষ্ঠী"),
        ("প্রাক-প্রাথমিক", "প্রাক-প্রাথমিক"),
        ("প্রাক প্রাথমিক", "প্রাক-প্রাথমিক"),
    ]
    for key, normalized in keys:
        if key in filename:
            return normalized
    return "unknown"


def infer_class(filename: str, title: str) -> str:
    source = f"{filename} {title}"
    patterns = [
        r"(প্রাক-প্রাথমিক)\s+স্তর",
        r"(প্রাক প্রাথমিক)\s+স্তর",
        r"(প্রথম|দ্বিতীয়|তৃতীয়|চতুর্থ|পঞ্চম|ষষ্ঠ|সপ্তম|অষ্টম|নবম-দশম|একাদশ-দ্বাদশ)\s+শ্রেণির",
        r"([০-৯]+(?:ম|য়|ষ্ঠ|র্থ|তম))\s+শ্রেণির",
        r"(নবম-দশম)\s+শ্রেণির",
        r"(একাদশ-দ্বাদশ)\s+শ্রেণির",
    ]
    for p in patterns:
        m = re.search(p, source)
        if m:
            return bn_to_en_digits(m.group(1))
    return "unknown"


def infer_version(text: str) -> str | None:
    t = norm_space(text)
    m = re.search(r"\(([^)]*(?:ভার্সন|version|সংস্করণ|edition)[^)]*)\)", t, flags=re.I)
    if m:
        return norm_space(m.group(1))
    m2 = re.search(r"((?:ইংলিশ|বাংলা)\s+ভার্সন)", t, flags=re.I)
    if m2:
        return norm_space(m2.group(1))
    m3 = re.search(r"((?:\d+(?:st|nd|rd|th)?\s+)?edition)", t, flags=re.I)
    if m3:
        return norm_space(m3.group(1))
    return None


def classify_language(name_bn: str, name_en: str, fallback: str) -> list[str]:
    langs: list[str] = []
    if name_bn:
        langs.append("bangla")
    if name_en:
        langs.append("english")
    f = fallback.lower()
    if not langs:
        if "english" in f or "ইংলিশ" in fallback:
            langs.append("english")
        elif "বাংলা" in fallback:
            langs.append("bangla")
        else:
            langs.append("unknown")
    return langs


def pick_header_indices(headers: list[str]) -> dict[str, int | list[int]]:
    result: dict[str, int | list[int]] = {
        "serial": -1,
        "name_bn": -1,
        "name_en": -1,
        "name_generic": -1,
        "subject": -1,
        "download_cols": [],
    }
    for i, h in enumerate(headers):
        hs = h.lower()
        if result["serial"] == -1 and ("ক্রমিক" in h or hs in {"sl", "serial"}):
            result["serial"] = i
        if "ডাউনলোড" in h or "download" in hs:
            result["download_cols"].append(i)
        if "বাংলা" in h and ("বিষ" in h or "নাম" in h or "subject" in hs):
            result["name_bn"] = i
        if "ইংরেজি" in h and ("বিষ" in h or "নাম" in h or "subject" in hs):
            result["name_en"] = i
        if result["name_generic"] == -1 and ("পাঠ্যপুস্তক" in h or "বই" in h or "বিষ" in h or "name" in hs):
            if "বাংলা" not in h and "ইংরেজি" not in h:
                result["name_generic"] = i
        if result["subject"] == -1 and ("বিষ" in h or "subject" in hs):
            result["subject"] = i
    return result


def parse_serial(text: str) -> int | None:
    t = bn_to_en_digits(norm_space(text))
    m = re.search(r"\d+", t)
    return int(m.group()) if m else None


def normalize_url(url: str) -> str:
    u = norm_space(url)
    if not u:
        return u
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return BASE_URL + u
    if u.startswith("www."):
        return "https://" + u
    return u


def analyze_url(url: str) -> tuple[str | None, bool]:
    parsed = urlparse(normalize_url(url))
    if parsed.scheme in {"http", "https"} and parsed.netloc and "." in parsed.netloc:
        return parsed.netloc, False
    return None, True


def extract_books_from_file(path: Path) -> tuple[list[dict], dict]:
    html = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")

    h2 = soup.find("h2")
    page_title = norm_space(h2.get_text(" ", strip=True)) if h2 else path.stem
    year_label = extract_year_label(path.name)
    stream = infer_stream(path.name)
    class_name = infer_class(path.name, page_title)

    update_text = ""
    upd = soup.find(string=re.compile("কনটেন্টটি শেষ হাল-নাগাদ"))
    if upd:
        update_text = norm_space(upd)

    tables = soup.find_all("table")
    records: list[dict] = []
    table_count_used = 0

    for t_index, table in enumerate(tables, start=1):
        table_text = norm_space(table.get_text(" ", strip=True))
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        if "ডাউনলোড" not in table_text and not table.find("a"):
            continue

        header_cells = rows[0].find_all(["th", "td"])
        headers = [norm_space(c.get_text(" ", strip=True)) for c in header_cells]
        has_header = any(
            key in " ".join(headers)
            for key in ["ক্রমিক", "পাঠ্যপুস্তক", "বিষয়", "বিষয়", "ডাউনলোড", "name", "subject", "serial"]
        )
        header_idx = pick_header_indices(headers if has_header else [])
        data_rows = rows[1:] if has_header else rows

        used_this_table = False
        for r_index, row in enumerate(data_rows, start=1):
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            cell_objs = []
            row_has_any_link_marker = False
            for c_idx, cell in enumerate(cells):
                text = norm_space(cell.get_text(" ", strip=True))
                anchors = cell.find_all("a")
                links = []
                for a in anchors:
                    href = normalize_url(a.get("href", ""))
                    ltxt = norm_space(a.get_text(" ", strip=True))
                    if href:
                        links.append({"url": href, "link_text": ltxt})
                if links:
                    row_has_any_link_marker = True
                elif "ডাউনলোড" in text or "download" in text.lower():
                    row_has_any_link_marker = True
                cell_objs.append({"index": c_idx, "text": text, "links": links, "element": cell})

            if not any(c["text"] or c["links"] for c in cell_objs):
                continue

            if not row_has_any_link_marker:
                continue

            used_this_table = True

            def cell_text_at(i: int) -> str:
                if i < 0 or i >= len(cell_objs):
                    return ""
                return cell_objs[i]["text"]

            name_bn = cell_text_at(header_idx["name_bn"]) if isinstance(header_idx["name_bn"], int) else ""
            name_en = cell_text_at(header_idx["name_en"]) if isinstance(header_idx["name_en"], int) else ""
            generic_name = cell_text_at(header_idx["name_generic"]) if isinstance(header_idx["name_generic"], int) else ""

            if not name_bn and not name_en:
                if "(ইংলিশ ভার্সন" in generic_name or "english" in generic_name.lower():
                    name_en = generic_name
                else:
                    name_bn = generic_name

            if not generic_name:
                generic_name = name_bn or name_en

            subject = cell_text_at(header_idx["subject"]) if isinstance(header_idx["subject"], int) else ""
            if not subject:
                subject = generic_name

            serial = None
            if isinstance(header_idx["serial"], int) and header_idx["serial"] >= 0:
                serial = parse_serial(cell_text_at(header_idx["serial"]))
            if serial is None and cell_objs:
                serial = parse_serial(cell_objs[0]["text"])

            version_guess = infer_version(" | ".join([name_bn, name_en, generic_name]))
            langs = classify_language(name_bn, name_en, generic_name)

            download_links = []
            for c in cell_objs:
                hdr = headers[c["index"]] if has_header and c["index"] < len(headers) else ""
                variant = "unknown"
                if "বাংলা" in hdr:
                    variant = "bangla"
                elif "ইংরেজি" in hdr:
                    variant = "english"
                elif "english" in hdr.lower():
                    variant = "english"
                elif "bangla" in hdr.lower():
                    variant = "bangla"

                if c["links"]:
                    for li in c["links"]:
                        host, invalid_url = analyze_url(li["url"])
                        download_links.append(
                            {
                                "variant": variant,
                                "column_header": hdr,
                                "column_index": c["index"],
                                "label": li["link_text"],
                                "url": li["url"],
                                "host": host,
                                "invalid_url": invalid_url,
                            }
                        )
                elif "ডাউনলোড" in c["text"] or "download" in c["text"].lower():
                    # Preserve each declared download slot even when href is absent.
                    raw_labels = [
                        norm_space(x.get_text(" ", strip=True))
                        for x in c["element"].find_all(["p", "div", "span"])
                        if ("ডাউনলোড" in norm_space(x.get_text(" ", strip=True)) or "download" in norm_space(x.get_text(" ", strip=True)).lower())
                    ]
                    labels = [x for x in raw_labels if x]
                    if not labels:
                        labels = [c["text"]]
                    for lbl in labels:
                        download_links.append(
                            {
                                "variant": variant,
                                "column_header": hdr,
                                "column_index": c["index"],
                                "label": lbl,
                                "url": None,
                                "host": None,
                                "missing_url": True,
                            }
                        )

            if not download_links:
                continue

            rec = {
                "source": {
                    "file_name": path.name,
                    "file_path": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "page_title": page_title,
                    "content_last_updated": update_text or None,
                    "table_index": t_index,
                    "row_index": r_index,
                },
                "curriculum_year_label": year_label,
                "education_stream": stream,
                "class": class_name,
                "serial": serial,
                "book_name_bn": name_bn or None,
                "book_name_en": name_en or None,
                "subject": subject or None,
                "version_or_edition": version_guess,
                "language_versions": langs,
                "download_links": download_links,
                "download_link_count": len(download_links),
                "additional_info": {
                    "table_headers": headers if has_header else None,
                    "raw_cells": [c["text"] for c in cell_objs],
                },
            }
            records.append(rec)

        if used_this_table:
            table_count_used += 1

    file_summary = {
        "file_name": path.name,
        "page_title": page_title,
        "curriculum_year_label": year_label,
        "education_stream": stream,
        "class": class_name,
        "tables_found": len(tables),
        "tables_used": table_count_used,
        "records_found": len([r for r in records if r["source"]["file_name"] == path.name]),
    }
    return records, file_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract all NCTB book rows and download links from local HTML files.")
    parser.add_argument("--folder", default="2026", help="Source folder under project root (e.g. 2025 or 2026).")
    parser.add_argument("--out", default=None, help="Optional output JSON file path.")
    args = parser.parse_args()

    src_dir = ROOT / args.folder
    if not src_dir.exists() or not src_dir.is_dir():
        raise FileNotFoundError(f"Source folder not found: {src_dir}")

    out_file = Path(args.out) if args.out else ROOT / f"nctb_{args.folder}_all_books_links.json"

    files = sorted(src_dir.glob("*.html"))
    all_records: list[dict] = []
    file_summaries: list[dict] = []

    for f in files:
        recs, summary = extract_books_from_file(f)
        all_records.extend(recs)
        file_summaries.append(summary)

    total_links = 0
    missing_link_slots = 0
    hosts: dict[str, int] = {}
    for r in all_records:
        for li in r["download_links"]:
            total_links += 1
            if li.get("missing_url"):
                missing_link_slots += 1
            host = li.get("host") or ("invalid" if li.get("invalid_url") else "missing")
            hosts[host] = hosts.get(host, 0) + 1

    out = {
        "metadata": {
            "generated_from": "Local HTML files provided by user",
            "source_directory": str(src_dir.relative_to(ROOT)).replace("\\", "/"),
            "generated_at": date.today().isoformat(),
            "total_source_files": len(files),
            "total_book_records": len(all_records),
            "total_download_link_entries": total_links,
            "missing_url_entries": missing_link_slots,
            "link_hosts_breakdown": hosts,
        },
        "source_files": file_summaries,
        "books": all_records,
    }

    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Written: {out_file}")
    print(f"Files: {len(files)} | Records: {len(all_records)} | Links: {total_links} | Missing URLs: {missing_link_slots}")


if __name__ == "__main__":
    main()
