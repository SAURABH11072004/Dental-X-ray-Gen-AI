# External validation: dataset eligibility, label mapping and protocol draft (v1)

Date 2026-10-25.
* **Sources:** the project's own audits (`reports/dataset_source_inventory.csv`, `reports/additional_dataset_candidates.md`,
  `reports/cluj_dataset_audit.json`, `reports/external_data_results.md`) and the dataset pages they cite.
* **Verification:** the licences were read in those earlier audits and were **not re-verified online in this session**, apart from the
  DENTEX GitHub repositories (see §4).
* **Nothing was downloaded, uploaded or evaluated in this session.**

## 1. Eligibility matrix

| Source | Access / licence (as recorded) | Independent of DENTEX training data? | Classes mappable to the four | Eligible for external validation? |
|---|---|---|---|---|
| DENTEX official test release (250 images) | public; CC BY-NC-SA 4.0 | same challenge and source institutions, so **not independent** (an internal hold-out at best) | treatment-oriented taxonomy (e.g. *curuk*, *lezyon*, *gomulu*); depth is not distinguished; a contradiction was recorded on the one shared radiograph | **No** as an external set. A possible secondary check only after a clinician confirms the mapping |
| Cluj (Zenodo 10.5281/zenodo.15487430), multi-center evaluation folder (180 images) | public; CC BY 4.0 | yes: different centres; 0 exact or near duplicates against DENTEX or Hanoi (`cluj_dataset_audit.json`) | Impacted (IMT) and Periapical Lesion (API); caries without depth only as "Caries-any" | **Conditional.** The set **failed the project's visual label check** (a block of images uses a different class numbering; about 30 % of Impacted labels wrong in that block). Usable only after clinician verification of the evaluation images |
| Hanoi (Mendeley kx52tk2ddj) | public; CC BY 4.0 (dataset record) | yes | Periapical Lesion only (PAI 3–5); positives only | **No** for a four-class evaluation: no negatives, so no precision or specificity |
| Tufts Dental Database | request form; licence not readable without access | yes | five-level abnormality descriptions, not the four classes | **Unknown.** Needs an access request (`reports/data_requests/tufts_access_request.md`) and a mapping review |
| Dental OPG (Mendeley c4hhrkxytw), Four dental diseases (wxv6h9p39g), Children's panoramic (Sci Data 2023) | public; CC BY 4.0 / not stated | yes | no depth split; "infection" undefined; paediatric domain | **No** (incompatible taxonomy or domain) |
| Institutional data (e.g. a partner dental college or hospital) | needs a data-use agreement and ethics approval | yes | can be labelled with the DENTEX definitions by qualified readers | **Best option**, but requires a clinical lead, ethics approval and annotation effort |

## 2. Label-mapping table (DENTEX definitions → external)

| DENTEX class | Cluj | Hanoi | DENTEX official test | Reliable? |
|---|---|---|---|---|
| Caries | CAR (no depth) → Caries-any | – | *curuk* (no depth) | **No** for Caries vs Deep Caries; only "caries-any" recall is defined |
| Deep Caries | not separable | – | not separable | **No** |
| Periapical Lesion | API (apical periodontitis) | PAI 3–5 | *lezyon* (definition unclear) | definition mapping only; needs clinician confirmation |
| Impacted | IMT | – | *gomulu* | plausible, but Cluj failed the label check |

## 3. External evaluation protocol (draft; freeze before any run)
1. **Data:** one source, chosen and licensed by the authors. The evaluation images and labels are fixed by SHA-256 before any
   inference.
2. **Overlap check:** exact and perceptual-hash duplicates against all DENTEX images, using the existing `cluj_dataset_audit`
   procedure. Overlapping images are excluded and reported.
3. **Model:** the BASE recipe, without retraining, threshold tuning or recalibration on the external data. The checkpoint and
   detector are identified by hash.
4. **Metrics:**
   - per-class recall, precision where negatives exist, and macro-F1 over the mappable classes only;
   - a radiograph bootstrap 95 % CI;
   - end-to-end and matched-box settings reported separately.
5. **Reporting:**
   - unmappable classes are listed as "not evaluated", never imputed;
   - distribution differences (scanner, image size, class mix) are described;
   - labelled "external validation" only if the source is independent and its labels are verified.
6. **No external data enters training by default.**

## 4. Existing exploratory evidence (do not present as external validation)
* **What exists:** `reports/external_data_results.md` contains a secondary, recall-only evaluation of single-split BASE checkpoints on
  Cluj crops. In it, Periapical Lesion recall was low (about 0.21) and Impacted recall high.
* **Why it doesn't qualify:**
  - the Cluj labels failed the visual check and are definition-mapped;
  - precision cannot be computed;
  - the models are not the CV5 models.
* **Use:** at most a caveated sentence in the limitations, at the authors' discretion. **It is not included in manuscript v3.**

## 5. Licence note found in this session
* The DENTEX GitHub repository states that the data are under CC BY-NC-SA 4.0.
* The HierarchicalDet repository states CC BY-SA 4.0 for the data.
* The authors must check which licence applies to the copy they used, from the official dataset record, before publication.

## 6. Blockers
1. The authors choose a source.
2. Access and licence are confirmed.
3. A clinician verifies the labels for any definition-mapped source.
4. The owner approves the frozen external protocol.
5. Hardware: inference only, which is possible on the local RTX 3050.
