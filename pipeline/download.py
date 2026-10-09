"""Download source files over HTTP with retries and exponential backoff."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable
from pathlib import Path

import requests

from pipeline import config

log = logging.getLogger(__name__)

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
CHUNK_SIZE = 1024 * 1024


class DownloadError(RuntimeError):
    """Raised when a file cannot be downloaded."""


def download_file(
    url: str,
    dest: Path,
    *,
    force: bool = False,
    session: requests.Session | None = None,
    retries: int = 4,
    backoff_seconds: float = 2.0,
    timeout_seconds: float = 60.0,
    sleep: Callable[[float], None] = time.sleep,
) -> Path:
    """Download url to dest, skipping if dest exists unless force is set.

    Data is written to a .part file first and renamed on success, so an
    interrupted download never leaves a truncated file at dest.
    """
    if dest.exists() and not force:
        log.info("Skipping download, file exists: %s", dest.name)
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    http = session or requests.Session()

    for attempt in range(1, retries + 1):
        try:
            with http.get(url, stream=True, timeout=timeout_seconds) as response:
                status = response.status_code
                if status in RETRYABLE_STATUS:
                    raise _RetryableError(f"HTTP {status}")
                if status == 404:
                    raise DownloadError(
                        f"Not found (HTTP 404): {url}. The month may not be published yet."
                    )
                if status != 200:
                    raise DownloadError(f"Unexpected HTTP {status} for {url}")
                with part.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                        handle.write(chunk)
            part.replace(dest)
            log.info("Downloaded %s (%d bytes)", dest.name, dest.stat().st_size)
            return dest
        except (_RetryableError, requests.ConnectionError, requests.Timeout) as exc:
            part.unlink(missing_ok=True)
            if attempt == retries:
                raise DownloadError(f"Giving up on {url} after {retries} attempts: {exc}") from exc
            delay = backoff_seconds * 2 ** (attempt - 1)
            log.warning(
                "Attempt %d/%d for %s failed (%s); retrying in %.1fs",
                attempt,
                retries,
                url,
                exc,
                delay,
            )
            sleep(delay)
        except DownloadError:
            part.unlink(missing_ok=True)
            raise

    raise AssertionError("unreachable")  # pragma: no cover


def download_trips(
    months: Iterable[str], raw_dir: Path, *, force: bool = False, **kwargs
) -> list[Path]:
    """Download one trip file per month into raw_dir."""
    return [
        download_file(
            config.trip_url(month), raw_dir / config.trip_filename(month), force=force, **kwargs
        )
        for month in months
    ]


def download_zones(raw_dir: Path, *, force: bool = False, **kwargs) -> Path:
    return download_file(config.ZONE_URL, raw_dir / config.ZONE_FILENAME, force=force, **kwargs)


class _RetryableError(Exception):
    pass
