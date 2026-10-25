// Builds docs/training/AIPIR_training_deck.pptx from paper/stats.json (numbers are never typed).
//   node docs/training/build_deck.js
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
// Optional: the pptx skill's apply_theme.js writes the theme colours into the file. Without it
// the deck still builds and uses PowerPoint's stock palette for scheme colours.
let applyTheme = async () => console.warn("PPTX_SKILL_DIR not set: theme colours not applied");
if (process.env.PPTX_SKILL_DIR) ({ applyTheme } = require(process.env.PPTX_SKILL_DIR + "/scripts/apply_theme.js"));

const ROOT = path.resolve(__dirname, "..", "..");
const S = JSON.parse(fs.readFileSync(path.join(ROOT, "paper/stats.json"), "utf8"));
const R = (v, d) => S.results[`${v}|test|${d}`];
const c = S.downtime.central;
const OUT = path.join(__dirname, "AIPIR_training_deck.pptx");
const VAL = fs.readFileSync(path.join(ROOT, "data/processed/iac_validation.txt"), "utf8").match(/SUMMARY pass=(\d+) fail=(\d+) skip=(\d+)/);
const N_TEMPLATES = (fs.readFileSync(path.join(ROOT, "deploy/README.md"), "utf8").match(/^\| \d+ \|/gm) || []).length;

const THEME = {
  name: "AIPIR Grid",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "14232B", lt1: "FFFFFF", dk2: "0B3C49", lt2: "EEF3F4",
    accent1: "0B3C49", accent2: "E39B2D", accent3: "3E7C7A", accent4: "9BB8BC",
    accent5: "B5462F", accent6: "5D6B72", hlink: "1F6F8B", folHlink: "5D6B72",
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "AIPIR workshop";
pres.author = "Friday Ogochukwu Ikwuogu";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

pres.defineSlideMaster({
  title: "AIPIR Dark",
  background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.5, w: 8.8, h: 1.4, fontSize: 38, bold: true, color: C.background1, valign: "bottom" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 3.05, w: 8.8, h: 1.4, fontSize: 18, color: C.background2, valign: "top" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "AIPIR Content",
  background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.75, fontSize: 30, bold: true, color: C.text2, valign: "middle" }, text: "" } },
    { text: { text: "AIPIR workshop  |  lab data only (HAI testbed)", options: { x: 0.5, y: 5.2, w: 6, h: 0.3, fontSize: 10, color: C.accent6 } } },
  ],
  slideNumber: { x: 9.0, y: 5.2, w: 0.5, h: 0.3, fontSize: 10, color: C.accent6, align: "right" },
});

let n = 0;
function content(title, section, notes) {
  const s = pres.addSlide({ masterName: "AIPIR Content", sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  if (notes) s.addNotes(notes);
  n++;
  return s;
}
function card(s, x, y, w, h, head, body, num, opts = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: opts.fill || C.background2 }, line: { color: opts.fill || C.background2 }, objectName: `card ${head}` });
  let tx = x + 0.2;
  if (num !== undefined) {
    s.addShape(pres.shapes.OVAL, { x: x + 0.18, y: y + 0.2, w: 0.45, h: 0.45, fill: { color: opts.dot || C.accent2 }, line: { color: opts.dot || C.accent2 }, objectName: `badge ${num}` });
    s.addText(String(num), { x: x + 0.18, y: y + 0.2, w: 0.45, h: 0.45, fontSize: 14, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true });
    tx = x + 0.75;
  }
  s.addText(head, { x: tx, y: y + 0.15, w: x + w - tx - 0.15, h: 0.55, fontSize: 15, bold: true, color: opts.headColor || C.text2, valign: "middle", margin: 0, isTextBox: true });
  s.addText(body, { x: x + 0.2, y: y + 0.75, w: w - 0.4, h: h - 0.9, fontSize: opts.bodySize || 13.5, color: opts.bodyColor || C.text1, valign: "top", margin: 0, isTextBox: true });
}
function stat(s, x, y, w, big, label, color) {
  s.addText(big, { x, y, w, h: 0.9, fontSize: 40, bold: true, color: color || C.accent1, fontFace: THEME.headFontFace, margin: 0, isTextBox: true });
  s.addText(label, { x, y: y + 0.9, w, h: 0.6, fontSize: 12, color: C.accent6, margin: 0, valign: "top", isTextBox: true });
}
const bullets = (items) => items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 6 } }));

// 1 title
pres.addSection({ title: "Opening" });
let s = pres.addSlide({ masterName: "AIPIR Dark", sectionTitle: "Opening" });
s.addText("AIPIR: Predictive Infrastructure Resilience", { placeholder: "title" });
s.addText("One-day hands-on workshop for energy-sector engineers and reliability managers. Observe, predict, respond, recover.", { placeholder: "body" });
s.addNotes("Welcome. Introduce the instructor and the training partner. Today is hands-on: six labs on recorded public data.");
n++;

// 2 safety
s = content("Ground rules for today", "Opening", "Say all four messages out loud. They protect the participants and the integrity of the work.");
[["Recorded public data only", "Everything runs on the open HAI testbed datasets. Nothing connects to a plant."],
 ["AIPIR never writes to controllers", "Real recovery goes through management of change, two people and MFA."],
 ["Lab tokens stay in the lab", "Pilot identities come from Entra ID with MFA, not from lab scripts."],
 ["Testbed numbers are not pilot numbers", "MTTD, MTTR, availability and drift targets are measured at a site, not here."]]
  .forEach(([h, b], i) => card(s, 0.5 + (i % 2) * 4.55, 1.3 + Math.floor(i / 2) * 1.9, 4.45, 1.75, h, b, i + 1));

// 3 four layers
s = content("Four layers, one loop", "Opening", "The loop closes: a recovered plant is observed again and must return below threshold.");
[["Observe", "Telemetry each second; Prometheus metrics and OpenTelemetry"], ["Predict", "Forecast each sensor 1 s ahead; score the deviations"],
 ["Respond", "Calibrated, debounced alarms routed to boiler, turbine or water"], ["Recover", "Approved Ansible playbooks; Terraform restores the stack"]]
  .forEach(([h, b], i) => {
    card(s, 0.5 + i * 2.3, 1.45, 2.1, 2.6, h, b, i + 1);
    if (i < 3) s.addShape(pres.shapes.RIGHT_TRIANGLE, { x: 2.62 + i * 2.3, y: 2.6, w: 0.14, h: 0.3, rotate: 90, fill: { color: C.accent6 }, line: { color: C.accent6 }, objectName: `arrow ${i}` });
  });
s.addText("Zero-Trust across all four: verified identity, least privilege, MFA, two-person rule, audit", { x: 0.5, y: 4.3, w: 9, h: 0.5, fontSize: 14, italic: true, color: C.accent3, isTextBox: true });

// 4 downtime equation
pres.addSection({ title: "M1 Why resilience" });
s = content("Downtime has three parts", "M1 Why resilience", "Most downtime is not in detection seconds; it is in recovery hours and in incidents nobody detected.");
[["Time to detect", "Seconds to minutes. What the detector improves."], ["Time to recover", "Minutes to hours. What playbooks and IaC improve."], ["Missed incidents", "Found late by other means. What event recall improves."]]
  .forEach(([h, b], i) => card(s, 0.5 + i * 3.05, 1.4, 2.85, 1.9, h, b, ["+", "+", "+"][i] === "+" ? i + 1 : undefined));
s.addText([{ text: "downtime  =  time to detect  +  time to recover", options: { bold: true, breakLine: true } }, { text: "or, when missed:  time to discover  +  manual recovery" }],
  { x: 0.5, y: 3.6, w: 9, h: 1.1, fontSize: 18, color: C.text2, fontFace: THEME.headFontFace, isTextBox: true });

// 5 scenario chart
s = content("Faster detection alone does not cut downtime", "M1 Why resilience",
  "Scenario model, not a measurement: measured time-to-detect plus ASSUMED recovery times (manual 4 h, automated 15 min, discovery of a missed attack 24 h).");
s.addChart(pres.charts.BAR, [{ name: "Total downtime (h)", labels: ["S0 limits + manual", "S1 AIPIR + manual", "S2 AIPIR + automated", "S3 layered (exploratory)"],
  values: [c.S0_h, c.S1_h, c.S2_h, c.S3_h].map((v) => Math.round(v)) }], {
  x: 0.5, y: 1.2, w: 5.6, h: 3.8, barDir: "bar", chartColors: [HEX.accent1], showValue: true, dataLabelPosition: "outEnd",
  dataLabelFontSize: 11, dataLabelColor: HEX.dk1, catAxisLabelColor: HEX.dk1, valAxisLabelColor: HEX.accent6, catAxisLabelFontSize: 11,
  valAxisLabelFontSize: 10, valGridLine: { color: "D9E2E4", size: 0.5 }, catGridLine: { style: "none" }, showLegend: false,
  showTitle: true, title: `Scenario: ${c.n_events} held-out attacks, hours`, titleFontSize: 12, titleColor: HEX.dk2,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", titleFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", catAxisOrientation: "maxMin",
});
stat(s, 6.5, 1.4, 3.0, `${Math.abs(c.S1_reduction_pct).toFixed(1)}% ${c.S1_reduction_pct < 0 ? "worse" : "better"}`, "AIPIR detection with manual recovery, vs limits", C.accent5);
stat(s, 6.5, 2.95, 3.0, `${c.S2_reduction_pct.toFixed(1)}% less`, `AIPIR + automated recovery (range ${S.downtime.S2_reduction_pct_min.toFixed(1)}-${S.downtime.S2_reduction_pct_max.toFixed(1)}%)`, C.accent3);

// 6 layer on top
s = content("AIPIR is a layer on existing alarms", "M1 Why resilience", "On HAI 21.03 the two detectors miss different attacks; together they catch more.");
const lay = S.layered["hai-21.03"];
stat(s, 0.6, 1.5, 2.8, `${lay.only_D0}`, "attacks caught only by static limits");
stat(s, 3.6, 1.5, 2.8, `${lay.only_D3}`, "attacks caught only by AIPIR");
stat(s, 6.6, 1.5, 2.8, `${lay.detected}/${lay.events}`, "caught by either (exploratory)", C.accent3);
s.addText(bullets(["Keep the limit alarms you trust", "Add the predictive layer for earlier warning and process routing", "Judge the combination on new data before claiming it"]),
  { x: 0.6, y: 3.3, w: 8.8, h: 1.6, fontSize: 15, color: C.text1, isTextBox: true });

// 7-9 observe/predict
pres.addSection({ title: "M2 Observe and Predict" });
s = content("Observe: every second, three signals", "M2 Observe and Predict", "Lab 1 and Lab 4 use these endpoints and signals.");
[["Prometheus metrics", "/metrics: score, threshold, alarm per process, residual per sensor. Scrapes authenticated with a workload token."],
 ["OpenTelemetry", "OTLP metrics, an aipir.alarm span per episode, an aipir.recovery span per recovery, and audit logs."],
 ["Status API", "/status and /recoveries in JSON, behind role-based access."]]
  .forEach(([h, b], i) => card(s, 0.5 + i * 3.05, 1.35, 2.85, 2.6, h, b, i + 1, { bodySize: 14 }));

s = content("Predict: what should the plant do next?", "M2 Observe and Predict", "Linear on purpose: it trains in seconds on a CPU, can be audited, and per-sensor residuals give routing for free.");
s.addText(bullets(["A ridge model predicts every sensor one second ahead from 30 s of history (lags 1, 2, 3, 5, 10, 20, 30 s)",
  "Each sensor's error is divided by its 99.9th percentile on normal data and capped at 5",
  "Score = mean of the 5 largest errors, averaged over the last 10 s (causal)",
  "Without robust scaling, setpoint steps flood the score (ablation in the paper)"]), { x: 0.5, y: 1.3, w: 5.4, h: 3.6, fontSize: 15, color: C.text1, isTextBox: true });
stat(s, 6.4, 1.4, 3.1, `${Math.round(S.qa["hai-21.03"].throughput_rows_per_s.D3).toLocaleString("en-US")}`, "telemetry-seconds scored per second (2 vCPU)");
stat(s, 6.4, 3.0, 3.1, `${S.lab_check.per_second_latency_ms.toFixed(2)} ms`, "streaming cost per telemetry second");

s = content("Respond: thresholds from normal data only", "M2 Observe and Predict", "Point to framework/aipir/config.py: FIT_FRACTION, FA_BUDGET_PER_DAY, MIN_DUR_S, MERGE_GAP_S.");
[["80 / 20 split", "First 80% of each normal file fits the model; last 20% sets the threshold."], ["1 false alarm per day", "Lowest threshold that stays within the budget on normal data."],
 ["Debounce and merge", "An alarm must last 5 s; runs closer than 30 s are one episode."], ["Route", "The top-contributing sensor names the process: P1 boiler, P2 turbine, P3 water."]]
  .forEach(([h, b], i) => card(s, 0.5 + (i % 2) * 4.55, 1.3 + Math.floor(i / 2) * 1.9, 4.45, 1.75, h, b, i + 1));

// 10-11 results
pres.addSection({ title: "M3 Results" });
s = content("HAI 21.03 held-out: earlier, but not more", "M3 Results", "45 held-out attacks over 4.2 days. Design frozen on one development file before scoring.");
const dets = ["D0", "D1", "D3"], names = ["Static limits", "PCA residual", "AIPIR"];
s.addChart(pres.charts.BAR, [{ name: "Attacks detected", labels: names, values: dets.map((d) => R("hai-21.03", d).events_detected) }], {
  x: 0.5, y: 1.2, w: 4.4, h: 3.8, barDir: "col", chartColors: [HEX.accent3], showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: HEX.dk1,
  catAxisLabelColor: HEX.dk1, valAxisLabelColor: HEX.accent6, valGridLine: { color: "D9E2E4", size: 0.5 }, catGridLine: { style: "none" }, showLegend: false,
  showTitle: true, title: `Attacks detected (of ${R("hai-21.03", "D3").events})`, titleFontSize: 12, titleColor: HEX.dk2, valAxisMinVal: 0,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", titleFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt",
});
s.addChart(pres.charts.BAR, [{ name: "Median time to detect (s)", labels: names, values: dets.map((d) => Math.round(R("hai-21.03", d).ttd_median_s)) }], {
  x: 5.1, y: 1.2, w: 4.4, h: 3.8, barDir: "col", chartColors: [HEX.accent2], showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: HEX.dk1,
  catAxisLabelColor: HEX.dk1, valAxisLabelColor: HEX.accent6, valGridLine: { color: "D9E2E4", size: 0.5 }, catGridLine: { style: "none" }, showLegend: false,
  showTitle: true, title: "Median time to detect, seconds", titleFontSize: 12, titleColor: HEX.dk2, valAxisMinVal: 0,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", titleFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt",
});

s = content("Reading the results honestly", "M3 Results", "Lab 2 makes participants find the missed attacks themselves.");
const d3 = R("hai-21.03", "D3"), d20 = R("hai-20.07", "D3");
card(s, 0.5, 1.3, 4.45, 2.6, "Strengths", `Earliest median detection (${Math.round(d3.ttd_median_s)} s). Best point-wise F1 (${d3.f1.toFixed(2)}). ${Math.round(100 * d3.routing_accuracy)}% of detected attacks routed to an attacked process. ${d3.false_episodes_per_day.toFixed(2)} false alarms per day.`, undefined, { headColor: C.accent3, bodySize: 15 });
card(s, 5.05, 1.3, 4.45, 2.6, "Weaknesses", `Fewer attacks detected than limits or PCA on HAI 21.03. On HAI 20.07 every detector is weak (AIPIR ${d20.events_detected}/${d20.events}). Testbed only: no field results yet.`, undefined, { headColor: C.accent5, bodySize: 15 });
s.addText("Use AIPIR as a layer on top of the alarms you already trust.", { x: 0.5, y: 4.15, w: 9, h: 0.5, fontSize: 15, italic: true, color: C.accent3, isTextBox: true });

// 12-13 zero trust
pres.addSection({ title: "M4 Zero-Trust" });
s = content("Zero-Trust for OT monitoring", "M4 Zero-Trust", "Map each card to a row in deploy/zero-trust/README.md.");
[["Identity", "Signed tokens on every call; Entra ID in a pilot"], ["RBAC", "Roles map to permissions; unknown roles grant nothing"], ["MFA", "Required to request, approve or change configuration"],
 ["Two-person", "The requester never approves their own recovery"], ["Segmentation", "Default-deny network; no route to controllers"], ["Audit", "Hash-chained log of every allow and deny"]]
  .forEach(([h, b], i) => card(s, 0.5 + (i % 3) * 3.05, 1.3 + Math.floor(i / 3) * 1.85, 2.85, 1.7, h, b, i + 1));

s = content("Roles and what they can do", "M4 Zero-Trust", "Admins cannot approve recoveries: separation of duties.");
const rows = [["Role", "Who", "Can", "MFA"], ["aipir.viewer", "Control room", "Read metrics and status", "-"], ["aipir.operator", "Shift engineer", "Request recovery, ack alerts", "Yes"],
  ["aipir.recovery-approver", "Second person", "Approve someone else's recovery", "Yes"], ["aipir.admin", "Platform owner", "Configuration, drift baseline", "Yes"],
  ["aipir.alert-relay", "Alertmanager", "Submit recovery requests", "Workload"], ["aipir.metrics-scraper", "Prometheus, OTel", "Read metrics", "Workload"]];
s.addTable(rows.map((r, i) => r.map((t) => ({ text: t, options: { bold: i === 0, color: i === 0 ? C.background1 : C.text1, fill: { color: i === 0 ? C.text2 : (i % 2 ? C.background2 : C.background1) } } }))),
  { x: 0.5, y: 1.3, w: 9, colW: [2.5, 2.0, 3.4, 1.1], fontSize: 13, border: { type: "solid", pt: 0.5, color: "D9E2E4" }, rowH: 0.45 });

// 14 otel
pres.addSection({ title: "M5 OpenTelemetry" });
s = content("Following an incident in OpenTelemetry", "M5 OpenTelemetry", "Traces carry the timestamps MTTD and MTTR need.");
[["Metrics", "aipir.anomaly.score, aipir.alarm.active{process}, aipir.recovery.events, aipir.config.drift.items"],
 ["Traces", "aipir.alarm: process, peak score, top sensors. aipir.recovery: requested, approved, finished"],
 ["Logs", "Every audit decision and alarm event, with token material scrubbed by the collector"]]
  .forEach(([h, b], i) => card(s, 0.5 + i * 3.05, 1.35, 2.85, 2.6, h, b, i + 1, { bodySize: 14 }));

// 15-16 recover
pres.addSection({ title: "M6 Recover" });
s = content("Four guards before anything changes", "M6 Recover", "Check mode is the default even after approval, until the site signs off.");
[["Approval", "Pending until an approver acts"], ["MFA", "Approver signed in with MFA"], ["Two people", "Approver is not the requester"], ["Baseline integrity", "SHA-256 of the known-good file must match"]]
  .forEach(([h, b], i) => {
    card(s, 0.5 + i * 2.3, 1.45, 2.1, 2.3, h, b, i + 1);
    if (i < 3) s.addShape(pres.shapes.RIGHT_TRIANGLE, { x: 2.62 + i * 2.3, y: 2.45, w: 0.14, h: 0.3, rotate: 90, fill: { color: C.accent6 }, line: { color: C.accent6 }, objectName: `guard arrow ${i}` });
  });
s.addText("Then: the site's own restore command, a verify loop, and an evidence record per host", { x: 0.5, y: 4.05, w: 9, h: 0.6, fontSize: 14, italic: true, color: C.accent3, isTextBox: true });

s = content("IaC library and configuration drift", "M6 Recover", "deploy/validate.sh checks every template with the real tools.");
stat(s, 0.6, 1.4, 2.6, String(N_TEMPLATES), "templates in the IaC library");
stat(s, 0.6, 3.0, 2.6, `${VAL[1]} / ${+VAL[1] + +VAL[2] + +VAL[3]}`, "validation checks passed in the build");
s.addText(bullets(["Terraform modules: detector, Kubernetes RBAC, OTel Collector, Entra ID Zero-Trust",
  "Signed configuration baseline; drift = declared vs live (files, Kubernetes, Terraform)",
  "A drift finding without an approved change counts as a misconfiguration",
  "Recovery of the stack = re-apply the declared state"]), { x: 3.6, y: 1.35, w: 5.9, h: 3.5, fontSize: 15, color: C.text1, isTextBox: true });

// 17 KPIs
pres.addSection({ title: "M7 Measuring a pilot" });
s = content("Measuring a pilot: same rules, both phases", "M7 Measuring a pilot", "The KPI tool computes; it does not supply data. SOW targets stay open until a real pilot measures them.");
const krows = [["KPI", "Definition", "SOW target"], ["MTTD", "detected minus first evidence", "30% lower than baseline"], ["MTTR", "verified recovery minus detection", "40% lower than baseline"],
  ["Availability", "1 - downtime / (window x subsystems)", "99.5% or higher"], ["Misconfigurations", "per 100 changes (incl. unapproved drift)", "2 or fewer"]];
s.addTable(krows.map((r, i) => r.map((t) => ({ text: t, options: { bold: i === 0, color: i === 0 ? C.background1 : C.text1, fill: { color: i === 0 ? C.text2 : (i % 2 ? C.background2 : C.background1) } } }))),
  { x: 0.5, y: 1.3, w: 9, colW: [2.0, 4.3, 2.7], fontSize: 13, border: { type: "solid", pt: 0.5, color: "D9E2E4" }, rowH: 0.45 });
s.addText("Status: open - measured only by the site pilot", { x: 0.5, y: 4.2, w: 9, h: 0.5, fontSize: 15, bold: true, color: C.accent5, isTextBox: true });

// 18 close
pres.addSection({ title: "Close" });
s = pres.addSlide({ masterName: "AIPIR Dark", sectionTitle: "Close" });
s.addText("Quiz, evaluation, next steps", { placeholder: "title" });
s.addText("15-question knowledge check (pass 12). Evaluation form. Replicate at your site with docs/REPLICATION_PLAYBOOK.md.", { placeholder: "body" });
s.addNotes("Hand out QUIZ.md and EVALUATION_FORM.md. Collect the attendance list for certificates.");
n++;

pres.writeFile({ fileName: OUT }).then(async () => {
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT, n, "slides");
});
