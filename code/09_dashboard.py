#!/usr/bin/env python3
"""09 - Build the static results dashboard published to GitHub Pages.

Reads only committed pipeline outputs (paper/stats.json, paper/tables/,
paper/figures/, AUTHORS.json, CITATION.cff, docs/release_ids.json) and writes
a self-contained static site to site/ (HTML + CSS + copied figures). No
server-side code runs on GitHub Pages: everything here is pre-rendered, so
the dashboard always reflects whatever was last committed to data/processed
and paper/. Re-run after run_all.sh to refresh it.
"""
import csv
import html
import json
import os
import re
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PAPER = os.path.join(ROOT, "paper")
SITE = os.path.join(ROOT, "site")

NAME = {"Static limits": "Static limits", "PCA residual": "PCA residual",
        "Isolation Forest": "Isolation Forest", "AIPIR predictive": "AIPIR predictive"}
FIGURES = [
    ("fig1_architecture.png", "AIPIR architecture: Observe -> Predict -> Respond -> Recover"),
    ("fig2_detection.png", "Attack events detected per detector, held-out tests"),
    ("fig3_ttd.png", "Time-to-detect distribution per detector"),
    ("fig4_fa_tradeoff.png", "False-alarm budget vs. recall tradeoff, held-out tests"),
    ("fig5_timeline.png", "HAI 21.03 test2, 6 h excerpt: shaded = labelled attacks"),
    ("fig6_downtime_scenario.png", "Downtime scenario: static alarms vs. AIPIR detection/recovery"),
]


def load_json(path, default=None):
    if os.path.exists(path):
        return json.load(open(path))
    return default


def pct(x):
    return f"{x:.1f}%"


def results_table(rows):
    cell_rows = []
    for r in rows:
        ttd = "-" if r["ttd_median_s"] in ("", None) else f"{float(r['ttd_median_s']):.0f}"
        route = "-" if r["routing_accuracy"] in ("", None) else pct(100 * float(r["routing_accuracy"]))
        row_class = "aipir" if r["detector"] == "AIPIR predictive" else ""
        cell_rows.append(
            f'<tr class="{row_class}"><td>{html.escape(r["detector"])}</td>'
            f'<td>{r["events_detected"]}/{r["events"]}</td>'
            f'<td>{ttd}</td><td>{float(r["f1"]):.2f}</td>'
            f'<td>{float(r["false_episodes_per_day"]):.2f}</td><td>{route}</td></tr>'
        )
    return (
        '<table class="results"><thead><tr><th>Detector</th><th>Attacks detected</th>'
        "<th>Median TTD (s)</th><th>Point-wise F1</th><th>False alarms/day</th>"
        "<th>Routed to attacked process</th></tr></thead><tbody>" + "".join(cell_rows) + "</tbody></table>"
    )


def main():
    stats = load_json(os.path.join(PAPER, "stats.json"), {})
    release = load_json(os.path.join(ROOT, "docs", "release_ids.json"), {})
    authors = load_json(os.path.join(ROOT, "AUTHORS.json"), {"authors": [], "collaborators": []})
    lab = load_json(os.path.join(ROOT, "data", "processed", "lab_stack_check.json"), {})
    iac_path = os.path.join(ROOT, "data", "processed", "iac_validation.txt")
    iac_summary = ""
    if os.path.exists(iac_path):
        m = re.search(r"SUMMARY pass=(\d+) fail=(\d+) skip=(\d+)", open(iac_path).read())
        if m:
            p, f, s = m.groups()
            iac_summary = f"{p} passed, {f} failed, {s} skipped"

    HEADLINE_DETECTORS = ["Static limits", "PCA residual", "Isolation Forest", "AIPIR predictive"]
    table_rows = list(csv.DictReader(open(os.path.join(PAPER, "tables", "table1_heldout_results.csv"))))
    table_rows = [r for r in table_rows if r["detector"] in HEADLINE_DETECTORS]
    by_version = {}
    for r in table_rows:
        by_version.setdefault(r["version"], []).append(r)
    for v in by_version:
        by_version[v].sort(key=lambda r: HEADLINE_DETECTORS.index(r["detector"]))

    dt = stats.get("downtime", {})
    central = dt.get("central", {})
    doi = (release.get("doi") or "").replace("https://doi.org/", "")
    concept_doi = (release.get("concept_doi") or "").replace("https://doi.org/", "")
    repo_url = release.get("repository_url", "https://github.com/foikwuogu/aipir")
    all_people = authors.get("authors", []) + authors.get("collaborators", [])
    author_names = ", ".join(p["name"] for p in all_people)

    results = stats.get("results", {})

    def test_days(v):
        d0 = results.get(f"{v}|test|D0", {})
        return f"{d0['test_days']:.1f}" if d0.get("test_days") is not None else "?"

    version_sections = "".join(
        f"<h3>{v.upper().replace('HAI-', 'HAI ')} held-out tests "
        f"({by_version[v][0]['events']} attacks over {test_days(v)} days)</h3>" + results_table(by_version[v])
        for v in sorted(by_version, reverse=True)
    )

    figs_html = "".join(
        f'<figure><img src="figures/{name}" alt="{html.escape(caption)}" loading="lazy">'
        f"<figcaption>{html.escape(caption)}</figcaption></figure>"
        for name, caption in FIGURES
        if os.path.exists(os.path.join(PAPER, "figures", name))
    )

    checks_html = ""
    if lab:
        checks_html += (
            f'<div class="stat-card"><div class="stat-value">{lab.get("passed", "?")}/'
            f'{lab.get("total", "?")}</div><div class="stat-label">Zero-Trust, recovery and '
            "OpenTelemetry checks passed (lab)</div></div>"
        )
    if iac_summary:
        checks_html += (
            f'<div class="stat-card"><div class="stat-value">{iac_summary}</div>'
            '<div class="stat-label">IaC template library validation</div></div>'
        )

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AIPIR - results dashboard</title>
<meta name="description" content="Held-out detection results and downtime scenario for the AIPIR predictive infrastructure resilience framework.">
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="hero">
  <h1>AIPIR</h1>
  <p class="tagline">AI-Enabled Predictive Infrastructure Resilience Framework</p>
  <p class="status">Results dashboard, generated from <code>paper/stats.json</code></p>
  <nav class="links">
    <a href="{html.escape(repo_url)}">GitHub repository</a>
    <a href="{html.escape(repo_url)}/blob/main/paper/AIPIR_manuscript.pdf">Manuscript (PDF)</a>
    {f'<a href="https://doi.org/{html.escape(concept_doi or doi)}">Zenodo DOI</a>' if (concept_doi or doi) else ""}
  </nav>
</header>

<main>
  <section>
    <h2>Headline results (held-out data)</h2>
    {version_sections}
    <p class="note"><strong>Read honestly:</strong> on HAI 21.03, AIPIR detects attacks earliest and
    routes them correctly, with the best F1, but static limits and PCA detect <em>more</em> attacks;
    on HAI 20.07 every detector is weak. The detectors miss different attacks, so AIPIR is best used
    as a layer on top of existing alarms.</p>
  </section>

  <section>
    <h2>Downtime scenario</h2>
    <p class="note">Assumed recovery times, not measured (<code>code/03_recovery_scenario.py</code>),
    over the {central.get("n_events", "?")} held-out attacks.</p>
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-value">{pct(central.get("S2_reduction_pct", 0))}</div>
        <div class="stat-label">Downtime reduction: AIPIR detection + automated recovery vs. static
        alarms + manual recovery (range {pct(dt.get("S2_reduction_pct_min", 0))} to
        {pct(dt.get("S2_reduction_pct_max", 0))})</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{central.get("S1_reduction_pct", 0):+.1f}%</div>
        <div class="stat-label">Downtime change: AIPIR detection + manual recovery vs. static alarms
        + manual recovery</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{pct(central.get("S3_reduction_pct", 0))}</div>
        <div class="stat-label">Exploratory layered setup (static limits + AIPIR), downtime
        reduction vs. static alarms + manual recovery</div>
      </div>
    </div>
  </section>

  {f'<section><h2>Platform checks (lab)</h2><div class="stat-grid">{checks_html}</div></section>' if checks_html else ""}

  <section>
    <h2>Figures</h2>
    <div class="fig-grid">
      {figs_html}
    </div>
  </section>
</main>

<footer>
  <p>{html.escape(author_names)}. <em>AIPIR: AI-Enabled Predictive Infrastructure Resilience
  Framework.</em>{f' doi:{html.escape(concept_doi or doi)}.' if (concept_doi or doi) else ""} See
  <code>CITATION.cff</code>.</p>
  <p>Code MIT; derived data and models CC BY-SA 4.0 (required by the HAI dataset); paper and docs
  CC BY 4.0.</p>
</footer>
</body>
</html>
"""

    shutil.rmtree(SITE, ignore_errors=True)
    os.makedirs(os.path.join(SITE, "figures"), exist_ok=True)
    open(os.path.join(SITE, "index.html"), "w", encoding="utf-8").write(html_doc)
    shutil.copy(os.path.join(HERE, "..", "dashboard", "style.css"), os.path.join(SITE, "style.css"))
    for name, _ in FIGURES:
        src = os.path.join(PAPER, "figures", name)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(SITE, "figures", name))
    open(os.path.join(SITE, ".nojekyll"), "w").close()
    print("wrote", os.path.join(SITE, "index.html"))


if __name__ == "__main__":
    main()
