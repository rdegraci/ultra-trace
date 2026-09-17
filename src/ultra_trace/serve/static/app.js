/* Ultra-Trace serve UI — vanilla JS only (Bootstrap provides components). */
(function () {
  "use strict";

  var selectedAlias = null;

  function el(id) {
    return document.getElementById(id);
  }

  function setAdvisory(text) {
    el("advisoryOut").textContent = text ? "advisory: " + text : "";
  }

  function showError(err) {
    var detail = err && err.detail ? err.detail : String(err);
    setAdvisory(detail);
  }

  async function api(path, options) {
    var res = await fetch(path, options || {});
    var data = null;
    try {
      data = await res.json();
    } catch (_e) {
      data = null;
    }
    if (!res.ok) {
      var detail = data && data.detail ? data.detail : res.statusText;
      throw { detail: detail };
    }
    return data;
  }

  function severityClass(sev) {
    if (sev === "critical" || sev === "high") return "text-danger";
    if (sev === "medium") return "text-warning";
    return "text-secondary";
  }

  function renderFindings(payload) {
    var list = el("findingsList");
    list.innerHTML = "";
    var findings = payload.findings || [];
    if (!findings.length) {
      list.innerHTML = '<div class="text-secondary">No findings.</div>';
      return;
    }
    findings.forEach(function (f) {
      var item = document.createElement("button");
      item.type = "button";
      item.className = "list-group-item list-group-item-action";
      if (selectedAlias === f.alias) item.classList.add("active");
      item.innerHTML =
        "<div class=\"d-flex justify-content-between\">" +
        "<strong>" +
        f.alias +
        "</strong>" +
        '<span class="' +
        severityClass(f.severity) +
        '">' +
        f.severity +
        "</span></div>" +
        "<div class=\"small\">" +
        f.rule_id +
        (f.candidate ? " · candidate" : "") +
        "</div>" +
        '<div class="small text-truncate">' +
        (f.symbol_name || "-") +
        " · " +
        f.file +
        ":" +
        f.line +
        "</div>";
      item.addEventListener("click", function () {
        selectFinding(f.alias);
      });
      list.appendChild(item);
    });
  }

  function renderDetail(f) {
    el("detailPane").innerHTML =
      "<div><strong>" +
      f.alias +
      "</strong> · " +
      f.severity +
      " · " +
      f.rule_id +
      "</div>" +
      "<div class=\"mt-2\">" +
      f.title +
      "</div>" +
      "<div class=\"small text-secondary mt-2\">" +
      (f.ide_uri
        ? "<a href=\"" +
          f.ide_uri +
          "\">" +
          f.file +
          ":" +
          f.line +
          "</a>"
        : f.file + ":" + f.line) +
      " · " +
      (f.symbol_name || "-") +
      "</div>" +
      "<div class=\"mt-3\"><strong>Path</strong><div class=\"small\">" +
      (f.path_summary || "") +
      "</div></div>" +
      "<div class=\"mt-3\"><strong>Recommended fix</strong><div class=\"small\">" +
      (f.recommended_fix || "") +
      "</div></div>" +
      "<div class=\"mt-3 small\">Proof tier " +
      f.proof_tier +
      " · supported=" +
      f.proof_supported +
      " · " +
      f.proof_kind +
      "</div>";
    el("btnWhy").disabled = false;
  }

  async function loadStatus() {
    var s = await api("/api/status");
    el("banner").textContent = s.banner;
    el("statusLine").textContent =
      s.repo_root +
      " · files=" +
      s.files_discovered +
      " · findings=" +
      s.findings_count +
      " · llm=" +
      (s.llm_available ? "on" : "off");
  }

  async function loadFindings() {
    var data = await api("/api/findings");
    renderFindings(data);
  }

  async function selectFinding(alias) {
    selectedAlias = alias;
    var data = await api("/api/findings/" + encodeURIComponent(alias));
    renderDetail(data);
    await loadFindings();
  }

  async function onWhy() {
    if (!selectedAlias) return;
    try {
      var data = await api("/api/why/" + encodeURIComponent(selectedAlias), {
        method: "POST",
      });
      setAdvisory(data.advisory || "");
    } catch (err) {
      showError(err);
    }
  }

  async function onAsk(ev) {
    ev.preventDefault();
    var q = el("askInput").value.trim();
    if (!q) return;
    try {
      var data = await api("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      setAdvisory(data.advisory || "");
      el("askInput").value = "";
    } catch (err) {
      showError(err);
    }
  }

  async function onTrace(ev) {
    ev.preventDefault();
    var sym = el("traceInput").value.trim();
    if (!sym) return;
    try {
      var data = await api("/api/trace", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: sym }),
      });
      el("traceOut").textContent = JSON.stringify(
        { symbols: data.symbols, related: data.related_findings },
        null,
        2
      );
      if (data.advisory) setAdvisory(data.advisory);
      if (data.related_findings && data.related_findings.length) {
        await selectFinding(data.related_findings[0].alias);
      }
    } catch (err) {
      showError(err);
    }
  }

  async function onExport() {
    try {
      var data = await api("/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dir: "" }),
      });
      setAdvisory("Exported:\n" + (data.paths || []).join("\n"));
    } catch (err) {
      showError(err);
    }
  }

  async function onReload() {
    try {
      await api("/api/reload", { method: "POST" });
      selectedAlias = null;
      el("btnWhy").disabled = true;
      el("detailPane").textContent = "Select a finding.";
      await loadStatus();
      await loadFindings();
      setAdvisory("Reloaded.");
    } catch (err) {
      showError(err);
    }
  }

  async function onSummary() {
    try {
      var data = await api("/api/summary", { method: "POST" });
      setAdvisory(data.advisory || "");
    } catch (err) {
      showError(err);
    }
  }

  async function onCandidates() {
    try {
      var data = await api("/api/candidates", { method: "POST" });
      await loadFindings();
      setAdvisory(
        "Candidates: " +
          ((data.candidates && data.candidates.length) || 0) +
          " (added " +
          ((data.added && data.added.length) || 0) +
          ")"
      );
    } catch (err) {
      showError(err);
    }
  }

  el("btnWhy").addEventListener("click", onWhy);
  el("askForm").addEventListener("submit", onAsk);
  el("traceForm").addEventListener("submit", onTrace);
  el("btnExport").addEventListener("click", onExport);
  el("btnReload").addEventListener("click", onReload);
  el("btnSummary").addEventListener("click", onSummary);
  el("btnCandidates").addEventListener("click", onCandidates);

  loadStatus()
    .then(loadFindings)
    .catch(function (err) {
      showError(err);
    });
})();
