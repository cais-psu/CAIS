import os
from urllib.parse import parse_qs, urlsplit
from serpapi import GoogleSearch
from util import *
from records import find_doi


def clean_authors(authors):
    """
    convert scholar author strings into a list
    """
    return [author.strip() for author in str(authors or "").split(",") if author.strip()]


def format_publication_date(value):
    """
    convert scholar date strings like YYYY/MM/DD or YYYY/MM to YYYY-MM-DD
    """
    return format_date(value) if value else ""


def truthy(value):
    """
    parse YAML/env truthy values
    """
    return str(value).lower() in ["1", "true", "yes", "on"]


def request_scholar(params, field):
    def request():
        try:
            # google-search-results 2.4 accepts only params_dict here. Its base
            # client reads the timeout attribute when issuing the HTTP request.
            client = GoogleSearch(params.copy())
            client.timeout = 30
            response = client.get_dict()
        except Exception as error:
            # HTTP exceptions may contain the API key in their request URL.
            # Report the exception type without exposing that URL or its key.
            raise RuntimeError(f"Google Scholar request failed ({type(error).__name__})") from None
        if response.get("error") or get_safe(response, "search_metadata.status", "Success") != "Success":
            message = str(response.get("error") or "Search did not complete")
            raise RuntimeError(f"Google Scholar API: {message.replace(params['api_key'], '[redacted]')}")
        value = response.get(field)
        valid = list_of_dicts(value) if field == "articles" else isinstance(value, dict) and bool(value.get("title"))
        if not valid:
            raise RuntimeError(f"Google Scholar response missing valid {field}")
        return response
    return retry_request(request)


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
    @cache.memoize(name="scholar:articles:v2", expire=1 * (60 * 60 * 24))
    def query_articles(_id, start, sort, language):
        query_params = params.copy()
        query_params["author_id"] = _id
        query_params["start"] = start
        return request_scholar(query_params, "articles")

    # query individual article details api
    @log_cache
    @cache.memoize(name="scholar:citation:v2", expire=7 * (60 * 60 * 24))
    def query_citation(citation_id, language):
        query_params = {
            "engine": "google_scholar_author",
            "api_key": api_key,
            "hl": get_safe(entry, "hl", "en"),
            "view_op": "view_citation",
            "citation_id": citation_id,
        }
        return request_scholar(query_params, "citation")["citation"]

    # get all pages of articles
    response = []
    start = 0
    page_size = params["num"]
    max_results = get_safe(entry, "max_results", None)
    if max_results is not None and int(max_results) <= 0:
        raise ValueError("max_results must be a positive integer")
    seen = set()
    while True:
        payload = query_articles(_id, start, sort, params["hl"])
        page = payload["articles"]
        added = 0
        for article in page:
            key = article.get("citation_id")
            if not key or not article.get("title"):
                raise RuntimeError("Google Scholar returned an article without citation_id or title")
            if key not in seen:
                seen.add(key)
                response.append(article)
                added += 1
        if page and not added:
            raise RuntimeError("Google Scholar repeated a page; refusing a partial update")
        if max_results and len(response) >= int(max_results):
            response = response[: int(max_results)]
            break
        next_url = get_safe(payload, "serpapi_pagination.next", "")
        if next_url:
            query = parse_qs(urlsplit(next_url).query)
            next_start = int((query.get("start") or query.get("cstart") or [start + len(page)])[0])
            if next_start <= start or not page:
                raise RuntimeError("Google Scholar returned invalid pagination")
            start = next_start
        elif len(page) < page_size:
            break
        else:
            start += len(page)

    fetch_details = truthy(get_safe(entry, "details", os.environ.get("GOOGLE_SCHOLAR_DETAILS", "")))

    # list of sources to return
    sources = []

    # go through response and format sources
    for work in response:
        citation_id = get_safe(work, "citation_id", "")
        details = {}
        detail_warning = ""
        if fetch_details and citation_id:
            try:
                details = query_citation(citation_id, params["hl"])
            except Exception as error:
                detail_warning = f"{citation_id}: {error}; using article-list metadata"

        # get details from article endpoint first, with list endpoint fallbacks
        title = get_safe(details, "title", "") or get_safe(work, "title", "")
        authors = clean_authors(get_safe(details, "authors", "") or get_safe(work, "authors", ""))
        publisher = (
            get_safe(details, "journal", "")
            or get_safe(details, "conference", "")
            or get_safe(details, "publisher", "")
            or get_safe(work, "publication", "")
        )
        link = get_safe(details, "link", "") or get_safe(work, "link", "")
        resource_links = [
            get_safe(resource, "link", "") for resource in get_safe(details, "resources", [])
        ]
        doi = find_doi(link, details.get("doi"), details.get("DOI"), work.get("doi"))
        if not doi:
            candidates = {find_doi(value) for value in resource_links} - {""}
            if len(candidates) == 1:
                doi = candidates.pop()
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
            source["_doi_inferred"] = True
        if detail_warning:
            source["_warnings"] = [detail_warning]
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
