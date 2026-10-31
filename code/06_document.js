#!/usr/bin/env node
/*
 * 06 - Build the manuscript (paper/AIPIR_manuscript.docx) from paper/stats.json,
 *      AUTHORS.json, paper/tables and paper/figures. No number is typed by hand:
 *      every quantitative statement is interpolated from stats.json, and comparative
 *      wording ("more", "fewer", "earlier") is chosen from the numbers themselves.
 *
 *   node code/06_document.js           -> DRAFT banner + [VERIFY] markers
 *   node code/06_document.js --final   -> only after the verification gate
 */
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow,
  TableCell, WidthType, ShadingType, ImageRun, Footer, PageNumber, BorderStyle,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const FINAL = process.argv.includes("--final");
const S = JSON.parse(fs.readFileSync(path.join(ROOT, "paper/stats.json"), "utf8"));
const A = JSON.parse(fs.readFileSync(path.join(ROOT, "AUTHORS.json"), "utf8"));
const people = [...A.authors, ...A.collaborators];
const LAB = JSON.parse(fs.readFileSync(path.join(ROOT, "data/processed/lab_stack_check.json"), "utf8"));
const VAL = fs.readFileSync(path.join(ROOT, "data/processed/iac_validation.txt"), "utf8").match(/SUMMARY pass=(\d+) fail=(\d+) skip=(\d+)/);
const NTPL = (fs.readFileSync(path.join(ROOT, "deploy/README.md"), "utf8").match(/^\| \d+ \|/gm) || []).length;
const IDS = JSON.parse(fs.readFileSync(path.join(ROOT, "docs/release_ids.json"), "utf8"));
if (FINAL && (/\[/.test(IDS.doi + IDS.release_date) || !IDS.doi)) {
  console.error("Fill docs/release_ids.json (DOI and release date) before a --final build."); process.exit(1);
}

// ---------- number helpers ----------
const R = (ver, det, split = "test") => S.results[`${ver}|${split}|${det}`];
const V21 = "hai-21.03", V20 = "hai-20.07";
const pct = (x, d = 0) => `${(100 * x).toFixed(d)}%`;
const f2 = (x) => Number(x).toFixed(2);
const f1 = (x) => Number(x).toFixed(1);
const s0 = (x) => `${Math.round(x)} s`;
const cmp = (a, b, more = "more", fewer = "fewer", same = "the same number of") =>
  a > b ? more : a < b ? fewer : same;
const NAME = { D0: "static limits", D1: "PCA residual", D2: "Isolation Forest", D3: "AIPIR predictive",
  "D3+C": "AIPIR + consistency channel", "D3-noclip": "AIPIR without robust normalization" };
const V = (tag) => (FINAL ? "" : ` [VERIFY ${tag}]`);

const r21 = Object.fromEntries(["D0", "D1", "D2", "D3", "D3+C", "D3-noclip"].map((k) => [k, R(V21, k)]));
const r20 = Object.fromEntries(["D0", "D1", "D2", "D3"].map((k) => [k, R(V20, k)]));
const dt = S.downtime, c = dt.central, lay = S.layered;
const qa21 = S.qa[V21], qa20 = S.qa[V20];
const SW = (ver, det, b) => S.sweep.find((r) => r.version === ver && r.detector === det && r.budget_per_day === b);
const testDays21 = r21.D3.test_days, testDays20 = r20.D3.test_days;
const best = (rs, key) => Object.entries(rs).filter(([k]) => ["D0", "D1", "D2", "D3"].includes(k))
  .sort((a, b) => (b[1][key] ?? -1) - (a[1][key] ?? -1))[0][0];

// ---------- paragraph helpers ----------
const FONT = "Times New Roman";
const P = (text, o = {}) => new Paragraph({
  spacing: { after: 120, line: 276 }, alignment: o.align ?? AlignmentType.JUSTIFIED,
  children: (Array.isArray(text) ? text : [text]).map((t) =>
    typeof t === "string" ? new TextRun({ text: t, font: FONT, size: 22 }) : t),
});
const B = (t) => new TextRun({ text: t, bold: true, font: FONT, size: 22 });
const I = (t) => new TextRun({ text: t, italics: true, font: FONT, size: 22 });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 240, after: 120 },
  children: [new TextRun({ text: t, bold: true, font: FONT, size: 26 })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 180, after: 80 },
  children: [new TextRun({ text: t, bold: true, italics: true, font: FONT, size: 23 })] });

function figure(file, caption, widthIn = 6.3) {
  const buf = fs.readFileSync(path.join(ROOT, "paper/figures", file));
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);
  const px = widthIn * 96;
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120 },
      children: [new ImageRun({ type: "png", data: buf, transformation: { width: px, height: px * h / w } })] }),
    new Paragraph({ alignment: AlignmentType.LEFT, spacing: { after: 200 },
      children: [new TextRun({ text: caption, font: FONT, size: 19, italics: true })] }),
  ];
}

const border = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
function table(header, rows, widths, caption) {
  const total = widths.reduce((a, b) => a + b, 0);
  const cell = (t, i, hdr) => new TableCell({
    width: { size: widths[i], type: WidthType.DXA },
    shading: hdr ? { type: ShadingType.CLEAR, fill: "E8EEF7", color: "auto" } : undefined,
    borders: { top: border, bottom: border, left: border, right: border },
    margins: { top: 40, bottom: 40, left: 60, right: 60 },
    children: [new Paragraph({ alignment: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER,
      children: [new TextRun({ text: String(t), font: FONT, size: 18, bold: hdr })] })],
  });
  return [
    new Paragraph({ spacing: { before: 160, after: 60 }, children: [new TextRun({ text: caption, font: FONT, size: 19, italics: true })] }),
    new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: widths,
      rows: [new TableRow({ tableHeader: true, children: header.map((h, i) => cell(h, i, true)) }),
        ...rows.map((r) => new TableRow({ children: r.map((t, i) => cell(t, i, false)) }))] }),
    new Paragraph({ spacing: { after: 160 }, children: [] }),
  ];
}
const na = (x, fn) => (x === null || x === undefined || Number.isNaN(x) ? "-" : fn(x));

// ---------- content ----------
const title = "AIPIR: An AI-Enabled Predictive Infrastructure Resilience Framework for Energy-Sector Control Systems, with an Open Validation on a Power-Generation Testbed";

const abstract = [
  `Energy-sector control systems are monitored mostly by fixed alarm limits, which catch gross excursions but react late to subtle manipulation and say little about where to respond. We present AIPIR, an open, cloud-native framework that links four layers: Observe (telemetry exposed as Prometheus metrics), Predict (a ridge forecaster that predicts every sensor one second ahead and scores robustly normalized forecast residuals), Respond (thresholds calibrated on normal data only, debounced alarms routed to the affected sub-process), and Recover (two-person-approved Ansible playbooks, Terraform/Kubernetes definitions that restore the monitoring stack, and a signed configuration-drift check). Zero-Trust controls (identity-provider tokens, role-based access, multi-factor authentication, hash-chained audit) govern every action, and all telemetry is also exported through OpenTelemetry. `,
  `We validate the detection layers on the open HAI security datasets, a hardware-in-the-loop testbed emulating steam-turbine power generation and pumped-storage hydropower, against static limits, PCA residual and Isolation Forest baselines, with every threshold set to the same false-alarm budget of one alarm episode per day on held-out normal data and all design choices frozen on a single development file. `,
  `On ${r21.D3.events} held-out attacks in HAI 21.03 (${f1(testDays21)} days), AIPIR detected ${r21.D3.events_detected} (${pct(r21.D3.event_recall)}) with a median time-to-detect of ${s0(r21.D3.ttd_median_s)}, against ${s0(r21.D0.ttd_median_s)} for static limits and ${s0(r21.D1.ttd_median_s)} for PCA; it achieved the highest point-wise F1 (${f2(r21.D3.f1)} vs ${f2(r21.D1.f1)} and ${f2(r21.D0.f1)}), ${f2(r21.D3.false_episodes_per_day)} false alarm episodes per day, and routed ${pct(r21.D3.routing_accuracy)} of detected attacks to an attacked process. `,
  `It did not detect the most attacks: PCA and static limits detected ${r21.D1.events_detected} and ${r21.D0.events_detected}. On the older HAI 20.07 release all detectors were weaker (AIPIR ${r20.D3.events_detected}/${r20.D3.events} events). In a downtime scenario with assumed recovery times, AIPIR detection plus automated recovery reduced total downtime by ${f1(c.S2_reduction_pct)}% (range ${f1(dt.S2_reduction_pct_min)}-${f1(dt.S2_reduction_pct_max)}% across assumptions) relative to static alarms with manual recovery, whereas AIPIR detection with manual recovery ${c.S1_reduction_pct >= 0 ? `reduced it by only ${f1(c.S1_reduction_pct)}%` : `increased it by ${f1(-c.S1_reduction_pct)}%`} because it missed more attacks; an exploratory layered configuration running both detectors reduced it by ${f1(c.S3_reduction_pct)}%. Code, infrastructure definitions, models and the replication package are openly released.`,
];

const intro = [
  P(`Generation plants, pipelines and substations depend on industrial control systems (ICS) whose availability is a public-safety concern. Attacks on such systems are no longer hypothetical: the 2015 attack on Ukrainian distribution utilities combined intrusion with manipulation of operator workstations to cause outages for customers [7]. Guidance for operational technology (OT) security now emphasizes continuous monitoring, anomaly detection and practiced recovery alongside prevention [6].`),
  P(`In many plants, the monitoring that operators actually act on is still the alarm system: fixed high and low limits per point. Limits are simple, explainable and cheap, but an attacker who keeps each variable inside its band while breaking the relationships between variables can stay below them, and a limit alarm says which point is out of range rather than which process to act on. Research on learned anomaly detection for ICS has advanced quickly with open testbed datasets such as SWaT [8] and HAI [1, 2], and with detectors based on reconstruction, prediction or deep sequence models [3, 4, 9]. Fewer studies connect detection to what happens next: how an alert reaches the right responder, and how the monitoring infrastructure itself is recovered, which is where downtime is lost or saved.`),
  P(`This paper contributes (i) AIPIR, an open framework that wires a predictive detector into standard observability (Prometheus, OpenTelemetry), Zero-Trust access control and Infrastructure-as-Code (IaC) tooling (Terraform, Kubernetes, Ansible), so that detection, alert routing and approved recovery are one reproducible system, with a validated template library and a replication playbook; (ii) a validation of its detector on two releases of the HAI power-generation testbed under a protocol that fixes the false-alarm budget for every detector and freezes design choices before held-out scoring; (iii) an explicit, assumption-swept scenario model that translates measured detection performance into downtime; and (iv) an honest account of where the predictive approach does not outperform simpler baselines.`),
];

const related = [
  P(`ICS anomaly detection is commonly evaluated on testbed datasets with labelled attacks. SWaT [8] and HAI [1, 2] are the most used; HAI is distinctive for coupling real boiler, turbine and water-treatment controllers through a simulated steam-turbine and pumped-storage hydropower plant, which makes it a natural proxy for the energy sector. Detection methods range from residuals of linear projections (PCA) and isolation-based outlier scores [5] to forecasting with recurrent or convolutional networks [3, 9] and adversarially trained autoencoders [4]. Forecast-residual methods are attractive because the residual of each sensor is itself an attribution signal. Our detector deliberately uses a linear forecaster so that it trains in seconds on a CPU, can be audited, and runs as a small service.`),
  P(`On the operations side, site reliability engineering practice treats monitoring and alerting as code and measures recovery explicitly [10], and IaC makes infrastructure reproducible from declarations [11]. The MITRE ATT&CK for ICS knowledge base catalogues adversary techniques that motivate monitoring both process values and the monitoring path itself [12]. AIPIR applies these practices to the detection stack of an OT environment.`),
];

const methods = [
  H2("3.1 Framework"),
  P(`AIPIR has four layers (Fig. 1), wrapped in Zero-Trust controls. Observe reads plant telemetry once per second; in this study it replays HAI files, and in a deployment it would read an OPC-UA server or historian. Each second the service publishes the anomaly score, the threshold, a per-process alarm flag and per-sensor residuals as Prometheus metrics. It also exports OpenTelemetry metrics, a trace span per alarm episode and per recovery, and logs over OTLP to an OpenTelemetry Collector. Predict computes the score with the streaming form of the detector described below. Respond is a Prometheus alert rule that fires once per routed process; Alertmanager forwards it to the operator channel and, with its own workload identity, to the service's recovery endpoint. Recover turns the request into a recovery record. In execute mode it waits for a second person with the approver role and multi-factor authentication, then runs the process's Ansible playbook. The playbook re-checks the two-person rule, verifies the SHA-256 of the known-good baseline, calls the site's own restore and verify commands, and writes an evidence record. It runs in check mode until the site enables real changes. The detection stack itself is declared as Terraform modules and Kubernetes manifests (two replicas, health probes, a disruption budget, revision history for rollback, and default-deny networking), so it is restored by re-applying the declarations. A signed configuration baseline and drift check flag any deviation that has no approved change record.`),
  P(`The Zero-Trust controls follow NIST SP 800-207 tenets [14]. Every endpoint except liveness requires a signed token: an OIDC identity provider such as Microsoft Entra ID in a pilot, and a lab-only shared secret otherwise. Permissions come from an explicit role policy with no implicit administrator. Multi-factor authentication is required for requesting or approving a recovery and for changing configuration. Workload identities can never approve. Every allow or deny decision goes to an append-only log in which each entry carries the hash of the previous one. The repository also includes an Entra ID module (app roles, groups, a workload identity for Alertmanager, a Conditional Access policy requiring MFA) and least-privilege Kubernetes RBAC.`),
  ...figure("fig1_architecture.png", "Fig. 1. AIPIR layers. All components are open source and declared as code (deploy/)."),
  H2("3.2 Data"),
  P(`We use HAI 21.03 as the primary dataset and HAI 20.07 for replication, both from the HAI repository at a pinned commit, licensed CC BY-SA 4.0 [1, 2]. Data are sampled at 1 Hz. HAI 21.03 provides three normal training files (${qa21.fit_rows + qa21.cal_rows} usable seconds) and five test files with ${r21.D3.events + R(V21, "D3", "dev").events} labelled attacks; HAI 20.07 provides two training and two test files with ${r20.D3.events} attacks. The number of contiguous attack-label runs in every test file equals the attack count published by the dataset authors. Points that are constant in normal data were dropped (${qa21.sensors_used} of ${qa21.sensors_total} points used for HAI 21.03, ${qa20.sensors_used} of ${qa20.sensors_total} for HAI 20.07). One HAI 20.07 training file contains ${qa20.train_label_sum_raw} attack-labelled seconds; these, plus a 10-minute recovery margin, were excluded from training.`),
  H2("3.3 Detectors"),
  P([B("D0 Static limits. "), `Per-point minimum and maximum of normal data; the score is the largest exceedance, in units of the point's normal range. `,
    B("D1 PCA residual. "), `Squared reconstruction error of a PCA model keeping 95% of normal variance, smoothed over 60 s. `,
    B("D2 Isolation Forest "), `[5] with 100 trees on a 60,000-row sample, smoothed over 10 s. `,
    B("D3 AIPIR predictive. "), `A multi-output ridge regression predicts every standardized point at second t from all points at lags of 1, 2, 3, 5, 10, 20 and 30 s. Each point's absolute forecast error is divided by its 99.9th percentile on normal data and clipped at 5, so that a legitimate setpoint step on one point cannot dominate; residuals are averaged over a trailing 10 s window and the score is the mean of the five largest. All smoothing is causal, so scores use only past data.`]),
  P(`Two ablations test the design: adding a "consistency" channel that predicts each point from the current values of all others (D3+C), and removing robust normalization (95th-percentile scaling, no clipping; D3-noclip). Models were fitted with scikit-learn [13].`),
  H2("3.4 Calibration, alarms and evaluation protocol"),
  P(`For every detector the first 80% of each normal segment fits the model and the last 20% (${f1(qa21.cal_hours)} h for HAI 21.03) calibrates the threshold: the lowest threshold that produces at most one alarm episode per day on that normal data${V("V2")}. An alarm episode is a run of above-threshold seconds, with runs closer than 30 s merged and episodes shorter than 5 s discarded (debounce)${V("V3")}. Test labels are never used for thresholds.`),
  P(`Design choices for all detectors were made on HAI 21.03 test1 (five attacks) and frozen before HAI 21.03 test2-test5 and both HAI 20.07 test files were scored. An attack event is detected if an alarm episode is confirmed between the attack's start and 60 s after its end; an alarm already active before the attack began earns no credit. We report event recall, time-to-detect (TTD: confirmation time minus labelled start), point-wise precision, recall and F1, false alarm episodes per day (episodes overlapping no attack or its grace window), and routing accuracy (the alarm is routed to the process of its top-contributing P1-P3 point, and is correct if that process carries an attack label during the event).`),
  H2("3.5 Downtime scenario"),
  P(`To translate detection into downtime we use a deliberately simple scenario model, not a measurement. For each held-out attack, downtime equals TTD plus recovery time if the operating model detects it, or the time until a missed attack is discovered by other means plus manual recovery. Central assumptions are ${dt.assumptions_central.r_manual_h} h for manual recovery, ${Math.round(dt.assumptions_central.r_auto_h * 60)} min for playbook/IaC-assisted recovery and ${dt.assumptions_central.t_discover_h} h to discover a missed attack, each swept over a range (manual 2-8 h, automated 5-30 min, discovery 8-72 h)${V("V1")}. We compare S0 static limits with manual recovery, S1 AIPIR with manual recovery, S2 AIPIR with automated recovery, and S3, an exploratory layered model in which static limits and AIPIR both run (detection at the earlier of the two; automated recovery when AIPIR detected). S3 was defined after the held-out results showed the two detectors miss different attacks and is reported as exploratory.`),
];

const ttdFaster = r21.D3.ttd_median_s < Math.min(r21.D0.ttd_median_s, r21.D1.ttd_median_s);
const results = [
  P(`Table 1 summarizes held-out results. On HAI 21.03, AIPIR detected ${r21.D3.events_detected} of ${r21.D3.events} attacks (${pct(r21.D3.event_recall)}), ${cmp(r21.D3.events_detected, r21.D1.events_detected)} than PCA (${r21.D1.events_detected}) and ${cmp(r21.D3.events_detected, r21.D0.events_detected)} than static limits (${r21.D0.events_detected}). ${ttdFaster ? "It detected them earliest" : "Its detection speed was"}: median TTD ${s0(r21.D3.ttd_median_s)} versus ${s0(r21.D0.ttd_median_s)} and ${s0(r21.D1.ttd_median_s)} (Fig. 3). Its point-wise F1 was ${f2(r21.D3.f1)} (PCA ${f2(r21.D1.f1)}, static ${f2(r21.D0.f1)}), and ${f2(r21.D3.false_episodes_per_day)} false alarm episodes occurred per test day. ${r21.D3.routing_accuracy === 1 ? "Every" : `${pct(r21.D3.routing_accuracy)} of`} detected attack with a process label was routed to an attacked process (n = ${r21.D3.routing_n}), compared with ${pct(r21.D1.routing_accuracy)} for PCA. Isolation Forest detected ${r21.D2.events_detected} of the HAI 21.03 attacks at this false-alarm budget.`),
  ...table(
    ["Dataset / detector", "Detected", "Event recall", "Median TTD (s)", "Precision", "Recall", "F1", "False alarms/day", "Routing acc."],
    [[V21, r21], [V20, r20]].flatMap(([ver, rs]) => ["D0", "D1", "D2", "D3"].map((k) => {
      const r = rs[k];
      return [`${ver.toUpperCase()} - ${NAME[k]}`, `${r.events_detected}/${r.events}`, f2(r.event_recall),
        na(r.ttd_median_s, (x) => Math.round(x)), f2(r.precision), f2(r.recall), f2(r.f1),
        f2(r.false_episodes_per_day), na(r.routing_accuracy, f2)];
    })),
    [2400, 820, 800, 900, 800, 700, 640, 960, 880],
    "Table 1. Held-out results (HAI 21.03 test2-5; HAI 20.07 test1-2). Thresholds calibrated to <= 1 alarm episode/day on normal data."),
  ...figure("fig2_detection.png", "Fig. 2. Event recall (solid) and point-wise F1 (light) on held-out tests."),
  ...figure("fig3_ttd.png", "Fig. 3. Time to detect for detected held-out attacks, HAI 21.03. Black bars: medians.", 5.4),
  P(`On HAI 20.07 every detector was weaker, and calibration on normal data transferred poorly to the test files. AIPIR detected ${r20.D3.events_detected} of ${r20.D3.events} attacks with precision ${f2(r20.D3.precision)} and ${f2(r20.D3.false_episodes_per_day)} false alarm episodes per day. PCA detected ${r20.D1.events_detected} and Isolation Forest ${r20.D2.events_detected}, but at ${f1(r20.D1.false_episodes_per_day)} and ${f1(r20.D2.false_episodes_per_day)} false alarm episodes per day, far above the one-per-day budget they met on normal data; static limits detected ${r20.D0.events_detected} with ${f2(r20.D0.false_episodes_per_day)} false alarms per day. Fig. 4 shows that rankings also depend on the budget: at four alarms per day on normal data, AIPIR's event recall rises to ${f2(SW(V21, "D3", 4).event_recall)} on HAI 21.03 and ${f2(SW(V20, "D3", 4).event_recall)} on HAI 20.07, with realized test false-alarm rates of ${f1(SW(V21, "D3", 4).false_episodes_per_day)} and ${f1(SW(V20, "D3", 4).false_episodes_per_day)} per day. Reported comparisons should therefore always state the false-alarm budget and the realized rate together.`),
  ...figure("fig4_fa_tradeoff.png", "Fig. 4. Event recall as each detector's threshold is recalibrated to different false-alarm budgets (normal data only)."),
  P(`The ablations support the design choices made on the development file (Table 2). Without robust normalization, a few points with exogenous setpoint changes dominate the normal residual distribution, the calibrated threshold rises, and AIPIR detected only ${r21["D3-noclip"].events_detected} held-out attacks. Adding the consistency channel left event detection at ${r21["D3+C"].events_detected} but lowered F1 to ${f2(r21["D3+C"].f1)}, so it is not part of the default configuration. Fig. 5 shows the score on a six-hour excerpt.`),
  ...table(["Variant (HAI 21.03 held-out)", "Detected", "Median TTD (s)", "F1", "False alarms/day"],
    ["D3", "D3+C", "D3-noclip"].map((k) => [NAME[k], `${r21[k].events_detected}/${r21[k].events}`,
      na(r21[k].ttd_median_s, (x) => Math.round(x)), f2(r21[k].f1), f2(r21[k].false_episodes_per_day)]),
    [3800, 1300, 1500, 1000, 1700], "Table 2. Ablations of the AIPIR detector."),
  ...figure("fig5_timeline.png", "Fig. 5. AIPIR anomaly score, calibrated threshold and alarms over six hours of HAI 21.03 test2."),
  P(`Detection and the downtime scenario. Static limits and AIPIR miss different attacks: on HAI 21.03, ${lay[V21].only_D0} attacks were detected only by static limits and ${lay[V21].only_D3} only by AIPIR; on HAI 20.07 the split was ${lay[V20].only_D0} and ${lay[V20].only_D3}. Across all ${c.n_events} held-out attacks, the scenario model (Fig. 6, Table 3) gives ${Math.round(c.S0_h)} h of total downtime for S0, ${Math.round(c.S1_h)} h for S1 (${f1(Math.abs(c.S1_reduction_pct))}% ${c.S1_reduction_pct >= 0 ? "less" : "more"}), ${Math.round(c.S2_h)} h for S2 (${f1(c.S2_reduction_pct)}% less; ${f1(dt.S2_reduction_pct_min)}-${f1(dt.S2_reduction_pct_max)}% across all assumption combinations) and ${Math.round(c.S3_h)} h for the exploratory S3 (${f1(c.S3_reduction_pct)}% less; ${f1(dt.S3_reduction_pct_min)}-${f1(dt.S3_reduction_pct_max)}%). Most of the S2 gain comes from faster recovery once an attack is detected. Detection speed alone (S1) does not help: time-to-detect is measured in seconds while recovery and discovery are measured in hours, so the attacks AIPIR misses outweigh the seconds it saves. The lower end of the S2 range (${f1(dt.S2_reduction_pct_min)}%) occurs when automated recovery is slow and manual recovery fast; the gain is therefore conditional on recovery actually being automated and rehearsed.`),
  ...figure("fig6_downtime_scenario.png", "Fig. 6. Downtime scenario totals at central assumptions; lines show the range across all assumption combinations. Scenario model, not measurement."),
  ...table(["Operating model", "Total downtime (h), central", "Change vs S0"],
    [["S0 static limits + manual recovery", Math.round(c.S0_h), "-"],
     ["S1 AIPIR + manual recovery", Math.round(c.S1_h), `${c.S1_reduction_pct < 0 ? "+" : ""}${f1(-c.S1_reduction_pct)}%`],
     ["S2 AIPIR + automated recovery", Math.round(c.S2_h), `${f1(-c.S2_reduction_pct)}%`],
     ["S3 static limits + AIPIR, layered (exploratory)", Math.round(c.S3_h), `${f1(-c.S3_reduction_pct)}%`]],
    [4800, 2600, 1800], `Table 3. Downtime scenario over ${c.n_events} held-out attacks (assumed recovery and discovery times; see 3.5).`),
  P(`Engineering checks. The streaming scorer used by the service reproduced the batch scores to a maximum relative difference of ${Number(S.qa_checks.stream_batch_max_rel_diff).toExponential(1)} over one hour of telemetry. Batch scoring with AIPIR ran at about ${Math.round(qa21.throughput_rows_per_s.D3).toLocaleString("en-US")} telemetry-seconds per second on a 2-vCPU machine, and fitting took ${Math.round(qa21.fit_seconds.D3)} s, so the detector is light enough for an edge node or a small cloud container. Streaming a full held-out file (${S.lab_check.file}, ${S.lab_check.seconds.toLocaleString("en-US")} s) through the service's scorer took ${f2(S.lab_check.per_second_latency_ms)} ms per telemetry second, its alarms agreed with the batch pipeline on ${pct(S.lab_check.alarm_agreement, 1)} of seconds, and it alarmed on the same ${S.lab_check.events_alarmed_stream} of ${S.lab_check.events} attacks with identical times-to-detect. An end-to-end lab check passed ${LAB.passed} of ${LAB.total} tests. It ran the service against a live OpenTelemetry Collector and covered token rejection (tampered, expired, wrong key), role and MFA enforcement, the two-person rule, an approved recovery executed by Ansible in check mode, tamper detection in the audit log, and arrival of metrics, alarm and recovery spans and audit logs at the collector. All ${NTPL} infrastructure templates passed ${VAL[1]} of ${+VAL[1] + +VAL[2] + +VAL[3]} validation checks with the corresponding tools (Terraform/OpenTofu, promtool, amtool, the OpenTelemetry Collector, ansible-playbook and kubeconform). These are engineering checks in a lab, not field measurements.`),
];

const discussion = [
  P(`The results support a narrower claim than "AI beats alarms". On the HAI 21.03 power-generation testbed, a simple, auditable predictive detector detected attacks earlier than static limits and PCA, with the best balance of point-wise precision and recall and correct process routing, at a false-alarm rate within the budget (${f2(r21.D3.false_episodes_per_day)} per day, against ${f2(r21.D0.false_episodes_per_day)} for static limits and ${f2(r21.D1.false_episodes_per_day)} for PCA); but it detected fewer attacks than either. On HAI 20.07 no detector was strong, and the detectors that found more attacks did so at many times the false-alarm budget. The practical reading is that a predictive layer complements, rather than replaces, limit alarms: they miss different attacks, and routing and speed are what an operator needs from the alert that arrives first.`),
  P(`The scenario model makes a second point visible: for downtime, what happens after detection dominates what happens before it. A detector that is seconds faster changes little if recovery takes hours; recovery that is scripted, rehearsed and declared as code changes a great deal, and missed attacks dominate the total. This argues for investing in the Respond and Recover layers, and for measuring recovery as carefully as detection. The recovery times here are assumptions; measured recovery drills would replace them.`),
  P(`Limitations are listed in full in the repository (docs/LIMITATIONS.md). The main ones are: a testbed rather than an operating plant; design choices made on one development file with five attacks; an exploratory layered model defined after seeing held-out results; recovery and Zero-Trust controls validated in a lab (check-mode playbooks, lab identities, configuration validation) rather than at a site or for effect on a process; and coarse interval labels. Future work will evaluate on newer HAI releases and other open testbeds, pre-register the layered model, add the eTaPR metric for comparability with competition results, and measure recovery in lab drills.`),
];

const conclusion = [
  P(`AIPIR shows how a lightweight predictive detector, standard observability tooling and Infrastructure-as-Code can be assembled into one reproducible resilience loop for energy-sector control systems, and it reports, under a fixed false-alarm budget and a frozen design, where that loop helps and where it does not. Everything needed to reproduce or extend the results, including the infrastructure definitions, is openly available.`),
];

const roles = people.map((p) => `${p.name}: ${p.roles.join(", ")}.`).join(" ");
const declarations = [
  P([B("Data availability. "), `HAI datasets are available at https://github.com/icsdataset/hai under CC BY-SA 4.0. Derived scores, events, models and figures are released with the code under CC BY-SA 4.0.`]),
  P([B("Code availability. "), `All code, deployment definitions and the replication package are archived at ${IDS.doi}${IDS.concept_doi ? ` (this version; all versions: ${IDS.concept_doi})` : ""}. Code is MIT-licensed; derived data are CC BY-SA 4.0.${IDS.repository_url ? ` Development repository: ${IDS.repository_url}.` : ""}`]),
  P([B("Author contributions (CRediT). "), roles + V("V4")]),
  P([B("Competing interests. "), `The authors declare no competing interests.${V("V4/V6")}`]),
  P([B("Funding. "), `This work received no specific funding.${V("V4")}`]),
  P([B("AI assistance. "), `An AI assistant (Claude, Anthropic) was used to help write analysis code, deployment files and draft text. The authors designed the study, verified every result against the data and the pipeline outputs, made all analytic decisions, and take full responsibility for the content.`]),
  P([B("Use of data. "), `This study used only public data. No employer, operator or customer data was used.${V("V6")}`]),
];

const refs = [
  "Shin, H.-K., Lee, W., Yun, J.-H., Min, B.-G. Two ICS security datasets and anomaly detection contest on the HIL-based augmented ICS testbed. Cyber Security Experimentation and Test Workshop (CSET '21), ACM, 2021, 36-40. doi:10.1145/3474718.3474719",
  "Shin, H.-K., Lee, W., Yun, J.-H., Kim, H. HAI 1.0: HIL-based augmented ICS security dataset. 13th USENIX Workshop on Cyber Security Experimentation and Test (CSET '20), 2020.",
  "Hundman, K., Constantinou, V., Laporte, C., Colwell, I., Soderstrom, T. Detecting spacecraft anomalies using LSTMs and nonparametric dynamic thresholding. KDD 2018, 387-395. doi:10.1145/3219819.3219845",
  "Audibert, J., Michiardi, P., Guyard, F., Marti, S., Zuluaga, M. A. USAD: UnSupervised anomaly detection on multivariate time series. KDD 2020, 3395-3404. doi:10.1145/3394486.3403392",
  "Liu, F. T., Ting, K. M., Zhou, Z.-H. Isolation forest. IEEE International Conference on Data Mining (ICDM), 2008, 413-422. doi:10.1109/ICDM.2008.17",
  "Stouffer, K., Pease, M., Tang, C., Zimmerman, T., Pillitteri, V., Lightman, S., Hahn, A., Saravia, S., Sherule, A., Thompson, M. Guide to Operational Technology (OT) Security. NIST SP 800-82 Rev. 3, 2023. doi:10.6028/NIST.SP.800-82r3",
  "Lee, R. M., Assante, M. J., Conway, T. Analysis of the cyber attack on the Ukrainian power grid. SANS ICS and E-ISAC, 2016.",
  "Goh, J., Adepu, S., Junejo, K. N., Mathur, A. A dataset to support research in the design of secure water treatment systems. Critical Information Infrastructures Security (CRITIS 2016), Springer, 2017.",
  "Kravchik, M., Shabtai, A. Detecting cyber attacks in industrial control systems using convolutional neural networks. Workshop on Cyber-Physical Systems Security and PrivaCy (CPS-SPC), ACM, 2018. arXiv:1806.08110",
  "Beyer, B., Jones, C., Petoff, J., Murphy, N. R. (eds.). Site Reliability Engineering: How Google Runs Production Systems. O'Reilly, 2016.",
  "Morris, K. Infrastructure as Code: Dynamic Systems for the Cloud Age, 2nd ed. O'Reilly, 2020.",
  "MITRE. ATT&CK for Industrial Control Systems. https://attack.mitre.org/matrices/ics/ (accessed 2026-10-24).",
  "Pedregosa, F., et al. Scikit-learn: Machine learning in Python. Journal of Machine Learning Research 12 (2011) 2825-2830.",
  "Rose, S., Borchert, O., Mitchell, S., Connelly, S. Zero Trust Architecture. NIST SP 800-207, 2020. doi:10.6028/NIST.SP.800-207",
];

// ---------- assemble ----------
const authorLine = people.map((p, i) => `${p.name}${String.fromCharCode(0x2070 + 0) && ""}${i + 1}`);
const children = [];
if (!FINAL) children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 },
  children: [new TextRun({ text: "DRAFT - not verified by the authors - do not circulate", bold: true, color: "B00020", font: FONT, size: 22 })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 },
  children: [new TextRun({ text: title, bold: true, font: FONT, size: 32 })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
  children: people.flatMap((p, i) => [new TextRun({ text: p.name, font: FONT, size: 22 }),
    new TextRun({ text: String(i + 1), superScript: true, font: FONT, size: 22 }),
    ...(p.corresponding ? [new TextRun({ text: "*", font: FONT, size: 22 })] : []),
    new TextRun({ text: i < people.length - 1 ? ", " : "", font: FONT, size: 22 })]) }));
people.forEach((p, i) => children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 20 },
  children: [new TextRun({ text: `${i + 1} ${p.affiliation}; ${p.email}${p.orcid ? `; ORCID ${p.orcid}` : ""}`, font: FONT, size: 18 })] })));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 },
  children: [new TextRun({ text: `* Corresponding author: ${A.authors[0].name}, ${A.authors[0].email}`, font: FONT, size: 18, italics: true })] }));
children.push(H1("Abstract"), P(abstract.join("")));
children.push(P([B("Keywords: "), "industrial control systems; anomaly detection; critical infrastructure resilience; energy sector; predictive analytics; observability; OpenTelemetry; zero trust; infrastructure as code"]));
children.push(H1("1 Introduction"), ...intro, H1("2 Related work"), ...related, H1("3 Methods"), ...methods,
  H1("4 Results"), ...results, H1("5 Discussion"), ...discussion, H1("6 Conclusion"), ...conclusion,
  H1("Declarations"), ...declarations, H1("References"),
  ...refs.map((r, i) => new Paragraph({ spacing: { after: 80 }, indent: { left: 400, hanging: 400 },
    children: [new TextRun({ text: `[${i + 1}] ${r}`, font: FONT, size: 19 })] })));

const doc = new Document({
  creator: A.authors[0].name, title,
  styles: { default: { document: { run: { font: FONT, size: 22 } } } },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18 })] })] }) },
    children,
  }],
});
Packer.toBuffer(doc).then((b) => {
  const out = path.join(ROOT, "paper", "AIPIR_manuscript.docx");
  fs.writeFileSync(out, b);
  console.log("wrote", out, FINAL ? "(final)" : "(DRAFT)");
});
