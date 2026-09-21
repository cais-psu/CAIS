"""Offline regression tests: no API keys, network or production-cache writes."""
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from requests.exceptions import Timeout

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
CACHE = tempfile.TemporaryDirectory()
os.environ['CITE_CACHE_DIR'] = CACHE.name
import cite
import util
from errors import ScholarQuotaError
from records import find_doi, normalize_record, reconcile, reconcile_update
scholar = importlib.import_module('plugins.google-scholar')
orcid = importlib.import_module('plugins.orcid')


def paper(identifier='doi:10.1234/example', **fields):
    return dict(id=identifier, title='Control of manufacturing systems', date='2025-08-17', authors=['Ilya Kovalenko'], publisher='IEEE Conference', **fields)


class RecordsTests(unittest.TestCase):
    def test_doi_url_case_encoding(self):
        result = reconcile([paper('DOI:10.1234/EXAMPLE'), {'id': 'https://doi.org/10.1234%2Fexample', 'image': 'manual.png'}])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 'doi:10.1234/example')
        self.assertEqual(result[0]['DOI'], '10.1234/example')
        self.assertEqual(result[0]['image'], 'manual.png')

    def test_doi_parentheses_and_routes(self):
        self.assertEqual(find_doi('https://publisher.org/doi/10.1002/(SICI)123/full?x=1'), '10.1002/(sici)123')
        self.assertEqual(find_doi('(doi:10.1234/abc(foo)).'), '10.1234/abc(foo)')
        self.assertEqual(find_doi('https://x.org/doi/pdf/10.1234/ABC%282%29'), '10.1234/abc(2)')

    def test_conflicting_fields_rejected(self):
        with self.assertRaises(ValueError):
            normalize_record({'id': 'doi:10.1234/a', 'DOI': '10.1234/b'})

    def test_scholar_orcid_title_match_keeps_fields(self):
        a = paper('author:abc', scholar_id='author:abc', citation_count=7)
        a['authors'] = ['I Kovalenko']
        a['title'] = 'Control of Manufacturing Systems.'
        b = paper(orcid='0000-test')
        result = reconcile([a, b, {'id': 'doi:10.1234/EXAMPLE', 'image': 'image.png'}])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['citation_count'], 7)
        self.assertEqual(result[0]['image'], 'image.png')
        self.assertIn('author:abc', result[0]['aliases'])

    def test_same_title_different_dois_not_merged(self):
        self.assertEqual(len(reconcile([paper('doi:10.1234/a'), paper('doi:10.1234/b')])), 2)

    def test_title_match_requires_metadata(self):
        self.assertEqual(len(reconcile([paper(), {'id': 'other', 'title': 'Control of manufacturing systems'}])), 2)
        b = paper('other'); b['authors'] = ['Someone Else']
        self.assertEqual(len(reconcile([paper(), b])), 2)

    def test_ambiguous_scholar_cannot_bridge_two_dois(self):
        rows = [paper('author:abc'), paper('doi:10.1234/a'), paper('doi:10.1234/b')]
        self.assertEqual(len(reconcile(rows)), 3)

    def test_preprint_and_published_version_kept(self):
        a = paper('author:abc', link='https://arxiv.org/abs/2501.12345')
        self.assertEqual(len(reconcile([a, paper()])), 2)

    def test_upstream_doi_conflict_reported(self):
        messages = []
        rows = [paper('doi:10.1234/a', scholar_id='author:abc'), paper('doi:10.1234/b', scholar_id='author:abc')]
        self.assertEqual(len(reconcile(rows, messages.append)), 2)
        self.assertTrue(messages)

    def test_id_only_record_cannot_bridge_conflicting_dois(self):
        rows = [paper('doi:10.1234/a', scholar_id='author:abc'), paper('doi:10.1234/b', scholar_id='author:abc'), paper('author:abc', scholar_id='author:abc')]
        self.assertEqual(len(reconcile(rows)), 3)

    def test_explicit_manual_alias_can_resolve_doi_conflict(self):
        result = reconcile([paper('doi:10.1234/a'), paper('doi:10.1234/b'), {'id': 'doi:10.1234/a', 'aliases': ['DOI:10.1234/B'], 'plugin': 'sources.py'}])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 'doi:10.1234/a')
        self.assertEqual(reconcile_update(result, [], []), result)

    def test_overlapping_title_candidates_do_not_duplicate_records(self):
        a, b, c = paper('a'), paper('b'), paper('c')
        a['date'], b['date'], c['date'] = '2023-01-01', '2024-01-01', '2025-01-01'
        self.assertEqual(len(reconcile([a, b, c])), 3)

    def test_missing_record_retained_and_remove_respected(self):
        old = [paper(), paper('doi:10.1234/old')]
        messages = []
        result = reconcile_update(old, [paper(citation_count=10)], [], messages.append)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['citation_count'], 10)
        self.assertTrue(messages)
        result = reconcile_update(result, [], [{'id': 'DOI:10.1234/OLD', 'remove': True}])
        self.assertEqual(len(result), 1)

    def test_duplicate_removal_does_not_remove_canonical_doi(self):
        old = reconcile([paper('author:abc', scholar_id='author:abc'), paper()])
        self.assertEqual(len(reconcile_update(old, [], [{'id': 'author:abc', 'remove': True}])), 1)
        self.assertEqual(reconcile_update(old, [], [{'id': 'doi:10.1234/example', 'remove': True}]), [])

    def test_idempotent_update(self):
        current = [paper('author:abc', scholar_id='author:abc'), paper()]
        once = reconcile_update([], current, [])
        self.assertEqual(reconcile_update(once, current, []), once)


class ScholarTests(unittest.TestCase):
    def setUp(self):
        util.cache.clear()
        self.env = patch.dict(os.environ, {'GOOGLE_SCHOLAR_API_KEY': 'test-only', 'GOOGLE_SCHOLAR_DETAILS': ''})
        self.env.start()
        self.sleep = patch('util.time.sleep'); self.sleep.start()
    def tearDown(self):
        self.env.stop(); self.sleep.stop()

    def article(self, suffix):
        return {'citation_id': f'author:{suffix}', 'title': f'Paper {suffix}', 'year': '2025'}

    def test_real_client_fetches_articles_and_details_with_timeout(self):
        # Keep the installed SerpApi constructor and JSON parsing in the test;
        # mock only HTTP so unsupported client arguments cannot slip through.
        payloads = [
            {'articles': [self.article('a')]},
            {'citation': {'title': 'Paper a', 'authors': 'Ilya Kovalenko', 'publication_date': '2025/08/17'}},
        ]
        with patch('serpapi.serp_api_client.requests.get') as http:
            http.side_effect = [SimpleNamespace(text=json.dumps(payload)) for payload in payloads]
            result = scholar.main({'gsid': 'author', 'details': True})
        self.assertEqual(result[0]['authors'], ['Ilya Kovalenko'])
        self.assertEqual(result[0]['date'], '2025-08-17')
        self.assertNotIn('_warnings', result[0])
        self.assertEqual(http.call_count, 2)
        for call in http.call_args_list:
            self.assertEqual(call.kwargs['timeout'], 30)
            self.assertEqual(call.args[1]['engine'], 'google_scholar_author')
            self.assertNotIn('timeout', call.args[1])
        self.assertEqual(http.call_args_list[0].args[1]['author_id'], 'author')
        self.assertEqual(http.call_args_list[1].args[1]['view_op'], 'view_citation')

    def test_real_timeout_is_identified_without_exposing_api_key(self):
        with patch('serpapi.serp_api_client.requests.get', side_effect=Timeout('request URL contains api_key=test-only')) as http:
            with self.assertRaises(RuntimeError) as caught:
                scholar.main({'gsid': 'author'})
        self.assertIn('Timeout', str(caught.exception))
        self.assertNotIn('test-only', str(caught.exception))
        self.assertEqual(http.call_count, 3)

    def test_short_page_with_next_is_followed_and_duplicates_removed(self):
        responses = [{'articles': [self.article('a'), self.article('b')], 'serpapi_pagination': {'next': 'https://serpapi.com/search?start=2'}}, {'articles': [self.article('b'), self.article('c')]}]
        with patch.object(scholar, 'GoogleSearch', autospec=True) as search:
            search.return_value.get_dict.side_effect = responses
            result = scholar.main({'gsid': 'author'})
            self.assertEqual(len(result), 3)
            self.assertEqual(search.call_args_list[1].args[0]['start'], 2)

    def test_api_error_not_cached_as_empty(self):
        with patch.object(scholar, 'GoogleSearch', autospec=True) as search:
            search.return_value.get_dict.return_value = {'error': 'quota exceeded'}
            with self.assertRaises(RuntimeError): scholar.main({'gsid': 'author'})
            search.return_value.get_dict.return_value = {'articles': [self.article('a')]}
            self.assertEqual(len(scholar.main({'gsid': 'author'})), 1)
            self.assertEqual(search.call_count, 2)

    def test_quota_is_decoded_redacted_and_not_retried(self):
        with patch.object(scholar, 'GoogleSearch', autospec=True) as search:
            search.return_value.get_dict.return_value = {'error': 'Your account has run out of&#x20;\nsearches. key=test-only'}
            with self.assertRaises(ScholarQuotaError) as caught:
                scholar.main({'gsid': 'author'})
        self.assertEqual(search.call_count, 1)
        self.assertIn('run out of searches', str(caught.exception))
        self.assertNotIn('test-only', str(caught.exception))
        self.assertIn('[redacted]', str(caught.exception))

    def test_pagination_quota_does_not_return_partial_profile(self):
        with patch.object(scholar, 'GoogleSearch', autospec=True) as search:
            search.return_value.get_dict.side_effect = [
                {'articles': [self.article('a')], 'serpapi_pagination': {'next': 'https://serpapi.com/search?start=1'}},
                {'error': 'Your account has run out of searches.'},
            ]
            with self.assertRaises(ScholarQuotaError):
                scholar.main({'gsid': 'author'})
        self.assertEqual(search.call_count, 2)

    def test_detail_quota_stops_remaining_detail_requests(self):
        with patch.object(scholar, 'GoogleSearch', autospec=True) as search:
            search.return_value.get_dict.side_effect = [
                {'articles': [self.article('a'), self.article('b')]},
                {'error': 'Your account has run out of searches.'},
            ]
            result = scholar.main({'gsid': 'author', 'details': True})
        self.assertEqual(search.call_count, 2)
        self.assertEqual([row['title'] for row in result], ['Paper a', 'Paper b'])
        self.assertIn('stopped detail requests', result[0]['_warnings'][0])

    def test_cached_details_do_not_override_newer_list_citation_count(self):
        with patch.object(scholar, 'GoogleSearch', autospec=True) as search:
            search.return_value.get_dict.side_effect = [
                {'articles': [{**self.article('a'), 'cited_by': {'value': 8}}]},
                {'citation': {'title': 'Paper a', 'journal': 'IEEE Access', 'total_citations': {'cited_by': {'total': 7}}}},
                {'articles': [{**self.article('a'), 'cited_by': {'value': 10}}]},
            ]
            first = scholar.main({'gsid': 'author', 'details': True})
            self.assertEqual(scholar.main({'gsid': 'author', 'details': True}), first)
            # Another sort requires a fresh list but can reuse the same details.
            second = scholar.main({'gsid': 'author', 'sort': 'pubdate', 'details': True})
        self.assertEqual(search.call_count, 3)
        self.assertEqual(first[0]['citation_count'], 8)
        self.assertEqual(second[0]['citation_count'], 10)
        self.assertEqual(second[0]['publisher'], 'IEEE Access')

    def test_repeated_page_fails(self):
        payload = {'articles': [self.article('a')], 'serpapi_pagination': {'next': 'https://serpapi.com/search?start=1'}}
        with patch.object(scholar, 'GoogleSearch', autospec=True) as search:
            search.return_value.get_dict.return_value = payload
            with self.assertRaises(RuntimeError): scholar.main({'gsid': 'author'})

    def test_detail_failure_preserves_article(self):
        with patch.object(scholar, 'GoogleSearch', autospec=True) as search:
            search.return_value.get_dict.side_effect = [{'articles': [self.article('a')]}, {'error': 'temporary'}, {'error': 'temporary'}, {'error': 'temporary'}]
            result = scholar.main({'gsid': 'author', 'details': True})
            self.assertEqual(result[0]['title'], 'Paper a')
            self.assertTrue(result[0]['_warnings'])

    def test_sort_and_language_are_part_of_cache_key(self):
        with patch.object(scholar, 'GoogleSearch', autospec=True) as search:
            search.return_value.get_dict.return_value = {'articles': [self.article('a')]}
            scholar.main({'gsid': 'author'})
            scholar.main({'gsid': 'author', 'sort': 'pubdate'})
            scholar.main({'gsid': 'author', 'hl': 'zh'})
            self.assertEqual(search.call_count, 3)

    def test_missing_articles_is_error(self):
        with patch.object(scholar, 'GoogleSearch', autospec=True) as search:
            search.return_value.get_dict.return_value = {'search_metadata': {'status': 'Success'}}
            with self.assertRaises(RuntimeError): scholar.main({'gsid': 'author'})


class OrcidTests(unittest.TestCase):
    def summary(self, identifier, relationship='self', rank='1'):
        return {'put-code': rank, 'display-index': rank, 'title': {'title': {'value': 'Actual paper'}}, 'publication-date': {'year': {'value': '2020'}, 'month': {'value': '3'}}, 'external-ids': {'external-id': [{'external-id-type': 'doi', 'external-id-value': identifier, 'external-id-relationship': relationship}]}}

    def test_preferred_self_identifier_and_publication_date(self):
        summaries = [self.summary('10.1234/unpreferred'), self.summary('https://doi.org/10.1234/PREFERRED', rank='10')]
        with patch.object(orcid, 'query', return_value=[{'work-summary': summaries}]):
            result = orcid.main({'orcid': 'test'})[0]
        self.assertEqual(result['id'], 'doi:10.1234/preferred')
        self.assertEqual(result['date'], '2020-03-01')
        self.assertEqual(result['title'], 'Actual paper')

    def test_parent_and_version_doi_not_used(self):
        for relationship in ['part-of', 'version-of']:
            with patch.object(orcid, 'query', return_value=[{'work-summary': [self.summary('10.1234/parent', relationship)]}]):
                result = orcid.main({'orcid': 'test'})[0]
            self.assertEqual(result['id'], 'orcid:test/1')
            self.assertEqual(result['aliases'], [])

    def test_missing_date_does_not_use_record_modified_date(self):
        summary = self.summary('10.1234/abc'); summary['publication-date'] = None
        with patch.object(orcid, 'query', return_value=[{'work-summary': [summary], 'last-modified-date': {'value': 1700000000000}}]):
            self.assertEqual(orcid.main({'orcid': 'test'})[0]['date'], '')


class PipelineTests(unittest.TestCase):
    def test_quota_preserves_scholar_and_updates_orcid_and_manual_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / '_data').mkdir()
            output = root / '_data/citations.yaml'
            old = paper(scholar_id='author:old', citation_count=42, image='old.png')
            orphan = {**paper('author:only'), 'scholar_id': 'author:only', 'title': 'Scholar-only research'}
            new = {**paper('doi:10.1234/new'), 'title': 'New ORCID research'}
            util.save_data(output, [old, orphan])
            (root / '_data/google-scholar.yaml').write_text('- gsid: author\n')
            (root / '_data/orcid.yaml').write_text('- orcid: test\n')
            (root / '_data/sources.yaml').write_text('- id: doi:10.1234/example\n  image: updated.png\n')
            with patch.object(scholar, 'main', side_effect=ScholarQuotaError('search credits exhausted')), \
                    patch.object(orcid, 'main', return_value=[new]), \
                    patch.object(cite, 'cite_with_manubot', side_effect=lambda identifier: new if identifier == new['id'] else paper()), \
                    patch.object(cite, 'log') as log:
                self.assertEqual(cite.run(root), 0)
            rows = {row['id']: row for row in util.load_data(output)}
            self.assertEqual(set(rows), {old['id'], orphan['id'], new['id']})
            self.assertEqual(rows[old['id']]['citation_count'], 42)
            self.assertEqual(rows[old['id']]['image'], 'updated.png')
            self.assertEqual(rows[orphan['id']]['title'], orphan['title'])
            self.assertTrue(any('retaining saved Scholar records' in str(call) for call in log.call_args_list))

    def test_quota_without_saved_profile_still_fails_atomically(self):
        for previous in ([], [paper(scholar_id='different-author:old')]):
            with self.subTest(previous=previous), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); (root / '_data').mkdir()
                output = root / '_data/citations.yaml'
                util.save_data(output, previous); before = output.read_bytes()
                (root / '_data/google-scholar.yaml').write_text('- gsid: author\n')
                with patch.object(scholar, 'main', side_effect=ScholarQuotaError('search credits exhausted')):
                    self.assertEqual(cite.run(root), 1)
                self.assertEqual(output.read_bytes(), before)

    def test_push_mode_uses_saved_profile_and_bootstraps_missing_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / '_data').mkdir()
            output = root / '_data/citations.yaml'
            util.save_data(output, [paper(scholar_id='author:old', citation_count=42)])
            (root / '_data/google-scholar.yaml').write_text('- gsid: author\n- gsid: new-author\n')
            imported = {**paper('new-author:new'), 'title': 'New author research', 'scholar_id': 'new-author:new'}
            with patch.object(scholar, 'main', return_value=[imported]) as fetch:
                self.assertEqual(cite.run(root, skip_scholar=True), 0)
                fetch.assert_called_once_with({'gsid': 'new-author'})
            rows = util.load_data(output)
            self.assertEqual(len(rows), 2)
            with patch.object(scholar, 'main', return_value=[]) as fetch:
                self.assertEqual(cite.run(root), 0)
                self.assertEqual(fetch.call_count, 2)

    def test_saved_profile_can_be_identified_after_alias_merge(self):
        self.assertTrue(cite.has_saved_scholar([paper(aliases=['author:old'])], {'gsid': 'author'}))
        self.assertTrue(cite.has_saved_scholar([paper(gsid='author')], {'gsid': 'author'}))
        self.assertFalse(cite.has_saved_scholar([paper(aliases=['another:old'])], {'gsid': 'author'}))

    def test_reimported_arxiv_is_removed_after_retaining_published_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / '_data').mkdir()
            output = root / '_data/citations.yaml'
            published = paper(image='manual.png', citation_count=42)
            preprint = {**paper('author:arxiv'), 'publisher': 'arXiv',
                        'scholar_id': 'author:arxiv', 'type': 'journal-article'}
            util.save_data(output, [published, preprint])
            (root / '_data/google-scholar.yaml').write_text('- gsid: author\n')
            with patch.object(scholar, 'main', return_value=[preprint]), patch.object(cite, 'cite_with_manubot') as resolver:
                self.assertEqual(cite.run(root), 0)
                once = output.read_bytes()
                self.assertEqual(cite.run(root), 0)
                self.assertEqual(output.read_bytes(), once)
                resolver.assert_not_called()
            rows = util.load_data(output)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['id'], published['id'])
            self.assertEqual(rows[0]['image'], 'manual.png')
            self.assertEqual(rows[0]['citation_count'], 42)
            self.assertNotIn(preprint['id'], rows[0].get('aliases', []))

    def test_manual_category_on_scholar_record_uses_saved_metadata(self):
        old = paper('author:abc', scholar_id='author:abc', plugin='google-scholar.py')
        with patch.object(cite, 'cite_with_manubot') as resolver:
            result = cite.enrich({'id': 'author:abc', 'category': 'other', 'plugin': 'sources.py'}, [old], lambda _: None)
            resolver.assert_not_called()
        self.assertEqual(result['category'], 'other')

    def test_category_override_is_applied_after_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / '_data').mkdir()
            output = root / '_data/citations.yaml'
            old = paper('author:abc', scholar_id='author:abc', plugin='google-scholar.py')
            util.save_data(output, [old])
            (root / '_data/sources-categories.yaml').write_text('- id: author:abc\n  category: other\n')
            with patch.object(cite, 'cite_with_manubot') as resolver:
                self.assertEqual(cite.run(root), 0)
                resolver.assert_not_called()
            rows = util.load_data(output)
            self.assertEqual(rows[0]['category'], 'other')
            self.assertEqual(rows[0]['classification']['basis'], 'manual')
            self.assertEqual(rows[0]['title'], old['title'])

    def test_resolver_failure_keeps_metadata(self):
        with patch.object(cite, 'cite_with_manubot', side_effect=RuntimeError('offline')):
            result = cite.enrich(paper(plugin='orcid.py'), [], lambda _: None)
        self.assertEqual(result['title'], 'Control of manufacturing systems')

    def test_wos_uses_summary_without_resolver(self):
        with patch.object(cite, 'cite_with_manubot') as resolver:
            result = cite.enrich(paper('wosuid:WOS:123', plugin='orcid.py'), [], lambda _: None)
            resolver.assert_not_called()
        self.assertNotEqual(result['title'], 'Web of Science')

    def test_wrong_inferred_doi_rejected(self):
        row = paper(scholar_id='author:abc', plugin='google-scholar.py', _doi_inferred=True)
        with patch.object(cite, 'cite_with_manubot', return_value={'title': 'Unrelated economics article'}):
            result = cite.enrich(row, [], lambda _: None)
        self.assertEqual(result['id'], 'author:abc')
        self.assertNotIn('doi', result)

    def test_metadata_priority_and_empty_fields(self):
        row = paper(plugin='google-scholar.py'); row['authors'] = []; row['date'] = '2025-01-01'
        with patch.object(cite, 'cite_with_manubot', return_value=paper()):
            result = cite.enrich(row, [], lambda _: None)
        self.assertEqual(result['authors'], ['Ilya Kovalenko'])
        self.assertEqual(result['date'], '2025-08-17')
        row['plugin'] = 'sources.py'; row['title'] = 'Manual corrected title'
        with patch.object(cite, 'cite_with_manubot', return_value=paper()):
            self.assertEqual(cite.enrich(row, [], lambda _: None)['title'], row['title'])

    def test_failed_provider_does_not_write_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / '_data').mkdir()
            output = root / '_data/citations.yaml'
            util.save_data(output, [paper()]); before = output.read_bytes()
            (root / '_data/google-scholar.yaml').write_text('- gsid: author\n')
            with patch.object(scholar, 'main', side_effect=RuntimeError('quota')):
                self.assertEqual(cite.run(root), 1)
            self.assertEqual(output.read_bytes(), before)

    def test_partial_fetch_preserves_previous_and_manual_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / '_data').mkdir()
            output = root / '_data/citations.yaml'
            util.save_data(output, [paper(), paper('doi:10.1234/older')])
            (root / '_data/sources.yaml').write_text('- id: doi:10.1234/EXAMPLE\n  title: Manual title\n- id: doi:10.1234/example\n  image: test.png\n')
            with patch.object(cite, 'cite_with_manubot', return_value=paper()):
                self.assertEqual(cite.run(root), 0)
                once = output.read_bytes()
                self.assertEqual(cite.run(root), 0)
            self.assertEqual(output.read_bytes(), once)
            rows = util.load_data(output)
            self.assertEqual(len(rows), 2)
            manual = next(row for row in rows if row['id'] == 'doi:10.1234/example')
            self.assertEqual(manual['title'], 'Manual title')
            self.assertEqual(manual['image'], 'test.png')


if __name__ == '__main__':
    unittest.main()
