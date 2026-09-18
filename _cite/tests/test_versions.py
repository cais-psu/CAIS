"""Regression coverage for the website's preference for published versions."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from classify import classify_citations, remove_superseded_arxiv


class PublicationVersionTests(unittest.TestCase):
    title = "Multi-Agent Control & Manufacturing"

    def published(self, **fields):
        return {"id": "doi:10.1234/published", "title": self.title,
                "type": "article-journal", "publisher": "Example Journal", **fields}

    def select(self, rows, report=lambda _: None):
        return remove_superseded_arxiv(classify_citations(rows), report)

    def test_arxiv_identifiers_venues_and_links_are_removed(self):
        versions = [
            {"id": "arXiv:2501.12345v2"},
            {"id": "https://doi.org/10.48550/arXiv.2501.12345"},
            {"id": "wosuid:PPRN:123", "publisher": "Arxiv", "type": "journal-article"},
            {"id": "scholar:abc", "publisher": "arXiv preprint arXiv:2501.12345"},
            {"id": "scholar:def", "link": "https://arxiv.org/abs/2501.12345"},
            {"id": "scholar:ghi", "type": "preprint", "link": "https://export.arxiv.org/pdf/2501.12345"},
        ]
        for version in versions:
            with self.subTest(version=version):
                preprint = {"title": self.title, **version}
                for published in (self.published(), self.published(type="paper-conference", publisher="Example Conference")):
                    messages = []
                    for rows in ([preprint, published], [published, preprint]):
                        self.assertEqual(self.select(rows, messages.append), classify_citations([published]))
                    self.assertEqual(len(messages), 2)
                    self.assertIn(version["id"], messages[0])
                    self.assertIn(published["id"], messages[0])

    def test_normalized_full_title_matches_without_year_or_author_requirement(self):
        preprint = {"id": "arxiv:2501.12345", "title": "<i>MULTI AGENT</i> control &amp; manufacturing!", "date": "2025-01-01"}
        published = self.published(date="2020-01-01", authors=["Ilya Kovalenko"])
        self.assertEqual(self.select([preprint, published]), classify_citations([published]))

    def test_arxiv_only_and_different_titles_remain(self):
        preprint = {"id": "arxiv:2501.12345", "title": self.title}
        self.assertEqual(self.select([preprint]), classify_citations([preprint]))
        for title in (self.title + ": An Extension", "Different research", "", "Web of Science"):
            rows = [self.published(title=title), {**preprint, "title": title} if title in ("", "Web of Science") else preprint]
            self.assertEqual(self.select(rows), classify_citations(rows))

    def test_books_and_non_arxiv_preprints_do_not_trigger_removal(self):
        rows = [
            {"id": "arxiv:2501.12345", "title": self.title},
            {"id": "isbn:123", "title": self.title, "type": "book"},
        ]
        self.assertEqual(self.select(rows), classify_citations(rows))
        rows = [self.published(),
                {"id": "doi:10.22541/au.123/v1", "title": self.title, "type": "manuscript"},
                {"id": "wosuid:PPRN:456", "title": self.title, "publisher": "bioRxiv"},
                {"id": "scholar:x", "title": self.title, "link": "https://example.org/arxiv/2501.12345"},
                {"id": "isbn:123", "title": self.title, "type": "book", "link": "https://arxiv.org/abs/2501.12345"}]
        self.assertEqual(self.select(rows), classify_citations(rows))

    def test_published_arxiv_mirrors_aliases_and_metadata_are_preserved(self):
        rows = classify_citations([
            self.published(link="https://arxiv.org/abs/2501.12345", aliases=["arxiv:2501.12345"], image="manual.png", citation_count=42),
            self.published(id="doi:10.1234/conference", type="paper-conference", publisher="Example Conference"),
            {"id": "arxiv:2501.12345", "title": self.title, "image": "preprint.png", "citation_count": 99},
        ])
        before = deepcopy(rows)
        result = remove_superseded_arxiv(rows)
        self.assertEqual(result, before[:2])
        self.assertEqual(rows, before)
        self.assertEqual(remove_superseded_arxiv(result), result)


if __name__ == "__main__":
    unittest.main()
