"""Validate this draft evidence room, without importing or running Furnace."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LINK = re.compile(r'\[([^\]\n]*)\]\(([^\s)]+)(?:\s+"([^"]*)")?\)')
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def pointer(value, path: str):
    for part in path.strip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def within(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"path outside investor room: {relative}")
    return path


class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def normalize(raw: str) -> str:
    parser = PageText()
    parser.feed(raw)
    return " ".join(html.unescape(" ".join(parser.parts)).split())


def validate(root: Path = ROOT, online: bool = False) -> list[str]:
    errors: list[str] = []
    sources = {s["id"]: s for s in load(root / "sources.json")}
    claims = load(root / "claims.json")
    urls: set[str] = set()

    def check(name, operation):
        try:
            operation()
        except Exception as exc:
            errors.append(f"{name}: {exc}")

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    for record in load(root / "provenance.json"):

        def verify_record(record=record):
            path = within(root, record["file"])
            require(
                hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"],
                "copied evidence hash differs",
            )
            expected = (
                f"https://github.com/dilipna/Furnace4LLM/blob/"
                f"{record['source_commit']}/{record['source_path']}"
            )
            require(record["url"] == expected, "provenance URL mismatch")
            urls.add(expected)

        check(record["file"], verify_record)

    for source in sources.values():

        def verify_source(source=source):
            require(source["excerpt_verified"], "source excerpt not verified")
            require(
                hashlib.sha256(source["excerpt"].encode()).hexdigest() == source["excerpt_sha256"],
                "source excerpt hash differs",
            )
            require(
                bool(source.get("response_sha256") or source.get("verification_method")),
                "missing retrieval identity/method",
            )
            urls.add(source["url"])

        check(source["id"], verify_source)

    def claim_value(key: str, trail=()):
        require(key not in trail, "cyclic claim inputs")
        claim = claims[key]
        kind = claim["kind"]
        label_number = NUMBER.search(claim["label"].replace(",", ""))
        require(label_number is not None, "numeric claim label missing")
        label_value = float(label_number.group()) * (
            1_000_000 if "million" in claim["label"] else 1
        )
        require(label_value == claim["value"], "claim label/value mismatch")
        if kind in ("measured", "derived"):
            actual = pointer(load(within(root, claim["file"])), claim["pointer"])
            if kind == "derived":
                require(claim["operation"] == "length", "unknown raw derivation")
                actual = len(actual)
            require(actual == claim["value"], f"raw value {actual!r} != {claim['value']!r}")
        elif kind == "proposal":
            require(
                claim["contains"] in within(root, claim["file"]).read_text(encoding="utf-8"),
                "proposal text missing",
            )
        elif kind == "external":
            source = sources[claim["source"]]
            excerpts = " ".join([source["excerpt"], *source.get("additional_excerpts", [])])
            require(claim["contains"] in excerpts, "number not in registered primary excerpt")
            # Ensure an arbitrary numeric value cannot be substituted behind a valid citation.
            digits = claim["contains"].replace(",", "")
            match = NUMBER.search(digits)
            require(match is not None, "external value has no numeric text")
            actual = float(match.group()) * (1_000_000 if "million" in digits else 1)
            require(actual == claim["value"], "source text/value mismatch")
        elif kind == "assumption":
            require(bool(claim["rationale"]), "unlabelled assumption")
        elif kind == "projection":
            values = [claim_value(k, (*trail, key)) for k in claim["inputs"]]
            operation = claim["operation"]
            if operation == "product":
                actual = 1
                for value in values:
                    actual *= value
            elif operation == "control_month":
                cores, cpu, ram, ram_rate, hours, seconds = values
                actual = (cores * cpu + ram * ram_rate) * hours * seconds
            elif operation == "control_per_user":
                allocated, reserve, customers = values
                actual = (allocated + reserve) / customers
            elif operation == "support":
                minutes, hour, hourly_rate = values
                actual = minutes / hour * hourly_rate
            else:
                raise ValueError(f"unknown calculation: {operation}")
            require(
                abs(actual - claim["value"]) < 0.0051,
                f"calculated {actual} != stated {claim['value']}",
            )
        else:
            raise ValueError(f"unknown claim kind: {kind}")
        return claim["value"]

    for key in claims:
        check(f"claim:{key}", lambda key=key: claim_value(key))

    for path in sorted(root.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for match in LINK.finditer(text):
            label, target, title = match.groups()

            def verify_link(target=target, title=title, label=label, path=path):
                if target.startswith("https://"):
                    urls.add(target)
                else:
                    parsed = urllib.parse.urlsplit(target)
                    require(not parsed.scheme, "unexpected link scheme")
                    dest = within(root, urllib.parse.unquote(parsed.path)) if parsed.path else path
                    require(dest.is_file(), f"missing link: {target}")
                    if parsed.fragment:
                        require(dest.suffix == ".md", "unsupported anchor target")
                        headings = re.findall(r"^#+ (.+)$", dest.read_text(encoding="utf-8"), re.M)
                        anchors = [
                            re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-") for h in headings
                        ]
                        require(parsed.fragment in anchors, f"missing anchor: {target}")
                if title and title.startswith("claim:"):
                    key = title.removeprefix("claim:")
                    claim = claims[key]
                    require(label == claim["label"], f"claim label differs: {key}")
                    expected = claim.get(
                        "file", "sources.json" if claim["kind"] == "external" else "claims.json"
                    )
                    require(target == expected, f"claim target differs: {key}")

            check(f"{path.name} link {target}", verify_link)
        if path.name in ("deck.md", "memo.md"):
            # Slide ordinals are the sole structural exception. All other numbers need claims.
            stripped = re.sub(r"^## Slide \d+ \u2014", "## Slide", text, flags=re.M)
            stripped = LINK.sub(
                lambda m: "" if (m.group(3) or "").startswith("claim:") else m.group(1), stripped
            )
            for match in NUMBER.finditer(stripped):
                errors.append(f"{path.name}: unregistered number {match.group()}")

    if online:
        pages: dict[str, str] = {}
        for url in sorted(urls):

            def fetch(url=url):
                require(
                    urllib.parse.urlsplit(url).scheme == "https", "only HTTPS sources permitted"
                )
                request = urllib.request.Request(  # noqa: S310 -- scheme validated above
                    url, headers={"User-Agent": "Furnace-evidence-review/1.0"}
                )
                with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 -- HTTPS input, final scheme checked
                    require(
                        urllib.parse.urlsplit(response.url).scheme == "https", "non-HTTPS redirect"
                    )
                    raw = response.read().decode("utf-8")
                page = normalize(raw)
                require(
                    not any(
                        t in page.lower()
                        for t in ("one moment, please", "verify you are human", "just a moment")
                    ),
                    "bot challenge, not source content",
                )
                pages[url] = page

            check(f"online {url}", fetch)
        for source in sources.values():

            def verify_live(source=source):
                text = pages[source["url"]]
                for excerpt in [source["excerpt"], *source.get("additional_excerpts", [])]:
                    require(excerpt in text, f"live excerpt missing: {excerpt}")

            check(f"live excerpt {source['id']}", verify_live)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--online", action="store_true")
    args = parser.parse_args()
    try:
        errors = validate(online=args.online)
    except Exception as exc:
        errors = [f"invalid room: {exc}"]
    if errors:
        print("FAIL\n" + "\n".join(errors))
        return 1
    print(
        "PASS: "
        + (
            "offline + live URL/excerpt checks"
            if args.online
            else "offline evidence checks; live URLs not checked"
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
