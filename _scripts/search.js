/* Page search: all words/phrases must match; multiple tag filters use OR. */
{
  const elementSelector = ".card, .citation, .post-excerpt";
  const normalize = (value = "") => String(value)
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim()
    .replace(/\s+/g, " ");

  window.normalizeTag = (tag) => normalize(tag).replace(/ /g, "-");

  const splitQuery = (query) => {
    // Accept tag:llm, tag:"digital twin", and legacy "tag: digital-twin" URLs.
    const parts = String(query).replace(/[“”]/g, '"')
      .match(/tag:\s*"[^"]*"|tag:\s*\S+|"[^"]*"|\S+/gi) || [];
    const terms = [], tags = [];
    for (let part of parts) {
      part = part.replace(/^"|"$/g, "").trim();
      if (/^tag:/i.test(part)) {
        const tag = window.normalizeTag(part.replace(/^tag:\s*/i, "").replace(/^"|"$/g, ""));
        if (tag) tags.push(tag);
      } else {
        const term = normalize(part);
        if (term) terms.push(term);
      }
    }
    return { terms, tags };
  };

  const getAttr = (element, attribute) => [element, ...element.querySelectorAll(`[data-${attribute}]`)]
    .map((node) => node.dataset[attribute] || "").join(" ");
  const corpus = (element) => normalize([
    element.textContent, getAttr(element, "tooltip"), getAttr(element, "search"),
  ].join(" "));
  const tagsOf = (element) => [...element.querySelectorAll(".tag")]
    .map((tag) => window.normalizeTag(tag.textContent));
  const container = (element) => element.closest(".citation-container") || element;
  let timer;
  let highlightVersion = 0;

  const highlightMatches = (terms) => {
    if (typeof Mark === "undefined") return;
    const version = ++highlightVersion;
    const elements = [...document.querySelectorAll(elementSelector)];
    new Mark(elements).unmark({ done: () => {
      if (version !== highlightVersion) return;
      const visible = elements.filter((element) => !container(element).hidden);
      let count = 0;
      new Mark(visible).mark(terms, {
        separateWordSearch: false,
        ignoreJoiners: true,
        filter: () => count++ < 100,
      });
    } });
  };

  const updateSearchBox = (query) => {
    document.querySelectorAll(".search-box").forEach((box) => {
      const input = box.querySelector("input");
      if (input.value !== query) input.value = query;
      const button = box.querySelector("button");
      button.disabled = !query.length;
      const icon = button.querySelector("i");
      if (icon) icon.className = query.length
        ? "icon fa-solid fa-xmark" : "icon fa-solid fa-magnifying-glass";
    });
  };

  const runSearch = (query = "") => {
    window.clearTimeout(timer);
    const { terms, tags } = splitQuery(query);
    const elements = [...document.querySelectorAll(elementSelector)];
    let matches = 0;
    for (const element of elements) {
      const text = corpus(element);
      const show = terms.every((term) => text.includes(term)) &&
        (!tags.length || tags.some((tag) => tagsOf(element).includes(tag)));
      container(element).hidden = !show;
      if (show) matches++;
    }
    updateSearchBox(query);
    document.querySelectorAll(".search-info").forEach((info) => {
      info.hidden = !query.trim();
      info.replaceChildren();
      if (!query.trim()) return;
      info.append(`${matches ? "Showing" : "No matches — showing"} ${matches} of ${elements.length} results. `);
      const clear = document.createElement("a");
      const url = new URL(window.location.href);
      url.searchParams.delete("search");
      clear.href = url.href;
      clear.textContent = "Clear search";
      clear.addEventListener("click", (event) => { event.preventDefault(); window.onSearchClear(); });
      info.append(clear);
    });
    document.querySelectorAll("[data-publication-group]").forEach((group) => {
      const papers = [...group.querySelectorAll(".citation-container")];
      const visible = papers.filter((paper) => !paper.hidden).length;
      group.hidden = !visible;
      const count = group.querySelector("[data-group-count]");
      if (count) count.textContent = query.trim() ? `(${visible} / ${papers.length})` : `(${papers.length})`;
    });
    document.querySelectorAll(".tag").forEach((tag) => {
      tag.toggleAttribute("data-active", tags.includes(window.normalizeTag(tag.textContent)));
    });
    highlightMatches(terms);
  };

  const updateUrl = (query = "") => {
    const url = new URL(window.location.href);
    if (query.trim()) url.searchParams.set("search", query);
    else url.searchParams.delete("search");
    window.history.replaceState(null, "", url);
  };
  const searchFromUrl = () => runSearch(new URLSearchParams(window.location.search).get("search") || "");

  window.onSearchInput = (target) => {
    window.clearTimeout(timer);
    updateUrl(target.value);
    updateSearchBox(target.value);
    timer = window.setTimeout(() => runSearch(target.value), 150);
  };
  window.onSearchClear = () => {
    window.clearTimeout(timer);
    updateUrl();
    runSearch();
  };
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && event.target.matches(".search-input")) {
      event.preventDefault();
      window.onSearchClear();
    }
  });
  window.addEventListener("load", searchFromUrl);
  window.addEventListener("popstate", searchFromUrl);
  window.addEventListener("tagsfetched", searchFromUrl);
}
