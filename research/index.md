---
title: Research
nav:
  order: 2
  tooltip: Published works
---

# {% include icon.html icon="fa-solid fa-microscope" %}Research

{% include search-box.html placeholder="Search title, author, DOI, or keyword (e.g. LLM, MPC)" label="Search publications" %}

{% include search-info.html %}

<div class="publication-group" data-publication-group="journal" role="region" aria-labelledby="journal-papers">
  <h2 id="journal-papers">Journal Papers <span class="publication-count" data-group-count></span></h2>
  {% include citation-section.html type="journal" %}
</div>

<div class="publication-group" data-publication-group="conference" role="region" aria-labelledby="conference-papers">
  <h2 id="conference-papers">Conference Papers <span class="publication-count" data-group-count></span></h2>
  {% include citation-section.html type="conference" %}
</div>

<div class="publication-group" data-publication-group="other" role="region" aria-labelledby="other-publications">
  <h2 id="other-publications">Other Publications <span class="publication-count" data-group-count></span></h2>
  <p>Books and book chapters, arXiv and other preprints, theses, and technical reports.</p>
  {% include citation-section.html type="other" %}
</div>
