"""Assign one publication category after reconciliation; no network is needed."""

import argparse
import html
import re
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from records import identity_keys, normalize_record


CATEGORIES = {"journal", "conference", "other"}
TYPES = {
    "journal": {"article-journal", "journal-article", "journal"},
    "conference": {"paper-conference", "conference-paper", "conference-abstract", "proceedings-article", "conference-proceeding"},
    "other": {"book", "chapter", "book-chapter", "book-section", "edited-book", "monograph", "reference-entry", "dissertation", "thesis", "report", "working-paper", "preprint", "posted-content", "manuscript", "dataset", "grant"},
}

# These proceedings series are often returned as journal-article by registries.
PROCEEDINGS = {"ifac papersonline", "ifac papers online", "ifac proceedings volumes", "procedia manufacturing", "procedia cirp"}
JOURNALS = {
    "ieee access", "robotics and computer integrated manufacturing",
    "control engineering practice", "smart and sustainable manufacturing systems",
    "battery energy", "frontiers in built environment", "mathematics",
}

# Search aliases are inferred only from titles and author-supplied keywords,
# never from a proceedings volume's list of unrelated conference topics.
TOPICS = [
    ("LLM", "large language model", "large language models", "大语言模型", "大型语言模型"),
    ("MPC", "model predictive control", "模型预测控制"),
    ("digital twin", "digital twins", "数字孪生"),
    ("multi-agent", "multiagent", "multi agent", "多智能体"),
    ("additive manufacturing", "3D printing", "增材制造", "3D打印"),
    ("human-robot", "human robot", "人机协作"),
    ("DES", "discrete event systems", "discrete event system", "离散事件系统"),
    ("PTA", "priced timed automata", "定价时间自动机"),
    ("fault-tolerant", "fault tolerant", "容错控制"),
]


def words(value):
    value = html.unescape(str(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    value = unicodedata.normalize("NFKD", value).casefold()
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^\w]+", " ", value, flags=re.UNICODE).strip()


def as_list(value):
    if isinstance(value, dict):
        return list(value)
    if isinstance(value, list):
        return value
    return [value] if value else []


def classification(record, override=None):
    """Return category, basis and whether the category needs a human review."""
    if override is not None:
        if override not in CATEGORIES:
            raise ValueError(f"Invalid category {override!r} for {record.get('id')}")
        return override, "manual", False

    record = normalize_record(record)
    identifier = record["id"].lower()
    doi = record.get("doi", "")
    kind = str(record.get("type") or record.get("genre") or "").lower().strip()
    venue = words(record.get("container-title") or record.get("venue") or record.get("publisher"))

    if identifier.startswith(("arxiv:", "wosuid:pprn:")) or doi.startswith(("10.48550/arxiv.", "10.22541/", "10.36227/techrxiv.", "10.1101/")):
        return "other", "preprint-identifier", False

    if re.match(r"10\.1109/(?:access|tase|tcst|lra|mra)\.", doi):
        return "journal", "journal-doi", False
    if venue in JOURNALS or venue.startswith("ieee transactions on ") or venue == "ieee robotics and automation letters":
        return "journal", "journal-venue", False

    if venue in PROCEEDINGS or doi.startswith(("10.1016/j.ifacol.", "10.1016/j.promfg.", "10.1016/j.procir.")):
        return "conference", "proceedings-series", False
    if re.match(r"10\.(?:1109|23919)/(?:case|ccta|acc|cdc|wodes|etfa|arso|iros|icra)(?:\d|\.)", doi) or re.match(r"10\.1115/(?:msec|dscc|detc|idetc)\d", doi):
        return "conference", "conference-doi", False

    if re.search(r"\b(?:arxiv|biorxiv|medrxiv|techrxiv|preprint|authorea)\b", venue):
        return "other", "preprint-venue", False
    if kind in TYPES["conference"]:
        return "conference", "publication-type", False
    if kind in TYPES["journal"]:
        return "journal", "publication-type", False
    # Conference book chapters belong with the conference papers, but a whole
    # book remains in Other. Publisher names such as Springer are not types.
    if re.search(r"\b(?:conference|workshop|symposium|proceedings)\b", venue) and kind not in {"book", "edited-book", "monograph"}:
        return "conference", "conference-venue", False
    if kind in TYPES["other"] or doi.startswith("10.1016/b978-"):
        return "other", "publication-type", False
    if re.search(r"\b(?:journal|transactions|letters|magazine)\b", venue):
        return "journal", "journal-venue", False
    if re.search(r"\b(?:encyclopedia|handbook)\b", venue):
        return "other", "book-venue", False

    # An arXiv mirror must not demote a known journal/conference publication.
    host = urlsplit(str(record.get("link") or "")).hostname or ""
    if host in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}:
        return "other", "preprint-link", False
    return "other", "insufficient-metadata", True


def search_terms(record):
    explicit = as_list(record.get("tags")) + as_list(record.get("keywords"))
    text = " " + words(" ".join(map(str, [record.get("title", ""), *explicit]))) + " "
    terms = set(map(str, explicit))
    for aliases in TOPICS:
        if any(f" {words(alias)} " in text for alias in aliases):
            terms.update(aliases)
    category = record["category"]
    terms.update({
        "journal": ("journal", "期刊论文"),
        "conference": ("conference", "会议论文"),
        "other": ("other publications", "其他出版物"),
    }[category])
    if record["classification"]["basis"].startswith("preprint"):
        terms.update(("preprint", "预印本"))
        if "arxiv" in words(record.get("publisher")) or "arxiv" in str(record.get("id")):
            terms.add("arxiv")
    if record.get("type") in {"book", "chapter", "book-chapter", "book-section"}:
        terms.update(("book", "book chapter", "书籍", "书籍章节"))
    return sorted(terms, key=lambda term: (term.casefold(), term))


def classify_citations(citations, sources=(), warn=lambda message: None):
    overrides = [source for source in sources if "category" in source and not source.get("remove")]
    for source in overrides:
        if source["category"] not in CATEGORIES:
            raise ValueError(f"Invalid manual category for {source.get('id')}: {source['category']!r}")
    output = []
    for citation in citations:
        record = dict(citation)
        matched = [source for source in overrides if identity_keys(source) & identity_keys(record)]
        override = matched[-1]["category"] if matched else None
        category, basis, review = classification(record, override)
        # Always recompute. A previously generated category is never an override.
        record["category"] = category
        record["classification"] = {"basis": basis, "needs_review": review}
        record["search_terms"] = search_terms(record)
        if review:
            warn(f"Review publication category: {record.get('id')} ({record.get('title')})")
        output.append(record)
    return output


def main():
    from util import load_data, save_data
    parser = argparse.ArgumentParser(description="Reclassify saved citations without fetching APIs")
    parser.add_argument("--write", action="store_true", help="Update the generated citations file")
    args = parser.parse_args()
    sources = []
    for path in sorted(Path("_data").glob("sources*.*")):
        if path.suffix in {".yaml", ".yml", ".json"}:
            sources.extend(load_data(path))
    rows = classify_citations(load_data("_data/citations.yaml"), sources, print)
    print(dict(Counter(row["category"] for row in rows)))
    if args.write:
        save_data("_data/citations.yaml", rows)


if __name__ == "__main__":
    main()
