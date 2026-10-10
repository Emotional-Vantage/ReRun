import os
import io
import pytest
import pymupdf

from tools.ingest import (
    validate_repo_url,
    check_symlinks,
    ingest_custom_repo,
    RepoIngestError
)
from tools.paper import validate_pdf_bytes, PDFValidationError

try:
    from backend.app.main import app
    from fastapi.testclient import TestClient
    HAS_APP = bool(getattr(app, "routes", None))
except (ImportError, AttributeError):
    app = None
    TestClient = None
    HAS_APP = False

def make_valid_pdf_bytes(text: str = "This is a valid research paper PDF with sufficient extractable text for testing purposes. We achieved a test accuracy of 0.956.") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    return doc.tobytes()

def make_scanned_pdf_bytes() -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    return doc.tobytes()

# ----------------- UNIT VALIDATION TESTS -----------------

def test_url_validation_rejects_non_github():
    with pytest.raises(RepoIngestError, match="Invalid repository URL"):
        validate_repo_url("https://gitlab.com/user/project")

def test_url_validation_rejects_file_scheme():
    with pytest.raises(RepoIngestError, match="file:// URLs are strictly prohibited"):
        validate_repo_url("file:///etc/passwd")

def test_url_validation_rejects_credentials():
    with pytest.raises(RepoIngestError, match="user credentials"):
        validate_repo_url("https://user:pass@github.com/org/repo")

def test_url_validation_rejects_ssh():
    with pytest.raises(RepoIngestError, match="SSH repository URLs are not supported"):
        validate_repo_url("git@github.com:org/repo.git")

def test_url_validation_accepts_valid_github():
    validate_repo_url("https://github.com/Kumar-Suryanshu/Black-bot")
    validate_repo_url("https://github.com/org-name/repo_name.git")

def test_pdf_validation_rejects_non_pdf_magic():
    with pytest.raises(PDFValidationError, match="missing '%PDF-' header"):
        validate_pdf_bytes(b"NOT A REAL PDF FILE")

def test_pdf_validation_rejects_oversized(monkeypatch):
    huge_bytes = b"%PDF-" + b"0" * (26 * 1024 * 1024)
    with pytest.raises(PDFValidationError, match="exceeds size limit of 25 MB"):
        validate_pdf_bytes(huge_bytes)

def test_pdf_validation_rejects_scanned_without_text():
    scanned_bytes = make_scanned_pdf_bytes()
    with pytest.raises(PDFValidationError, match="contains no extractable text"):
        validate_pdf_bytes(scanned_bytes)

def test_pdf_validation_rejects_over_60_pages():
    doc = pymupdf.open()
    for _ in range(65):
        p = doc.new_page()
        p.insert_text((50, 50), "Sample text content page")
    over_pages = doc.tobytes()
    with pytest.raises(PDFValidationError, match="exceeds maximum page limit of 60 pages"):
        validate_pdf_bytes(over_pages)

def test_pdf_validation_accepts_valid_pdf():
    valid_bytes = make_valid_pdf_bytes()
    info = validate_pdf_bytes(valid_bytes)
    assert "sha256" in info
    assert info["page_count"] == 1
    assert info["text_length"] > 20

def test_symlink_escaping_rejected(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    secret_file = outside_dir / "secret.txt"
    secret_file.write_text("secret_data")

    escaped_symlink = repo_dir / "leak.txt"
    escaped_symlink.symlink_to(secret_file)

    with pytest.raises(RepoIngestError, match="Escaping symlink detected"):
        check_symlinks(repo_dir)

# ----------------- API INTEGRATION NEGATIVE TESTS -----------------

@pytest.mark.skipif(not HAS_APP, reason="FastAPI app with routes is implemented in Stage 7")
def test_api_rejects_when_custom_repos_disabled(monkeypatch):
    monkeypatch.setenv("ALLOW_CUSTOM_REPOS", "0")
    client = TestClient(app)
    valid_pdf = make_valid_pdf_bytes()
    resp = client.post(
        "/api/projects",
        data={"repo_url": "https://github.com/foo/bar"},
        files={"paper": ("paper.pdf", valid_pdf, "application/pdf")}
    )
    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"].lower()

@pytest.mark.skipif(not HAS_APP, reason="FastAPI app with routes is implemented in Stage 7")
def test_api_negative_non_github_url():
    client = TestClient(app)
    valid_pdf = make_valid_pdf_bytes()
    resp = client.post(
        "/api/projects",
        data={"repo_url": "https://gitlab.com/foo/bar"},
        files={"paper": ("paper.pdf", valid_pdf, "application/pdf")}
    )
    assert resp.status_code == 400
    assert "Invalid repository URL" in resp.json()["detail"]

@pytest.mark.skipif(not HAS_APP, reason="FastAPI app with routes is implemented in Stage 7")
def test_api_negative_file_url():
    client = TestClient(app)
    valid_pdf = make_valid_pdf_bytes()
    resp = client.post(
        "/api/projects",
        data={"repo_url": "file:///etc/passwd"},
        files={"paper": ("paper.pdf", valid_pdf, "application/pdf")}
    )
    assert resp.status_code == 400
    assert "file://" in resp.json()["detail"]

@pytest.mark.skipif(not HAS_APP, reason="FastAPI app with routes is implemented in Stage 7")
def test_api_negative_credentials_in_url():
    client = TestClient(app)
    valid_pdf = make_valid_pdf_bytes()
    resp = client.post(
        "/api/projects",
        data={"repo_url": "https://user:token@github.com/foo/bar"},
        files={"paper": ("paper.pdf", valid_pdf, "application/pdf")}
    )
    assert resp.status_code == 400
    assert "credentials" in resp.json()["detail"]

@pytest.mark.skipif(not HAS_APP, reason="FastAPI app with routes is implemented in Stage 7")
def test_api_negative_scanned_pdf():
    client = TestClient(app)
    scanned_pdf = make_scanned_pdf_bytes()
    resp = client.post(
        "/api/projects",
        data={"repo_url": "https://github.com/foo/bar"},
        files={"paper": ("paper.pdf", scanned_pdf, "application/pdf")}
    )
    assert resp.status_code == 400
    assert "contains no extractable text" in resp.json()["detail"]

@pytest.mark.skipif(not HAS_APP, reason="FastAPI app with routes is implemented in Stage 7")
def test_api_negative_oversized_pdf():
    client = TestClient(app)
    huge_pdf = b"%PDF-" + b"x" * (26 * 1024 * 1024)
    resp = client.post(
        "/api/projects",
        data={"repo_url": "https://github.com/foo/bar"},
        files={"paper": ("paper.pdf", huge_pdf, "application/pdf")}
    )
    assert resp.status_code == 400
    assert "exceeds size limit" in resp.json()["detail"]

@pytest.mark.skipif(not HAS_APP, reason="FastAPI app with routes is implemented in Stage 7")
def test_api_negative_non_pdf_with_pdf_name():
    client = TestClient(app)
    fake_pdf = b"This is just plain text, not a PDF file."
    resp = client.post(
        "/api/projects",
        data={"repo_url": "https://github.com/foo/bar"},
        files={"paper": ("paper.pdf", fake_pdf, "application/pdf")}
    )
    assert resp.status_code == 400
    assert "missing '%PDF-' header" in resp.json()["detail"]

@pytest.mark.skipif(not HAS_APP, reason="FastAPI app with routes is implemented in Stage 7")
def test_api_negative_nonexistent_repo():
    client = TestClient(app)
    valid_pdf = make_valid_pdf_bytes()
    resp = client.post(
        "/api/projects",
        data={"repo_url": "https://github.com/nonexistent-org-rerun-9999/nonexistent-repo-9999"},
        files={"paper": ("paper.pdf", valid_pdf, "application/pdf")}
    )
    assert resp.status_code == 400
    assert "Failed to clone repository" in resp.json()["detail"]

@pytest.mark.skipif(not HAS_APP, reason="FastAPI app with routes is implemented in Stage 7")
def test_api_negative_huge_repo(monkeypatch):
    client = TestClient(app)
    valid_pdf = make_valid_pdf_bytes()
    def mock_ingest(*args, **kwargs):
        raise RepoIngestError("Repository size (520.0 MB) exceeds maximum allowed cap of 500 MB.")
    monkeypatch.setattr("tools.ingest.ingest_custom_repo", mock_ingest)
    resp = client.post(
        "/api/projects",
        data={"repo_url": "https://github.com/valid-org/huge-repo"},
        files={"paper": ("paper.pdf", valid_pdf, "application/pdf")}
    )
    assert resp.status_code == 400
    assert "exceeds maximum allowed cap" in resp.json()["detail"]

@pytest.mark.skipif(not HAS_APP, reason="FastAPI app with routes is implemented in Stage 7")
def test_api_negative_escaping_symlink(monkeypatch):
    client = TestClient(app)
    valid_pdf = make_valid_pdf_bytes()
    def mock_ingest(*args, **kwargs):
        raise RepoIngestError("Escaping symlink detected: 'leak.txt' points outside workspace to '/etc/passwd'. Rejected for security.")
    monkeypatch.setattr("tools.ingest.ingest_custom_repo", mock_ingest)
    resp = client.post(
        "/api/projects",
        data={"repo_url": "https://github.com/valid-org/symlink-repo"},
        files={"paper": ("paper.pdf", valid_pdf, "application/pdf")}
    )
    assert resp.status_code == 400
    assert "Escaping symlink detected" in resp.json()["detail"]
