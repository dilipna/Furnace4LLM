"""Ephemeral text extraction worker. No filenames, document bytes or errors are logged."""

from __future__ import annotations

import base64
import io
import json
import sys
import zipfile

from defusedxml import ElementTree

MAX_TEXT = 128000


def extract(kind: str, data: bytes) -> str:
    if kind in {"txt", "md"}:
        text = data.decode("utf-8-sig")
    elif kind == "docx":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            info = archive.getinfo("word/document.xml")
            if info.file_size > 2_000_000:
                raise ValueError("Document XML is too large")
            xml = archive.read(info)
        if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
            raise ValueError("Document entities are not supported")
        root = ElementTree.fromstring(xml)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        text = "\n".join("".join(p.itertext()) for p in root.findall(".//w:p", ns))
    elif kind == "pdf":
        from pypdf import PdfReader, overwrite_configuration

        overwrite_configuration(
            maximum_declared_stream_length=2_000_000,
            zlib_maximum_output_length=2_000_000,
            lzw_maximum_output_length=2_000_000,
            run_length_maximum_output_length=2_000_000,
            array_based_stream_maximum_output_length=2_000_000,
            stream_decoding_work_maximum_length=8_000_000,
            stream_parsing_work_maximum_count=200_000,
            page_tree_maximum_entries=1000,
            jbig2dec_binary=None,
        )
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted or len(reader.pages) > 40:
            raise ValueError("Encrypted PDFs or more than 40 pages are not supported")
        parts = []
        for page in reader.pages:
            contents = page.get_contents()
            if contents and len(contents.get_data()) > 2_000_000:
                raise ValueError("PDF page is too complex")
            parts.append(page.extract_text() or "")
            if sum(map(len, parts)) > MAX_TEXT:
                raise ValueError("Document text is too long")
        text = "\n".join(parts)
    else:
        raise ValueError("Unsupported document type")
    if not text.strip():
        raise ValueError("No text found; scanned PDFs need OCR, which is not included")
    if len(text.encode("utf-8")) > MAX_TEXT:
        raise ValueError("Document text is too long; split it into smaller files")
    return text


def main() -> None:
    # On Windows the parent assigns a bounded Job Object before sending stdin.
    if sys.platform != "win32":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (384 * 1024**2, 384 * 1024**2))
        resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
    try:
        request = json.loads(sys.stdin.buffer.read(4_100_000))
        data = base64.b64decode(request["data"], validate=True)
        if len(data) > 3_000_000:
            raise ValueError("File exceeds 3 MB")
        result = {"text": extract(request["kind"], data)}
    except Exception:
        # Parser exceptions may contain original document text or paths.
        result = {
            "error": "Could not read this document. Use UTF-8 text, a text PDF (up to 40 pages), or DOCX; maximum 24,000 UTF-8 text bytes. Encrypted/scanned PDFs and complex files are not supported."
        }
    sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    main()
