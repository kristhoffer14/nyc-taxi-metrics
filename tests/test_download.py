import pytest
import requests

from pipeline import download


class FakeResponse:
    def __init__(self, status_code, body=b""):
        self.status_code = status_code
        self._body = body

    def iter_content(self, chunk_size):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i : i + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeSession:
    """Returns (or raises) the queued outcomes in order, one per get() call."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def get(self, url, stream, timeout):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_success_writes_file(tmp_path):
    dest = tmp_path / "f.parquet"
    session = FakeSession([FakeResponse(200, b"data")])
    download.download_file("http://x", dest, session=session, sleep=lambda s: None)
    assert dest.read_bytes() == b"data"
    assert not (tmp_path / "f.parquet.part").exists()


def test_existing_file_is_skipped_unless_forced(tmp_path):
    dest = tmp_path / "f.parquet"
    dest.write_bytes(b"old")
    session = FakeSession([FakeResponse(200, b"new")])
    download.download_file("http://x", dest, session=session)
    assert session.calls == 0
    download.download_file("http://x", dest, session=session, force=True)
    assert dest.read_bytes() == b"new"


def test_retries_with_exponential_backoff(tmp_path):
    delays = []
    session = FakeSession(
        [
            FakeResponse(503),
            requests.ConnectionError("reset"),
            FakeResponse(200, b"ok"),
        ]
    )
    download.download_file(
        "http://x", tmp_path / "f", session=session, backoff_seconds=1.0, sleep=delays.append
    )
    assert session.calls == 3
    assert delays == [1.0, 2.0]


def test_gives_up_after_max_retries(tmp_path):
    session = FakeSession([FakeResponse(500)] * 3)
    with pytest.raises(download.DownloadError, match="after 3 attempts"):
        download.download_file(
            "http://x", tmp_path / "f", session=session, retries=3, sleep=lambda s: None
        )
    assert not (tmp_path / "f").exists()


def test_404_fails_fast_with_clear_message(tmp_path):
    session = FakeSession([FakeResponse(404)])
    with pytest.raises(download.DownloadError, match="may not be published yet"):
        download.download_file("http://x", tmp_path / "f", session=session)
    assert session.calls == 1
