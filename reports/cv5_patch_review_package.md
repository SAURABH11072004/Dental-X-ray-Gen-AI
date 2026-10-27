# CV5 import wiring, BASE-P2 path and reviewer authorization: review package

Date 2026-10-25. **Status: proposal for owner review.**
* Nothing here is applied, registered or signed.
* `kaggle/make_cv5_notebook.py` (frozen, Amendment 01b, `4a5efda8…`) is **unchanged**; its wiring change exists only as a patch file.
* No training, test-set use, ledger disclosure, candidate reservation, data request or commit took place.
* All clinical artifacts in the tests are synthetic fixtures. **Real-data validity is unverified.**

## 1. Integrity at the start of this work (recomputed, not copied)

| Check | Result |
|---|---|
| Pre-audit set (revision 2 proposal, CV5 protocol / results / noise report + script, change proposals, class-distribution CSV, fold file) | 8 / 8 OK |
| Amendment 01b change set | 12 / 12 OK, frozen generator `4a5efda8…` |
| Approved protocol / ledger / BASE notebook / `cv5_lib.py` / `dentamind_kaggle.py` / `dsutil.py` | `0771b5f8…` / `f117c1a3…` (5 entries, chain intact) / `dd65c7c7…` / `72084f9b…` / `879faa93…` / `debeb7f0…` |
| CV5 archive / historical bundle | `4ac56843…`, 88 / 88 SHA256SUMS entries / `9d070fc7…` |
| Working tree | 21 modified tracked files, the same set as at session start (backend / frontend / ledger / reporting, untouched here); new files untracked; no commit |
| Patch at start | `1dfc288c…`, one target file, 4 hunks (+88 / −7), applied cleanly with `git apply --check` |

The same checks were repeated after the work. All results were identical.

## 2. Gap 1 resolved: a separate BASE-P2 path (`kaggle/make_base_p2_notebook.py`)

* **No bypass of the candidate refusal.** The candidate generator is never asked for a BASE configuration (a test spies on it). BASE-P2
  takes the candidate path's training / evidence / aggregation / package cell *text*, generated for the proposed candidate PAD25.
  Every candidate-specific expression is replaced by an exact, asserted substitution:
  - model: `DK.new_model` (ResNet-50);
  - crop tag: `s224_p0.10`;
  - config: `BASE_P2_CFG`;
  - labels: "reference": "BASE-P2".

  The generator fails on any template drift.
* **BASE unchanged.** The BASE crop and detector cells are reused byte for byte. The trainer is `dentamind_kaggle:train_run`, and the
  notebook asserts this. `cv5_interventions.py` is not embedded. The BASE notebook and BASE code are not modified.
* **Frozen registration.** The notebook is generated only from a `dentamind-cv5-base-p2-registration-v1` JSON. It is refused unless:
  - it has no placeholders;
  - `config == asdict(EXPERIMENTS["BASE"])`, seeds are 42–46 and folds 0–4;
  - the fold-file SHA-256 is the approved one;
  - `split_semantics` is the fixed wording;
  - the import parameters (manifest, V6 record, reviewer authorization, Kaggle input folder) are well-formed, and **Amendment 02 names
    all three hashes**;
  - `code_sha256` equals the current hashes of every embedded / bundle / generator file (10 files, including the generator itself);
  - `required_outputs` is the fixed list;
  - both amendment files match their registered SHA-256 and their "Registered by" row is filled (see decision D-B2).

  The notebook re-checks the embedded and bundle code hashes and the BASE config against the registration before anything runs.
* **Training-only imports.** The import cell is the shared template `cv5_imports.notebook_import_cell` (the same text as the candidate
  patch). It asserts that every inner-validation and held-out list is unchanged after augmentation.
* **Generator behaviour:**
  - `write_base_p2_notebook` writes the notebook once.
  - `python kaggle/make_base_p2_notebook.py` only prints the registration template.
  - No registration exists, and none was created.

## 3. Gap 2 resolved: reviewer authorization

**Format `dentamind-reviewer-authorization-v1`**, built locally by `scripts/dataset/build_reviewer_authorization.py` from
`data/annotation/reviewers.csv`, written once, versioned:

```json
{"format": "dentamind-reviewer-authorization-v1", "version": 1, "issued_at": "<UTC>", "issued_by": "<owner's choice>",
 "registry_sha256": "<sha256 of the local reviewers.csv>", "previous_version_sha256": null,
 "reviewers": [{"reviewer_id": "<internal id>", "qualification_attested": true, "attested_on": "YYYY-MM-DD",
                "valid_from": "YYYY-MM-DD", "valid_to": null, "status": "active", "revoked_on": null}],
 "content_sha256": "<sha256 of the canonical content>"}
```

* **No personal data.** Only internal reviewer IDs and dates are included; any other per-reviewer field is refused. Names, registration
  numbers and logins stay in the local registry, bound by `registry_sha256`.
* **Versioning.** Version N > 1 must reference version N−1 by SHA-256, and earlier revocations must be repeated.
* **Manifest v2 binding:**
  - Import manifest format `dentamind-cv5-import-manifest-v2` records `reviewer_authorization: {sha256, version}`.
  - Every finding carries `binding_sha256` = SHA-256 over sample, image hash, radiograph group, box, label, source, label source, review
    record hash, reviewer, decision, review date and the authorization SHA-256.
* **Builder checks.** The builder refuses an authorization that was not derived from the same `reviewers.csv`.
* **Notebook checks.** The notebook loads the authorization by its **registered** SHA-256. It refuses a missing, modified, stale or
  foreign version, and a manifest built with another version. For every finding it refuses:
  - an unlisted or revoked reviewer;
  - a review outside the validity window;
  - a broken binding.
* **Not fabricated.** No reviewer, registry, authorization or annotation was created. Tests use synthetic fixtures in temporary folders.
  `data/annotation/` is unchanged.

## 4. Exact dependency list

| File | Role | SHA-256 now | Frozen? |
|---|---|---|---|
| `kaggle/make_cv5_notebook.py` | candidate generator | `4a5efda8951126644d0e91b4778e3d7c6d93e174cebc6a371f3a7001e2920641` | yes (01b), unchanged |
| `patches/cv5_import_wiring.patch` | proposed change to the above, **unapplied** | `ed26e064e86d9136f6026515937b9ba26c123bfeeb94d9b843957e749e639d5d` | proposal |
| `kaggle/cv5_imports.py` | manifest v2, authorization, V6 record, shared import cell | `f9c061cb1aab3ecb83a46815b796c68b527c03743b4acc359c7549a10393bf64` | not yet |
| `kaggle/make_base_p2_notebook.py` | BASE-P2 generator | `778fb45fe5ec0493cf526b07c1177cf1db83ad211bd6824ccb20d50cf36f8364` | not yet |
| `scripts/dataset/build_cv5_import_manifest.py` | local manifest builder (needs the authorization) | `b5f61e978fbad115c2cd2b86f55794e0d6b3c594eb9a8ca212a1577ce33f5daa` | not yet |
| `scripts/dataset/build_reviewer_authorization.py` | local authorization issuer | `f9a2943593955f37238e41d7160771a6202a69dc7c08f89777664f942e192fd9` | not yet |
| `scripts/dataset/run_cv5_import_v6.py` | local full gate V6 record | `817fe904225e1227275767f595995b89a340badc2e3296083297984b2d8712f7` | not yet |
| `kaggle/cv5_lib.py`, `kaggle/cv5_accept.py`, `kaggle/dentamind_kaggle.py`, `scripts/dataset/dsutil.py`, `scripts/dataset/make_cv_folds.py`, `kaggle/make_notebook.py`, `data/splits/cv5_folds_v1.csv` | unchanged inputs | as in Amendment 01b and bundle v3 | yes / bundle |
| `scripts/dataset/clinical_review.py`, `verified_to_manifest.py` | P1 route (read-only use) | unchanged | — |

## 5. Tests (all synthetic; exact results)

| File | Tests | Covers |
|---|---:|---|
| `tests/test_cv5_base_p2.py` | 20 | template refused; valid registration; 12 refusals (config, intervention key, seeds, fold hash, changed / missing code hash, import parameters, outputs, split semantics, amendment hash, registered_by, missing field); unsigned or mismatched amendments; candidate generator never asked for BASE; BASE-only cells; writer refuses and writes once; frozen files unchanged; executed import cell (imports only in fitting parts, held-out unchanged, 224 px BASE crops); CV-pool twin and in-population group refused |
| `tests/test_reviewer_authorization.py` | 11 | no personal data; attested reviewers only; immutability; version chain and persistent revocation; 5 validation refusals plus an edit without re-hash; manifest binding and label tampering; unlisted / revoked / out-of-window / stale / missing / foreign authorizations |
| `tests/test_cv5_import_wiring.py` | 14 | patch targets only the frozen file and stays unapplied; default output byte-identical; import-mode structure and order; parameter validation; writer needs Amendment 02 naming all three hashes; executed cell (fitting only; wrong / stale hashes; altered image; CV-pool twin); V6 record rules; local V6 with a test-split twin |
| `tests/test_cv5_imports.py` | 22 | manifest v2 building, immutability, validation, independence, fold plans, P2 counting, protection |
| **Full suite** | **507 passed**, 0 failed | |

## 6. Decisions for human review (the protocol does not specify these; nothing was invented)

* **D-B1: revoked reviewers.** The implementation refuses **all** labels of a reviewer whose authorization is revoked, whatever the
  review date. This is conservative. The alternative is to keep labels reviewed before `revoked_on`.
* **D-B2: signature detection.** "Signed" is detected from a filled "Registered by (owner's own full name)" table row and the file's
  registered SHA-256. There are no cryptographic signatures. Are a dated text signature and a registered hash sufficient, or should a
  digital signature be required?
* **D-B3: BASE-P2 metrics visibility.** The BASE-P2 notebook logs pooled metrics, as CV5-BASE run 1 did. The protocol only requires
  that candidates are registered before BASE-P2 is *run*. Should BASE-P2 metrics be sealed (written to files only) until the first
  candidate's gate R?
* **D-B4: BASE-P2 run failures.** Protocol §9 classifies candidate runs. The BASE-P2 path reuses the same rules (retries,
  NO-VERDICT-style refusal of aggregation when runs are missing). What happens to the programme if BASE-P2 itself ends incomplete or
  diverges? Re-registration? Abandoning imports?
* **D-B5: reviewer qualification criteria.** The authorization only records that qualification was attested. Which qualifications are
  acceptable, and is a second reader required? See the data-acquisition checklist.
* **D-B6: whether to apply the wiring patch,** and when. It changes a frozen file, so it needs a dated change with new hashes, a new
  candidate bundle version and a repeat Kaggle pre-flight.

## 7. Remaining approvals and blockers
* **Owner approvals:**
  - the two ledger disclosures;
  - signing Amendment 01;
  - applying the patch (D-B6);
  - decisions D-B1 to D-B5;
  - registering reviewers and issuing authorization v1;
  - later, signing Amendment 02 and the BASE-P2 registration.
* **Data:** P2 is not met (PL +171 findings / +106 radiographs; DC +283 / +150). There are 0 clinician-verified labels. The imports
  dataset (manifest, V6 record, authorization and images) does not exist.

## 8. Exact proposed diff (UNAPPLIED) for `kaggle/make_cv5_notebook.py`

`patches/cv5_import_wiring.patch` (sha256 `ed26e064…`), applies cleanly to `4a5efda8…`. Verbatim:

```diff
diff --git a/kaggle/make_cv5_notebook.py b/kaggle/make_cv5_notebook.py
index 05fa1b5..91da7e4 100644
--- a/kaggle/make_cv5_notebook.py
+++ b/kaggle/make_cv5_notebook.py
@@ -343,6 +343,8 @@ log(f"ARCHIVE {zp}  {zp.stat().st_size / 2**20:.1f} MB  sha256 {CV.sha256_file(z
 # packaged as run evidence before any aggregation; aggregation runs only when all 25 runs are valid and complete.
 CANDIDATE_EMBED = {**EMBED, "kaggle/cv5_accept.py": HERE / "cv5_accept.py", "kaggle/cv5_interventions.py": HERE / "cv5_interventions.py"}
 ACCEPT_PROTOCOL = "reports/cv5_acceptance_protocol.md"
+# Training imports (protocol section 3.1, Amendment 02): OFF unless candidate_cells(..., imports=...) is given a registered manifest.
+IMPORTS_EMBED = {"kaggle/cv5_imports.py": HERE / "cv5_imports.py"}
 
 
 def _sub(src: str, old: str, new: str) -> str:
@@ -365,10 +367,21 @@ def _check_candidate(candidate_id: str, cfg: dict) -> None:
     CI.check_single_intervention(DK.ExpConfig(**cfg))          # V3: exactly one intervention key, nothing else
 
 
-def candidate_cells(candidate_id: str, cfg: dict) -> list:
-    """Cells of the CV5 notebook for one registered candidate (cfg: complete DK.ExpConfig field dict)."""
+def _check_imports(imports: dict) -> None:
+    import cv5_imports as CIM
+    CIM.check_import_params(imports)          # registered manifest / V6-record / reviewer-authorization SHA-256 + Kaggle input folder
+
+
+def candidate_cells(candidate_id: str, cfg: dict, imports: dict | None = None) -> list:
+    """Cells of the CV5 notebook for one registered candidate (cfg: complete DK.ExpConfig field dict). imports None (default): no
+    import code at all - the cells are exactly those of the import-free notebook. imports {manifest_sha256, v6_record_sha256,
+    reviewer_authorization_sha256, input_dir}: the registered manifest is loaded, checked and added to every fold's fitting part
+    (section 3.1, Amendment 02)."""
     _check_candidate(candidate_id, cfg)
-    files = {k: p.read_bytes().decode("utf-8") for k, p in CANDIDATE_EMBED.items()}
+    if imports is not None:
+        _check_imports(imports)
+    embed_files = CANDIDATE_EMBED if imports is None else {**CANDIDATE_EMBED, **IMPORTS_EMBED}
+    files = {k: p.read_bytes().decode("utf-8") for k, p in embed_files.items()}
     shas = {k: hashlib.sha256(v.encode("utf-8")).hexdigest() for k, v in files.items()}
     head = ("markdown", f"""# DentaMind AI - CV5 candidate `{candidate_id}` vs the BASE reference (Kaggle GPU)
 
@@ -525,7 +538,34 @@ log(f"RUN EVIDENCE {EVZ}  sha256 {CV.sha256_file(EVZ)}")""")
                           'CANDIDATE["extra"])\nlog("crop rule:", CI.resolve(CANDIDATE["extra"]), "crops", X_ALL.shape)'))
     det = ("code", _sub(CELLS[8][1], 'XD, MI, MISSED = DK.build_detector_crops(POOL, DATA_ROOT, DET_CACHE, lambda r: r["project_image_id"])',
                         'XD, MI, MISSED = CI.build_detector_crops(POOL, DATA_ROOT, DET_CACHE, lambda r: r["project_image_id"], CANDIDATE["extra"])'))
-    return [head, CELLS[1], CELLS[2], CELLS[3], embed, CELLS[5], CELLS[6], crops, det, train, evidence, ("code", agg), ("code", pkg)]
+    cells = [head, CELLS[1], CELLS[2], CELLS[3], embed, CELLS[5], CELLS[6], crops, det, train, evidence, ("code", agg), ("code", pkg)]
+    return cells if imports is None else _with_imports(cells, imports)
+
+
+def _with_imports(cells: list, imports: dict) -> list:
+    """Import mode: one cell after the detector cell (load, verify, independence, fitting-part augmentation, import crops) and three
+    substitutions (per-run manifest separates imported rows; evidence and package keep the import check and manifest)."""
+    import cv5_imports as CIM
+    crops = 'CI.build_crops(IMP_ROWS, IMPORT_DIR, CACHE / f"imports_gt_{CI.crop_tag(CANDIDATE[\'extra\'])}.npz", CANDIDATE["extra"])'
+    imp = ("code", CIM.notebook_import_cell(imports, crops))
+    k_det = next(i for i, (_, src) in enumerate(cells) if "CI.build_detector_crops(" in src)
+    out = cells[:k_det + 1] + [imp] + cells[k_det + 1:]
+    for i, (kind, src) in enumerate(out):
+        if "CA.run_isolated(" in src:
+            src = _sub(src, 'rows_json = CA.write_rows(CACHE / f"f{k}_rows.json", plan["fit"], plan["inner"])',
+                       'rows_json = CA.write_rows(CACHE / f"f{k}_rows.json", [r for r in plan["fit"] if "import_source_id" not in r], '
+                       'plan["inner"],\n                               [r for r in plan["fit"] if "import_source_id" in r])')
+        elif "run evidence (always packaged" in src:
+            src = _sub(src, 'for f in ("run_status.json", "training_log.txt"):', 'for f in ("run_status.json", "training_log.txt", "import_check.json"):')
+        elif "package artifacts" in src:
+            src = _sub(src, '(pkg / "checkpoint_manifest.json").write_text(json.dumps(ck, indent=1))',
+                       '(pkg / "checkpoint_manifest.json").write_text(json.dumps(ck, indent=1))\n(pkg / "imports").mkdir()\n'
+                       'for f in ("import_manifest.json", "import_v6_record.json", "reviewer_authorization.json"):\n'
+                       '    shutil.copy2(IMPORT_DIR / f, pkg / "imports" / f)\n'
+                       'shutil.copy2(ART / "import_check.json", pkg / "imports" / "import_check.json")')
+            src = _sub(src, '"kaggle/cv5_interventions.py", ', '"kaggle/cv5_interventions.py", "kaggle/cv5_imports.py", ')
+        out[i] = (kind, src)
+    return out
 
 
 def _notebook(cells: list) -> dict:
@@ -541,13 +581,23 @@ def _notebook(cells: list) -> dict:
     return nb
 
 
-def write_candidate_notebook(candidate_id: str, cfg: dict, registration, out) -> Path:
-    """Writes a candidate notebook only for a candidate named in an existing dated registration amendment (protocol section 4.5)."""
+def write_candidate_notebook(candidate_id: str, cfg: dict, registration, out, imports: dict | None = None,
+                             imports_registration=None) -> Path:
+    """Writes a candidate notebook only for a candidate named in an existing dated registration amendment (protocol section 4.5).
+    With imports, the BASE-P2 amendment (imports_registration) must exist and name all three registered SHA-256 values."""
     reg = Path(registration)
     if not reg.is_file() or candidate_id not in reg.read_text(encoding="utf-8"):
         raise ValueError(f"no registration amendment naming candidate {candidate_id!r}: {reg}")
+    if imports is not None:
+        r2 = Path(imports_registration) if imports_registration else None
+        txt = r2.read_text(encoding="utf-8") if r2 and r2.is_file() else ""
+        keys = ("manifest_sha256", "v6_record_sha256", "reviewer_authorization_sha256")
+        if not all(imports.get(k) and imports[k] in txt for k in keys):
+            raise ValueError("imports need an Amendment 02 file that names the registered manifest, V6-record and "
+                             "reviewer-authorization SHA-256 values")
     out = Path(out)
-    out.write_text(json.dumps(_notebook(candidate_cells(candidate_id, cfg)), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
+    out.write_text(json.dumps(_notebook(candidate_cells(candidate_id, cfg, imports)), indent=1, ensure_ascii=False) + "\n",
+                   encoding="utf-8")
     return out
 
 
```

---

## Addendum 2026-10-25: superseded diff
* **Superseded:** the diff in §8 (`ed26e064…`) is superseded by the byte-exact regeneration `patches/cv5_import_wiring.patch`
  `33ec47e6…`. The resulting generator content is identical (`d15b1a55…`).
* **Now part of a set:** the patch is one of three in `patches/cv5_patch_set_v1.json`; see `reports/cv5_patch_application_plan_v2.md`.
