from __future__ import annotations

import csv
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
LOG_DIR = DATA_DIR / "logs"
MANIFEST_DIR = DATA_DIR / "manifests"
CONFIG_FILE = ROOT / "config" / "sources.yaml"

DEFAULT_SOURCES: dict[str, Any] = {
    "spc_tornado": {
        "tornado_csv_url": "https://www.spc.noaa.gov/wcm/data/1950-2023_actual_tornadoes.csv",
        "metadata_page": "https://www.spc.noaa.gov/wcm/",
    },
    "ncei_storm_events": {
        "index_url": "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/",
        "file_pattern": "StormEvents_details-ftp_v1.0_d",
        "year_start": 1963,
        "year_end": 2023,
    },
    "omni": {
        "base_url": "https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni/",
        "files": ["omni2_all_years.dat"],
        "expected_start_year": 1963,
        "expected_end_year": 2023,
    },
    "icme": {
        "richardson_cane_html": "https://izw1.caltech.edu/ACE/ASC/DATA/level3/icmetable2.htm",
        "richardson_cane_txt": "https://izw1.caltech.edu/ACE/ASC/DATA/level3/icmetable2.txt",
    },
    "hcs": {
        "candidate_urls": [
            "http://wso.stanford.edu/SB/SB.html",
            "http://wso.stanford.edu/Tilts.html",
        ]
    },
    "green_corona": {
        "candidate_urls": [
            "https://www.ngdc.noaa.gov/stp/solar/green.html",
            "https://www.swpc.noaa.gov/products/solar-cycle-progression",
        ]
    },
    "era5": {
        "cds_api_docs": "https://cds.climate.copernicus.eu/api-how-to",
        "dataset": "reanalysis-era5-single-levels",
        "years": [2021, 2022, 2023],
    },
    "spc_outlooks": {
        "archive_urls": [
            "https://www.spc.noaa.gov/products/outlook/archive/",
            "https://www.spc.noaa.gov/products/outlook/archive/2021/",
        ]
    },
}


@dataclass(slots=True)
class DownloadResult:
    url: str
    path: Path
    ok: bool
    status_code: int | None
    error: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    row_count: int | None = None


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()


def make_logger(name: str) -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = logging.FileHandler(LOG_DIR / f"{name}.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def make_session() -> dict[str, str]:
    return {"User-Agent": "reanalysis-data-acquisition/1.0"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)
        return sum(1 for _ in reader)


def download_binary(
    session: dict[str, str],
    url: str,
    out_path: Path,
    logger: logging.Logger,
    timeout: int = 120,
    retries: int = 5,
) -> DownloadResult:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading %s -> %s", url, out_path)
    last_error: str | None = None
    for attempt in range(1, retries + 1):
        try:
            req = Request(url, headers=session)
            with urlopen(req, timeout=timeout) as response:  # noqa: S310
                status_code = getattr(response, "status", 200)
                if status_code != 200:
                    return DownloadResult(
                        url=url,
                        path=out_path,
                        ok=False,
                        status_code=status_code,
                        error=f"HTTP {status_code}",
                    )
                out_path.write_bytes(response.read())
                digest = sha256_file(out_path)
                return DownloadResult(
                    url=url,
                    path=out_path,
                    ok=True,
                    status_code=status_code,
                    sha256=digest,
                    size_bytes=out_path.stat().st_size,
                )
        except HTTPError as exc:
            status = exc.code
            if status in {429, 500, 502, 503, 504} and attempt < retries:
                last_error = f"HTTP {status}"
                time.sleep(min(2**attempt, 10))
                continue
            return DownloadResult(
                url=url,
                path=out_path,
                ok=False,
                status_code=status,
                error=f"HTTP {status}",
            )
        except URLError as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(min(2**attempt, 10))
                continue
            break
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            if attempt < retries:
                time.sleep(min(2**attempt, 10))
                continue
            break

    logger.error("Download failed for %s after %s attempts: %s", url, retries, last_error)
    return DownloadResult(
        url=url,
        path=out_path,
        ok=False,
        status_code=None,
        error=last_error,
    )


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped:
            self.parts.append(stripped)


def html_to_text(html: str) -> str:
    parser = TextExtractor()
    parser.feed(html)
    return "\n".join(parser.parts)


def extract_links(html: str) -> list[str]:
    return re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)


def fetch_html_and_parse(
    session: dict[str, str],
    url: str,
    html_path: Path,
    parsed_text_path: Path,
    logger: logging.Logger,
    timeout: int = 120,
) -> DownloadResult:
    result = download_binary(session, url, html_path, logger, timeout=timeout)
    if not result.ok:
        return result

    html_text = html_path.read_text(encoding="utf-8", errors="ignore")
    parsed_text_path.parent.mkdir(parents=True, exist_ok=True)
    parsed_text_path.write_text(html_to_text(html_text), encoding="utf-8")
    return result


def write_manifest(name: str, payload: dict[str, Any]) -> Path:
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    path = MANIFEST_DIR / f"{name}.json"
    payload = {"generated_at": utc_now(), **payload}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def result_to_dict(result: DownloadResult) -> dict[str, Any]:
    return {
        "url": result.url,
        "path": str(result.path.relative_to(ROOT)),
        "ok": result.ok,
        "status_code": result.status_code,
        "error": result.error,
        "sha256": result.sha256,
        "size_bytes": result.size_bytes,
        "row_count": result.row_count,
    }


def sleep_briefly(seconds: float = 0.25) -> None:
    time.sleep(seconds)


def load_sources() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return DEFAULT_SOURCES
    text = CONFIG_FILE.read_text(encoding="utf-8")
    try:
        import yaml

        parsed = yaml.safe_load(text)
        return parsed if isinstance(parsed, dict) else DEFAULT_SOURCES
    except Exception:  # noqa: BLE001
        return DEFAULT_SOURCES


def validate_year_range(years: Iterable[int], expected_start: int, expected_end: int) -> tuple[bool, str]:
    years_list = sorted(set(years))
    if not years_list:
        return False, "No years found"
    actual_start = years_list[0]
    actual_end = years_list[-1]
    if actual_start > expected_start or actual_end < expected_end:
        return (
            False,
            f"Observed range {actual_start}-{actual_end}, expected coverage {expected_start}-{expected_end}",
        )
    return True, f"Observed range {actual_start}-{actual_end}"
