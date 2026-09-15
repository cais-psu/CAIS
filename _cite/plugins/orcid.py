import json
from urllib.request import Request, urlopen

from manubot.cite.handlers import prefix_to_handler as manubot_citable
from records import normalize_id
from util import cache, format_date, get_safe, list_of_dicts, log_cache, retry_request


@log_cache
@cache.memoize(name="orcid:works:v2", expire=24 * 60 * 60)
def query(orcid):
    def request():
        req = Request(f"https://pub.orcid.org/v3.0/{orcid}/works", headers={"Accept": "application/json"})
        with urlopen(req, timeout=30) as response:
            data = json.load(response)
        if not list_of_dicts(data.get("group")):
            raise RuntimeError("ORCID response missing valid work groups")
        return data["group"]
    return retry_request(request)


def self_ids(summary):
    return [
        item for item in get_safe(summary, "external-ids.external-id", []) or []
        if item.get("external-id-relationship") == "self" and item.get("external-id-value")
    ]


def main(entry):
    orcid = entry.get("orcid")
    if not orcid:
        raise ValueError('No "orcid" key')
    sources = []
    for work in query(orcid):
        summaries = sorted(work.get("work-summary") or [], key=lambda s: int(s.get("display-index") or 0), reverse=True)
        if not summaries:
            raise RuntimeError("ORCID returned a group without work summaries")
        # Parent and version-of identifiers do not identify this exact paper.
        selected = summaries[0]
        ids = self_ids(selected)
        citable = [item for item in ids if item.get("external-id-type", "").lower() in manubot_citable]
        citable.sort(key=lambda item: item.get("external-id-type", "").lower() != "doi")
        work_id = f"orcid:{orcid}/{selected['put-code']}"
        source = {"id": work_id, "orcid_work_id": work_id}
        if citable:
            item = citable[0]
            source["id"] = normalize_id(f"{item['external-id-type']}:{item['external-id-value']}")
        # Preserve metadata even for resolvable IDs: WOS may return a login page.
        source["title"] = get_safe(selected, "title.title.value", "") or ""
        source["publisher"] = get_safe(selected, "journal-title.value", "") or ""
        source["link"] = get_safe(selected, "url.value", "") or ""
        source["type"] = selected.get("type", "")
        year = get_safe(selected, "publication-date.year.value", "")
        month = get_safe(selected, "publication-date.month.value", "") or "1"
        day = get_safe(selected, "publication-date.day.value", "") or "1"
        source["date"] = format_date(f"{year}-{month}-{day}") if year else ""
        # Only use aliases from this summary; a group can include other versions.
        source["aliases"] = sorted({
            normalize_id(f"{item['external-id-type']}:{item['external-id-value']}")
            for item in ids if item.get("external-id-type")
        } - {source["id"]})
        if not source["link"]:
            source["link"] = next((get_safe(item, "external-id-url.value", "") for item in ids if get_safe(item, "external-id-url.value", "")), "")
        source.update(entry)
        sources.append(source)
    return sources
