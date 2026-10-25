# Next steps (v0.2 and beyond)

- Evaluate on HAI 22.04 / 23.05 (Git LFS downloads) and on a second open testbed family
  (e.g., power-system or gas-pipeline ICS datasets with permissive licenses).
- Pre-register the layered (static limits + AIPIR) operating model and test it on data not yet
  seen, so scenario S3 can move from exploratory to confirmatory.
- Replace the dev-file design with nested cross-validation across test files.
- Add the eTaPR metric used by the HAICon competitions for comparability with published results.
- Measure real recovery times in a lab exercise (tabletop + Kubernetes rollback drills) to
  replace the assumed recovery times in the downtime scenario.
- Add an OPC-UA reader to the Observe layer and an Ansible hook for `execute` recovery mode,
  behind a two-person approval step.
- Package `framework/` for PyPI and consider a JOSS submission once the API is stable.
