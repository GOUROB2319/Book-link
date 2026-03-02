from __future__ import annotations

import copy
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from requests.exceptions import RequestException, SSLError
import urllib3

from extract_books import analyze_url, extract_books_from_file, normalize_url

ROOT = Path(r"c:\Users\GourobSaha\OneDrive - Gourob Saha\Downloads\Book-link")
YEARS = [str(y) for y in range(2017, 2027)]

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def classify_link(url: str | None) -> str:
    if not url:
        return "missing"

    lower = url.lower()
    if "/pages/static-pages/" in lower:
        return "navigation_page"

    if lower.endswith(".pdf") or ".pdf?" in lower:
        return "direct_book"

    if "drive.google.com/file/d/" in lower:
        return "direct_book"

    if "drive.egovcloud.gov.bd" in lower:
        return "direct_book"

    return "other"


def extract_year(year: str) -> dict[str, Any]:
    src_dir = ROOT / year
    files = sorted(src_dir.glob("*.html"))
    all_records: list[dict[str, Any]] = []
    file_summaries: list[dict[str, Any]] = []

    for f in files:
        recs, summary = extract_books_from_file(f)
        all_records.extend(recs)
        file_summaries.append(summary)

    total_links = 0
    missing_link_slots = 0
    hosts: dict[str, int] = {}

    for rec in all_records:
        for link in rec["download_links"]:
            total_links += 1
            if link.get("missing_url"):
                missing_link_slots += 1
            host = link.get("host") or ("invalid" if link.get("invalid_url") else "missing")
            hosts[host] = hosts.get(host, 0) + 1

    out = {
        "metadata": {
            "generated_from": "Local HTML files provided by user",
            "source_directory": year,
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

    out_path = ROOT / f"nctb_{year}_all_books_links.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def clean_dataset(dataset: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    clean = copy.deepcopy(dataset)

    original_links = 0
    cleaned_links = 0
    removed_duplicate_link_entries = 0
    direct_book_links = 0
    navigation_links = 0
    missing_url_details: list[dict[str, Any]] = []
    invalid_url_details: list[dict[str, Any]] = []
    unique_urls: set[str] = set()

    for rec in clean["books"]:
        seen: set[tuple[Any, ...]] = set()
        cleaned_per_rec: list[dict[str, Any]] = []

        for link in rec["download_links"]:
            original_links += 1
            cloned = dict(link)
            raw_url = cloned.get("url")
            url = normalize_url(raw_url) if raw_url else None
            cloned["url"] = url

            host = None
            invalid_url = False
            if url:
                host, invalid_url = analyze_url(url)

            if not url:
                cloned["missing_url"] = True
            if invalid_url:
                cloned["invalid_url"] = True
            if host:
                cloned["host"] = host

            link_type = classify_link(url)
            cloned["link_type"] = link_type

            key = (
                cloned.get("variant"),
                cloned.get("column_index"),
                (cloned.get("label") or "").strip().lower(),
                (url or ""),
            )
            if key in seen:
                removed_duplicate_link_entries += 1
                continue
            seen.add(key)

            cleaned_per_rec.append(cloned)
            cleaned_links += 1

            if link_type == "direct_book":
                direct_book_links += 1
            elif link_type == "navigation_page":
                navigation_links += 1

            if not url:
                missing_url_details.append(
                    {
                        "file": rec["source"]["file_name"],
                        "serial": rec.get("serial"),
                        "book": rec.get("book_name_bn") or rec.get("book_name_en") or rec.get("subject"),
                        "label": cloned.get("label"),
                    }
                )
            elif invalid_url:
                invalid_url_details.append(
                    {
                        "file": rec["source"]["file_name"],
                        "serial": rec.get("serial"),
                        "book": rec.get("book_name_bn") or rec.get("book_name_en") or rec.get("subject"),
                        "url": url,
                    }
                )
            else:
                unique_urls.add(url)

        rec["download_links"] = cleaned_per_rec
        rec["download_link_count"] = len(cleaned_per_rec)

    clean.setdefault("metadata", {})["cleaning"] = {
        "cleaned_on": date.today().isoformat(),
        "original_link_entries": original_links,
        "cleaned_link_entries": cleaned_links,
        "removed_duplicate_link_entries": removed_duplicate_link_entries,
        "direct_book_link_entries": direct_book_links,
        "navigation_page_link_entries": navigation_links,
    }

    audit = {
        "audit_date": date.today().isoformat(),
        "source_json": "",
        "clean_json": "",
        "source_files_count": clean["metadata"].get("total_source_files"),
        "book_records_count": clean["metadata"].get("total_book_records"),
        "original_link_entries": original_links,
        "cleaned_link_entries": cleaned_links,
        "removed_duplicate_link_entries": removed_duplicate_link_entries,
        "direct_book_link_entries": direct_book_links,
        "navigation_page_link_entries": navigation_links,
        "missing_url_entries_unique": len(missing_url_details),
        "missing_url_details": missing_url_details,
        "invalid_url_entries": len(invalid_url_details),
        "invalid_url_details": invalid_url_details,
    }

    return clean, audit, sorted(unique_urls)


def check_one_url(session: requests.Session, url: str) -> dict[str, Any]:
    result = {
        "url": url,
        "ok": False,
        "status_code": None,
        "final_url": None,
        "error": None,
        "tls_bypass_used": False,
    }

    try:
        response = session.get(url, timeout=25, allow_redirects=True)
        result["status_code"] = response.status_code
        result["final_url"] = response.url
        result["ok"] = response.status_code < 400
        return result
    except SSLError as e:
        host = urlparse(url).netloc.lower()
        if host.endswith("nctb.gov.bd"):
            try:
                response = session.get(url, timeout=25, allow_redirects=True, verify=False)
                result["tls_bypass_used"] = True
                result["status_code"] = response.status_code
                result["final_url"] = response.url
                result["ok"] = response.status_code < 400
                return result
            except RequestException as e2:
                result["error"] = str(e2)
                return result
        result["error"] = str(e)
        return result
    except RequestException as e:
        result["error"] = str(e)
        return result


def live_check_urls(urls: list[str], workers: int = 20) -> dict[str, Any]:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (LinkAuditBot/1.0)"})

    details: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(check_one_url, session, url): url for url in urls}
        for future in as_completed(futures):
            details.append(future.result())

    details.sort(key=lambda x: x["url"])
    ok_urls = sum(1 for d in details if d["ok"])
    failed = [d for d in details if not d["ok"]]

    status_breakdown: dict[str, int] = {}
    for d in details:
        code = d["status_code"] if d["status_code"] is not None else "error"
        key = str(code)
        status_breakdown[key] = status_breakdown.get(key, 0) + 1

    tls_bypass_ok = sum(1 for d in details if d["tls_bypass_used"] and d["ok"])

    return {
        "checked_at": date.today().isoformat(),
        "unique_urls_checked": len(urls),
        "ok_urls": ok_urls,
        "failed_urls": len(failed),
        "status_breakdown": status_breakdown,
        "nctb_tls_bypass_success_count": tls_bypass_ok,
        "failed_details": failed,
    }


def run_for_year(year: str) -> dict[str, Any]:
    dataset = extract_year(year)
    clean, audit, urls = clean_dataset(dataset)

    source_json = f"nctb_{year}_all_books_links.json"
    clean_json = f"nctb_{year}_all_books_links_clean.json"
    audit_json = f"nctb_{year}_audit_report.json"
    health_json = f"nctb_{year}_link_health_report.json"

    audit["source_json"] = source_json
    audit["clean_json"] = clean_json

    health = {
        "source_file": source_json,
        "total_urls_in_dataset": sum(
            1
            for rec in clean["books"]
            for link in rec["download_links"]
            if link.get("url")
        ),
    }
    live = live_check_urls(urls)
    health.update(live)

    audit["live_check"] = {
        "unique_urls_checked": live["unique_urls_checked"],
        "ok_urls": live["ok_urls"],
        "failed_urls": live["failed_urls"],
        "status_breakdown": live["status_breakdown"],
        "nctb_tls_bypass_success_count": live["nctb_tls_bypass_success_count"],
    }

    (ROOT / clean_json).write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / audit_json).write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / health_json).write_text(json.dumps(health, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "year": year,
        "files": dataset["metadata"]["total_source_files"],
        "books": dataset["metadata"]["total_book_records"],
        "links": dataset["metadata"]["total_download_link_entries"],
        "missing": dataset["metadata"]["missing_url_entries"],
        "unique_urls": live["unique_urls_checked"],
        "ok": live["ok_urls"],
        "failed": live["failed_urls"],
    }


def main() -> None:
    summary: list[dict[str, Any]] = []
    for year in YEARS:
        src = ROOT / year
        if not src.exists() or not src.is_dir():
            continue
        print(f"[RUN] {year}")
        year_summary = run_for_year(year)
        summary.append(year_summary)
        print(
            f"[DONE] {year} | files={year_summary['files']} books={year_summary['books']} "
            f"links={year_summary['links']} unique_urls={year_summary['unique_urls']} "
            f"ok={year_summary['ok']} failed={year_summary['failed']}"
        )

    output = {
        "generated_at": date.today().isoformat(),
        "years": summary,
        "totals": {
            "files": sum(x["files"] for x in summary),
            "books": sum(x["books"] for x in summary),
            "links": sum(x["links"] for x in summary),
            "missing": sum(x["missing"] for x in summary),
            "unique_urls": sum(x["unique_urls"] for x in summary),
            "ok": sum(x["ok"] for x in summary),
            "failed": sum(x["failed"] for x in summary),
        },
    }

    (ROOT / "nctb_rebuild_summary_2017_2026.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("[SUMMARY]", json.dumps(output["totals"], ensure_ascii=False))


if __name__ == "__main__":
    main()
