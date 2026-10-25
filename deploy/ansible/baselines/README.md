Signed known-good baselines (setpoint exports, controller configuration exports) live here per
site, never in the public repository. The lab ships small example files so the playbooks run.
Each baseline has a `.sha256` file; `ot_restore` refuses to restore from a file whose hash does
not match, and the drift check (`python -m aipir.drift`) watches this folder.
