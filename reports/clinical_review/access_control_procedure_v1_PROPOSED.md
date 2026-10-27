# Clinical-review file access: findings and PROPOSED procedure (v1)

Date 2026-10-25.
* **Read-only inspection.** No file was moved, deleted, renamed, re-permissioned or uploaded.
* Every step in §3 needs the project owner's authorization and is carried out by the coordinator.

## 1. Findings (verified)

| Finding | Evidence |
|---|---|
| All clinical-review files are in `reports/clinical_review/` inside the project folder | directory listing |
| They inherit the drive's default permissions: **BUILTIN\Users: read**, **Authenticated Users: modify** | `icacls` on the folder and on the v2 key |
| The folder is **untracked and not git-ignored**; the repository has a GitHub remote `origin` (`SAURABH11072004/Dental-X-ray-Gen-AI`) | `git status`, `git check-ignore`, `git remote -v`. Whether that GitHub repository is public was **not** checked |
| The keys can be **regenerated** from repository content: the build scripts are deterministic (fixed seeds) and read files in the repository | `scripts/build_clinician_review_queue.py` (seed 20261025), `scripts/build_clinician_review_queue_v2.py` (seed 20261026) |
| The v2 reviewer worksheet contains only `review_id`, `image_code`, `fdi_tooth` and empty answer fields. No file name, image hash, box coordinates, label, target / control flag or mapping; 0 matches for file-name, hash, bracket, label or set patterns | column listing and pattern check in this session; `tests/test_improvement_round2.py` |

## 2. Files that must be restricted (reviewers must never see them)

| File | Why |
|---|---|
| `reports/clinical_review/caries_rereading_key_v1_COORDINATOR_ONLY.csv` | review ID → finding, label, target / control, model consistency |
| `reports/clinical_review/caries_rereading_key_v2_COORDINATOR_ONLY.csv` | same, plus image code → file and box |
| `reports/clinical_review/caries_rereading_worksheet_v1_BLINDED.csv` | file name, image hash and box, which can be matched to the **public** DENTEX labels (superseded by v2) |
| `reports/cv5_caries_clinician_review_list.csv` | lists the 110 **targets** with image paths and labels |
| `kaggle/artifacts_cv5_run1/caries_confusion_findings.csv` | per-finding confusion counts (identifies targets and controls) |
| The repository as a whole, including the build scripts and manifests | allows the keys to be regenerated |

The manifests (`caries_rereading_manifest_v1.json`, `caries_rereading_manifest_v2.json`) hold hashes and paths only, not the mapping.
They still belong to the coordinator side.

## 3. Proposed procedure (requires authorization; not executed)
1. **Decide custody.** The project owner names the coordinator, a person who is not a reader.
2. **Separate.** The coordinator copies the five files of §2 to restricted storage, e.g. a folder outside the repository with an ACL
   limited to the coordinator's account, or encrypted storage.
   - Verify each copy's SHA-256 against the manifests or this session's hashes **before** removing anything from the repository
     folder.
   - Removing the originals is a separate, explicit owner decision. The record value of v1 may favour keeping a restricted copy only.
3. **Prevent publication.** The owner decides whether to add `reports/clinical_review/*COORDINATOR_ONLY*` and the v1 worksheet to
   `.gitignore` before any commit or push. Nothing has been committed so far.
4. **Reviewer package.** It contains only:
   - `caries_rereading_worksheet_v2_BLINDED.csv` (SHA-256 `effa7db6…`);
   - a viewer that shows each coded image with its box drawn, configured by the coordinator from key v2;
   - the CL's written definitions.

   Reviewers get **no repository access** and no access to DENTEX annotation files.
5. **Verify before the first reading session.** A second person checks that:
   - the reviewer account cannot open the §2 files (attempt to read, expect "access denied");
   - the worksheet hash equals `effa7db6…`;
   - the viewer shows no label, model output or file name;
   - record the check (date, who) in the review log.
6. **After reading.** Completed worksheets return to the coordinator. The results file is a new version; the original labels are never
   edited.

## 4. Residual risks
* **A reviewer who knows DENTEX** could recognise a radiograph visually. Mitigation: readers attest that they have not used DENTEX
  annotations; the CL decides.
* **Disk-level access** by administrators cannot be excluded on a shared machine. Use a machine or account the readers do not
  administer.
