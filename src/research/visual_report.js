/* RiffBand Visual Report — JavaScript for TOC + anchors + theme */
(function() {

/* ── Theme Toggle ──────────────────────────────── */
window.toggleTheme = function() {
  var html = document.documentElement;
  html.dataset.theme = html.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem("theme", html.dataset.theme);
};

(function() {
  var saved = localStorage.getItem("theme");
  if (saved) document.documentElement.dataset.theme = saved;
})();

/* ── Anchor Links ──────────────────────────────── */
(function() {
  var headings = document.querySelectorAll(".prose h1, .prose h2, .prose h3, .prose h4");
  headings.forEach(function(h) {
    if (!h.id) return;
    var anchor = document.createElement("a");
    anchor.href = "#" + h.id;
    anchor.className = "heading-anchor";
    anchor.setAttribute("aria-label", "Link to this section");
    anchor.innerHTML = " #";
    anchor.style.cssText = "opacity:0;font-size:0.8em;text-decoration:none;transition:opacity 0.15s;margin-left:4px;";
    h.appendChild(anchor);
    h.addEventListener("mouseenter", function() { anchor.style.opacity = "1"; });
    h.addEventListener("mouseleave", function() { anchor.style.opacity = "0"; });
  });
})();

/* ── TOC Scroll Highlight ─────────────────────── */
(function() {
  var tocLinks = document.querySelectorAll(".toc a");
  var sections = [];
  tocLinks.forEach(function(link) {
    var href = link.getAttribute("href");
    if (!href || !href.startsWith("#")) return;
    var target = document.getElementById(href.slice(1));
    if (target) sections.push({ link: link, target: target });
  });

  if (sections.length === 0) return;

  function onScroll() {
    var scrollTop = window.scrollY + 80;
    var active = null;
    for (var i = sections.length - 1; i >= 0; i--) {
      if (sections[i].target.offsetTop <= scrollTop) {
        active = sections[i];
        break;
      }
    }
    sections.forEach(function(s) { s.link.classList.remove("active"); });
    if (active) active.link.classList.add("active");
  }

  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
})();

/* ── Smooth Scroll ────────────────────────────── */
(function() {
  document.addEventListener("click", function(e) {
    var link = e.target.closest("a");
    if (!link) return;
    var href = link.getAttribute("href");
    if (!href || !href.startsWith("#")) return;
    var target = document.getElementById(href.slice(1));
    if (!target) return;
    e.preventDefault();
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    history.pushState(null, "", href);
  });
})();

/* Visual chart/table rendering */
function readJsonPayload(container, selector) {
  var script = container.querySelector(selector);
  if (!script) return null;
  try {
    return JSON.parse(script.textContent || "{}");
  } catch (err) {
    return null;
  }
}

function renderTable(container, data) {
  if (!data || !Array.isArray(data.rows)) return;
  var table = document.createElement("table");
  table.className = "visual-data-table";

  if (Array.isArray(data.headers) && data.headers.length) {
    var thead = document.createElement("thead");
    var headRow = document.createElement("tr");
    data.headers.forEach(function(header) {
      var th = document.createElement("th");
      th.textContent = String(header);
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);
  }

  var tbody = document.createElement("tbody");
  data.rows.forEach(function(row) {
    var tr = document.createElement("tr");
    (Array.isArray(row) ? row : [row]).forEach(function(value) {
      var td = document.createElement("td");
      td.textContent = String(value);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);

  container.querySelectorAll("table").forEach(function(existing) {
    existing.remove();
  });
  container.appendChild(table);
}

window.renderVisualArtifacts = function() {
  document.querySelectorAll(".chart-container").forEach(function(container, index) {
    var data = readJsonPayload(container, ".chart-data");
    if (!data) return;
    if (!container.id) container.id = "chart-auto-" + index;
    var chartType = container.getAttribute("data-chart-type") || "bar";
    if (typeof window.renderChart === "function") {
      window.renderChart(container.id, chartType, data);
    }
  });

  document.querySelectorAll(".table-container").forEach(function(container) {
    renderTable(container, readJsonPayload(container, ".table-data"));
  });
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", window.renderVisualArtifacts);
} else {
  window.renderVisualArtifacts();
}

})();
