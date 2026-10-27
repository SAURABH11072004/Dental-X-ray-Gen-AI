# Submission package for manuscript v2 (DRAFT, 2026-10-25)

Manuscript: `reports/manuscript/DentaMind_CV5_manuscript_v2_journal.docx` (with a PDF copy). Its audited source is
`DentaMind_CV5_manuscript_v2_journal.md`, and the audit result is in `manuscript_v2_number_audit.md` (0 untraced numbers).

Everything in square brackets must be filled in by the authors. Nothing in this package has been sent to any journal.

---

## 1. Cover letter (template)

[Date]

To the Editor-in-Chief, [Journal name]

Dear [Editor's name],

Please consider our manuscript, "Classifying dental findings on panoramic radiographs: a cross-validated baseline, negative results
and a pre-registered acceptance protocol on the DENTEX dataset", for publication as a [research article / original article] in
[Journal name].

Deep-learning studies of panoramic radiographs often report performance on a single split, where estimates for rare but clinically
important findings are unstable, and improvements can arise from repeated evaluation on the same held-out data. Our study takes the
opposite approach on the public DENTEX benchmark:
* we report a radiograph-grouped, five-seed cross-validated baseline with bootstrap uncertainty, in three evaluation settings;
* we show that deep caries and periapical lesions remain the weakest classes, mostly through confusion with caries;
* we report that six imbalance strategies, external training data and ensembling failed their pre-registered acceptance rules;
* we describe an acceptance protocol frozen before any new candidate was trained.

All numbers are traceable to archived, checksum-verified artifacts. We believe the work fits [Journal name]'s interest in
[reproducible methods / dental imaging / negative results], and that it will help readers judge future claims of improvement on this
benchmark.

[Authors to confirm each of the following:]
* the manuscript is original and has not been published, and is not under consideration elsewhere;
* all authors approved the submission;
* the competing-interest, funding and ethics statements in the manuscript are complete.

Suggested reviewers: [optional; per the journal's rules, with no conflicts of interest].

Sincerely,
[Corresponding author name, affiliation, e-mail]
on behalf of Nilesh Sonawane, Saurabh Mali, Sadhyoj Hanwate and Sachet Lothe
(Department of Computer Engineering, PCCOE, Pune; guide: Dr. Pradnya Narkhede)

## 2. Highlights (if the journal asks for them; each under 85 characters)

* Radiograph-grouped 5-fold, 5-seed cross-validated baseline on DENTEX
* Detector-box macro-F1 0.677 (95 % CI 0.652–0.701)
* Deep caries and periapical lesion recall stayed below 0.5
* Re-weighting, sampling, focal loss, extra data and ensembling all failed
* Acceptance protocol for future models frozen before any candidate was trained

(Numbers as in the audited manuscript: abstract and Table 1.)

## 3. Choosing a venue (authors' decision)

The paper has no improvement claim. Its value lies in methodological rigour, reproducibility and negative results. Journals that judge
submissions on soundness rather than novelty, or that state they welcome negative results or reproducibility studies, are therefore
the most realistic targets. Dental-imaging journals are also possible, but reviewers there may expect a clinical advance.

| Type of venue | Examples to evaluate | Fit | Caution |
|---|---|---|---|
| Multidisciplinary journals judged on soundness | PLOS ONE; Scientific Reports | rigorous methods and negative results are within their stated remit | fees and scope must be checked; reviewers may ask for an external test set |
| Open-access oral-health journals | BMC Oral Health | dental AI studies are published there | check the article type and the requirements for ethics statements |
| Dental and maxillofacial radiology | Dentomaxillofacial Radiology; Oral Radiology; Imaging Science in Dentistry | the topic is a direct match | a clinical-impact expectation is likely; a baseline-only paper may be judged too limited |
| Diagnostic imaging (MDPI) | Diagnostics | several cited works appeared there | check scope and fees |

The assistant has not checked current scope pages, fees, indexing or acceptance rates. The authors and guide must verify them on each
journal's official website. Avoid any journal that cannot be verified in recognised indexes, because predatory journals often target
student authors.

## 4. What reviewers are likely to ask, and the honest answer available now

| Likely request | Status | Possible response |
|---|---|---|
| An external or independent test set | not available | stated as a limitation; the test split was used previously and is reported as such |
| Comparison with published DENTEX methods | not done | other papers use different tasks and splits; a direct comparison would need re-implementation under the same folds (a future experiment, not to be estimated) |
| Clinician verification of the confused findings | not done | the 110 findings are listed for review; this needs a qualified clinician |
| Inference latency | not measured | it would need a planned measurement; no estimate is given |
| Other architectures (e.g. ConvNeXt) or larger crops | implemented, not trained | registered as future candidates under the frozen protocol |
| Code availability | undecided | the authors should publish the repository before submission if possible; journals increasingly expect this |
