---
title: News
nav:
  order: 4
  tooltip: Musings and miscellany
---

# {% include icon.html icon="fa-solid fa-feather-pointed" %}News


{% include section.html %}

{% include search-box.html %}

{% assign news_tags = site.tags | object_items | sort %}
{% include tags.html tags=news_tags %}

{% include search-info.html %}

{% include list.html data="posts" component="post-excerpt" %}
