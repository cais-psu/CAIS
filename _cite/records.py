"""Publication identity and lossless reconciliation, shared by all importers."""

import html
import re
import unicodedata
from copy import deepcopy
from urllib.parse import unquote


DOI_PATTERN = re.compile(r"10\.\d{4,9}/[^\s<>\"?#]+", re.I)
GENERIC_TITLES = {"web of science", "error", "access denied", "just a moment"}


def normalize_doi(value):
    value = html.unescape(unquote(str(value or ""))).strip()
    value = re.sub(r"^doi:\s*", "", value, flags=re.I)
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value, flags=re.I)
    if not DOI_PATTERN.fullmatch(value):
        return ""
    return value.lower()


def find_doi(*values):
    """Extract explicit DOIs; strip publisher URL routes, not DOI punctuation."""
    for value in values:
        value = html.unescape(unquote(str(value or "")))
        match = DOI_PATTERN.search(value)
        if not match:
            continue
        doi = match.group().rstrip(".,;")
        # Closing parentheses can be part of a DOI (e.g. older Elsevier DOIs).
        while doi.endswith(")") and doi.count(")") > doi.count("("):
            doi = doi[:-1]
        if value.startswith(("http://", "https://")):
            doi = re.sub(r"/(?:full|pdf|epdf|abstract|pdfdirect)/?$", "", doi, flags=re.I)
        return normalize_doi(doi)
    return ""


def normalize_id(value):
    value = str(value or "").strip()
    doi = normalize_doi(value)
    if doi:
        return f"doi:{doi}"
    if ":" in value:
        prefix, rest = value.split(":", 1)
        if prefix.lower() in {"doi", "arxiv", "pubmed", "pmid", "pmc", "wosuid", "orcid", "isbn", "url"}:
            return f"{prefix.lower()}:{rest.strip()}"
    return value


def title_key(value):
    value = re.sub(r"<[^>]*>", "", html.unescape(str(value or "")))
    value = unicodedata.normalize("NFKC", value).casefold()
    return "".join(char for char in value if char.isalnum())


def useful_title(value):
    return bool(title_key(value)) and str(value).strip().lower() not in GENERIC_TITLES


def normalize_record(record):
    record = deepcopy(record)
    record["id"] = normalize_id(record.get("id"))
    if record.get("aliases"):
        record["aliases"] = sorted({normalize_id(value) for value in record["aliases"]})
    dois = {normalize_doi(record.get(key)) for key in ("id", "doi", "DOI")} - {""}
    if len(dois) > 1:
        raise ValueError(f"Conflicting DOI fields for {record['id']}: {sorted(dois)}")
    doi = normalize_doi(record["id"]) or normalize_doi(record.get("doi")) or normalize_doi(record.get("DOI"))
    if doi:
        record.update(id=f"doi:{doi}", doi=doi, DOI=doi)
    return record


def identity_keys(record):
    values = [record.get("id"), record.get("scholar_id"), record.get("orcid_work_id")]
    values += record.get("aliases", [])
    return {normalize_id(value) for value in values if value}


def preprint(record):
    text = " ".join(str(record.get(k, "")) for k in ("id", "link", "publisher", "type")).lower()
    return any(token in text for token in ("arxiv", "techrxiv", "biorxiv", "medrxiv", "10.22541/", "preprint"))


def compatible_title(a, b):
    """Exact normalized title plus corroborating metadata; never fuzzy-merge."""
    if not useful_title(a.get("title")) or title_key(a.get("title")) != title_key(b.get("title")):
        return False
    if a.get("doi") and b.get("doi") and a["doi"] != b["doi"]:
        return False
    if preprint(a) != preprint(b):
        return False
    year_a, year_b = str(a.get("date", ""))[:4], str(b.get("date", ""))[:4]
    if not (year_a.isdigit() and year_b.isdigit()) or abs(int(year_a) - int(year_b)) > 1:
        return False
    authors_a, authors_b = a.get("authors") or [], b.get("authors") or []
    if authors_a and authors_b:
        # Scholar abbreviates given names, but retains surnames.
        surnames_a = {title_key(name.split()[-1]) for name in authors_a if name.split()}
        surnames_b = {title_key(name.split()[-1]) for name in authors_b if name.split()}
        return bool(surnames_a & surnames_b)
    venue_a, venue_b = title_key(a.get("publisher")), title_key(b.get("publisher"))
    if venue_a and venue_b and (venue_a in venue_b or venue_b in venue_a):
        return True
    # ORCID's WOS summaries often omit authors and use a different proceedings
    # title. An exact, distinctive paper title plus year can bridge that gap.
    return len(title_key(a.get("title"))) >= 40


def merge_record(a, b):
    """Later records win populated fields; preserve all known identifiers."""
    result = deepcopy(a)
    for key, value in b.items():
        if value is not None and value != "" and value != []:
            if (a.get("doi") and not b.get("doi") and b.get("plugin") != "sources.py"
                    and key in {"title", "authors", "publisher", "date", "link", "type"}
                    and result.get(key)):
                continue
            result[key] = deepcopy(value)
    # A Scholar identifier must not demote a previously resolved DOI.
    doi = b.get("doi") or a.get("doi")
    if doi:
        result.update(id=f"doi:{doi}", doi=doi, DOI=doi)
    aliases = identity_keys(a) | identity_keys(b)
    aliases.discard(result.get("id"))
    if aliases:
        result["aliases"] = sorted(aliases)
    return result


def reconcile(records, warn=lambda message: None):
    """Match stable identifiers first, then unambiguous corroborated titles."""
    result = []
    for record in records:
        record = normalize_record(record)
        matches = []
        for i, other in enumerate(result):
            shared = identity_keys(record) & identity_keys(other)
            if not shared:
                continue
            conflict = record.get("doi") and other.get("doi") and record["doi"] != other["doi"]
            explicit = record.get("plugin") == "sources.py" and other.get("id") in record.get("aliases", [])
            if conflict and not explicit:
                warn(f"Conflicting DOIs share an upstream identifier; kept separate: {other['id']} / {record['id']}")
            else:
                matches.append(i)
        matched_dois = {result[i].get("doi") for i in matches} - {None, ""}
        explicit_group = record.get("plugin") == "sources.py" and all(
            result[i].get("id") == record.get("id") or result[i].get("id") in record.get("aliases", [])
            for i in matches
        )
        if len(matched_dois) > 1 and not explicit_group:
            warn(f"Ambiguous upstream identifier spans multiple DOIs; kept separate: {record['id']}")
            matches = []
        if matches:
            first = matches[0]
            merged = result[first]
            for i in matches[1:]:
                merged = merge_record(merged, result[i])
            result[first] = merge_record(merged, record)
            for i in reversed(matches[1:]):
                result.pop(i)
        else:
            result.append(record)

    # Find all candidates before merging: an ID-less record must not arbitrarily
    # bridge two different DOIs with the same title.
    candidates = {
        i: [j for j, other in enumerate(result) if i != j and compatible_title(record, other)]
        for i, record in enumerate(result)
    }
    consumed = set()
    output = []
    for i, record in enumerate(result):
        if i in consumed:
            continue
        group = sorted({i, *candidates[i]})
        if all({j, *candidates[j]} == set(group) for j in group):
            record = result[group[0]]
            for j in group[1:]:
                record = merge_record(record, result[j])
            consumed.update(group)
        elif candidates[i]:
            warn(f"Ambiguous title match; kept separate: {record.get('title')}")
        output.append(record)
    return output


def reconcile_update(previous, current, removals, warn=lambda message: None):
    """An incomplete upstream response is never an implicit deletion."""
    merged = reconcile([*previous, *current], warn)
    # A historical remove rule for a duplicate WOS/Scholar record must not
    # remove the DOI publication after that record becomes an alias.
    removed_ids = {normalize_id(row.get("id")) for row in removals} - {""}
    current_keys = set().union(*(identity_keys(row) for row in current)) if current else set()
    for record in merged:
        if record.get("id") not in removed_ids and not identity_keys(record) & current_keys:
            warn(f"Retained previously published record absent from this fetch: {record.get('id') or record.get('title')}")
    return [row for row in merged if row.get("id") not in removed_ids]
