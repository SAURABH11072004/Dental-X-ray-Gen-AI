# Data-request checklist (prepared; nothing has been sent)

Date 2026-10-25. Use one copy per data holder. The project owner sends every request personally. The assistant drafts only.
Existing drafts: `reports/data_requests/dentex_organizers_email.md`, `reports/data_requests/tufts_access_request.md`.

## Before sending
- [ ] **Need:** the request states the exact need. Today's gap is Periapical Lesion +171 findings / +106 radiographs and Deep Caries
      +283 findings / +150 radiographs (`reports/expanded_class_distribution.csv`). Prefer panoramic radiographs with these findings,
      or unlabelled panoramics for clinician review.
- [ ] **Use stated:** non-commercial academic research (PCCOE, Department of Computer Engineering), training only, results
      reported per source, no redistribution unless the licence allows it.
- [ ] **Data rules stated:**
  - [ ] no patient identifiers requested;
  - [ ] de-identified images only;
  - [ ] the holder's ethics / de-identification statement is requested.
- [ ] **Requested from the holder:**
  - [ ] licence and data-use terms;
  - [ ] version;
  - [ ] official citation;
  - [ ] archive checksums;
  - [ ] label taxonomy and annotation protocol;
  - [ ] whether patient IDs exist (needed for patient-level grouping).
- [ ] **Overlap with DENTEX asked about:** shared radiographs would be refused by gate V6 in any case.
- [ ] **Sender:** the owner's institutional address and the guide's name (Dr. Pradnya Narkhede), as the holder requires.
- [ ] **Commitments reviewed:** nothing in the request commits to publication of the holder's data, or to a result.

## On receipt
- [ ] Record licence, provenance, version, retrieval date and archive SHA-256 in a copy of
      `reports/templates/source_provenance_template.json`.
- [ ] Add the radiographs to the annotation pool through `scripts/dataset/build_annotation_pool.py`. This step applies SHA-256 and
      near-duplicate grouping and assigns the split lock.
- [ ] If the source carries labels, record its taxonomy and get an owner decision on any mapping. Unmapped labels are not used.
      Source labels never count toward P2 without clinician verification through the P1 route.
- [ ] Track the requests and responses below.

| Holder | Draft | Sent on (owner) | Response | Licence recorded | Added to pool |
|---|---|---|---|---|---|
| DENTEX organisers | `reports/data_requests/dentex_organizers_email.md` | | | | |
| Tufts Dental Database | `reports/data_requests/tufts_access_request.md` | | | | |
