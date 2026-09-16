// Render the actual research/citation templates with Liquid's Jekyll include mode.
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { Liquid } = require('liquidjs');
const root = path.resolve(__dirname, '../..');

async function renderResearch() {
  const data = JSON.parse(execFileSync(process.env.CITE_PYTHON || 'python3', ['-c',
    'import json,yaml; print(json.dumps({name:yaml.safe_load(open("_data/"+name+".yaml")) for name in ["citations","types"]},default=str))',
  ], { cwd: root, maxBuffer: 10 * 1024 * 1024 }).toString());
  const engine = new Liquid({ root: path.join(root, '_includes'), extname: '.html', jekyllInclude: true });
  const escape = (value) => String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  engine.registerFilter('xml_escape', escape);
  engine.registerFilter('relative_url', (value) => String(value || ''));
  engine.registerFilter('uri_escape', (value) => String(value || ''));
  engine.registerFilter('regex_strip', (value) => String(value || '').replace(/<[^>]+>/g, ''));
  engine.registerFilter('regex_replace', (value, pattern, replacement) => String(value || '').replace(new RegExp(pattern, 'g'), replacement));
  engine.registerFilter('markdownify', (value) => String(value || ''));
  engine.registerFilter('array_carve', (values, size) => values.length > size * 2 ? [...values.slice(0, size), '...', ...values.slice(-size)] : values);
  engine.registerFilter('object_items', (value) => Array.isArray(value) || typeof value === 'string' ? value : Object.keys(value || {}));
  engine.registerFilter('array_filter', (values) => values.filter(Boolean));
  let template = fs.readFileSync(path.join(root, 'research/index.md'), 'utf8').replace(/^---[\s\S]*?---\s*/, '');
  template = template.replace(/^# (.*)$/m, '<h1>$1</h1>');
  const body = await engine.parseAndRender(template, { site: { data }, page: { dir: '/research/' } });
  return { body, citations: data.citations };
}
module.exports = { renderResearch, root };

if (require.main === module) {
  renderResearch().then(({ body }) => {
    const output = process.argv[2];
    const styles = `body {font:16px/1.5 system-ui,sans-serif;margin:32px auto;max-width:1100px;padding:0 24px;color:#233040} h1{font-size:34px} h2{margin-top:36px} a{color:#14577b} .search-box{display:flex;gap:8px} .search-input{flex:1;padding:12px;border:1px solid #aab7c2;border-radius:6px} .search-help,.publication-count{color:#64748b} .citation{display:flex;gap:20px;padding:20px;margin:18px 0;border:1px solid #dce2e7;border-radius:8px} .citation-image{display:none} .citation-text{display:flex;flex-wrap:wrap;gap:10px} .citation-title,.citation-authors,.citation-details{width:100%} .citation-title{font-weight:600} [hidden]{display:none!important}`;
    fs.writeFileSync(output, `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CAIS publication search preview</title><style>${styles}</style><body>${body}<script>${fs.readFileSync(path.join(root, '_scripts/search.js'), 'utf8')}</script></body></html>`);
    console.log(`Rendered preview: ${output}`);
  }).catch((error) => { console.error(error); process.exitCode = 1; });
}
