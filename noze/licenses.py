"""Turn the zoo of license strings/URLs from every source into one usage class.

The point: "bisa dipake ga?" must be answerable at a glance for every asset.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Usage


@dataclass(frozen=True)
class LicenseInfo:
    code: str
    label: str
    usage: str
    url: str = ""


_KNOWN: dict[str, LicenseInfo] = {
    "cc0": LicenseInfo("cc0", "CC0 (public domain)", Usage.FREE, "https://creativecommons.org/publicdomain/zero/1.0/"),
    "pdm": LicenseInfo("pdm", "Public Domain Mark", Usage.FREE, "https://creativecommons.org/publicdomain/mark/1.0/"),
    "public-domain": LicenseInfo("public-domain", "Public domain", Usage.FREE),
    "nasa": LicenseInfo(
        "nasa", "NASA media (generally public domain; no NASA endorsement/logo use)", Usage.FREE,
        "https://www.nasa.gov/nasa-brand-center/images-and-media/",
    ),
    "pexels": LicenseInfo("pexels", "Pexels License (free, credit appreciated)", Usage.FREE, "https://www.pexels.com/license/"),
    "unsplash": LicenseInfo("unsplash", "Unsplash License (free, credit appreciated)", Usage.FREE, "https://unsplash.com/license"),
    "pixabay": LicenseInfo("pixabay", "Pixabay Content License", Usage.FREE, "https://pixabay.com/service/license-summary/"),
    "lottie-simple": LicenseInfo("lottie-simple", "Lottie Simple License", Usage.FREE, "https://lottiefiles.com/page/license"),
    "ofl-1.1": LicenseInfo("ofl-1.1", "SIL Open Font License 1.1", Usage.FREE, "https://openfontlicense.org"),
    "ufl": LicenseInfo("ufl", "Ubuntu Font License", Usage.FREE, "https://ubuntu.com/legal/font-licence"),
    "unlicense": LicenseInfo("unlicense", "The Unlicense", Usage.FREE, "https://unlicense.org"),
    "wtfpl": LicenseInfo("wtfpl", "WTFPL", Usage.FREE),
    "0bsd": LicenseInfo("0bsd", "0BSD", Usage.FREE),
    "mit": LicenseInfo("mit", "MIT (keep the license notice when redistributing files)", Usage.FREE, "https://opensource.org/license/mit"),
    "isc": LicenseInfo("isc", "ISC (keep the license notice when redistributing files)", Usage.FREE),
    "bsd-2-clause": LicenseInfo("bsd-2-clause", "BSD-2-Clause (keep notice)", Usage.FREE),
    "bsd-3-clause": LicenseInfo("bsd-3-clause", "BSD-3-Clause (keep notice)", Usage.FREE),
    "apache-2.0": LicenseInfo("apache-2.0", "Apache-2.0 (keep notice)", Usage.FREE, "https://www.apache.org/licenses/LICENSE-2.0"),
    "zlib": LicenseInfo("zlib", "zlib", Usage.FREE),
    "gpl": LicenseInfo("gpl", "GPL (copyleft: credit + share source of derivative code)", Usage.CREDIT),
    "lgpl": LicenseInfo("lgpl", "LGPL (copyleft)", Usage.CREDIT),
    "agpl": LicenseInfo("agpl", "AGPL (strong copyleft)", Usage.CREDIT),
    "mpl-2.0": LicenseInfo("mpl-2.0", "MPL-2.0 (file-level copyleft)", Usage.CREDIT),
    "gfdl": LicenseInfo("gfdl", "GNU FDL (credit + share-alike)", Usage.CREDIT),
    "fal": LicenseInfo("fal", "Free Art License (credit + share-alike)", Usage.CREDIT),
    "attribution": LicenseInfo("attribution", "Attribution required", Usage.CREDIT),
    "sampling+": LicenseInfo("sampling+", "CC Sampling+ (check terms)", Usage.CHECK, "https://creativecommons.org/licenses/sampling+/1.0/"),
    "nc-sampling+": LicenseInfo("nc-sampling+", "CC NonCommercial Sampling+", Usage.NONCOMMERCIAL),
    "giphy": LicenseInfo("giphy", "GIPHY terms — rights stay with creators (reference/social use)", Usage.REFERENCE, "https://support.giphy.com/hc/en-us/articles/360020027752"),
    "in-copyright": LicenseInfo("in-copyright", "In copyright — reference only", Usage.REFERENCE, "http://rightsstatements.org/vocab/InC/1.0/"),
    "reference": LicenseInfo("reference", "All rights reserved by the creator — reference/inspiration only", Usage.REFERENCE),
    "no-license": LicenseInfo("no-license", "No license given (all rights reserved) — reference only", Usage.REFERENCE),
    "ai-generated": LicenseInfo("ai-generated", "AI-generated, shared publicly — check the platform's terms", Usage.CHECK),
    "own": LicenseInfo("own", "Your own asset", Usage.OWN),
    "unknown": LicenseInfo("unknown", "Unknown — check the source page", Usage.CHECK),
}

_ALIASES = {
    "cc0-1.0": "cc0",
    "cc-zero": "cc0",
    "publicdomain/zero": "cc0",
    "public domain": "public-domain",
    "publicdomain": "public-domain",
    "pd": "public-domain",
    "pd-old": "public-domain",
    "pd-usgov": "public-domain",
    "publicdomain/mark": "pdm",
    "no restrictions": "public-domain",
    "no known copyright restrictions": "public-domain",
    "ofl": "ofl-1.1",
    "ofl-1.0": "ofl-1.1",
    "sil open font license": "ofl-1.1",
    "apache": "apache-2.0",
    "apache 2.0": "apache-2.0",
    "apache license 2.0": "apache-2.0",
    "bsd": "bsd-3-clause",
}

_CC_RE = re.compile(
    r"(?:^|[\s/(_-]|cc[\s_-]?)(by(?:[\s_-]?nc)?(?:[\s_-]?nd|[\s_-]?sa)?)(?:[\s/_-]*v?(\d(?:\.\d)?))?",
    re.IGNORECASE,
)

_CC_NAMES = {
    "by": ("CC BY", Usage.CREDIT, ""),
    "by-sa": ("CC BY-SA", Usage.CREDIT, "credit + share-alike"),
    "by-nd": ("CC BY-ND", Usage.CREDIT, "credit, no edits allowed"),
    "by-nc": ("CC BY-NC", Usage.NONCOMMERCIAL, "non-commercial"),
    "by-nc-sa": ("CC BY-NC-SA", Usage.NONCOMMERCIAL, "non-commercial, share-alike"),
    "by-nc-nd": ("CC BY-NC-ND", Usage.NONCOMMERCIAL, "non-commercial, no edits"),
}


def known(code: str) -> LicenseInfo:
    return _KNOWN.get(code, _KNOWN["unknown"])


def _cc(kind: str, version: str | None, url: str = "") -> LicenseInfo:
    kind = re.sub(r"[\s_]", "-", kind.lower())
    kind = kind.replace("--", "-")
    if kind not in _CC_NAMES:
        return _KNOWN["unknown"]
    name, usage, note = _CC_NAMES[kind]
    version = version or ""
    if version and "." not in version:
        version = f"{version}.0"
    label = f"{name} {version}".strip()
    if note:
        label += f" ({note})"
    code = f"cc-{kind}" + (f"-{version}" if version else "")
    if not url:
        url = f"https://creativecommons.org/licenses/{kind}/{version or '4.0'}/"
    return LicenseInfo(code, label, usage, url)


def normalize_license(raw: str | None = None, url: str | None = None) -> LicenseInfo:
    """Best-effort mapping of a license name and/or URL to a LicenseInfo."""
    text = (raw or "").strip()
    link = (url or "").strip()
    probe = f"{text} {link}".lower()
    if not probe.strip():
        return _KNOWN["unknown"]

    if text.lower() in _KNOWN:
        info = _KNOWN[text.lower()]
        return LicenseInfo(info.code, info.label, info.usage, link or info.url)

    # rightsstatements.org vocab
    if "rightsstatements.org" in probe:
        if "/inc" in probe:
            return LicenseInfo("in-copyright", _KNOWN["in-copyright"].label, Usage.REFERENCE, link)
        return LicenseInfo("unknown", "Rights statement — check the source page", Usage.CHECK, link)

    # creativecommons.org URLs / CC names
    if "nc-sampling" in probe:
        return _KNOWN["nc-sampling+"]
    if "sampling+" in probe or "sampling%2b" in probe:
        return _KNOWN["sampling+"]
    if "publicdomain/zero" in probe or re.search(r"\bcc[\s_-]?0\b|\bcc0\b|cc-zero", probe):
        return LicenseInfo("cc0", _KNOWN["cc0"].label, Usage.FREE, link or _KNOWN["cc0"].url)
    if "publicdomain/mark" in probe or probe.strip() == "pdm":
        return LicenseInfo("pdm", _KNOWN["pdm"].label, Usage.FREE, link or _KNOWN["pdm"].url)

    cc_source = link if "creativecommons.org/licenses/" in link.lower() else text
    if "creativecommons.org/licenses/" in cc_source.lower() or re.search(r"\bcc\b|\bcc[-_ ]by|^by([\s_-]|$)|creative commons", probe):
        m = re.search(r"licenses/([a-z-]+)/(\d(?:\.\d)?)", cc_source.lower())
        if m:
            return _cc(m.group(1), m.group(2), link)
        m = _CC_RE.search(text.lower())
        if m:
            return _cc(m.group(1), m.group(2), link)

    for alias, code in _ALIASES.items():
        if probe.strip() == alias or text.lower() == alias or alias in link.lower():
            info = _KNOWN[code]
            return LicenseInfo(info.code, info.label, info.usage, link or info.url)

    spdx = text.lower()
    if spdx.startswith("cc-by") or spdx.startswith("cc by"):
        m = _CC_RE.search(spdx)
        if m:
            return _cc(m.group(1), m.group(2), link)
    for prefix, code in (("agpl", "agpl"), ("lgpl", "lgpl"), ("gpl", "gpl"), ("gfdl", "gfdl"), ("mpl", "mpl-2.0")):
        if spdx.startswith(prefix):
            info = _KNOWN[code]
            return LicenseInfo(info.code, f"{text} — {info.label}", info.usage, link or info.url)
    for key in ("mit", "isc", "0bsd", "unlicense", "wtfpl", "zlib", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "ofl-1.1"):
        if spdx == key or spdx.startswith(key):
            info = _KNOWN[key]
            return LicenseInfo(info.code, info.label, info.usage, link or info.url)
    if "public domain" in probe:
        return LicenseInfo("public-domain", _KNOWN["public-domain"].label, Usage.FREE, link)
    if "free art" in probe:
        return _KNOWN["fal"]
    if "noassertion" in probe or "other" == spdx:
        return LicenseInfo("unknown", "Custom license — check the repository", Usage.CHECK, link)
    return LicenseInfo("custom", text[:120] or "Custom license", Usage.CHECK, link)


def attribution_line(title: str, author: str, source_label: str, license_label: str, page_url: str) -> str:
    """TASL-style credit line: Title, Author, Source, License."""
    parts: list[str] = []
    t = f'"{title}"' if title else "Untitled"
    if author:
        t += f" by {author}"
    parts.append(t)
    if source_label:
        parts.append(f"via {source_label}")
    if license_label:
        parts.append(license_label.split(" (")[0])
    line = " — ".join(parts)
    if page_url:
        line += f" — {page_url}"
    return line
