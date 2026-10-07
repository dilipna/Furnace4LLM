import io
import stat
import tarfile
import zipfile
from pathlib import Path

import pytest
from furnace.security.redact import find_secrets, redact
from furnace.security.safe_extract import (
    ArchiveRejected,
    ExtractLimits,
    safe_extract_tar,
    safe_extract_zip,
)
from furnace.security.ssrf import UnsafeURL, is_public_ip, validate_url

# ------------------------------------------------------------------ archives


def _zip(tmp: Path, entries: dict[str, bytes], *, symlink: str | None = None) -> Path:
    p = tmp / "a.zip"
    with zipfile.ZipFile(p, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
        if symlink:
            info = zipfile.ZipInfo(symlink)
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(info, "/etc/passwd")
    return p


def _tar(tmp: Path, members: list[tarfile.TarInfo], data: dict[str, bytes] | None = None) -> Path:
    p = tmp / "a.tar.gz"
    with tarfile.open(p, "w:gz") as tf:
        for m in members:
            payload = (data or {}).get(m.name)
            tf.addfile(m, io.BytesIO(payload) if payload is not None else None)
    return p


def test_zip_extracts_normal_tree(tmp_path):
    src = _zip(tmp_path, {"app/main.py": b"print(1)", "README.md": b"# hi"})
    stats = safe_extract_zip(src, tmp_path / "out")
    assert stats.files == 2
    assert (tmp_path / "out/app/main.py").read_bytes() == b"print(1)"


@pytest.mark.parametrize(
    "name", ["../evil.py", "a/../../evil.py", "/etc/evil", "C:/evil", "a\\..\\..\\evil"]
)
def test_zip_rejects_traversal_and_absolute(tmp_path, name):
    src = _zip(tmp_path, {name: b"x"})
    with pytest.raises(ArchiveRejected):
        safe_extract_zip(src, tmp_path / "out")
    assert not (tmp_path / "evil.py").exists()


def test_zip_rejects_symlink(tmp_path):
    src = _zip(tmp_path, {"ok.txt": b"x"}, symlink="link")
    with pytest.raises(ArchiveRejected, match="symlink"):
        safe_extract_zip(src, tmp_path / "out")


def test_zip_bomb_rejected_by_ratio(tmp_path):
    src = _zip(tmp_path, {"bomb.txt": b"\0" * (8 * 2**20)})  # compresses ~1000x
    with pytest.raises(ArchiveRejected, match="ratio"):
        safe_extract_zip(src, tmp_path / "out")


def test_total_bytes_enforced_while_streaming(tmp_path):
    src = _zip(tmp_path, {f"f{i}.bin": bytes(range(256)) * 400 for i in range(5)})  # 5 x 100 KiB
    limits = ExtractLimits(max_total_bytes=300 * 1024)
    with pytest.raises(ArchiveRejected, match="expands beyond"):
        safe_extract_zip(src, tmp_path / "out", limits)


def test_entry_count_limit(tmp_path):
    src = _zip(tmp_path, {f"f{i}": b"x" for i in range(30)})
    with pytest.raises(ArchiveRejected, match="entries"):
        safe_extract_zip(src, tmp_path / "out", ExtractLimits(max_entries=10))


def test_tar_github_style_strip_and_links_rejected(tmp_path):
    f = tarfile.TarInfo("repo-abc123/app.py")
    f.size = 5
    ok = _tar(tmp_path, [f], {"repo-abc123/app.py": b"hello"})
    stats = safe_extract_tar(ok, tmp_path / "out", strip_components=1)
    assert stats.files == 1 and (tmp_path / "out/app.py").read_bytes() == b"hello"

    link = tarfile.TarInfo("repo/link")
    link.type = tarfile.SYMTYPE
    link.linkname = "/etc/passwd"
    bad = _tar(tmp_path, [link])
    with pytest.raises(ArchiveRejected, match="link"):
        safe_extract_tar(bad, tmp_path / "out2")

    dev = tarfile.TarInfo("repo/dev")
    dev.type = tarfile.CHRTYPE
    with pytest.raises(ArchiveRejected, match="special"):
        safe_extract_tar(_tar(tmp_path, [dev]), tmp_path / "out3")


def test_tar_traversal_rejected(tmp_path):
    m = tarfile.TarInfo("../../evil.py")
    m.size = 1
    with pytest.raises(ArchiveRejected, match="traversal"):
        safe_extract_tar(_tar(tmp_path, [m], {"../../evil.py": b"x"}), tmp_path / "out")


# ------------------------------------------------------------------ secrets

FAKE_OPENAI = "sk-proj-" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6"
FAKE_GH = "ghp_" + "A" * 36


def test_detects_and_redacts_known_token_formats():
    text = f'OPENAI_API_KEY = "{FAKE_OPENAI}"\ntoken: {FAKE_GH}\n'
    kinds = {f.kind for f in find_secrets(text)}
    assert {"openai_key", "github_token"} <= kinds
    out = redact(text)
    assert FAKE_OPENAI not in out and FAKE_GH not in out
    assert "[REDACTED:openai_key]" in out


def test_high_entropy_assignment_and_db_url_password():
    text = 'db_password = "q8#Lr2!vZ9@mK4pX"\nDATABASE_URL=postgres://app:S3cr3tPassw0rd@db:5432/x'
    out = redact(text)
    assert "q8#Lr2!vZ9@mK4pX" not in out
    assert "S3cr3tPassw0rd" not in out
    assert "postgres://app:" in out  # only the password is replaced


def test_placeholders_and_low_entropy_are_not_flagged():
    text = (
        'api_key = "your-api-key-here"\nLLM_API_KEY = "not-needed"\npassword = "aaaaaaaaaaaaaaaa"'
    )
    assert find_secrets(text) == []


def test_finding_line_numbers():
    text = f"a\nb\nkey={FAKE_GH}"
    assert find_secrets(text)[0].line == 3


# ------------------------------------------------------------------ ssrf


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.1.2.3",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "100.64.0.1",
        "::1",
        "fd00::1",
        "::ffff:127.0.0.1",
        "0.0.0.0",
    ],
)
def test_private_and_metadata_ips_blocked(ip):
    assert not is_public_ip(ip)


def test_public_ips_allowed():
    assert is_public_ip("8.8.8.8") and is_public_ip("2606:4700:4700::1111")


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com",
        "http://user:pw@example.com",
        "http://localhost:8000",
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data",
    ],
)
def test_validate_url_rejects(url):
    with pytest.raises(UnsafeURL):
        validate_url(url)


def test_private_allowed_only_when_explicit():
    v = validate_url("http://127.0.0.1:8100/v1", allow_private=True)
    assert v.ip == "127.0.0.1" and v.port == 8100


def test_production_refuses_dev_secrets(monkeypatch, tmp_path):
    import pytest
    from furnace.settings import Settings

    monkeypatch.chdir(tmp_path)  # no .env file here: only the variables set below apply
    monkeypatch.setenv("FURNACE_ENV", "prod")
    with pytest.raises(ValueError, match="FURNACE_MASTER_KEY"):
        Settings()
    monkeypatch.setenv("FURNACE_MASTER_KEY", "cHJvZC1rZXktZm9yLXRlc3RzLW9ubHktMzItYnl0ZXM=")
    with pytest.raises(ValueError, match="FURNACE_SESSION_SECRET"):
        Settings()
    monkeypatch.setenv("FURNACE_SESSION_SECRET", "s3cret-for-tests")
    with pytest.raises(ValueError, match="LABELS_WRITABLE"):
        Settings()
    monkeypatch.setenv("FURNACE_LABELS_WRITABLE", "false")
    assert Settings().env == "prod"
