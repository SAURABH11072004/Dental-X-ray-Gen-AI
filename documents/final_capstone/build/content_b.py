"""Chapters 5-8 of the capstone report. Table values are read from the project's evaluation reports at build time."""
import docx_lib as dl

CLS = ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]


def f3(v):
    return f"{v:.3f}"


def write(R, J, FIG, gray_copy):
    ev = {f"{m}_{s}": J(f"Data/reports/eval_dentex_{m}_v1_{s}.json")["metrics"]
          for m in ["teeth_detection", "teeth_segmentation", "fdi_numbering", "findings_classification"] for s in ["val", "test"]}
    e2e = J("Data/reports/end_to_end_validation_evaluation.json")
    unc = J("Data/reports/uncertainty_evaluation.json")
    imb = J("docs/audit_evidence/ml_improvement/imbalance/results.json")["methods"]
    rec = J("Data/reports/training_recipe_comparison_results.json")
    crop = J("Data/reports/crop_robustness_experiment.json")
    bench = J("Data/reports/benchmark_inference.json")
    al = J("Data/reports/active_learning_experiment.json")["macro_f1_by_budget"]
    leak = J("Data/reports/leakage_check.json")

    # =====================================================================================================================
    R.ch("Project Implementation")
    R.h2("5.1", "Overview of Project Modules")
    R.p("The implementation is organised into nine modules. Table 5.1 lists them with their main source locations; each "
        "module is described in more detail in Section 5.5.")
    R.tab("Project modules and source locations", ["Module", "Responsibility", "Main location"],
          [["Data audit and splitting", "Discover DENTEX sub-sets, hash images, group duplicates, assign persistent splits, run leakage checks", "src/dentexmodel/data/"],
           ["Model training", "Train detection, numbering, segmentation and classification; write sidecars and manifests", "src/dentexmodel/training/"],
           ["Inference pipeline", "Detect, number, segment, crop, classify, flip-TTA, flags and abstention", "backend/services/pipeline.py"],
           ["Uncertainty and calibration", "Entropy, Jensen–Shannon disagreement, mask instability, ECE, temperature scaling", "src/dentexmodel/uncertainty/"],
           ["Report generation", "Evidence bundle, template generator, optional LLM path, validator, EN/HI/MR localisation", "src/dentexmodel/reporting/"],
           ["Review and annotation", "Revisioned region decisions, approvals, export of approved labels", "src/dentexmodel/annotation/"],
           ["Active learning", "Pool scoring and selection strategies (random, entropy, combined)", "src/dentexmodel/active_learning/"],
           ["Registry, promotion and ledger", "Checkpoint registry, evidence-backed promotion with rollback, test-set ledger", "src/dentexmodel/inference/, evaluation/"],
           ["Web interface", "Analysis, Reports, Review Findings and research pages", "frontend/src/"]],
          [0.24, 0.5, 0.26], font=19)
    R.h2("5.2", "Data Collection and Preprocessing")
    R.ps(
        "No new data were collected; the project uses the public DENTEX release [@dentex]. The first preprocessing step is an "
        "audit that opens every image, records its format, size and mode, and computes a hash of its pixel content. Files with "
        "identical pixels are grouped as one radiograph, and near-duplicate candidates are confirmed by pixel correlation "
        "(≥ 0.97) before they are treated as the same film. This step matters because the DENTEX folders overlap heavily: for "
        "example, 235 radiographs appear in three of the labelled sub-sets at once.",
        "Splits are assigned per unique radiograph by a seeded, group-aware procedure. Each group is ordered by a SHA-256 "
        "hash of the seed and its key, and groups are placed into test, calibration, validation and train until the target "
        "fractions of 10 %, 10 %, 10 % and 70 % are filled. The split file is append-only: a radiograph that has been "
        "assigned never moves, so later re-processing cannot move a training film into the test split. Applied to the 1,133 "
        "annotated radiographs, this gives 794 train, 113 validation, 113 calibration and 113 test radiographs. Within each "
        "task the split is then restricted to the sub-set that carries the needed labels: the detection, numbering and "
        "segmentation models used 440 train and 69 validation radiographs of the enumeration sub-set, and the classifier used "
        "476 train and 65 validation radiographs of the disease sub-set.",
        "Images are read as 8-bit grayscale and replicated to three channels, because all backbones were pre-trained on "
        "RGB images. The end-to-end evaluation confirmed that the production loader and the training loader produce "
        "pixel-identical inputs (maximum absolute difference 0). For classification, each finding box is enlarged by 10 % "
        "padding, cropped, resized to 224 × 224 pixels and normalised with ImageNet mean and standard deviation. This produced "
        "2,520 training crops (Caries 1,550, Deep Caries 438, Impacted 412, Periapical Lesion 120), 331 validation crops and "
        "354 test crops. The classifier was trained with horizontal flips and contrast jitter. The numbering model was "
        "trained without horizontal flips, because a flip swaps left and right FDI numbers.")
    R.fig(FIG / "fig_splits.png", "Duplicate-aware split of the 1,133 annotated radiographs", 4.2)
    R.h2("5.3", "Generative AI Model Selection")
    R.ps(
        "Two options were considered for the generative report component: a large language model that writes the report "
        "from the evidence, and a deterministic natural-language generator based on templates. Given the findings of "
        "Section 2.3, that LLM-written dental reports can omit key details [@stephan2024], and given that the project had no "
        "dental experts to review generated wording, the deterministic generator was selected as the default. It produces "
        "a summary paragraph and one sentence per finding, uses the same wording rules for every report, and is localised "
        "into Hindi and Marathi through translation tables, so the three language versions always contain the same findings "
        "and values.",
        "The LLM option was kept as an extension point. When it is configured, the service sends a de-identified evidence "
        "payload to an OpenAI-compatible chat-completions endpoint with temperature 0 and a JSON response format, expects a "
        "summary and one note per finding identifier, and runs the same validator on the result. Any failure, whether invalid "
        "JSON, a missing field or an unsupported claim, causes the draft to be rejected and replaced by the template output, "
        "with the rejection reasons recorded. No LLM endpoint was configured in this project, so the evaluated system is "
        "entirely template-based.")
    R.h2("5.4", "Model Configuration / Fine-Tuning")
    R.ps(
        "All four networks were fine-tuned from public pre-trained weights using transfer learning. Table 5.2 lists the "
        "configurations, which are recorded in each checkpoint’s JSON sidecar. The detectors were initialised from torchvision "
        "COCO weights [@lin2014coco], which are general-domain and not dental, and the classifier from ImageNet weights "
        "[@deng2009]. All models used the AdamW optimiser [@loshchilov2019] with a cosine learning-rate schedule. The detection "
        "models used automatic mixed precision to fit into 4 GB of GPU memory, which also limited the batch size to 2 for "
        "Faster R-CNN and 1 for Mask R-CNN.",
        "Model selection always used the validation split. The detectors were selected by validation box mAP over IoU 0.5 to "
        "0.95, and the classifier by validation macro-F1; its best epoch was the fifth, after which the training loss kept "
        "falling while the validation macro-F1 dropped to about 0.70, a sign of over-fitting on the small minority classes. "
        "The numbering model also had to pass a registration gate (exact FDI accuracy of at least 0.80 among localised "
        "validation teeth) before the application would load it; it reached 0.936.")
    R.tab("Training configuration of the deployed checkpoints", ["Model", "Architecture and initialisation", "Training data", "Schedule and selection"],
          [["dentex_teeth_detection_v1", "Faster R-CNN, ResNet-50 FPN, 1 class; COCO weights [@ren2015; @lin2017fpn]", "440 train / 69 val radiographs (enumeration sub-set)", "12 epochs, batch 2, AdamW lr 1e-4, cosine, AMP; best epoch 9 (val box mAP)"],
           ["dentex_fdi_numbering_v1", "Faster R-CNN, ResNet-50 FPN, 32 FDI classes; COCO weights", "440 / 69 radiographs; no flip augmentation", "16 epochs, batch 2, AdamW lr 1e-4; best epoch 15 (val mAP); gate ≥ 0.80 passed"],
           ["dentex_teeth_segmentation_v1", "Mask R-CNN, ResNet-50 FPN, 1 class, polygon masks; COCO weights [@he2017mask]", "440 / 69 radiographs", "8 epochs, batch 1, AdamW lr 1e-4, cosine, AMP; best epoch 8"],
           ["dentex_findings_classification_v1", "ResNet-50, 4 classes, 224 px crops; ImageNet weights [@he2016]", "2,520 crops from 476 radiographs / 331 val crops", "15 epochs, batch 32, AdamW lr 3e-4, cosine, inverse-frequency weights, flip + contrast jitter; best epoch 5 (val macro-F1)"]],
          [0.22, 0.28, 0.23, 0.27], font=18,
          note="Source: checkpoint sidecars in Data/checkpoints and docs/MODEL_TRAINING.md. All four checkpoints pre-date the training-manifest system and are labelled ‘legacy’; their SHA-256 hashes start with a68ce488, 83f97b2e, dd13568c and 5aa878e1.")
    R.h2("5.5", "Project Modules")
    R.h3("5.5.1", "Inference Pipeline Service")
    R.ps(
        "The pipeline service runs the steps of Fig. 4.2 for one image and stores the result. It records the status and "
        "duration of each step, so a failure in one optional stage (for example segmentation) still returns the other "
        "results with an explanation. Thresholds are read from the calibration report when it exists and otherwise fall back "
        "to defaults; Table 5.3 lists the values in use. Each region carries separate flags for each cause, so the interface "
        "can say why a region needs review rather than showing a single generic warning.")
    thr = J("Data/reports/uncertainty_thresholds.json")
    R.tab("Operating thresholds of the deployed pipeline", ["Parameter", "Value", "Origin"],
          [["Detector score threshold", "0.3", "Fixed operating point used in all evaluations"],
           ["Weak-detection flag", "score < 0.5", "Pipeline default"],
           ["Numbering match", "IoU ≥ 0.5", "Same rule in evaluation and application"],
           ["Abstention (no reliable class candidate)", f"H~n~ ≥ {thr['review_if_any']['normalised_entropy_ge']:.4f}", "Youden’s J on the calibration split (provisional)"],
           ["Unstable under flip", f"D~JS~ ≥ {thr['unstable_under_flip_if']['tta_disagreement_ge']:.4f}", "Youden’s J on the calibration split (provisional)"],
           ["Unstable outline", "1 − mask IoU ≥ 0.3", "Pipeline default"],
           ["Crop padding / size", "10 % / 224 px", "Same as classifier training"]],
          [0.38, 0.22, 0.4])
    R.h3("5.5.2", "Report Service")
    R.ps(
        "The report service builds an evidence bundle from a stored analysis. Each finding receives a stable identifier "
        "(F1, F2, …) and carries the tooth number, the class name or abstention, the raw score, the uncertainty and the "
        "review status. The template generator writes the summary, including how many regions were found, numbered, "
        "outlined and flagged, and one sentence per finding. The text states explicitly that the classifier has no healthy "
        "class, so a class name is not a statement that the finding is present. A fixed list of limitations is attached "
        "to every report. The validator described in Section 6.2 checks the draft before it is stored, and the report can "
        "be exported as HTML or text in English, Hindi or Marathi. A report changes from “awaiting review” to “reviewed” "
        "only when a named person marks it as reviewed.")
    R.h3("5.5.3", "Review, Registry and Integrity Services")
    R.ps(
        "The review service implements the workflow of Fig. 4.4 with seven actions: confirm candidate, correct class, "
        "reject candidate, set tooth number, mark number unassigned, specialist review and unusable image. The registry "
        "lists checkpoints with their hashes and sidecars. A new checkpoint can be promoted to the live system only with a "
        "validation report and a written justification; each promotion is recorded with the previous model so that it can be "
        "rolled back. The test-set ledger appends one hash-chained entry for every evaluation on the test split and refuses a "
        "second test evaluation of the same checkpoint. Its five entries are the historical evaluations of the four deployed "
        "models and the uncertainty evaluation.")
    R.h3("5.5.4", "Web Interface")
    R.ps(
        "The React interface has four main pages. Home explains the purpose and starts an analysis. X-ray Analysis combines "
        "the uploader, a zoomable viewer with boxes, numbers and outlines, and a region table that lists the tooth number, "
        "the candidate class or abstention, the raw score and the warning chips for every region. Reports shows saved drafts "
        "in the three languages, and Review Findings holds the review queue. Research pages for segmentation, uncertainty, "
        "active learning, annotations, model training, experiments and the model registry can be switched on in the "
        "settings. Screenshots are shown in Section 7.8.")
    R.h2("5.6", "Tools and Technologies Used")
    R.ps(
        "Python 3.13 with PyTorch 2.6 and torchvision 0.21 [@paszke2019] was used for all modelling, with CUDA 12.4 on the "
        "laptop GPU. FastAPI and Uvicorn serve the REST API, SQLite stores application data, and NumPy and Pillow handle "
        "image processing and metrics. The frontend uses React 18 with React Router, Vite 5 as the build tool and development "
        "proxy, Tailwind CSS for styling, Recharts for charts and lucide-react for icons. pytest runs the automated tests, and "
        "command-line scripts in the scripts folder perform the leakage check, the evaluations, the experiments and the "
        "ledger verification. The charts in this report were drawn with Matplotlib directly from the JSON evaluation reports, "
        "and the diagrams were drawn as editable shapes in Microsoft PowerPoint.")
    R.h2("5.7", "Algorithm Details")
    R.p("The three central algorithms are given below in step form.")
    algo = [["Algorithm 5.1  Region analysis of one radiograph"],
            ["Input: radiograph I; models f~det~, f~num~, f~seg~, f~cls~; thresholds τ~det~ = 0.3, τ~H~, τ~JS~\n"
             "1. X ← three-channel tensor of grayscale(I)\n"
             "2. D ← boxes of f~det~(X) with score ≥ τ~det~\n"
             "3. For each d in D: attach the FDI number of the f~num~(X) box with IoU(d, ·) ≥ 0.5, else mark it unnumbered\n"
             "4. Attach to each d the f~seg~(X) mask that overlaps it best, if any\n"
             "5. For each d: c ← crop(I, d, pad 10 %, 224 px); p ← f~cls~(c); q ← f~cls~(flip(c))\n"
             "6.     H ← H~n~(p); S ← D~JS~(p, q); label ← argmax p\n"
             "7.     if H ≥ τ~H~: status ← abstained (label and score kept, shown as ‘no reliable class candidate’)\n"
             "8.     if S ≥ τ~JS~: add flag ‘unstable under flip’; add detection and mask flags from the flipped image\n"
             "9. Store regions with flags; mark review_required if any flag is set\n"
             "Output: list of regions (box, FDI, mask, candidate class, raw score, uncertainty, flags)"]]
    R.d.table(algo[0], [algo[1]], widths=[1.0], font_half_pts=20, header_fill="F2F2F2")
    R.d.add(dl.empty("TableNote"))
    algo2 = [["Algorithm 5.2  Validation of a generated report"],
             ["Input: draft report r, evidence e, vocabulary V, forbidden phrases F\n"
              "1. Reject if required fields are missing or have the wrong type\n"
              "2. For each finding in r: it must exist in e with the same tooth number, label, score and uncertainty\n"
              "3. The number of findings in r must equal the number in e; every FDI number must be valid\n"
              "4. All scores and uncertainties in e must lie in [0, 1]; labels must belong to V\n"
              "5. Scan the free text: reject any phrase in F (e.g. ‘diagnos’, ‘recommend’, ‘treatment plan’, ‘confirmed’)\n"
              "6. Reject any tooth number, decimal number or finding name in the text that is not in e\n"
              "7. The status must be ‘research draft’ or ‘reviewed’\n"
              "Output: passed / failed with the list of errors"]]
    R.d.table(algo2[0], [algo2[1]], widths=[1.0], font_half_pts=20, header_fill="F2F2F2")
    R.d.add(dl.empty("TableNote"))
    algo3 = [["Algorithm 5.3  Duplicate-aware, persistent split assignment"],
             ["Input: annotated images with pixel hashes; seed s; fractions (train .7, val .1, calibration .1, test .1); existing split file\n"
              "1. Group images by unique radiograph (identical pixel content)\n"
              "2. Keep every group that already has an assignment in its split (append-only)\n"
              "3. Order the remaining groups by SHA-256(s : group key)\n"
              "4. Fill test, then calibration, then validation, then train up to their target counts\n"
              "5. Write the split file; run the 18 leakage checks before any training\n"
              "Output: split per image; all members of a group share one split"]]
    R.d.table(algo3[0], [algo3[1]], widths=[1.0], font_half_pts=20, header_fill="F2F2F2")
    R.d.add(dl.empty("TableNote"))

    # =====================================================================================================================
    R.ch("Software Testing")
    R.h2("6.1", "Test Cases")
    R.ps(
        "Testing was carried out at three levels: automated unit and integration tests, scripted checks of data integrity, "
        "and manual end-to-end checks of the running application in a browser. The automated suite contains 233 tests in "
        "16 files, and all 233 passed in the last recorded run on 15 October 2026. Table 6.1 groups them by area.")
    R.tab("Automated test suite by area", ["Test file(s)", "Area covered", "Tests"],
          [["test_dataset_pipeline, test_real_dentex_layout, test_preprocess", "Dataset discovery, manifest, hashing, preprocessing", "41"],
           ["test_leakage, test_research_integrity", "Leakage checks, test-set ledger, provenance, promotion gate", "27"],
           ["test_annotation_reporting, test_i18n_reports", "Evidence bundle, template, validator, EN/HI/MR reports", "31"],
           ["test_review_pipeline", "Review actions, revisions, approvals, training eligibility", "12"],
           ["test_backend_services, test_security_and_training_api", "API services, token auth, rate limits, upload and path validation", "41"],
           ["test_training_registry, test_uncertainty_eval", "Trainer, registry, uncertainty measures, calibration", "34"],
           ["test_geometry_fdi, test_active_learning", "Box geometry, FDI validity, active-learning selection", "23"],
           ["test_audit_regressions, test_skeleton", "Regression tests for defects found in the functionality audit", "26"]],
          [0.4, 0.46, 0.14], align_num={2},
          note="Counts are the test functions defined per file group (235 functions in total); pytest collected and passed 233 tests in the last recorded run.")
    R.p("Table 6.2 lists representative functional test cases with the observed result.")
    R.tab("Representative functional test cases", ["ID", "Test case", "Expected result", "Observed"],
          [["TC-1", "Analyse DENTEX test image val_0 from the ‘Test data’ source in the browser", "Regions with boxes, numbers and outlines; flags per region", "27 regions in 4.4 s; 26 numbered, 26 with mask, 20 flagged"],
           ["TC-2", "Generate a report for that analysis and switch language", "Validated draft in EN, HI and MR with identical values", "Report RPT-8C9DE6104F created, status ‘awaiting review’"],
           ["TC-3", "Run the leakage checker on the current splits", "No overlap between train, val, calibration and test", "17 checks pass, 1 informational warning"],
           ["TC-4", "Verify the test-set ledger", "Hash chain intact; one test use per checkpoint", "5 historical entries, chain verified"],
           ["TC-5", "Submit the same review decision twice", "Second submission refused", "Refused as duplicate (unit test)"],
           ["TC-6", "Call the API without a token", "Request rejected", "401 Unauthorized (unit test)"],
           ["TC-7", "Report text mentions a tooth or number absent from the evidence", "Validator rejects the draft", "Rejected with error list (unit test)"],
           ["TC-8", "Promote a checkpoint without a validation report", "Promotion refused", "Refused (unit test)"]],
          [0.08, 0.34, 0.3, 0.28], font=18)
    R.p("The single leakage warning concerns three unlabelled demo files in validation_data (val_4, val_22 and val_29) that "
        "are byte-identical to test radiographs. They are never used for training or scoring and are listed in the interface "
        "as copies of test films; the warning was left visible on purpose.")
    R.h2("6.2", "Generative AI Output Testing")
    R.ps(
        "Because generated text is the part of the system most likely to overstate results, every draft passes through the "
        "validator of Algorithm 5.2 before it is stored, and the validator itself is covered by unit tests with deliberately "
        "faulty drafts. The checks fall into four groups. Schema checks require all fields, with the correct types and a "
        "research-draft or reviewed status. Evidence checks require that every finding in the report exists in the evidence "
        "with the same tooth number, label, score and uncertainty, and that no finding is added or dropped. Claim checks scan "
        "the free text for forbidden phrases such as “diagnosis”, “recommend”, “treatment plan”, “extraction”, “definitely” "
        "and “confirmed”, and for any tooth number, decimal number or finding name not present in the evidence. Range checks "
        "require scores in [0, 1] and labels from the model vocabulary.",
        "For the LLM path, the tests inject a fake transport that returns invalid JSON, a missing field, an invented tooth "
        "number or a forbidden phrase, and confirm that each case is rejected and replaced by the template draft with the "
        "reasons recorded. The localisation tests check that the Hindi and Marathi reports contain exactly the same "
        "findings, numbers and identifiers as the English one. The Hindi and Marathi wording has not been reviewed by a "
        "native-speaking dental professional, which is listed as a limitation.")
    R.h2("6.3", "Performance Evaluation")
    st = bench["stages"]
    R.p(f"Inference speed was measured on {bench['n_images']} DENTEX radiographs on the RTX 3050 laptop GPU. Table 6.3 lists "
        "the mean, median and 95th-percentile time per image and the peak GPU memory of each stage; no failures occurred.")
    rows = []
    for k, label in [("detection", "Detection"), ("segmentation", "Segmentation"), ("detection+numbering (total)", "Detection + numbering"),
                     ("detection+classification (total)", "Detection + classification")]:
        s = st[k]
        rows.append([label, f"{s['mean_s']:.3f}", f"{s['median_s']:.3f}", f"{s['p95_s']:.3f}", f"{s['images_per_s']:.1f}", f"{s['peak_gpu_mb']:.0f}"])
    R.tab("Inference latency per image (RTX 3050 Laptop GPU)", ["Stage", "Mean (s)", "Median (s)", "P95 (s)", "Images/s", "Peak GPU (MB)"],
          rows, [0.3, 0.13, 0.14, 0.13, 0.13, 0.17], align_num={1, 2, 3, 4, 5},
          note="Source: Data/reports/benchmark_inference.json. A full analysis in the application additionally runs the flipped-image passes and stores the result; for val_0 (2872 × 1504 pixels) this took 4.4 s end to end.")

    # =====================================================================================================================
    R.ch("Results and Discussion")
    R.p("Throughout this chapter, **validation** results come from the split that was also used to select epochs and compare "
        "models, so they are slightly optimistic. **Historical test** results come from the test split, which was evaluated "
        "once per deployed checkpoint before the test-set ledger existed. Those uses are now recorded in the ledger, and the "
        "test split was never used to choose a model or a threshold. The two kinds of result are reported side by side and "
        "are never mixed in one average.", "BodyNoIndent")
    R.h2("7.1", "Project Outcomes")
    R.ps(
        "The project delivered a working, locally deployed system that meets the functional requirements of Section 3.3. "
        "Given a panoramic radiograph, it locates the teeth, numbers and outlines them, proposes a candidate finding or "
        "abstains, flags doubtful regions by cause, and generates a validated draft report in three languages. The review "
        "workflow keeps a revisioned, second-person-approved record of every decision.",
        "The project also delivered an evaluation infrastructure: a dataset audit with duplicate-aware splits, 18 automated "
        "leakage checks, evaluation scripts that record dataset fingerprints and software versions, a hash-chained test-set "
        "ledger, and pre-registered experiment protocols. The infrastructure is the reason the results below can be stated "
        "with their limitations rather than as single optimistic numbers.")
    R.h2("7.2", "Result Analysis")
    R.h3("7.2.1", "Tooth Detection and Segmentation")
    dv, dt = ev["teeth_detection_val"]["detection"], ev["teeth_detection_test"]["detection"]
    sv, stt = ev["teeth_segmentation_val"]["segmentation"], ev["teeth_segmentation_test"]["segmentation"]
    rows = []
    for name, m in [("Detection, validation", dv), ("Detection, historical test", dt), ("Segmentation, validation", sv), ("Segmentation, historical test", stt)]:
        op = m["operating_point"]
        f1 = 2 * op["tp"] / (2 * op["tp"] + op["fp"] + op["fn"])
        rows.append([name, str(m["n_images"]), f"{op['tp']} / {op['fp']} / {op['fn']}", f3(op["precision"]), f3(op["recall"]), f3(f1),
                     f3(m["ap50"]), f3(m["map"]), f3(m["mask_ap50"]) if "mask_ap50" in m else "–"])
    R.tab("Tooth detection and segmentation (score ≥ 0.3, IoU ≥ 0.5)", ["Model and split", "Images", "TP / FP / FN", "Precision", "Recall", "F1", "Box AP50", "Box mAP", "Mask AP50"],
          rows, [0.24, 0.07, 0.15, 0.09, 0.08, 0.08, 0.09, 0.09, 0.11], align_num={1, 2, 3, 4, 5, 6, 7, 8}, font=18,
          note=f"F1 is derived from the TP/FP/FN counts. On the historical test split the segmentation masks reached mean Dice {stt['mean_dice_matched']:.3f} and mean mask IoU {stt['mean_mask_iou_matched']:.3f} over {stt['n_matched_for_iou']:,} matched teeth (mask IoU on a 4× sub-sampled grid).")
    R.ps(
        "Tooth localisation is strong and stable between the two splits: precision stays near 0.96 and recall drops only "
        "from 0.984 to 0.974, with about one false positive per image. The gap between AP50 (0.97 to 0.98) and mAP over IoU "
        "0.5 to 0.95 (0.52 to 0.57) shows that the boxes overlap the teeth well but are not pixel-tight. This matters later, "
        "because the classifier crops come from these boxes. The segmentation masks reach a mean Dice of 0.873 on the "
        "historical test split, enough to outline teeth in the viewer but not intended for measurement. Fig. 7.1 compares "
        "the two splits.")
    R.fig(FIG / "fig_detection_segmentation.png", "Detection and segmentation on validation and historical test splits", 5.8)
    R.h3("7.2.2", "FDI Tooth Numbering")
    nv, nt = ev["fdi_numbering_val"]["numbering"]["numbering"], ev["fdi_numbering_test"]["numbering"]["numbering"]
    R.tab("FDI tooth numbering", ["Split", "GT teeth", "Localised (coverage)", "Exact FDI (of localised)", "Correct quadrant", "Strict (all GT)"],
          [[s, f"{n['n_ground_truth_teeth']:,}", f"{n['n_matched_iou50']:,} ({n['coverage']:.3f})", f3(n["exact_accuracy_among_matched"]),
            f3(n["quadrant_accuracy_among_matched"]), f3(n["strict_accuracy_all_gt"])] for s, n in [("Validation", nv), ("Historical test", nt)]],
          [0.2, 0.12, 0.2, 0.18, 0.15, 0.15], align_num={1, 2, 3, 4, 5})
    R.ps(
        "Among teeth that were localised, the numbering model assigns the exact FDI number in 93.6 % of validation cases and "
        "96.8 % of historical test cases, and the quadrant is almost always right (99.7 % and 99.9 %). Fig. 7.2 "
        "shows the per-tooth accuracy on the validation split: the lowest value is for tooth 36 (0.82), and other molars "
        "such as 18, 37 and 47 lie between 0.86 and 0.87, while the incisors are numbered almost perfectly. The strict accuracy, which "
        "counts every unlocalised tooth as wrong, is 0.915 and 0.938.")
    R.fig(FIG / "fig_numbering_per_tooth.png", "Exact FDI numbering accuracy per tooth on the validation split", 5.8)
    R.h3("7.2.3", "Finding Classification on Ground-Truth Tooth Boxes")
    cv, ct = ev["findings_classification_val"]["classification"], ev["findings_classification_test"]["classification"]
    R.tab("Finding classification with ground-truth boxes: summary", ["Split", "Crops", "Accuracy", "Macro precision", "Macro recall", "Macro F1"],
          [["Validation", str(cv["n_crops"]), f3(cv["accuracy"]), f3(cv["macro_precision"]), f3(cv["macro_recall"]), f3(cv["macro_f1"])],
           ["Historical test", str(ct["n_crops"]), f3(ct["accuracy"]), f3(ct["macro_precision"]), f3(ct["macro_recall"]), f3(ct["macro_f1"])]],
          [0.24, 0.1, 0.15, 0.17, 0.17, 0.17], align_num={1, 2, 3, 4, 5},
          note=f"Historical test macro one-vs-rest ROC-AUC: {ct['macro_roc_auc_ovr']:.3f}. Specificity and ROC-AUC are computed among the four finding classes only, because there is no healthy class.")
    rows = []
    for c in CLS:
        a, b = cv["per_class"][c], ct["per_class"][c]
        rows.append([c, f"{a['support']} / {b['support']}", f"{a['precision']:.3f} / {b['precision']:.3f}", f"{a['recall']:.3f} / {b['recall']:.3f}",
                     f"{a['f1']:.3f} / {b['f1']:.3f}", f"{b['roc_auc_ovr']:.3f}"])
    R.tab("Per-class results (validation / historical test)", ["Class", "Support", "Precision", "Recall", "F1", "Test ROC-AUC"],
          rows, [0.22, 0.13, 0.17, 0.17, 0.17, 0.14], align_num={1, 2, 3, 4, 5})
    R.ps(
        "The classifier separates the four findings far better than chance (macro ROC-AUC 0.910), but its decisions are "
        "uneven across classes. Impacted teeth are recognised reliably (F1 0.93 on both splits), because impaction is a "
        "matter of position and shape that is visible at crop level. Caries is also good (F1 0.87 and 0.84). Deep Caries is "
        "weak (F1 0.48 and 0.45). The confusion matrix in Fig. 7.4 shows that 20 of the 45 validation Deep Caries crops are "
        "predicted as Caries and 18 Caries crops as Deep Caries. The two labels describe depth along a continuum, and the "
        "boundary is hard to see on a panoramic film. Periapical Lesion has only 9 validation and 13 test crops, so its "
        "results swing widely: recall is 0.78 on validation and 0.31 on test, and a single prediction changes the "
        "validation recall by 11 percentage points.",
        "Accuracy is a misleading summary here. Caries makes up 62 % of the validation crops, so a model that is good at "
        "Caries and poor at the rare classes still reaches high accuracy. For this reason macro-F1 is the primary metric "
        "throughout the project.")
    R.fig(FIG / "fig_classifier_per_class.png", "Per-class precision, recall and F1 of the finding classifier", 5.8)
    R.fig(FIG / "fig_confusion_val.png", "Confusion matrix on the validation split (ground-truth boxes)", 3.6)
    R.h2("7.3", "Generated Output Analysis")
    R.ps(
        "Reports were generated for real analyses during testing. For the DENTEX test image val_0, the generated English "
        "summary reads, in part: “The detection model (dentex_teeth_detection_v1) located 27 tooth region(s). … The "
        "classification model (dentex_findings_classification_v1) gave each region its closest class among four trained "
        "findings. It has no healthy class, so a class name here is not a statement that the finding is present. Of these, 26 "
        "have a tooth number from the numbering model, 26 have a matched segmentation mask, and 20 are flagged for manual "
        "review.” The summary is followed by one line per finding with its identifier, tooth number, candidate class or "
        "abstention, raw score, uncertainty and review status, and by the fixed list of limitations (Fig. 7.12).",
        "Three properties of the generated output were checked. Faithfulness: every number and tooth in the text comes from "
        "the evidence, because the validator rejects anything else. Consistency: the English, Hindi and Marathi versions "
        "contain identical findings and values, which the localisation tests confirm. Caution: the text uses the wording "
        "“closest class” and “flagged for manual review” and never names a diagnosis, and forbidden phrases are blocked "
        "automatically. The same example also shows the main weakness of the system: 18 of the 27 regions on val_0 "
        "abstained. The report is therefore honest, but it is less informative for a radiograph whose teeth are mostly "
        "healthy, which is exactly the situation the classifier was never trained on.")
    R.h2("7.4", "Performance Metrics")
    R.p("Table 7.5 brings the main metrics of all four models together, with validation and historical test results kept "
        "separate.")
    R.tab("Summary of model performance", ["Model", "Metric", "Validation", "Historical test"],
          [["Tooth detection", "Precision / recall / AP50", f"{dv['operating_point']['precision']:.3f} / {dv['operating_point']['recall']:.3f} / {dv['ap50']:.3f}", f"{dt['operating_point']['precision']:.3f} / {dt['operating_point']['recall']:.3f} / {dt['ap50']:.3f}"],
           ["Tooth segmentation", "Mask AP50 / box F1", f"{sv['mask_ap50']:.3f} / 0.976", f"{stt['mask_ap50']:.3f} / 0.971"],
           ["Tooth segmentation", "Mean Dice / mask IoU", "not computed", f"{stt['mean_dice_matched']:.3f} / {stt['mean_mask_iou_matched']:.3f}"],
           ["FDI numbering", "Exact accuracy (of localised)", f3(nv["exact_accuracy_among_matched"]), f3(nt["exact_accuracy_among_matched"])],
           ["Finding classifier (GT boxes)", "Accuracy / macro-F1", f"{cv['accuracy']:.3f} / {cv['macro_f1']:.3f}", f"{ct['accuracy']:.3f} / {ct['macro_f1']:.3f}"],
           ["Finding classifier (GT boxes)", "Macro precision / recall", f"{cv['macro_precision']:.3f} / {cv['macro_recall']:.3f}", f"{ct['macro_precision']:.3f} / {ct['macro_recall']:.3f}"],
           ["Classifier on detector boxes", "Accuracy / macro-F1 (323 teeth)", f"{e2e['matched@0.5']['B_detector_boxes']['accuracy']:.3f} / {e2e['matched@0.5']['B_detector_boxes']['macro_f1']:.3f}", "not evaluated"],
           ["End-to-end (all 331 findings)", "Accuracy / macro-F1", f"{e2e['end_to_end@0.5']['accuracy']:.3f} / {e2e['end_to_end@0.5']['macro_f1']:.3f}", "not evaluated"]],
          [0.28, 0.28, 0.22, 0.22], align_num={2, 3}, font=19,
          note="Segmentation box F1 is derived from TP/FP/FN (1,972/70/28 and 1,754/69/36). The detector-box and end-to-end evaluations were run on the validation split only, so that the test split is not reused.")
    R.h2("7.5", "Accuracy / Relevance / Quality Evaluation")
    R.h3("7.5.1", "Ground-Truth Boxes versus Detector Boxes")
    m5, ee = e2e["matched@0.5"], e2e["end_to_end@0.5"]
    dec = e2e["decomposition@0.5"]
    R.ps(
        "In the application the classifier never sees a ground-truth box; it classifies crops cut from the detector’s boxes. "
        "To measure what the user actually gets, the 331 validation findings were matched one-to-one to detector boxes at "
        f"IoU ≥ 0.5. {m5['n_matched']} findings were matched and {m5['n_missed']} were not. On the same {m5['n_matched']} "
        f"teeth, ground-truth crops give accuracy {m5['A2_gt_boxes_same_teeth']['accuracy']:.3f} and macro-F1 "
        f"{m5['A2_gt_boxes_same_teeth']['macro_f1']:.3f}, while detector crops give {m5['B_detector_boxes']['accuracy']:.3f} "
        f"and {m5['B_detector_boxes']['macro_f1']:.3f}. Counting the unmatched findings as errors, the end-to-end accuracy is "
        f"{ee['accuracy']:.3f} and the macro-F1 {ee['macro_f1']:.3f} (Table 7.6 and Fig. 7.5).",
        f"The drop is concentrated in the rare classes. End to end, Deep Caries recall is {ee['per_class']['Deep Caries']['recall_end_to_end']:.3f} "
        f"and only 4 of the 9 Periapical Lesion findings are recovered. The errors decompose as follows: {dec['both correct']} findings "
        f"are correct with both box types and {dec['wrong with both boxes']} are wrong with both. {dec['correct with GT box, wrong with detector box']} "
        f"are correct only with the ground-truth box and {dec['wrong with GT box, correct with detector box']} only with the "
        "detector box, and 8 are unmatched. Of the unmatched findings, 4 are genuine detector misses and 4 sit on teeth that "
        "carry two findings, which a single box cannot represent. The detector itself is not the problem: on the 24 validation "
        "images with full tooth annotations it found 716 of 719 teeth with 17 false positives (precision 0.977, recall 0.996). "
        "The cause is crop sensitivity. About 10 % of predictions change even when the detector box overlaps the ground-truth "
        "box at IoU above 0.9, because the classifier was trained only on ground-truth crops.")
    R.tab("Classification with ground-truth and detector crops (validation)", ["Setting", "Findings", "Accuracy", "Macro-F1", "Deep Caries recall", "Periapical Lesion recall"],
          [["Ground-truth boxes, all findings", "331", f3(e2e["A2_production_gt_boxes"]["accuracy"]), f3(e2e["A2_production_gt_boxes"]["macro_f1"]),
            f3(e2e["A2_production_gt_boxes"]["per_class"]["Deep Caries"]["recall"]), f3(e2e["A2_production_gt_boxes"]["per_class"]["Periapical Lesion"]["recall"])],
           ["Ground-truth boxes, matched teeth", str(m5["n_matched"]), f3(m5["A2_gt_boxes_same_teeth"]["accuracy"]), f3(m5["A2_gt_boxes_same_teeth"]["macro_f1"]),
            f3(m5["A2_gt_boxes_same_teeth"]["per_class"]["Deep Caries"]["recall"]), f3(m5["A2_gt_boxes_same_teeth"]["per_class"]["Periapical Lesion"]["recall"])],
           ["Detector boxes, matched teeth", str(m5["n_matched"]), f3(m5["B_detector_boxes"]["accuracy"]), f3(m5["B_detector_boxes"]["macro_f1"]),
            f3(m5["B_detector_boxes"]["per_class"]["Deep Caries"]["recall"]), f3(m5["B_detector_boxes"]["per_class"]["Periapical Lesion"]["recall"])],
           ["End-to-end (misses count as wrong)", "331", f3(ee["accuracy"]), f3(ee["macro_f1"]),
            f3(ee["per_class"]["Deep Caries"]["recall_end_to_end"]), f3(ee["per_class"]["Periapical Lesion"]["recall_end_to_end"])]],
          [0.29, 0.12, 0.12, 0.12, 0.17, 0.18], align_num={1, 2, 3, 4, 5}, font=19,
          note="Source: Data/reports/end_to_end_validation_evaluation.json (one-to-one greedy matching by IoU, detector score ≥ 0.3, classifier argmax).")
    R.fig(FIG / "fig_gt_vs_detector.png", "Effect of detector crops on finding classification (validation split)", 5.8)
    R.ps(
        "A related problem is the missing healthy class. Of the 1,903 detector boxes on the 65 validation images, 1,580 do "
        "not correspond to any labelled finding, yet the classifier still assigns each of them one of the four findings. "
        "Most of these teeth are probably healthy, but DENTEX does not label healthy teeth, so this cannot be measured. "
        "The abstention rule and the wording “closest class” exist because of this limitation.")
    R.h3("7.5.2", "Uncertainty and Abstention")
    ts, cs = unc["test_split"], unc["calibration_split"]
    R.ps(
        f"The uncertainty thresholds were chosen on the calibration split ({cs['n']} crops) and then measured once on the "
        f"historical test split ({ts['n']} crops). Normalised entropy ranks the classifier’s errors with an AUROC of "
        f"{ts['auroc_entropy_for_errors']:.3f}, and flip disagreement with {ts['auroc_tta_disagreement_for_errors']:.3f}. At the "
        f"chosen threshold, {ts['flagged_for_review_fraction']:.0%} of test crops are flagged, and these flagged crops contain "
        f"{ts['errors_caught_fraction']:.0%} of all errors. The error rate is {ts['error_rate_flagged']:.1%} among flagged crops and "
        f"{ts['error_rate_not_flagged']:.1%} among the rest (Table 7.7 and Fig. 7.6).",
        f"The raw scores are reasonably calibrated: the expected calibration error is {ts['ece']:.3f} on the test split. "
        f"Temperature scaling with T = {cs['temperature_fit']:.2f}, fitted on the calibration split [@guo2017], would reduce it to "
        f"{ts['ece_after_temperature_fitted_on_calibration']:.3f}, but it increases the calibration-split ECE from "
        f"{cs['ece']:.3f} to {cs['ece_after_temperature']:.3f}. Because the evidence is mixed, the temperature is reported but "
        "not applied, and the interface labels scores as raw model scores. Flagging works as a triage signal, but flagging "
        "more than half of all crops is a heavy burden for a reviewer, and the thresholds remain provisional because they "
        "come from one seed and one dataset.")
    R.tab("Uncertainty evaluation of the finding classifier", ["Quantity", "Calibration split", "Historical test split"],
          [["Crops / accuracy", f"{cs['n']} / {cs['accuracy']:.3f}", f"{ts['n']} / {ts['accuracy']:.3f}"],
           ["ECE before / after temperature scaling", f"{cs['ece']:.3f} / {cs['ece_after_temperature']:.3f}", f"{ts['ece']:.3f} / {ts['ece_after_temperature_fitted_on_calibration']:.3f}"],
           ["Brier score", f"{cs['brier']:.3f}", f"{ts['brier']:.3f}"],
           ["AUROC for errors: entropy / flip disagreement / 1 − max p", f"{cs['auroc_entropy_for_errors']:.3f} / {cs['auroc_tta_disagreement_for_errors']:.3f} / {cs['auroc_one_minus_maxprob_for_errors']:.3f}",
            f"{ts['auroc_entropy_for_errors']:.3f} / {ts['auroc_tta_disagreement_for_errors']:.3f} / {ts['auroc_one_minus_maxprob_for_errors']:.3f}"],
           ["Flagged fraction / errors caught", "thresholds chosen here", f"{ts['flagged_for_review_fraction']:.3f} / {ts['errors_caught_fraction']:.3f}"],
           ["Error rate flagged / not flagged", "–", f"{ts['error_rate_flagged']:.3f} / {ts['error_rate_not_flagged']:.3f}"],
           ["Error rate unstable / stable under flip", "–", f"{ts['error_rate_tta_unstable']:.3f} / {ts['error_rate_tta_stable']:.3f}"]],
          [0.46, 0.27, 0.27], align_num={1, 2}, font=19)
    R.fig(FIG / "fig_uncertainty.png", "Error rate of flagged and unflagged crops, and calibration error", 5.6)

    R.h2("7.6", "Validation of Results")
    R.p("This section reports the experiments that tried to improve the classifier, and the checks that support the "
        "integrity of all results. Every improvement had to pass a rule written before the experiment was run, and no "
        "experiment used the test split.")
    R.h3("7.6.1", "Class-Imbalance Experiments")
    order = [("C0", "C0 baseline: inverse-frequency weights (cap 5)"), ("I_sampler", "A: weighted sampler, p ∝ n~c~^−0.5^, no weights"),
             ("C3b_oversample_baselineaug", "B: oversampling of minority crops, weights kept"), ("I_focal", "C: focal loss, γ = 2, no weights"),
             ("I_weights_sqrt", "D: square-root inverse-frequency weights"), ("I_minority_geom", "E: extra geometric augmentation for minority classes"),
             ("C_unweighted", "Reference: plain cross-entropy")]
    paired = {"I_sampler": "+0.002 (2/5)", "C3b_oversample_baselineaug": "+0.010 (3/5)", "I_focal": "−0.014 (0/5)",
              "I_weights_sqrt": "−0.022 (1/5)", "I_minority_geom": "−0.013 (1/5)"}
    rows = []
    for k, label in order:
        a = imb[k]["aggregate"]
        rows.append([label, f"{a['macro_f1'][0]:.3f} ± {a['macro_f1'][1]:.3f}", paired.get(k, "–"),
                     f"{a['Deep Caries|recall'][0]:.3f}", f"{a['Periapical Lesion|recall'][0]:.3f}", f"{a['accuracy'][0]:.3f}"])
    R.ps(
        "Because the minority classes were the weak point, five standard remedies for class imbalance [@buda2018; "
        "@lin2017focal] were compared with the baseline C0, a ResNet-50 trained with inverse-frequency class weights capped "
        "at 5. Each variant changed exactly one factor; everything else, including data, schedule and seeds 42 to 46, was "
        "identical. A re-run of the baseline (C0r) reproduced C0 bit for bit on all five seeds, so the comparison is "
        "deterministic and differences are caused by the change itself. The rule fixed in advance required a paired "
        "macro-F1 gain above 0.027, which is the seed-to-seed standard deviation of the baseline, in at least four of five "
        "seeds, without lowering minority-class recall. Validation was used for both epoch selection and reporting, which "
        "gives every method the same optimistic bias.")
    R.tab("Class-imbalance experiments on the validation split (5 seeds)", ["Variant", "Macro-F1 (mean ± SD)", "Paired Δ vs C0 (seeds better)", "Deep Caries recall", "Periapical Lesion recall", "Accuracy"],
          rows, [0.36, 0.14, 0.15, 0.11, 0.12, 0.12], align_num={1, 2, 3, 4, 5}, font=18,
          note="Source: docs/audit_evidence/ml_improvement/imbalance/results.json (sample SD across seeds). Validation supports: 205 / 45 / 72 / 9.")
    R.ps(
        "No variant passed, as Table 7.8 and Fig. 7.7 show. Oversampling (B) had the largest mean gain, +0.010, but it was "
        "better in only three of five seeds and the gain is well inside the noise. The sampler, oversampling and focal-loss "
        "variants raised precision on the minority classes but lowered their recall. For example, Deep Caries recall fell by "
        "0.098 with the sampler and Periapical Lesion recall by 0.111 with focal loss. For a screening aid, missing a lesion "
        "is worse than flagging one too many, so this trade is the wrong direction. Square-root weights lowered "
        "macro-F1 and Periapical Lesion F1. Minority-only augmentation (E) lowered Deep Caries recall by 0.124 in all five seeds.",
        "Post-hoc threshold tuning was also tested. Class-specific decision weights fitted on the validation split raised "
        "macro-F1 by 0.023 in-sample, but under cross-fitting, where weights are fitted on one half and scored on the other, "
        "the gain became −0.005, and the fitted weights changed erratically between seeds. The decision rule therefore stays "
        "at argmax. These remedies did not qualify for promotion because none produced an improvement larger than the "
        "variation between random seeds, and most of them made the clinically important minority classes worse. The "
        "deployed classifier was kept unchanged.")
    R.fig(FIG / "fig_imbalance.png", "Macro-F1 and minority-class recall of the imbalance variants (C0 baseline, A–E, reference)", 5.8)
    R.h3("7.6.2", "Crop-Robustness Candidate")
    pc = crop["paired_B_minus_C0r"]
    R.ps(
        "Because Section 7.5.1 identified crop sensitivity as a cause of errors, a second pre-registered experiment trained "
        "the classifier with box jitter sampled from the real offsets between detector and ground-truth boxes on the train "
        "split (Candidate B). Its detector-crop macro-F1 was "
        f"{crop['aggregate_mean_sd']['B_cropjitter']['det_macro_f1'][0]:.3f} ± {crop['aggregate_mean_sd']['B_cropjitter']['det_macro_f1'][1]:.3f} "
        f"against {crop['aggregate_mean_sd']['C0r']['det_macro_f1'][0]:.3f} ± {crop['aggregate_mean_sd']['C0r']['det_macro_f1'][1]:.3f} for the baseline "
        f"(paired difference {pc['det_macro_f1']['mean']:+.3f}, better in {pc['det_macro_f1']['n_better']} of 5 seeds), so it failed the primary "
        f"criterion. It raised macro recall in all five seeds ({pc['det_macro_recall']['mean']:+.3f}) and Deep Caries recall by "
        f"{pc['det_Deep Caries_recall']['mean']:+.3f}, but at the cost of precision ({pc['det_macro_precision']['mean']:+.3f}). It was not promoted.")
    R.h3("7.6.3", "Training-Recipe Comparison")
    ag = rec["aggregate_mean_sd"]
    pv = [rec["models"]["P_production_recipe"][s]["det_all"]["macro_f1"] if "det_all" in rec["models"]["P_production_recipe"][s]
          else rec["models"]["P_production_recipe"][s]["det_matched"]["macro_f1"] for s in ["42", "43", "44", "45", "46"]]
    R.ps(
        "The crop-robustness study revealed that the deployed classifier scored lower on detector crops than every baseline "
        "run of the experiment trainer. A third pre-registered study therefore compared the production training recipe (P) "
        "with the experiment recipe (E). The production trainer with seed 42 reproduced the deployed checkpoint bit for "
        f"bit. Over five seeds, recipe P reached a detector-crop macro-F1 of {ag['P_production_recipe']['det_macro_f1'][0]:.3f} ± "
        f"{ag['P_production_recipe']['det_macro_f1'][1]:.3f} and recipe E {ag['E_C0r_recipe']['det_macro_f1'][0]:.3f} ± "
        f"{ag['E_C0r_recipe']['det_macro_f1'][1]:.3f}. Recipe E was better in only "
        f"{rec['cross_pairs_det_macro_f1']['n_E_better']} of {rec['cross_pairs_det_macro_f1']['n']} cross pairs and lowered "
        "Periapical Lesion recall, so it failed. The study did show that the deployed model is the weakest of the five "
        f"production runs ({pv[0]:.3f} against {min(pv[1:]):.3f} to {max(pv[1:]):.3f}, Fig. 7.8). The spread between seeds of the "
        "same recipe is larger than any effect of the imbalance remedies. Choosing a different seed on the validation "
        "split would have been selection on noise, so the deployed model was kept. Single-seed results should not be "
        "trusted for this task.")
    R.fig(FIG / "fig_recipe.png", "Detector-crop macro-F1 of five seeds of each training recipe (validation)", 5.0)
    R.h3("7.6.4", "Integrity and Reproducibility Checks")
    R.ps(
        f"The leakage checker ran {len(leak['checks'])} checks: overlap between every pair of splits across all labelled sub-sets, "
        "the images actually used by each task for training and epoch selection against all test radiographs, the "
        "unlabelled pool, approved review items, the unlabelled demo files and near-duplicate films confirmed by pixel "
        f"correlation. {leak['summary']['passed']} checks passed and {leak['summary']['warnings']} produced the informational "
        "warning explained in Section 6.1. Every evaluation report records the dataset fingerprint, the split hash and the "
        "software versions, and the test-set ledger verifies its hash chain. Because the dataset contains no patient "
        "identifiers, separation at the patient level cannot be proven: two different radiographs of the same patient "
        "could still fall into different splits.",
        "An active-learning experiment was also run (ResNet-18 at 160 px, 3 seeds, budgets of 60 to 300 training "
        "radiographs). Entropy-based and combined selection did not outperform random selection; at 300 radiographs the "
        f"macro-F1 values were {al['random']['300']['mean']:.3f} (random), {al['entropy']['300']['mean']:.3f} (entropy) and "
        f"{al['combined']['300']['mean']:.3f} (combined), within one standard deviation of each other (Fig. 7.9). The active-"
        "learning module is therefore offered as a tool, without a claim that it saves annotation effort on this data "
        "[@settles2009].")
    R.fig(FIG / "fig_active_learning.png", "Active learning versus random selection on the validation split", 4.8)

    R.h2("7.7", "Comparison with Existing Approaches")
    R.ps(
        "A direct numerical comparison with published work is not meaningful, and we avoid one. The published studies use "
        "different images (periapical versus panoramic), different label sets, different splits and different metrics. Our "
        "classification metric is computed on tooth crops rather than on detected finding boxes, as in the DENTEX "
        "challenge. Table 7.9 therefore compares approaches qualitatively and quotes published numbers only where we "
        "verified them in the original paper.")
    R.tab("Qualitative comparison with existing approaches", ["Aspect", "Typical published systems", "DentaMind AI"],
          [["Scope", "One task: caries [@lee2018], numbering [@tuzoff2019; @chen2019], or lesions [@ekert2019]", "Detection, numbering, segmentation and four findings in one pipeline"],
           ["Reported performance", "Lee et al.: caries accuracy 82.0–89.0 % on periapical films [@lee2018]", "Validation: detection recall 0.984, numbering 93.6 %, classifier macro-F1 0.718 (GT boxes) and 0.634 end to end"],
           ["Uncertainty", "Rarely reported", "Entropy + flip-TTA, abstention, calibrated thresholds, ECE reported"],
           ["Report generation", "Free text, learned [@jing2018] or prompted [@stephan2024]", "Template generation from evidence + automatic validator; three languages"],
           ["Evaluation hygiene", "Often a single split; leakage rarely audited [@varoquaux2022]", "Duplicate-aware splits, 18 leakage checks, test ledger, pre-registered experiments"],
           ["Human oversight", "Usually outside the system", "Built-in review queue, revisions and second-person approval"],
           ["Clinical validation", "Limited; reader studies in some works", "None (research prototype)"]],
          [0.2, 0.38, 0.42], font=19)
    R.ps(
        "The comparison shows where this project adds value. Its accuracy on the hard findings is not better than "
        "specialised systems. Its contribution is the integration of the tasks, the visible uncertainty, the grounded "
        "report generation and the evaluation discipline, which are the aspects the literature identifies as missing "
        "[@schwendicke2019; @varoquaux2022].")
    R.h2("7.8", "Screenshots of the Implemented System")
    R.p("The following screenshots were captured from the running application on 15 October 2026, using the DENTEX test "
        "image val_0 from the unlabelled validation_data folder. They are reproduced in grayscale, as the report format "
        "requires; the application itself uses colour to separate the categories.")
    g0 = gray_copy("documents/showcase/screenshots/00_image_selected_before_analysis.jpg", "screenshot_select_gray.png")
    g1 = gray_copy("documents/showcase/screenshots/01_analysis_val0_27_regions.jpg", "screenshot_analysis_gray.png")
    g2 = gray_copy("documents/showcase/screenshots/02_report_draft_val0.jpg", "screenshot_report_gray.png")
    R.fig(g0, "X-ray Analysis page with a test image selected, before analysis", 5.8)
    R.fig(g1, "Analysis result for val_0: 27 regions with FDI numbers, outlines and review markers", 5.8)
    R.fig(g2, "Reports page with the validated draft report for val_0, awaiting review", 5.8)

    # =====================================================================================================================
    R.ch("Conclusion and Future Work")
    R.h2("8.1", "Conclusion")
    R.ps(
        "This project designed, implemented and evaluated DentaMind AI, an AI-assisted system for panoramic dental "
        "radiographs that combines tooth detection, FDI numbering, tooth segmentation and four-class finding "
        "classification with uncertainty-based abstention, evidence-grounded multilingual report generation and a human "
        "review workflow. The tooth-level tasks perform well. On the validation split, detection reached precision 0.962 "
        "and recall 0.984, and 93.6 % of localised teeth received the exact FDI number. On the historical test split, "
        "segmentation reached a mean Dice of 0.873.",
        "Finding classification is the weak link. With ground-truth boxes the classifier reached a validation macro-F1 of "
        "0.718 (historical test 0.646). On the detector’s own crops it fell to 0.649, and end to end to 0.634, with Deep "
        "Caries and Periapical Lesion as the main sources of error. Five class-imbalance remedies, a crop-robustness "
        "candidate and an alternative training recipe were evaluated under pre-registered rules, and none earned "
        "promotion. The variation between random seeds was as large as any of the effects.",
        "The most important outcome is therefore not a single accuracy figure but a system that tells the user when it is "
        "unsure, cannot write a statement it has no evidence for, keeps humans responsible for every decision, and reports "
        "its own performance honestly. DentaMind AI is a research prototype; it has not been clinically validated and must "
        "not be used for diagnosis.")
    R.h2("8.2", "Limitations of the Proposed System")
    R.ps(
        "**No healthy class.** DENTEX labels findings only on affected teeth, so the classifier has never seen a healthy "
        "tooth and assigns one of four findings to every detected tooth. Abstention reduces the damage but cannot replace "
        "a real healthy class; on the test image val_0, 18 of 27 regions abstained, and 1,580 of 1,903 detected validation "
        "teeth had no finding label at all.",
        "**Rare-class performance.** Deep Caries (end-to-end recall 0.33 on validation) and Periapical Lesion (4 of 9 "
        "recovered) are weak, and with only 9 validation and 13 test examples of Periapical Lesion the estimates are very "
        "uncertain.",
        "**Crop sensitivity.** Classification depends on the exact crop. About 10 % of predictions change even between "
        "almost identical boxes, and the classifier is weaker on detector crops than on ground-truth crops.",
        "**No independent external validation.** All results come from one public dataset. There are no images from other "
        "clinics, machines or populations, and no patient identifiers, so patient-level separation between splits cannot be "
        "proven. The test split was used historically once per checkpoint, and the uncertainty thresholds are provisional.",
        "**Generative component.** Reports come from deterministic templates; the optional LLM path was not configured or "
        "evaluated, and the Hindi and Marathi wording has not been reviewed by native-speaking dental professionals.",
        "**Deployment.** The system runs on one machine without multi-user authentication or DICOM/PACS integration, and "
        "it is not a medical device.")
    R.h2("8.3", "Future Work")
    R.ps(
        "The first priority is data rather than algorithms. Adding healthy-tooth and “other finding” labels would turn the "
        "classifier into an open-set model that can say “no finding”. Collecting more Deep Caries and Periapical Lesion "
        "examples, ideally with a second annotator to measure agreement, would make the rare-class estimates meaningful.",
        "On the modelling side, the classifier should be trained on detector-style crops or replaced by a detector that "
        "predicts findings directly, as in hierarchical DENTEX methods [@hierdet]. Ensembles or multiple seeds could be used "
        "both to reduce the seed sensitivity observed here and to provide a better uncertainty estimate, and calibration "
        "should be revisited with a larger calibration set. Grad-CAM-style explanations [@selvaraju2017] could show which "
        "part of the crop drove each suggestion.",
        "For validation, the next step is an external, multi-centre test set with patient-level splits, followed by a reader "
        "study in which dentists read radiographs with and without the system. Only after such a study could any claim about "
        "clinical usefulness be made. The language-model wording layer could then be enabled and evaluated with dental "
        "experts, keeping the validator as a hard gate, and the system could be integrated with DICOM and PACS workflows and "
        "proper user authentication.")
    R.h2("8.4", "Applications")
    R.ps(
        "In its current form, DentaMind AI is suited to research and education: as a teaching aid that shows students tooth "
        "numbering and typical findings together with the model’s uncertainty, as a pre-annotation tool that proposes boxes, "
        "numbers and outlines for human annotators to correct, and as a platform for studying how AI suggestions and "
        "uncertainty displays affect human reviewers.",
        "After the future work above and proper clinical validation, the same architecture could support screening "
        "programmes in which many panoramic radiographs must be triaged, structured report drafting that saves typing time "
        "for dentists, and quality-assurance checks that highlight teeth a reader may have missed. In every case the "
        "clinician would remain responsible for the diagnosis.")
