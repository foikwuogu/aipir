# Limitations

Written before the discussion section of the manuscript so the paper cannot outrun it.

1. **Testbed, not a field plant.** HAI is a hardware-in-the-loop testbed (real boiler, turbine
   and water-treatment controllers coupled through a simulated steam-turbine and pumped-storage
   hydropower model). Attacks are scripted by the dataset authors. Results show how the detectors
   behave on this testbed; they are not evidence of performance in any operating utility,
   pipeline, or generation facility, and no operator data was used.
2. **One design file.** Every design choice (detector variants, robust normalization, smoothing,
   top-k, baseline settings) was made on a single labelled file, HAI 21.03 test1, which holds
   5 attacks. That is a small development set; choices tuned on it may not be optimal, and the
   held-out files were scored only after the choices were frozen. The event-credit rule (no
   credit for an alarm already active before the attack) was tightened after the first
   development run, before held-out scoring, and applies identically to every detector.
3. **AIPIR is not uniformly better.** On HAI 21.03 the static-limit and PCA baselines detect
   more attack events than the AIPIR predictive detector, and static limits raise fewer false
   alarm episodes; AIPIR's advantages are earlier detection, the best point-wise F1, and process
   routing. On HAI 20.07 every detector is weak, the detectors that find more attacks do so at
   many times the false-alarm budget, and rankings change with the budget (fig4). AIPIR with
   manual recovery alone does not reduce scenario downtime versus static limits. Read results
   per metric.
4. **Layered operating model is post hoc.** Scenario S3 (static limits plus AIPIR) was defined
   after held-out results showed the two detectors miss different events. It is exploratory and
   must be confirmed on new data before it is claimed. Its false-alarm rate is the sum of both
   detectors' rates.
5. **Downtime is a scenario, not a measurement.** Time-to-detect is measured; recovery times
   (manual and IaC/playbook-assisted) and the time to discover a missed attack are assumptions
   [VERIFY V1], swept over ranges. No recovery was executed against a control system. The
   scenario's totals are dominated by missed attacks, so they mainly reflect event recall and the
   assumed discovery time.
6. **Recover layer validated for configuration, not for effect.** Terraform, Kubernetes and
   Prometheus/Alertmanager files are syntax-checked and the detector service was exercised end to
   end in lab mode (replay, metrics, recovery webhook in dry-run). Recovery playbooks are
   illustrative templates; real playbooks require the site's management-of-change process.
7. **Labels are coarse.** Attack labels mark intervals set by the dataset authors; detection
   within the 60 s grace window after an attack ends counts as detection. Point-wise metrics
   reward long alarms, which is why event recall, time-to-detect and false alarms per day are
   reported alongside them.
8. **Routing evaluated only where labels allow.** Routing accuracy uses the attack_P1-P3
   labels; an alarm routed to any process that the attack touched counts as correct. Events with
   several attacked processes therefore make routing easier.
9. **Calibration window.** Thresholds use the last 20 % of each normal file (about two days of
   HAI 21.03 data). A false-alarm budget of one per day cannot be estimated precisely from two
   days; realized test false-alarm rates are reported separately and can exceed the budget.
10. **Model portability.** Models are fitted per dataset version; sensor sets differ between
    versions, so a model is not transferred across versions. Saved models load only with the
    pinned scikit-learn version.
11. **Zero-Trust and recovery are validated in a lab, not at a site.** The access rules, MFA
    checks, two-person rule and audit chain are tested with lab-signed tokens
    (`tests/integration/lab_stack_check.py`). The Entra ID module passes `terraform validate` but
    was not applied to a tenant: its Conditional Access policy needs Entra ID P1 and a tenant
    administrator. Ansible playbooks ran against localhost with placeholder site commands.
12. **Infrastructure templates are validated, not deployed.** Terraform modules were validated
    with OpenTofu 1.8 (Terraform-compatible) and Kubernetes manifests with kubeconform against
    Kubernetes 1.30 schemas. No cluster was provisioned and the container image was not built in
    the build environment (no Docker daemon); the Compose stack is untested as a whole.
13. **The SOW's measured targets are open.** MTTD, MTTR, availability and misconfiguration targets,
    and the 5 TB labelled dataset, can only come from the site pilot. The KPI and drift tools
    compute those measures from site records; they contain no pilot data, and the synthetic
    training records in `docs/training/` must never be reported as results.
