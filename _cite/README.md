# Publication updates

Run from the repository root:

```sh
python -m pip install -r _cite/requirements.txt
python _cite/cite.py
python -m unittest discover -s _cite/tests -v
```

Google Scholar requires `GOOGLE_SCHOLAR_API_KEY` (SerpApi), supplied through the
environment or a local `.env` file. GitHub Actions uses the repository secret of
the same name. Never commit the key. `_data/google-scholar.yaml` controls profile,
language (`hl`), sort order, detail fetching, and optional `max_results`. Leave
`max_results` unset for a complete bibliography. Article pages cache for one day;
details and DOI metadata cache for seven days. `CITE_CACHE_DIR` can select a fresh
cache for troubleshooting without changing the existing cache.

## How matching works

- Normalize DOI casing, `doi:` prefixes, DOI URLs and URL encoding before matching.
- Match DOI, Scholar citation ID, ORCID work ID and recorded aliases first.
- Match exact normalized titles only with compatible publication years and no
  conflicting DOIs or preprint/published distinction. When both author lists are
  available, require a shared surname. Otherwise require a matching venue or a
  distinctive title (at least 40 letters/digits). Ambiguous matches stay separate.
- DOI metadata supplies bibliographic fields; Scholar supplies citation counts.
  Explicit `_data/sources.yaml` fields take precedence. Empty upstream values do
  not erase populated fields. Images and identifiers survive merging.
- Different DOIs with the same title stay separate and generate a warning. The
  page renders the reconciled records; it does not hide papers by title.

ORCID uses the summary with the highest `display-index` and only `self`
identifiers. `part-of` may identify an entire book/proceedings, and `version-of`
may identify a different version. Publication dates come from `publication-date`,
never the date someone edited their ORCID record. WOS records use ORCID summary
metadata instead of trying to cite a Web of Science login page.

## Failure handling and corrections

Provider errors and malformed/repeated pages fail the run without changing
`_data/citations.yaml`. Individual detail/DOI lookup failures retain available
metadata and generate warnings. Previously published records missing from a
successful fetch are also retained with warnings: upstream absence does not
automatically delete a paper. Output is written atomically only after validation.

Make corrections in `_data/sources.yaml`, not the generated citations file:

```yaml
- id: doi:10.1234/canonical
  title: Corrected title
  image: /images/paper/example.png
  # Use only after confirming these identify the same work/version.
  aliases:
    - author-id:scholar-citation-id
    - wosuid:WOS:123456789

- id: doi:10.1234/unwanted
  remove: true
```

Removal targets the final canonical `id`. An old removal rule for a duplicate
WOS/Scholar identifier will not delete the DOI publication when that identifier
has become an alias. To remove that publication, use its canonical DOI ID.
To deliberately consolidate different DOI versions, list the unwanted DOI ID in
the preferred manual record's `aliases`; this is never inferred from title alone.

Scheduled updates rebuild the site after committing changed citations. Site
builds check out the latest branch contents to include the generated commit.

References: [SerpApi author API](https://serpapi.com/google-scholar-author-api),
[ORCID grouping and preferred sources](https://info.orcid.org/ufaqs/how-are-items-grouped-together-in-an-orcid-record/).
