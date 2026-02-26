---
title: Research
nav:
  order: 2
  tooltip: Published works
---

# {% include icon.html icon="fa-solid fa-microscope" %}Research




## All

{% include search-box.html %}
{% include search-info.html %}

{%- assign sorted = site.data.citations | sort: "date" | reverse -%}
{%- assign seen_titles = "" -%}
{%- assign bar = "|" -%}

### Journal Articles
{%- for c in sorted -%}
  {%- assign title = c.title | default: c.id | strip -%}
  {%- assign title_key = title | downcase | replace: ".", "" | replace: ",", "" | replace: ";", "" | replace: ":", "" | replace: "—", " " | replace: "-", " " | replace: "(", "" | replace: ")", "" | replace: "[", "" | replace: "]", "" | replace: "{", "" | replace: "}", "" | replace: "  ", " " | replace: "  ", " " | strip -%}
  {%- assign pad = bar | append: title_key | append: bar -%}

  {%- assign t = c.type | default: c.genre | default: "" | downcase -%}
  {%- assign venue = c["container-title"] | default: c.venue | default: c.publisher | default: "" | downcase -%}
  {%- assign link_lc = c.link | default: "" | downcase -%}
  {%- assign doi_lc = c.DOI | default: c.doi | default: c.id | default: "" | downcase -%}

  {%- assign is_journal = false -%}
  {%- if t contains "journal" or t contains "article" -%}{%- assign is_journal = true -%}{%- endif -%}
  {%- if venue contains "journal" or venue contains "letters" or venue contains "transactions" or venue contains "magazine" or venue contains "frontiers" or venue contains "nature" or venue contains "ieee access" or venue contains "international journal" or venue contains "control engineering practice" or venue contains "robotics and automation letters" or venue contains "robotics and computer-integrated manufacturing" or venue contains "smart and sustainable manufacturing systems" or venue contains "journal of medical devices" or venue contains "procedia manufacturing" or venue contains "procedia cirp" or venue contains "battery energy" or venue contains "IEEE Access" or venue contains "Robotics and Computer-Integrated Manufacturing" or venue contains "robotics and automation letters" or venue contains "robotics and computer-integrated manufacturing" or venue contains "smart and sustainable manufacturing systems" or venue contains "journal of medical devices" or venue contains "procedia manufacturing" or venue contains "procedia cirp" or venue contains "battery energy" -%}{%- assign is_journal = true -%}{%- endif -%}

  {%- assign is_conf = false -%}
  {%- if t contains "proceedings" or t contains "conference" or t contains "workshop" or t contains "symposium" -%}{%- assign is_conf = true -%}{%- endif -%}
  {%- if venue contains "conference" or venue contains "proceedings" or venue contains "workshop" or venue contains "symposium" or venue contains "case" or venue contains "acc" or venue contains "cdc" or venue contains "ccta" or venue contains "msec" or venue contains "etfa" or venue contains "arso" or venue contains "detc" or venue contains "dscc" or venue contains "ifac-papersonline" or venue contains "volume " -%}{%- assign is_conf = true -%}{%- endif -%}
  {%- if doi_lc contains "/msec" or doi_lc contains "/dscc" or doi_lc contains "/detc" or doi_lc contains "/case" or doi_lc contains "/ccta" or doi_lc contains "/acc" or doi_lc contains "/cdc" or doi_lc contains "/etfa" or doi_lc contains "/arso" -%}{%- assign is_conf = true -%}{%- endif -%}

  {%- assign is_arxiv = false -%}
  {%- if c.id and c.id contains "arxiv:" -%}{%- assign is_arxiv = true -%}{%- endif -%}
  {%- if doi_lc contains "10.48550/arxiv" or link_lc contains "arxiv.org" or venue contains "arxiv" -%}{%- assign is_arxiv = true -%}{%- endif -%}

  {%- assign is_book = false -%}
  {%- if t contains "chapter" or t contains "book" -%}{%- assign is_book = true -%}{%- endif -%}
  {%- if venue contains "lecture notes" or venue contains "encyclopedia" or venue contains "handbook" or venue contains "springer" or venue contains "wiley" or venue contains "book" or venue contains "chapter" -%}{%- assign is_book = true -%}{%- endif -%}

  {%- if venue contains "ifac-papersonline" -%}{%- assign is_journal = false -%}{%- assign is_conf = true -%}{%- endif -%}

  {%- if is_journal and is_conf == false and is_book == false and is_arxiv == false -%}
    {%- unless seen_titles contains pad -%}
      {%- assign lookup_key = c.id | default: c.title -%}
      {% include citation.html lookup=lookup_key style="rich" %}
      {%- assign seen_titles = seen_titles | append: pad -%}
    {%- endunless -%}
  {%- endif -%}
{%- endfor -%}

### Conference Papers
{%- for c in sorted -%}
  {%- assign title = c.title | default: c.id | strip -%}
  {%- assign title_key = title | downcase | replace: ".", "" | replace: ",", "" | replace: ";", "" | replace: ":", "" | replace: "—", " " | replace: "-", " " | replace: "(", "" | replace: ")", "" | replace: "[", "" | replace: "]", "" | replace: "{", "" | replace: "}", "" | replace: "  ", " " | replace: "  ", " " | strip -%}
  {%- assign pad = bar | append: title_key | append: bar -%}

  {%- assign t = c.type | default: c.genre | default: "" | downcase -%}
  {%- assign venue = c["container-title"] | default: c.venue | default: c.publisher | default: "" | downcase -%}
  {%- assign link_lc = c.link | default: "" | downcase -%}
  {%- assign doi_lc = c.DOI | default: c.doi | default: c.id | default: "" | downcase -%}

  {%- assign is_arxiv = false -%}
  {%- if c.id and c.id contains "arxiv:" -%}{%- assign is_arxiv = true -%}{%- endif -%}
  {%- if doi_lc contains "10.48550/arxiv" or link_lc contains "arxiv.org" or venue contains "arxiv" -%}{%- assign is_arxiv = true -%}{%- endif -%}

  {%- assign is_book = false -%}
  {%- if t contains "chapter" or t contains "book" -%}{%- assign is_book = true -%}{%- endif -%}
  {%- if venue contains "lecture notes" or venue contains "encyclopedia" or venue contains "handbook" or venue contains "springer" or venue contains "wiley" or venue contains "book" or venue contains "chapter" -%}{%- assign is_book = true -%}{%- endif -%}

  {%- assign is_conf = false -%}
  {%- if t contains "proceedings" or t contains "conference" or t contains "workshop" or t contains "symposium" -%}{%- assign is_conf = true -%}{%- endif -%}
  {%- if venue contains "conference" or venue contains "proceedings" or venue contains "workshop" or venue contains "symposium" or venue contains "case" or venue contains "acc" or venue contains "cdc" or venue contains "ccta" or venue contains "msec" or venue contains "etfa" or venue contains "arso" or venue contains "detc" or venue contains "dscc" or venue contains "ifac-papersonline" or venue contains "volume " -%}{%- assign is_conf = true -%}{%- endif -%}
  {%- if doi_lc contains "/msec" or doi_lc contains "/dscc" or doi_lc contains "/detc" or doi_lc contains "/case" or doi_lc contains "/ccta" or doi_lc contains "/acc" or doi_lc contains "/cdc" or doi_lc contains "/etfa" or doi_lc contains "/arso" -%}{%- assign is_conf = true -%}{%- endif -%}
  {%- if venue contains "ifac-papersonline" -%}{%- assign is_conf = true -%}{%- endif -%}

  {%- if is_conf and is_book == false and is_arxiv == false -%}
    {%- unless seen_titles contains pad -%}
      {%- assign lookup_key = c.id | default: c.title -%}
      {% include citation.html lookup=lookup_key style="rich" %}
      {%- assign seen_titles = seen_titles | append: pad -%}
    {%- endunless -%}
  {%- endif -%}
{%- endfor -%}

### Other Publications
{%- for c in sorted -%}
  {%- assign title = c.title | default: c.id | strip -%}
  {%- assign title_key = title | downcase | replace: ".", "" | replace: ",", "" | replace: ";", "" | replace: ":", "" | replace: "—", " " | replace: "-", " " | replace: "(", "" | replace: ")", "" | replace: "[", "" | replace: "]", "" | replace: "{", "" | replace: "}", "" | replace: "  ", " " | replace: "  ", " " | strip -%}
  {%- assign pad = bar | append: title_key | append: bar -%}

  {%- assign t = c.type | default: c.genre | default: "" | downcase -%}
  {%- assign venue = c["container-title"] | default: c.venue | default: c.publisher | default: "" | downcase -%}
  {%- assign link_lc = c.link | default: "" | downcase -%}
  {%- assign doi_lc = c.DOI | default: c.doi | default: c.id | default: "" | downcase -%}

  {%- assign is_arxiv = false -%}
  {%- if c.id and c.id contains "arxiv:" -%}{%- assign is_arxiv = true -%}{%- endif -%}
  {%- if doi_lc contains "10.48550/arxiv" or link_lc contains "arxiv.org" or venue contains "arxiv" -%}{%- assign is_arxiv = true -%}{%- endif -%}

  {%- assign is_book = false -%}
  {%- if t contains "chapter" or t contains "book" -%}{%- assign is_book = true -%}{%- endif -%}
  {%- if venue contains "lecture notes" or venue contains "encyclopedia" or venue contains "handbook" or venue contains "springer" or venue contains "wiley" or venue contains "book" or venue contains "chapter" -%}{%- assign is_book = true -%}{%- endif -%}

  {%- assign is_journal = false -%}
  {%- if t contains "journal" or t contains "article" -%}{%- assign is_journal = true -%}{%- endif -%}
  {%- if venue contains "journal" or venue contains "letters" or venue contains "transactions" or venue contains "magazine" or venue contains "frontiers" or venue contains "nature" or venue contains "ieee access" or venue contains "international journal" or venue contains "control engineering practice" or venue contains "robotics and automation letters" or venue contains "robotics and computer-integrated manufacturing" or venue contains "smart and sustainable manufacturing systems" or venue contains "journal of medical devices" or venue contains "procedia manufacturing" or venue contains "procedia cirp" or venue contains "battery energy" -%}{%- assign is_journal = true -%}{%- endif -%}

  {%- assign is_conf = false -%}
  {%- if t contains "proceedings" or t contains "conference" or t contains "workshop" or t contains "symposium" -%}{%- assign is_conf = true -%}{%- endif -%}
  {%- if venue contains "conference" or venue contains "proceedings" or venue contains "workshop" or venue contains "symposium" or venue contains "case" or venue contains "acc" or venue contains "cdc" or venue contains "ccta" or venue contains "msec" or venue contains "etfa" or venue contains "arso" or venue contains "detc" or venue contains "dscc" or venue contains "ifac-papersonline" or venue contains "volume " -%}{%- assign is_conf = true -%}{%- endif -%}
  {%- if doi_lc contains "/msec" or doi_lc contains "/dscc" or doi_lc contains "/detc" or doi_lc contains "/case" or doi_lc contains "/ccta" or doi_lc contains "/acc" or doi_lc contains "/cdc" or doi_lc contains "/etfa" or doi_lc contains "/arso" -%}{%- assign is_conf = true -%}{%- endif -%}

  {%- if venue contains "ifac-papersonline" -%}{%- assign is_journal = false -%}{%- assign is_conf = true -%}{%- endif -%}

  {%- assign is_journal_only = false -%}
  {%- if is_journal and is_conf == false and is_book == false and is_arxiv == false -%}{%- assign is_journal_only = true -%}{%- endif -%}

  {%- assign is_conf_only = false -%}
  {%- if is_conf and is_book == false and is_arxiv == false -%}{%- assign is_conf_only = true -%}{%- endif -%}

  {%- if is_journal_only == false and is_conf_only == false -%}
    {%- unless seen_titles contains pad -%}
      {%- assign lookup_key = c.id | default: c.title -%}
      {% include citation.html lookup=lookup_key style="rich" %}
      {%- assign seen_titles = seen_titles | append: pad -%}
    {%- endunless -%}
  {%- endif -%}
{%- endfor -%}

