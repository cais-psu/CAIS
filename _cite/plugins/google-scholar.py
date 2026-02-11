import os
import re
from urllib.parse import urlparse, parse_qs, unquote
from serpapi import GoogleSearch
from util import *


_DOI_RE = re.compile(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.IGNORECASE)
_ARXIV_RE = re.compile(r"\b(\d{4}\.\d{4,5})(v\d+)?\b", re.IGNORECASE)

def _extract_doi(text: str) -> str:
    if not text:
        return ""
    m = _DOI_RE.search(text)
    return m.group(1).rstrip(").,;") if m else ""

def _extract_arxiv(text: str) -> str:
    if not text:
        return ""
    m = _ARXIV_RE.search(text)
    return m.group(1) if m else ""

def _to_manubot_id(link: str) -> str:
    """
    Returns a Manubot-citeable id: doi:..., arxiv:..., url:...
    """
    if not link:
        return ""

    # unescape common scholar redirect patterns
    # e.g. https://scholar.google.com/scholar_url?url=<ENCODED>&...
    try:
        u = urlparse(link)
        if "scholar.google" in u.netloc and u.path.endswith("/scholar_url"):
            qs = parse_qs(u.query)
            if "url" in qs and qs["url"]:
                link = unquote(qs["url"][0])
    except Exception:
        pass

    # DOI anywhere in link
    doi = _extract_doi(link)
    if doi:
        return f"doi:{doi}"

    # arXiv patterns
    # e.g. https://arxiv.org/abs/2510.11405 or .../pdf/2510.11405.pdf
    arx = _extract_arxiv(link)
    if arx and ("arxiv.org" in link.lower() or "arxiv" in link.lower()):
        return f"arxiv:{arx}"

    # sometimes DOI is not in link but appears in title/publisher—handled elsewhere
    return f"url:{link}"


def main(entry):
    api_key = os.environ.get("GOOGLE_SCHOLAR_API_KEY", "")
    if not api_key:
        raise Exception('No "GOOGLE_SCHOLAR_API_KEY" env var')

    params = {
        "engine": "google_scholar_author",
        "api_key": api_key,
        "num": 100,
    }

    _id = get_safe(entry, "gsid", "")
    if not _id:
        raise Exception('No "gsid" key')

    def query(_id):
        params["author_id"] = _id
        return get_safe(GoogleSearch(params).get_dict(), "articles", [])

    response = query(_id)

    sources = []
    for work in response:
        year = get_safe(work, "year", "")
        link = get_safe(work, "link", "")

        # try to produce a citeable id
        manubot_id = _to_manubot_id(link)

        # fallback: DOI sometimes appears in title or publication string
        if not manubot_id:
            doi = _extract_doi(get_safe(work, "title", "")) or _extract_doi(get_safe(work, "publication", ""))
            if doi:
                manubot_id = f"doi:{doi}"

        source = {
            "id": manubot_id,  # << key change
            "title": get_safe(work, "title", ""),
            "authors": list(map(str.strip, get_safe(work, "authors", "").split(","))),
            "publisher": get_safe(work, "publication", ""),
            "date": (year + "-01-01") if year else "",
            "link": link,
            # keep original scholar id (optional, for debugging)
            "scholar_citation_id": get_safe(work, "citation_id", ""),
        }

        source.update(entry)
        sources.append(source)

    return sources
