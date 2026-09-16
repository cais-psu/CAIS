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

## Publication categories

Classification runs after reconciliation and writes exactly one `category`:
`journal`, `conference`, or `other`. The research page uses this field directly.
Original `type` metadata is retained for reference.

The rules in `classify.py` use this order:

1. A reviewed `category` override in `_data/sources*.yaml`.
2. Specific identifiers and known publication series. IEEE Access and the IEEE
   journal DOI families are journals. IFAC-PapersOnLine, Procedia Manufacturing
   and Procedia CIRP are conference proceedings, even when registries label
   individual papers `article-journal`. arXiv/PPRN identifiers identify preprints.
3. Explicit publication types, then bounded venue patterns. A Springer publisher
   name, `Volume 2`, or an arbitrary URL substring does not establish a category.
   A link to an arXiv copy does not reclassify an identified journal/conference paper.
4. Unknown records stay in Other and emit a review warning. They are not removed.

Other includes books, book chapters, arXiv/other preprints, theses, technical
reports and miscellaneous records. The `classification` field records the rule
used and `needs_review`. This information is for maintenance, not website display.

To correct an exception, add its canonical ID or known alias to
`_data/sources-categories.yaml`:

```yaml
- id: doi:10.1234/example
  category: journal
```

Categories are recomputed on every run; generated values are never treated as
manual overrides. Removing the override restores automatic classification.
To review or update the existing data without API calls:

```sh
python _cite/classify.py          # print counts and records needing review
python _cite/classify.py --write  # update the generated data
```

The proceedings exceptions follow the publication series, rather than simply
copying registry type names. See [IFAC's proceedings description](https://ifac-control.org/publications/what-is-ifac-papersonline/).

## Publication keyword search

Search covers titles, full author lists, publication venues, dates, DOI and other
identifiers, aliases, tags and keywords. Common research abbreviations (LLM,
MPC, DES, PTA), full phrases and selected Chinese equivalents are generated in
`search_terms`. These expansions come from titles or explicit tags/keywords, not
from the many unrelated topics listed in a proceedings volume title.

All query words and quoted phrases must match. Case, accents, hyphens and extra
whitespace are normalized. Examples: `IEEE Access`, `LLM manufacturing`,
`"model predictive control" "energy aware"`, and `数字孪生`.
Tag queries also accept `tag:resource`, `tag:"digital twin"`, and existing
`"tag: digital-twin"` links. Clearing a search cancels pending input work and
preserves unrelated URL parameters and anchors. Empty publication groups are
hidden while searching, with visible/total counts shown for remaining groups.

DOM tests render the actual Liquid research and citation templates with the
checked-in data. They run in CI alongside the Python regression tests. To run
them locally with Node 22+ (Python also needs PyYAML):

```sh
npm install --prefix /tmp/cais-search-tests jsdom@26 liquidjs@10 --no-audit --no-fund
NODE_PATH=/tmp/cais-search-tests/node_modules node --test _cite/tests/search.test.cjs
```

These tests cover the templates and DOM interaction; they do not replace a full
Jekyll build or browser layout review.
