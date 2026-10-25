# Publication-readiness checklist: manuscript v2 (journal format)

Date 2026-10-25. Supersedes v1 for the journal manuscript; `publication_readiness_checklist_v1.md` is kept unchanged.

**Bottom line.** The technical and writing work is complete for a baseline-plus-negative-results paper. **Acceptance cannot be
guaranteed by anyone.** It depends on the venue, the reviewers and the open items in B–D, which only the authors and the guide can
close. Nothing below has been filled in on their behalf.

## A. Done and verified in this session

| # | Item | Evidence |
|---|---|---|
| A1 | Journal-style manuscript: structured abstract, keywords, IMRaD, 3 tables, 5 figures, 16 numbered references, line and page numbers (18 pages, 3,749 words in Word's count) | `DentaMind_CV5_manuscript_v2_journal.docx` / `.pdf` |
| A2 | Every number traced to an archived source: 170 traced, 0 untraced | `manuscript_v2_number_audit.md` |
| A3 | Word file is identical to the audited source in its numbers: 165 distinct numbers checked, 0 missing, no tags left | builder check in this session |
| A4 | Per-class 95 % CIs: post-hoc and descriptive, computed from archived predictions; the recomputation reproduces the archived macro-F1 intervals exactly | `scripts/per_class_bootstrap_cv5.py`; `reports/cv5_per_class_bootstrap.json` |
| A5 | Figures drawn only from verified artifacts, with a hash manifest | `figures_v2/` and `figures_manifest.json` |
| A6 | Negative results, limitations and the protocol's disclosure about when the margins were set | manuscript §2.7, 2.8, 3.7 and 4.4 |
| A7 | Citation keys and DOIs checked (15 / 16 resolve, with matching titles) | `citation_audit_v1.md` |
| A8 | Cover letter template, highlights, venue guidance and reviewer-question table | `submission_package_v2.md` |
| A9 | No latency, no candidate results and no clinical claims | manuscript §3.8, §4.4 |

## B. Authors and guide must decide or provide (blocking for submission)

1. Approval to submit, from all four authors and the guide.
2. Author order, corresponding author, ORCID iDs and CRediT contributions.
3. Choice of venue (see `submission_package_v2.md` §3), then reformatting to its template, reference style and word limits.
4. Ethics statement for secondary use of public DENTEX data, following PCCOE or the institution's rules.
5. The DENTEX licence terms, quoted in the paper, and a check that the figures show no dataset images that the licence forbids
   reproducing. The v2 figures contain no radiograph images.
6. Funding, competing interests, acknowledgements, and an AI-assistance statement that follows the journal's policy.
7. **Overlap with earlier papers.** `documents/` holds earlier papers on DentaMind (e.g. `123B1B260-Research_Paper_*`,
   `dentist-research-paper.*`). If any of them was submitted or published, declare it and make sure this paper is not a duplicate
   submission. Use the journal's similarity check; no similarity outcome is guaranteed.
8. Code availability: a public repository and release, recommended.
9. Read each cited paper, to confirm that it supports the sentence citing it. Confirm `guo` (no DOI; PMLR volume 70) and `bittar`
   (dated 2026).

## C. Records outside the paper (do not block a baseline paper, but should be honest)

* Two ledger disclosures of earlier test-split use are pending with the accountable test-set authorizer. The paper reports no
  test-set result and states that the split was used previously.
* The protocol's approval is a written statement in the protocol file, not a signed record.

## D. What would make the paper substantially stronger (needs new work; not done, and must not be estimated)

* An external test set from another centre or source, under a data-use agreement.
* Clinician re-reading of the 110 consistently confused findings.
* The registered candidates (larger crops, more padding, ConvNeXt-Tiny), evaluated under the frozen protocol. This needs owner
  approvals, a BASE-P2 run and GPU sessions.
* A planned inference-latency measurement.
