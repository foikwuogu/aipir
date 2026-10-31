#!/usr/bin/env python3
"""Write the release identifiers into every file that cites them, so nothing is edited by hand.

    python scripts/set_release_ids.py --doi 10.5281/zenodo.NNNN [--concept-doi 10.5281/zenodo.MMMM]
                                      [--repo https://github.com/<user>/aipir]

--doi          this version's DOI (the one reserved on the Zenodo draft you are about to publish)
--concept-doi  the "Cite all versions" DOI (exists after the first version is published)
--repo         the public GitHub repository URL (optional)

Updates docs/release_ids.json, CITATION.cff and docs/zenodo_metadata.json. The README and the
manuscript read docs/release_ids.json when they are rebuilt (scripts/make_zenodo_release.sh).
"""
import argparse
import json
import re

DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--doi", required=True)
    ap.add_argument("--concept-doi")
    ap.add_argument("--repo")
    a = ap.parse_args()
    clean = lambda d: d.replace("https://doi.org/", "").strip() if d else d  # noqa: E731
    doi, concept = clean(a.doi), clean(a.concept_doi)
    for d in filter(None, [doi, concept]):
        if not DOI_RE.match(d):
            raise SystemExit(f"not a DOI: {d}")
    if a.repo and not re.match(r"^https://github\.com/[\w.-]+/[\w.-]+/?$", a.repo):
        raise SystemExit(f"repository URL should look like https://github.com/<user>/aipir, got {a.repo}")
    repo = a.repo.rstrip("/") if a.repo else ""

    ids = json.load(open("docs/release_ids.json"))
    ids.update({"doi": f"https://doi.org/{doi}", "repository_url": repo})
    ids["concept_doi"] = f"https://doi.org/{concept}" if concept else ""
    json.dump(ids, open("docs/release_ids.json", "w"), indent=2)

    c = open("CITATION.cff").read()
    c = re.sub(r'^doi: .*\n', "", c, flags=re.M)
    c = re.sub(r'^repository-code: .*\n', "", c, flags=re.M)
    c = re.sub(r'^identifiers:\n(?:  - .*\n|    .*\n)+', "", c, flags=re.M)
    extra = f'doi: "{doi}"\n'
    if concept:
        extra += ("identifiers:\n  - type: doi\n    value: \"%s\"\n    description: \"Concept DOI (all versions)\"\n"
                  "  - type: doi\n    value: \"%s\"\n    description: \"This version\"\n" % (concept, doi))
    if repo:
        extra += f'repository-code: "{repo}"\n'
    c = re.sub(r'^(license: .*\n)', r"\1" + extra.replace("\\", "\\\\"), c, count=1, flags=re.M)
    open("CITATION.cff", "w").write(c)

    z = json.load(open("docs/zenodo_metadata.json"))
    z["doi"] = doi
    rel = [r for r in z.get("related_identifiers", []) if "[" not in r["identifier"] and "github.com" not in r["identifier"]]
    if repo:
        rel.insert(0, {"identifier": repo, "relation": "isSupplementTo", "scheme": "url"})
    z["related_identifiers"] = rel
    json.dump(z, open("docs/zenodo_metadata.json", "w"), indent=2, ensure_ascii=False)
    print(f"version DOI {doi}" + (f", concept DOI {concept}" if concept else "") + (f", repository {repo}" if repo else ""))


if __name__ == "__main__":
    main()
