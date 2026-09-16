import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from classify import classification, classify_citations


class ClassificationTests(unittest.TestCase):
    def category(self, **record):
        return classification(record)[0]

    def test_ieee_access_is_always_a_journal(self):
        for record in (
            {"publisher": "IEEE Access"},
            {"publisher": "IEEE Access", "type": "paper-conference"},
            {"id": "doi:10.1109/ACCESS.2022.3165551", "publisher": "IEEE"},
            {"publisher": "IEEE Access", "link": "https://arxiv.org/abs/2501.12345"},
        ):
            self.assertEqual(self.category(**record), "journal")

    def test_proceedings_series_override_registry_journal_type(self):
        for publisher in ("IFAC-PapersOnLine", "IFAC PAPERSONLINE", "Procedia Manufacturing", "Procedia CIRP"):
            self.assertEqual(self.category(publisher=publisher, type="article-journal"), "conference")
        self.assertEqual(self.category(id="doi:10.1016/J.IFACOL.2025.01.139", type="article-journal"), "conference")

    def test_conferences_and_books_have_distinct_signals(self):
        self.assertEqual(self.category(publisher="2026 Workshop on Discrete Event Systems (WODES)"), "conference")
        self.assertEqual(self.category(id="doi:10.1115/MSEC2025-155848", publisher="Volume 2: Energy"), "conference")
        self.assertEqual(self.category(type="book-chapter", publisher="Encyclopedia of Sustainable Technologies"), "other")
        self.assertEqual(self.category(type="book-chapter", publisher="Proceedings of a Robotics Conference"), "conference")
        self.assertEqual(self.category(type="book", publisher="Proceedings of a Robotics Conference"), "other")

    def test_publisher_names_and_random_urls_are_not_types(self):
        self.assertEqual(self.category(type="article-journal", publisher="Springer", link="https://publisher.org/bookmark/showcase"), "journal")
        self.assertTrue(classification({"publisher": "IEEE", "link": "https://ieeexplore.ieee.org/document/123"})[2])
        self.assertTrue(classification({"publisher": "Volume 2"})[2])

    def test_arxiv_metadata_cannot_be_mistaken_for_journals(self):
        self.assertEqual(self.category(type="journal-article", publisher="Arxiv"), "other")
        self.assertEqual(self.category(type="journal-article", id="wosuid:PPRN:123"), "other")
        self.assertEqual(self.category(type="article-journal", id="doi:10.48550/arXiv.2501.12345"), "other")
        self.assertEqual(self.category(link="https://arxiv.org/abs/2501.12345"), "other")

    def test_formal_publication_can_link_to_arxiv(self):
        self.assertEqual(self.category(type="paper-conference", publisher="IEEE", link="https://arxiv.org/abs/2501.12345"), "conference")
        self.assertEqual(self.category(type="article-journal", publisher="Some New Journal", link="https://arxiv.org/abs/2501.12345"), "journal")

    def test_manual_override_and_removing_override(self):
        rows = [{"id": "doi:10.1234/test", "aliases": ["scholar:abc"], "publisher": "IEEE Access", "category": "other"}]
        result = classify_citations(rows, [{"id": "scholar:abc", "category": "other"}])
        self.assertEqual(result[0]["category"], "other")
        self.assertEqual(result[0]["classification"]["basis"], "manual")
        self.assertEqual(classify_citations(result)[0]["category"], "journal")
        with self.assertRaises(ValueError):
            classify_citations(rows, [{"id": "scholar:abc", "category": "journla"}])

    def test_unknowns_are_preserved_for_review(self):
        messages = []
        rows = classify_citations([{"id": "unknown:1", "title": "A new contribution"}], warn=messages.append)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "other")
        self.assertTrue(rows[0]["classification"]["needs_review"])
        self.assertEqual(len(messages), 1)

    def test_topic_aliases_are_bidirectional_and_not_volume_topics(self):
        rows = classify_citations([
            {"title": "Large Language Models for Multi-Agent Systems"},
            {"title": "MPC for Digital Twins"},
            {"title": "Robotic Assembly", "publisher": "Volume 2: Model Predictive Control; Large Language Models"},
        ])
        self.assertIn("LLM", rows[0]["search_terms"])
        self.assertIn("多智能体", rows[0]["search_terms"])
        self.assertIn("model predictive control", rows[1]["search_terms"])
        self.assertIn("数字孪生", rows[1]["search_terms"])
        self.assertNotIn("MPC", rows[2]["search_terms"])
        self.assertNotIn("LLM", rows[2]["search_terms"])

    def test_reclassification_is_idempotent(self):
        rows = classify_citations([{"title": "LLM for Digital Twins", "publisher": "IEEE Access", "keywords": ["llm"]}])
        self.assertEqual(rows, classify_citations(rows))


if __name__ == "__main__":
    unittest.main()
