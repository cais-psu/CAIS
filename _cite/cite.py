"""Compile, enrich and reconcile publications without deleting missing records."""

from difflib import SequenceMatcher
from html import escape
from importlib import import_module
from pathlib import Path
import os

from dotenv import load_dotenv
from classify import classify_citations, remove_superseded_arxiv
from errors import ScholarQuotaError
from records import identity_keys, normalize_record, reconcile, reconcile_update, title_key, useful_title
from util import cite_with_manubot, format_date, list_of_dicts, load_data, log, save_data


PLUGINS = ["google-scholar", "pubmed", "orcid", "sources"]


def enrich(source, previous, warn):
    source = normalize_record(source)
    for message in source.pop("_warnings", []):
        warn(message)
    inferred = source.pop("_doi_inferred", False)
    identifier = source.get("id", "")
    plugin = source.get("plugin")
    citation = {}
    # These identifiers have local summary metadata, but no reliable resolver.
    resolvable = identifier and not identifier.startswith(("orcid:", "wosuid:"))
    scholar_identifier = source.get("scholar_id") == identifier or any(
        old.get("scholar_id") == identifier for old in previous
    )
    resolvable = resolvable and not (scholar_identifier or (plugin == "google-scholar.py" and not identifier.startswith("doi:")))
    if resolvable:
        try:
            citation = dict(cite_with_manubot(identifier))
            if not useful_title(citation.get("title")):
                raise ValueError("Resolver returned no usable paper title")
            if inferred and useful_title(source.get("title")):
                similarity = SequenceMatcher(None, title_key(source["title"]), title_key(citation["title"])).ratio()
                if similarity < 0.8:
                    warn(f"DOI title disagrees with Scholar; retained Scholar record without inferred DOI: {identifier}")
                    source["id"] = source["scholar_id"]
                    source.pop("doi", None)
                    source.pop("DOI", None)
                    citation = {}
        except Exception:
            # The existing citation and source metadata remain usable offline.
            citation = {}
            warn(f"Could not enrich {identifier}; retaining available metadata")
    populated = {k: v for k, v in source.items() if v is not None and v != "" and v != []}
    if plugin == "sources.py":
        citation.update(populated)
    else:
        # DOI metadata supplies full authors/date; Scholar supplies citation count.
        citation = {**populated, **{k: v for k, v in citation.items() if v is not None and v != "" and v != []}}
    citation = normalize_record(citation)
    citation["date"] = format_date(citation.get("date", ""))
    if not useful_title(citation.get("title")):
        from records import identity_keys
        if not any(identity_keys(citation) & identity_keys(old) and useful_title(old.get("title")) for old in previous):
            raise ValueError(f"No usable title or previous metadata for {identifier}; refusing incomplete output")
    return citation


def has_saved_scholar(previous, entry):
    profile = entry.get("gsid")
    return bool(profile) and any(
        useful_title(row.get("title")) and (
            row.get("gsid") == profile
            or any(key.startswith(f"{profile}:") for key in identity_keys(row))
        ) for row in previous
    )


def report_scholar_quota_skips(profiles):
    """Make an incomplete refresh visible without failing other source updates."""
    if not profiles or os.environ.get("GITHUB_ACTIONS") != "true":
        return
    profiles = ", ".join(dict.fromkeys(profiles))
    message = (
        f"SerpApi search quota exhausted for Scholar profile(s): {profiles}. "
        "Saved records and citation counts were retained; new Scholar-only papers "
        "and fresh citation counts could not be fetched. Other sources still run. "
        "Restore SerpApi search quota, then rerun the citation workflow with Scholar refresh enabled."
    )
    # A workflow command must occupy its own line, with untrusted data escaped.
    escaped = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"\n::warning title=Google Scholar refresh skipped::{escaped}", flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(f"\n### Google Scholar refresh skipped\n\n{escape(message)}\n")


def run(root=Path.cwd(), skip_scholar=False):
    output = root / "_data/citations.yaml"
    errors, warnings, sources = [], [], []
    quota_skipped_profiles = []

    def warn(message):
        warnings.append(message)
        log(message, level="WARNING")

    previous = load_data(output) if output.exists() else []
    if not list_of_dicts(previous):
        raise ValueError("Existing citations must be a list of records")
    previous = [normalize_record(row) for row in previous]
    for plugin in PLUGINS:
        files = sorted(path for path in (root / "_data").glob(f"{plugin}*.*") if path.suffix in (".yaml", ".yml", ".json"))
        for file in files:
            try:
                entries = load_data(file)
                if not list_of_dicts(entries):
                    raise ValueError(f"{file.name} must contain a list of records")
                for entry in entries:
                    saved_scholar = plugin == "google-scholar" and has_saved_scholar(previous, entry)
                    if saved_scholar and skip_scholar:
                        log(f"{file.name}: using saved Scholar records for {entry['gsid']}; refresh runs on schedule or manual request", level="INFO")
                        continue
                    try:
                        expanded = import_module(f"plugins.{plugin}").main(entry)
                    except ScholarQuotaError as error:
                        if not saved_scholar:
                            raise
                        warn(f"{file.name}: {error}; retaining saved Scholar records and citation counts for {entry['gsid']}; continuing other sources")
                        quota_skipped_profiles.append(entry["gsid"])
                        continue
                    if not list_of_dicts(expanded):
                        raise ValueError(f"{plugin} returned invalid records")
                    for row in expanded:
                        sources.append({**row, "plugin": f"{plugin}.py", "file": file.name})
                    log(f"{file.name}: fetched {len(expanded)} records")
            except Exception as error:
                # Stop publication, but collect errors from remaining providers.
                errors.append(f"{file.name}: {error}")
                log(errors[-1], level="ERROR")

    report_scholar_quota_skips(quota_skipped_profiles)
    if errors:
        log(f"{len(errors)} error(s). Existing citations were not changed.", level="ERROR")
        return 1

    # Combine manual field overrides before enrichment, so a later image-only
    # entry cannot undo an earlier hand-corrected title or author list.
    sources = [row for row in sources if row['plugin'] != 'sources.py'] + reconcile(
        [row for row in sources if row['plugin'] == 'sources.py'], warn
    )
    current, removals = [], []
    for source in sources:
        if source.get("remove") is True:
            removals.append(normalize_record(source))
            continue
        try:
            current.append(enrich(source, previous, warn))
        except Exception as error:
            errors.append(str(error))
            log(error, level="ERROR")

    if errors:
        log(f"{len(errors)} error(s). Existing citations were not changed.", level="ERROR")
        return 1
    current = reconcile(current, warn)
    citations = reconcile_update(previous, current, removals, warn)
    citations = classify_citations(citations, [row for row in sources if row["plugin"] == "sources.py"], warn)
    # Apply after retaining previous records so upstream imports cannot restore
    # same-title arXiv versions when a journal/conference version is available.
    citations = remove_superseded_arxiv(citations, lambda message: log(message, level="INFO"))
    # Other different-DOI versions still need review.
    titles = {}
    for row in citations:
        key = title_key(row.get("title"))
        if key in titles and row.get("doi") != titles[key].get("doi"):
            warn(f"Same title has different identifiers; review versions: {titles[key].get('id')} / {row.get('id')}")
        titles[key] = row
    citations.sort(key=lambda row: (str(row.get("date") or ""), title_key(row.get("title")), row.get("id", "")), reverse=True)
    save_data(output, citations)
    log(f"Saved {len(citations)} citations; {len(warnings)} warning(s)", level="SUCCESS")
    return 0


if __name__ == "__main__":
    load_dotenv()
    raise SystemExit(run(skip_scholar=os.environ.get("CITE_SKIP_GOOGLE_SCHOLAR", "").strip().lower() in {"1", "true", "yes", "on"}))
