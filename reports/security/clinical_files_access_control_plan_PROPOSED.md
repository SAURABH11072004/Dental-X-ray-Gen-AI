# Clinical-review files: access-control and Git-exposure plan (PROPOSED; NOTHING EXECUTED)

Date 2026-10-25.
* **All findings below were obtained read-only.**
* No permission, file, `.gitignore`, remote or repository setting has been changed.
* No file content is reproduced here: names, sizes and hashes only.
* **Every action in §4 needs the project owner's explicit approval of the exact action list before execution.**

## 1. Restricted artifacts (identity only)

| # | Path | Bytes | SHA-256 (prefix) | Why restricted |
|---|---|---|---|---|
| F1 | `reports/clinical_review/caries_rereading_key_v1_COORDINATOR_ONLY.csv` | 38,413 | `81cabdc8` | unblinding key (v1) |
| F2 | `reports/clinical_review/caries_rereading_key_v2_COORDINATOR_ONLY.csv` | 75,526 | `c459f5da` | unblinding key (v2) |
| F3 | `reports/clinical_review/caries_rereading_worksheet_v1_BLINDED.csv` | 39,272 | `9d737e27` | identifiers traceable to public DENTEX labels |
| F4 | `reports/cv5_caries_clinician_review_list.csv` | 16,621 | `011dfb19` | names the 110 targets |
| F5 | `kaggle/artifacts_cv5_run1/caries_confusion_findings.csv` | 320,962 | `9998c945` | per-finding confusion counts (targets and controls) |
| F6 | `kaggle/dentamind_5fold_cv_artifacts.zip` | – | `4ac56843` | **contains a compressed copy of F5** (protected CV5 archive; must stay in place) |

* **Other copies:** a byte-identical search of the project folder (excluding `.venv`, `node_modules`, `.git`) found **no other copies**
  of F1–F5.
* **Regeneration risk:** F1–F3 can be regenerated from the repository (`scripts/build_clinician_review_queue*.py`, deterministic
  seeds). Reviewers therefore need **no access to the repository at all**, not just to F1–F6.

## 2. Current state (verified)

| Property | Finding |
|---|---|
| Owner (all six) | `SAURABH\chand` |
| ACLs (all six, and the worksheet v2) | inherited only (`AreAccessRulesProtected = False`): `BUILTIN\Administrators` Full; `NT AUTHORITY\SYSTEM` Full; **`NT AUTHORITY\Authenticated Users` Modify**; **`BUILTIN\Users` Read & execute** |
| Local accounts | enabled: `chand` (member of Administrators; Microsoft account), `saura` (**not** in Administrators). Disabled: Administrator, Guest, DefaultAccount, WDAGUtilityAccount, WsiAccount |
| Effect today | **any enabled local account, including `saura`, can read every restricted file**; any authenticated user can modify them |
| File system | NTFS (ACLs are enforceable) |
| Access test as `chand` (`scripts/security/check_clinical_access.ps1`) | all seven checked paths READABLE → **FAIL** (expected baseline) |

## 3. Git exposure audit (verified, read-only)

| Check | Result |
|---|---|
| Tracked (`git ls-files`) | none of F1–F6, nor `reports/clinical_review/`, nor `kaggle/artifacts_cv5_run1/` |
| Staged (`git diff --cached`) | nothing staged |
| History (`git log --all` on these paths) | no commit touches them; the only commit `6340f09` contains no file whose name matches the restricted artifacts |
| Refs | `refs/heads/main` = `refs/remotes/origin/main` = `6340f09`; no stash |
| Ignored (`git check-ignore`) | **F1–F6 are NOT ignored**; all appear as untracked (`??`) |
| `.gitignore` | no rule for `reports/`, `kaggle/artifacts_*`, `*.csv` or `*.zip` that covers them |
| Remotes | one: `origin` → `https://github.com/SAURABH11072004/Dental-X-ray-Gen-AI.git` (fetch and push); `main` tracks `origin/main` |
| Remote visibility | **PUBLIC**: unauthenticated GitHub API `GET /repos/SAURABH11072004/Dental-X-ray-Gen-AI` → HTTP 200, `"private": false`, `"visibility": "public"`, last push 2026-10-15T15:52:51Z |
| Remote content | `git ls-remote origin`: `HEAD` = `refs/heads/main` = `6340f09`, identical to local. `GET …/contents/reports/clinical_review` → 404 |
| **Conclusion** | **No restricted artifact is in Git or on GitHub today.** A future `git add .` / `git add reports kaggle` followed by a push would publish F1–F6 to a **public** repository. History rewriting and credential rotation are **not needed** (nothing was exposed) |
| Not verified | other copies outside the project folder (e.g. Kaggle notebook outputs, downloads, backups, cloud sync); the visibility of the Kaggle notebook that produced F5 / F6 |

## 4. Proposed actions (for approval; exact paths and commands; NOT executed)

Roles to be named by the owner:
* **Coordinator account (`<COORDINATOR_ACCOUNT>`):** not a reader.
* **Reviewer accounts (`<REVIEWER_ACCOUNT>`):** non-administrators.
* **Test account (`<TEST_ACCOUNT>`):** non-privileged, e.g. a new local standard user. `saura` must not be assumed to be any of these
  without the owner's say.

### Step 1: prevent publication (highest priority; no effect on running code)
Append to `.gitignore`:
```
# clinical-review blinding: never commit (see reports/security/clinical_files_access_control_plan_PROPOSED.md)
reports/clinical_review/*COORDINATOR_ONLY*
reports/clinical_review/caries_rereading_worksheet_v1_BLINDED.csv
reports/cv5_caries_clinician_review_list.csv
kaggle/artifacts_cv5_run1/caries_confusion_findings.csv
kaggle/dentamind_5fold_cv_artifacts.zip
```
**Verify:**
* `git check-ignore -v <each path>` reports a rule for F1–F6;
* `git status --short` no longer lists them.

**Note:** `.gitignore` does not protect against `git add -f`. Before any future push, run the §3 audit again.

### Step 2: restrict F1–F5 in place (keeps every path, manifest, test and SHA256SUMS valid)
For each of F1–F5, run in an elevated PowerShell:
```
icacls "<path>" /inheritance:r /grant:r "<COORDINATOR_ACCOUNT>:(R,W)" "NT AUTHORITY\SYSTEM:(F)" "BUILTIN\Administrators:(F)"
```
* This removes `Authenticated Users` and `Users`.
* Administrators keep access: they can always take ownership, so denying them gives no real protection.
* Hashes must be unchanged afterwards (ACLs do not alter content). Verify with `sha256sum` against §1.

### Step 3: keep reviewers out of the repository
Strongest option: readers use **another machine or account that never has a copy of the repository**. On this machine:
```
icacls "D:\Dentex-Gen Ai" /deny "<REVIEWER_ACCOUNT>:(OI)(CI)(RX)"
```
This is applied per reviewer account. A deny entry overrides the inherited `Users` read access.

F6 stays in place, unreadable by reviewers through this deny. Moving it would break the archive integrity checks.

### Step 4: reviewer share (least privilege)
Create `D:\DentaMind_review_share\` **outside** the repository. Copy only `caries_rereading_worksheet_v2_BLINDED.csv` (SHA-256
`effa7db6…`) and verify its hash. Then:
```
icacls "D:\DentaMind_review_share" /inheritance:r /grant:r "<REVIEWER_ACCOUNT>:(OI)(CI)(RX)" "<COORDINATOR_ACCOUNT>:(OI)(CI)(M)" "NT AUTHORITY\SYSTEM:(OI)(CI)(F)" "BUILTIN\Administrators:(OI)(CI)(F)"
```
Readers record their answers in a personal copy, returned to the coordinator. The coded images for the viewer are prepared by the
coordinator in a reviewer-readable folder with **coded file names only**.

### Step 5: access test (required before claiming that access is fixed)
1. Log in as `<TEST_ACCOUNT>` (or a reviewer account), which is non-administrative. The human enters credentials; they are never given
   to the assistant.
2. The coordinator first copies `scripts/security/check_clinical_access.ps1` into a location the test account can read. After
   Step 3 the test account cannot read the repository, and so cannot run the script from there. Verify the copy's SHA-256 against
   the original, then run the copy:
   `powershell -ExecutionPolicy Bypass -File "<copy>\check_clinical_access.ps1" -RepoRoot "D:\Dentex-Gen Ai" -ShareRoot "D:\DentaMind_review_share"`
   - **PASS** requires every repository path to be DENIED (or MISSING if Step 3 blocks the folder), and the v2 worksheet to be
     READABLE.
   - If the test account is outside the repository entirely, a "MISSING / DENIED" mix is expected.
3. As `<COORDINATOR_ACCOUNT>`, F1–F2 are READABLE.
4. A second person records the output (date, accounts, result) in the review log.
5. **Until this test passes, access is NOT fixed.**

### Step 6: rollback (if anything breaks)
* `icacls "<path>" /reset` restores inherited ACLs.
* `icacls "D:\Dentex-Gen Ai" /remove:d "<REVIEWER_ACCOUNT>"` removes the deny entry.
* Delete the share folder.
* Revert the `.gitignore` lines.
* No file content is touched at any step.

## 5. Explicitly NOT proposed
Rewriting Git history, force-pushing, changing remotes or repository visibility, rotating credentials, deleting or moving F1–F6.
None of these is needed on the current evidence. The owner may separately consider making the GitHub repository private, but that is a
repository-settings decision outside this plan.
