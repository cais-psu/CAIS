import os
import re
from serpapi import GoogleSearch
from util import *


DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
DOI_TRAILING_PATHS = ["/full"]


def clean_authors(authors):
    """
    convert scholar author strings into a list
    """
    return [author.strip() for author in authors.split(",") if author.strip()]


def format_publication_date(value):
    """
    convert scholar date strings like YYYY/MM/DD or YYYY/MM to YYYY-MM-DD
    """
    if not value:
        return ""
    parts = str(value).replace("-", "/").split("/")
    if not parts[0]:
        return ""
    year = parts[0]
    month = parts[1] if len(parts) > 1 and parts[1] else "1"
    day = parts[2] if len(parts) > 2 and parts[2] else "1"
    return f"{year}-{month}-{day}"


def find_doi(*values):
    """
    find a DOI in Scholar-provided text fields and links
    """
    for value in values:
        match = DOI_PATTERN.search(str(value or ""))
        if match:
            doi = match.group(0).rstrip(".,;)").lower()
            for suffix in DOI_TRAILING_PATHS:
                if doi.endswith(suffix):
                    doi = doi[: -len(suffix)]
            return doi
    return ""


def truthy(value):
    """
    parse YAML/env truthy values
    """
    return str(value).lower() in ["1", "true", "yes", "on"]


def main(entry):
    """
    receives single list entry from google-scholar data file
    returns list of sources to cite
    """

    # get api key (serp api key to access google scholar)
    api_key = os.environ.get("GOOGLE_SCHOLAR_API_KEY", "")
    if not api_key:
        raise Exception('No "GOOGLE_SCHOLAR_API_KEY" env var')

    # serp api properties
    params = {
        "engine": "google_scholar_author",
        "api_key": api_key,
        "num": 100,  # max allowed
        "hl": get_safe(entry, "hl", "en"),
    }
    sort = get_safe(entry, "sort", "")
    if sort:
        params["sort"] = sort

    # get id from entry
    _id = get_safe(entry, "gsid", "")
    if not _id:
        raise Exception('No "gsid" key')

    # query author articles api
    @log_cache
    @cache.memoize(name=__file__, expire=1 * (60 * 60 * 24))
    def query_articles(_id, start):
        query_params = params.copy()
        query_params["author_id"] = _id
        query_params["start"] = start
        return get_safe(GoogleSearch(query_params).get_dict(), "articles", [])

    # query individual article details api
    @log_cache
    @cache.memoize(name=f"{__file__}:citation", expire=7 * (60 * 60 * 24))
    def query_citation(citation_id):
        query_params = {
            "engine": "google_scholar_author",
            "api_key": api_key,
            "hl": get_safe(entry, "hl", "en"),
            "view_op": "view_citation",
            "citation_id": citation_id,
        }
        return get_safe(GoogleSearch(query_params).get_dict(), "citation", {})

    # get all pages of articles
    response = []
    start = 0
    page_size = params["num"]
    max_results = get_safe(entry, "max_results", None)
    while True:
        page = query_articles(_id, start)
        response.extend(page)
        if max_results and len(response) >= int(max_results):
            response = response[: int(max_results)]
            break
        if len(page) < page_size:
            break
        start += page_size

    fetch_details = truthy(get_safe(entry, "details", os.environ.get("GOOGLE_SCHOLAR_DETAILS", "")))

    # list of sources to return
    sources = []

    # go through response and format sources
    for work in response:
        citation_id = get_safe(work, "citation_id", "")
        details = query_citation(citation_id) if fetch_details and citation_id else {}

        # get details from article endpoint first, with list endpoint fallbacks
        title = get_safe(details, "title", "") or get_safe(work, "title", "")
        authors = clean_authors(get_safe(details, "authors", "") or get_safe(work, "authors", ""))
        publisher = (
            get_safe(details, "journal", "")
            or get_safe(details, "publisher", "")
            or get_safe(work, "publication", "")
        )
        link = get_safe(details, "link", "") or get_safe(work, "link", "")
        resource_links = [
            get_safe(resource, "link", "") for resource in get_safe(details, "resources", [])
        ]
        doi = find_doi(
            link,
            get_safe(work, "publication", ""),
            *resource_links,
        )
        year = get_safe(work, "year", "")
        date = format_publication_date(get_safe(details, "publication_date", ""))
        if not date and year:
            date = f"{year}-01-01"

        # create source
        source = {
            "id": f"doi:{doi}" if doi else citation_id,
            "scholar_id": citation_id,
            # api does not provide Manubot-citeable id, so keep citation details
            "title": title,
            "authors": authors,
            "publisher": publisher,
            "date": date,
            "link": link,
            "citation_count": get_safe(
                details,
                "total_citations.cited_by.total",
                get_safe(work, "cited_by.value", ""),
            ),
        }
        if doi:
            source["doi"] = doi
            source["DOI"] = doi
        if get_safe(details, "volume", ""):
            source["volume"] = get_safe(details, "volume", "")
        if get_safe(details, "issue", ""):
            source["issue"] = get_safe(details, "issue", "")
        if get_safe(details, "pages", ""):
            source["pages"] = get_safe(details, "pages", "")
        # copy public fields from entry to source
        for key, value in entry.items():
            if key not in ["details", "max_results", "sort", "hl"]:
                source[key] = value

        # add source to list
        sources.append(source)

    return sources
