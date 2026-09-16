const { test, before } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');
const { renderResearch, root } = require('./render-research.cjs');
const script = fs.readFileSync(path.join(root, '_scripts/search.js'), 'utf8');
let rendered;
before(async () => { rendered = await renderResearch(); });
const accessCount = () => rendered.citations.filter((row) => row.publisher?.toLowerCase() === 'ieee access').length;

async function page(t, body = rendered.body, url = 'https://www.caislab.com/research/') {
  const dom = new JSDOM(body, { url, runScripts: 'outside-only' });
  t.after(() => dom.window.close());
  dom.window.eval(script);
  await new Promise((resolve) => dom.window.addEventListener('load', resolve, { once: true }));
  return dom.window;
}
function query(window, text) {
  const url = new URL(window.location.href);
  url.searchParams.set('search', text);
  window.history.replaceState(null, '', url);
  window.dispatchEvent(new window.PopStateEvent('popstate'));
}
function visible(window) {
  return [...window.document.querySelectorAll('.citation-container')].filter((row) => !row.hidden);
}

test('real templates render every publication exactly once in three groups', async (t) => {
  const w = await page(t);
  assert.equal(w.document.querySelectorAll('[data-publication-group]').length, 3);
  assert.equal(visible(w).length, rendered.citations.length);
  for (const category of ['journal', 'conference', 'other']) {
    const group = w.document.querySelector(`[data-publication-group="${category}"]`);
    assert.equal(group.querySelectorAll('.citation').length, rendered.citations.filter((row) => row.category === category).length);
  }
  assert.equal(new Set([...w.document.querySelectorAll('.citation-id')].map((row) => row.textContent.trim())).size, rendered.citations.length);
});

test('IEEE Access finds its papers in journals; empty groups are hidden', async (t) => {
  const w = await page(t);
  query(w, 'IEEE Access');
  const rows = visible(w);
  assert.ok(accessCount() > 0);
  assert.equal(rows.length, accessCount());
  assert.ok(rows.every((row) => row.closest('[data-publication-group]').dataset.publicationGroup === 'journal'));
  assert.ok(w.document.querySelector('[data-publication-group="conference"]').hidden);
  assert.ok(w.document.querySelector('[data-publication-group="other"]').hidden);
  assert.ok(w.document.querySelector('.search-info').textContent.includes(`Showing ${accessCount()} of`));
});

test('LLM and MPC abbreviations find full-name titles', async (t) => {
  const w = await page(t);
  for (const [short, full] of [['LLM', 'Large Language Model'], ['MPC', 'Model Predictive Control']]) {
    query(w, short);
    assert.ok(visible(w).some((row) => row.querySelector('.citation-title').textContent.toLowerCase().includes(full.toLowerCase())));
  }
  query(w, '数字孪生');
  assert.ok(visible(w).some((row) => /digital twin/i.test(row.textContent)));
});

test('multi-word, hyphenated and quoted searches match predictably', async (t) => {
  const w = await page(t);
  query(w, 'multi-agent');
  const ids = visible(w).map((row) => row.querySelector('.citation-id').textContent);
  query(w, 'multi agent');
  assert.deepEqual(visible(w).map((row) => row.querySelector('.citation-id').textContent), ids);
  query(w, '“model predictive control” “energy aware”');
  assert.ok(visible(w).length > 0);
  assert.ok(visible(w).every((row) => /model predictive control/i.test(row.textContent) && /energy.aware/i.test(row.textContent)));
});

test('all authors, DOI and alias identifiers are searchable', async (t) => {
  const w = await page(t);
  const record = rendered.citations.find((row) => row.doi && row.aliases?.length && row.authors?.length);
  for (const term of [record.doi.toUpperCase(), record.aliases[0], record.authors[record.authors.length - 1]]) {
    query(w, term);
    assert.ok(visible(w).some((row) => row.querySelector('.citation-id').textContent.trim() === record.id), term);
  }
});

test('hidden papers return when the query is replaced or cleared', async (t) => {
  const w = await page(t);
  query(w, 'definitely-no-matching-publication');
  assert.equal(visible(w).length, 0);
  assert.match(w.document.querySelector('.search-info').textContent, /No matches/);
  query(w, 'IEEE Access');
  assert.equal(visible(w).length, accessCount());
  w.onSearchClear();
  assert.equal(visible(w).length, rendered.citations.length);
  assert.equal(new URL(w.location.href).searchParams.has('search'), false);
  assert.ok([...w.document.querySelectorAll('[data-publication-group]')].every((group) => !group.hidden));
});

test('clear and Escape cancel a pending input search and preserve other URL state', async (t) => {
  const w = await page(t, rendered.body, 'https://www.caislab.com/research/?keep=1#conference-papers');
  const input = w.document.querySelector('.search-input');
  for (const clear of [() => w.onSearchClear(), () => input.dispatchEvent(new w.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))]) {
    input.value = 'IEEE Access';
    w.onSearchInput(input);
    clear();
    await new Promise((resolve) => w.setTimeout(resolve, 200));
    assert.equal(input.value, '');
    assert.equal(visible(w).length, rendered.citations.length);
    assert.equal(w.location.search, '?keep=1');
    assert.equal(w.location.hash, '#conference-papers');
  }
});

test('tag syntax supports old links and works for project cards', async (t) => {
  const w = await page(t, '<div class="card" id="first">Robot <a class="tag">digital-twin</a></div><div class="card" id="second">Other</div>');
  for (const term of ['"tag: digital-twin"', 'tag:digital-twin', 'tag:"digital twin"']) {
    query(w, term);
    assert.equal(w.document.querySelector('#first').hidden, false);
    assert.equal(w.document.querySelector('#second').hidden, true);
  }
});

test('GitHub tags can load without data-link and create encoded search URLs', async (t) => {
  const w = await page(t, '<div class="card"><div class="tags" data-repo="org/repo"></div></div>');
  w.fetch = async () => ({ json: async () => ({ names: ['digital twin'] }) });
  const done = new Promise((resolve) => w.addEventListener('tagsfetched', resolve, { once: true }));
  w.eval(fs.readFileSync(path.join(root, '_scripts/fetch-tags.js'), 'utf8'));
  w.dispatchEvent(new w.Event('load'));
  await done;
  const link = w.document.querySelector('.tag');
  assert.equal(new URL(link.href).pathname, '/research/');
  assert.equal(new URL(link.href).searchParams.get('search'), 'tag:"digital twin"');
});
