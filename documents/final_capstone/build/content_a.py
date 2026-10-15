"""Chapters 1-4 of the capstone report (Introduction, Literature Survey, Requirements, System Design)."""
import docx_lib as dl
from docx_lib import mf, mr, msub, msup, msum, mdel, mtxt, mfunc


def write(R, J, FIG, gray_copy):
    audit = J("Data/reports/dataset_audit.json")
    src = {s["name"]: s for s in audit["sources"]}
    tot = audit["totals"]

    # =====================================================================================================================
    R.ch("Introduction")
    R.h2("1.1", "Overview of Generative AI")
    R.ps(
        "Generative artificial intelligence refers to models that learn the distribution of their training data well enough to "
        "produce new samples from it: sentences, images, audio or structured records. Three families dominate the field. "
        "Generative adversarial networks pit a generator against a discriminator until the generated samples become hard to "
        "distinguish from real ones [@goodfellow2014]. Diffusion models learn to reverse a gradual noising process and now "
        "produce some of the most realistic images available [@ho2020]. Transformer-based language models, built on the "
        "self-attention mechanism [@vaswani2017], are trained to predict the next token of text and, when scaled up, can "
        "follow instructions and write fluent paragraphs from only a few examples [@brown2020].",
        "These capabilities have quickly reached medicine. Report-generation systems describe chest radiographs in sentences, "
        "and general-purpose chat models have been tried for drafting dental radiology reports [@jing2018; @stephan2024]. The "
        "same studies also show the main weakness of generated text in a clinical setting: a fluent sentence is not "
        "necessarily a supported one. A model can omit an important finding, describe something the image does not show, or "
        "word a tentative observation as a diagnosis. Grounding the generation in verified evidence, for example by retrieving "
        "facts before writing [@lewis2020], is therefore as important as the fluency of the output.",
        "Generative techniques are also used inside perception models. The strongest published system on the DENTEX "
        "panoramic X-ray benchmark used in this project treats object detection as a diffusion process that gradually turns "
        "random boxes into tooth and finding boxes [@hierdet]. This project uses generative AI in a deliberately restricted way. "
        "The image-analysis models are discriminative (detection, segmentation and classification networks), and the "
        "generative component is the report generator. It turns the structured output of those models into readable "
        "multilingual draft reports, and it is wrapped in a validator that rejects any statement not backed by the evidence.")
    R.h2("1.2", "Project Background")
    R.ps(
        "A panoramic radiograph, also called an orthopantomogram (OPG), captures both jaws and all teeth in a single image. "
        "It is inexpensive, fast and widely used for screening, treatment planning and follow-up. Reading it, however, "
        "requires the dentist to examine around thirty teeth, number each according to the FDI two-digit notation "
        "standardised in ISO 3950 [@iso3950], and look for findings such as caries, deep caries that approach the pulp, "
        "impacted teeth and periapical lesions at the root tip. The image superimposes structures, contrast varies between "
        "machines, and early lesions are subtle, so findings are easy to miss when a clinician is busy.",
        "Convolutional neural networks (CNNs) have been applied to dental images for almost a decade. A scoping review of 36 "
        "studies found that most CNN applications targeted panoramic and periapical radiographs, and that CNNs often performed "
        "similarly to dentists in research settings, but that their usefulness and generalisability under realistic clinical "
        "conditions had not been shown [@schwendicke2019]. Public data were scarce until the DENTEX challenge at MICCAI 2023 "
        "released hierarchically annotated panoramic radiographs with quadrant, tooth-number and diagnosis labels "
        "[@dentex]. DentaMind AI builds on this dataset.")
    R.h2("1.3", "Motivation")
    R.ps(
        "The motivation for this work came from three observations. First, research prototypes usually solve one sub-task, "
        "such as tooth numbering or caries detection, while a dentist needs all of them in one place, linked to the same tooth. "
        "Second, a classifier always produces an answer, even when it is guessing; without a visible measure of doubt, a "
        "confident-looking label can mislead the reader more than no label at all. Third, many published results are "
        "difficult to trust because the same radiograph may appear in training and test data, or the test split may have "
        "been used repeatedly while developing the model [@kaufman2012; @varoquaux2022].",
        "We therefore set out to build a system that is useful as a whole, honest about its uncertainty, and evaluated in a "
        "way that another team could reproduce. Generative AI is attractive for the last step, turning model output into a "
        "readable report, but only if the text is constrained to what the models actually found.")
    R.h2("1.4", "Problem Statement")
    R.ps(
        "To design, implement and evaluate an AI-assisted panoramic dental X-ray analysis system that, for a given radiograph, "
        "(i) detects and outlines every tooth, (ii) assigns an FDI tooth number, (iii) suggests the closest of four trained "
        "findings (Caries, Deep Caries, Impacted, Periapical Lesion) for each tooth, (iv) quantifies the uncertainty of each "
        "suggestion and abstains when it is too uncertain, and (v) generates a structured, multilingual draft report that "
        "contains only evidence-supported statements and must be reviewed by a qualified person.",
        "The system must be trained and evaluated on public data without leakage between training, validation, calibration "
        "and test radiographs, and any model change must be justified by validation evidence rather than by results on the "
        "test split. The work is constrained by the public DENTEX labels, which contain no healthy-tooth class and no patient "
        "identifiers, and by a single laptop GPU with 4 GB of memory.")
    R.h2("1.5", "Objectives")
    R.p("The objectives of the project, each of which is evaluated later in the report, are as follows.", "BodyNoIndent")
    R.tab("Project objectives", ["No.", "Objective", "Where evaluated"],
          [["O1", "Audit and de-duplicate the DENTEX data and create leakage-free train, validation, calibration and test splits per unique radiograph.", "Sections 3.6, 5.2, 6.1"],
           ["O2", "Train tooth detection, FDI numbering, tooth instance segmentation and finding classification models with transfer learning.", "Sections 5.4, 7.2"],
           ["O3", "Combine the models in a single inference pipeline with flip test-time augmentation, uncertainty flags and abstention.", "Sections 4.3, 7.5"],
           ["O4", "Generate evidence-grounded draft reports in English, Hindi and Marathi and validate every draft automatically.", "Sections 5.3, 6.2, 7.3"],
           ["O5", "Provide a web interface for analysis, reports and human review with an auditable decision trail.", "Sections 5.5, 7.8"],
           ["O6", "Evaluate with precision, recall, F1, AP, Dice and calibration metrics, and test class-imbalance remedies against a pre-registered rule.", "Chapter 7"]],
          [0.08, 0.7, 0.22])
    R.h2("1.6", "Scope of the Work")
    R.ps(
        "The scope covers adult panoramic radiographs from the DENTEX dataset, the four finding classes annotated in that "
        "dataset, and a single-machine deployment in which the API listens only on the loopback address. The system includes "
        "data auditing, model training and evaluation, the inference pipeline, report generation in three languages, a review "
        "workflow and research pages for experiments, active learning and model management.",
        "The following are explicitly out of scope: clinical diagnosis or treatment advice; findings other than the four "
        "trained classes; periapical, bitewing and CBCT images; multi-user authentication for a hospital network; and "
        "integration with DICOM or PACS systems. An interface for an external large language model exists in the code but was "
        "not configured or evaluated, so every report discussed in this document was produced by the deterministic template "
        "generator. DentaMind AI is a research prototype; it has not been clinically validated and is not a medical device.")

    # =====================================================================================================================
    R.ch("Literature Survey")
    R.h2("2.1", "Review of Recent Literature")
    R.ps(
        "Early deep-learning work in dentistry focused on single tasks. Lee et al. trained a GoogLeNet Inception v3 network on "
        "3,000 periapical radiographs to detect dental caries and reported diagnostic accuracies of 89.0 %, 88.0 % and 82.0 % "
        "for the premolar, molar and combined models [@lee2018]. The study showed that transfer learning from natural images "
        "works for dental radiographs, but it handled one finding on cropped periapical films, not whole panoramic images.",
        "Tooth detection and numbering received attention next. Tuzoff et al. combined a Faster R-CNN detector with a "
        "convolutional classifier to detect and number teeth on 1,352 panoramic radiographs [@tuzoff2019], and Chen et al. "
        "used Faster R-CNN on periapical films, adding rule-based post-processing that removes duplicate boxes and corrects "
        "numbers that violate the tooth-numbering system [@chen2019]. Both works treat numbering as a geometric problem and "
        "show that domain rules can repair detector mistakes; neither addresses pathology.",
        "For pathology, Ekert et al. applied deep CNNs to detect apical lesions on panoramic radiographs [@ekert2019]. The "
        "scoping review by Schwendicke et al. summarised 36 studies and pointed out recurring weaknesses: small and private "
        "datasets, a wide range of incomparable metrics, and almost no evaluation of the effect on clinical decisions "
        "[@schwendicke2019]. The DENTEX benchmark was designed to address the data problem. It provides 693 radiographs with "
        "quadrant labels, 634 with quadrant and tooth-number labels, and 705 with quadrant, tooth-number and diagnosis labels "
        "for four findings, together with a pool of unlabelled images [@dentex]. The accompanying HierarchicalDet method "
        "exploits this hierarchy with a diffusion-based detector and was reported to outperform RetinaNet, Faster R-CNN, DETR "
        "and DiffusionDet on the task [@hierdet].")
    R.h2("2.2", "Generative AI: Existing Approaches")
    R.ps(
        "Generative models relevant to medical imaging fall into four groups. Adversarial networks [@goodfellow2014] have been "
        "used for data augmentation and image translation. Diffusion models [@ho2020] produce realistic synthetic images and, "
        "as HierarchicalDet shows, can be adapted to structured prediction such as detection [@hierdet]. Transformer language "
        "models [@vaswani2017; @brown2020] generate text and are the basis of current report-writing assistants. Finally, "
        "retrieval-augmented generation conditions a language model on retrieved documents so that the generated text can be "
        "traced to a source [@lewis2020].",
        "For report generation, two strategies exist. Free generation trains or prompts a model to write the whole report, "
        "which gives natural language but offers no guarantee that each sentence is supported. Structured generation first "
        "extracts facts (findings, positions, scores) with dedicated models and then verbalises them through templates or a "
        "constrained language model. DentaMind AI follows the structured strategy: the evidence is a list of findings with "
        "tooth numbers, scores and uncertainty values, and the text is generated from that list and then checked against it.")
    R.h2("2.3", "Review of Related Generative AI Systems")
    R.ps(
        "Jing et al. proposed a multi-task model that predicts tags, localises abnormal regions with co-attention and writes "
        "long paragraphs with a hierarchical LSTM; it was evaluated on two public chest X-ray datasets [@jing2018]. The "
        "approach produces coherent reports, but its sentences are learned from data and can still describe findings that "
        "are not present.",
        "Closer to our domain, Stephan et al. asked 100 dental students to write panoramic radiograph reports either "
        "manually or with ChatGPT using a standardised prompt [@stephan2024]. The ChatGPT-assisted reports were textually "
        "similar to reference reports and were judged readable and free of errors, but they frequently omitted key diagnostic "
        "details, and the authors called for better prompt design and validation before clinical use. This result supports "
        "the design choice in DentaMind AI to treat the language model, if one is used at all, as a wording layer on top of "
        "verified structured evidence, never as the source of findings.")
    R.h2("2.4", "Existing Solutions / State-of-the-Art Methods")
    R.ps(
        "Two-stage detectors remain a strong baseline for teeth. Faster R-CNN proposes candidate regions with a region "
        "proposal network and then classifies and refines them [@ren2015]; Mask R-CNN adds a branch that predicts a pixel mask "
        "for each instance [@he2017mask]. Both are usually combined with a ResNet backbone [@he2016] and a feature pyramid "
        "network that handles objects of different sizes [@lin2017fpn], and they are initialised from weights pre-trained on "
        "COCO [@lin2014coco]. Image classifiers for crops are typically ImageNet-pre-trained ResNets [@deng2009; @he2016].",
        "Several techniques address problems that matter in this project. Focal loss down-weights easy examples to cope with "
        "imbalance [@lin2017focal], and a systematic study of class imbalance in CNNs found oversampling to be the most "
        "effective of the remedies it compared [@buda2018]. Temperature scaling is a simple and effective method to improve "
        "the calibration of modern neural networks [@guo2017], and test-time augmentation has been used to estimate the "
        "uncertainty of medical image segmentation [@wang2019]. Grad-CAM produces class-specific heat maps for visual "
        "explanation [@selvaraju2017]. Active learning selects the most informative unlabelled samples for annotation "
        "[@settles2009]. Table 2.1 summarises the most relevant works.")
    R.tab("Summary of related work", ["Work", "Task and data", "Method", "Observation relevant to this project"],
          [["Lee et al. [@lee2018]", "Caries, 3,000 periapical radiographs", "GoogLeNet Inception v3, transfer learning", "Single finding; no numbering, uncertainty or report"],
           ["Tuzoff et al. [@tuzoff2019]", "Tooth detection and numbering, 1,352 panoramic radiographs", "Faster R-CNN + CNN classifier", "No pathology"],
           ["Chen et al. [@chen2019]", "Tooth detection and numbering, periapical films", "Faster R-CNN + rule-based post-processing", "Domain rules repair numbering; no pathology"],
           ["Ekert et al. [@ekert2019]", "Apical lesions, panoramic radiographs", "Deep CNN", "Single finding; no human-review loop"],
           ["DENTEX / HierarchicalDet [@dentex; @hierdet]", "Enumeration and diagnosis, panoramic radiographs (public)", "Diffusion-based hierarchical detector", "Benchmark; no calibrated abstention or reporting"],
           ["Jing et al. [@jing2018]", "Report generation, chest X-ray", "Co-attention + hierarchical LSTM", "Fluent text, not verified against evidence"],
           ["Stephan et al. [@stephan2024]", "OPG reports, 100 dental students", "ChatGPT with a standard prompt", "Readable but omitted key diagnostic details"],
           ["This project", "DENTEX, four findings + teeth", "Faster/Mask R-CNN, ResNet-50, template + validator", "Integrated pipeline, abstention, review trail, leakage audit"]],
          [0.2, 0.25, 0.25, 0.3], font=19)
    R.h2("2.5", "Gap Identification")
    R.ps(
        "Reading the literature against the needs of a practical assistant reveals five gaps. The first is integration: "
        "detection, numbering, segmentation and finding classification are usually reported separately, and few works show "
        "how errors of one stage affect the next. The second is uncertainty. A closed-set classifier always returns one of its "
        "classes, and DENTEX labels findings only on affected teeth, so a classifier trained on it has never seen a healthy "
        "tooth. Without abstention, such a classifier will label every healthy tooth with a finding.",
        "The third gap is faithful generation. Free-text generation, whether learned or prompted, can omit or invent findings "
        "[@stephan2024], so generated reports need an automatic check against the evidence. The fourth is evaluation hygiene. "
        "Duplicates across dataset folders, repeated use of a test split and selection on the reporting split are common "
        "sources of optimistic results in medical imaging [@kaufman2012; @varoquaux2022]. The fifth is class imbalance. Rare "
        "findings such as periapical lesions are often hidden behind accuracy figures dominated by frequent classes.")
    R.h2("2.6", "Common Findings from Literature")
    R.ps(
        "Across the surveyed work, tooth detection and numbering reach high accuracy with standard two-stage detectors and "
        "transfer learning, so the main difficulty lies in finding-level classification, especially for rare and visually "
        "subtle findings. Reported numbers are hard to compare because datasets, image types and metrics differ "
        "[@schwendicke2019]. Generated reports read well but need explicit grounding and human review. Finally, the "
        "literature agrees that external validation on independent data is required before any clinical claim, a requirement "
        "that this project, like most academic prototypes, does not yet meet.")

    # =====================================================================================================================
    R.ch("Requirements Specification")
    R.h2("3.1", "Hardware Requirements")
    R.p("All development, training and evaluation in this project was performed on a single laptop. Table 3.1 lists the "
        "configuration that was used, which is also the minimum we can vouch for.")
    R.tab("Hardware used for training, evaluation and deployment", ["Component", "Specification used", "Purpose"],
          [["GPU", "NVIDIA GeForce RTX 3050 Laptop GPU, 4 GB, CUDA 12.4", "Training and inference of all four models"],
           ["Operating system", "Windows 11 (64-bit)", "Development and local deployment"],
           ["Storage", "Local disk (dataset, checkpoints, SQLite database, reports)", "DENTEX images (3,653 PNG files) and model files"],
           ["Display / browser", "Any modern browser on the same machine", "Web interface on localhost"]],
          [0.2, 0.45, 0.35],
          note="With 4 GB of GPU memory only one GPU job can run at a time; the API must be stopped before training because it keeps the models loaded.")
    R.h2("3.2", "Software Requirements")
    R.tab("Software stack and versions", ["Layer", "Software (version)", "Role"],
          [["Language", "Python 3.13", "Backend, training and evaluation scripts"],
           ["Deep learning", "PyTorch 2.6.0 + torchvision 0.21.0 (CUDA 12.4)", "Faster R-CNN, Mask R-CNN, ResNet-50 [@paszke2019]"],
           ["Numerics / images", "NumPy 2.5.4, Pillow 12.3.0", "Image loading, hashing, crops, metrics"],
           ["Web API", "FastAPI 0.143.0, Uvicorn 0.54.0", "REST API with token authentication and rate limits"],
           ["Database", "SQLite", "Analyses, reports, reviews, jobs, experiments, promotions"],
           ["Frontend", "React 18.3, React Router 6.26, Vite 5, Tailwind CSS, Recharts 2.12, lucide-react", "Single-page web interface"],
           ["Testing", "pytest", "233 automated tests"]],
          [0.2, 0.45, 0.35])
    R.h2("3.3", "Functional Requirements")
    R.tab("Functional requirements", ["ID", "Requirement"],
          [["FR-1", "The user can upload a panoramic radiograph (PNG or JPEG, up to 25 MB) or choose an existing test image."],
           ["FR-2", "The system detects every tooth and shows its box, outline and FDI number on the image."],
           ["FR-3", "For every detected tooth the system shows the closest of four trained findings with its raw score, or states that no reliable class candidate exists."],
           ["FR-4", "The system flags regions for review separately by cause: weak detection, unstable outline, class unstable under flip, missing number and abstention."],
           ["FR-5", "The user can generate a draft report in English, Hindi or Marathi; every draft is validated against the evidence before it is stored."],
           ["FR-6", "A reviewer can confirm, correct or reject a finding, set or clear a tooth number, or mark the image for specialist review or as unusable; every decision is stored as a revision."],
           ["FR-7", "A second person approves or rejects review decisions; only approved decisions can be exported or used for training."],
           ["FR-8", "Research pages show dataset statistics, the leakage audit, experiments, active learning and the model registry; promotion of a model requires a validation report and a justification."]],
          [0.12, 0.88])
    R.h2("3.4", "Non-Functional Requirements")
    R.tab("Non-functional requirements", ["Category", "Requirement and how it is met"],
          [["Safety and honesty", "Every screen and report states that the output is a research draft, not a diagnosis. Scores are labelled as raw model scores, not probabilities of disease."],
           ["Security", "The API binds to 127.0.0.1, requires a token (injected by the development proxy, never sent to the browser), limits request rates and validates uploads and paths."],
           ["Reproducibility", "Checkpoints carry SHA-256 hashes and JSON sidecars; new checkpoints get a training manifest with data and code hashes; evaluation reports record the software versions and the dataset fingerprint."],
           ["Research integrity", "Splits are made per unique radiograph; 18 leakage checks run automatically; the test split is gated by a hash-chained ledger and is never used for selection."],
           ["Performance", "A full analysis with flip test-time augmentation of a 2872 × 1504 radiograph took 4.4 s on the RTX 3050 laptop GPU."],
           ["Usability", "Responsive interface, keyboard-accessible region table, separate warning chips per cause, and reports in three languages."]],
          [0.22, 0.78])
    R.h2("3.5", "Generative AI Model Requirements")
    R.ps(
        "The report generator must satisfy four requirements. It must use only the structured evidence of an analysis "
        "(findings with identifiers, FDI numbers, class names, scores and uncertainty values). It must never introduce a "
        "tooth number, a numeric value or a finding name that is not in that evidence. It must avoid clinical directives "
        "such as treatment recommendations or definitive diagnostic statements. Finally, it must produce the same content in "
        "English, Hindi and Marathi, so that only the language changes, never the findings or values.",
        "The default generator is deterministic and template-based, which satisfies these requirements by construction. "
        "The optional language-model path must call an OpenAI-compatible endpoint with temperature 0 and a JSON response "
        "format, send only a de-identified evidence payload, and fall back to the template if the output fails validation. "
        "This optional path is implemented and unit-tested with an injected transport, but no external model was configured "
        "during this project, so no claim is made about the quality of language-model wording.")
    R.h2("3.6", "Dataset / Knowledge-Base Requirements")
    R.ps(
        "The models require panoramic radiographs with tooth-level boxes and polygons, FDI numbers and finding labels. The "
        f"DENTEX release on disk contains {tot['images_on_disk']:,} PNG files in five folders. A pixel-hash audit found "
        f"{audit['duplicates']['groups_with_multiple_files']} groups of files that contain the same radiograph, reducing the "
        f"collection to {audit['duplicates']['unique_radiographs']:,} unique radiographs, of which "
        f"{tot['annotated_distinct_radiographs']:,} carry annotations. The same film often appears in several sub-sets, and "
        f"{audit['duplicates']['same_file_name_different_pixels']} file names are reused for different images, so neither "
        "file names nor folder membership can be used to split the data. Table 3.5 summarises the sub-sets, and Fig. 3.1 "
        "and Fig. 3.2 show the file counts and the label distribution.")
    q, qe, qed, ul, vd = (src["training_data/quadrant"], src["training_data/quadrant_enumeration"], src["training_data/quadrant-enumeration-disease"],
                          src["training_data/unlabelled"], src["validation_data/quadrant_enumeration_disease"])
    R.tab("DENTEX sub-sets as found on disk", ["Sub-set", "Files", "Annotations", "Labels", "Used for"],
          [["training_data/quadrant", f"{q['n_images']}", f"{q['n_annotations']:,} quadrant boxes", "Quadrant 1-4", "Audit only (no tooth labels)"],
           ["training_data/quadrant_enumeration", f"{qe['n_images']}", f"{qe['n_annotations']:,} tooth polygons", "Quadrant + tooth 1-8 (FDI)", "Detection, numbering, segmentation"],
           ["training_data/quadrant-enumeration-disease", f"{qed['n_images']}", f"{qed['n_annotations']:,} finding boxes", "FDI + 4 findings", "Finding classification"],
           ["training_data/unlabelled", f"{ul['n_images']:,}", "none", "none", "Active-learning pool"],
           ["validation_data/quadrant_enumeration_disease", f"{vd['n_images']}", "none (labels not released)", "none", "Demo images only"]],
          [0.42, 0.07, 0.17, 0.16, 0.18], font=18,
          note="Counts are read from Data/reports/dataset_audit.json. The finding labels in the disease sub-set are Caries 2,189, Deep Caries 578, Impacted 604 and Periapical Lesion 158. No sub-set labels healthy teeth, and no patient identifiers are provided.")
    R.fig(FIG / "fig_dataset_sources.png", "Image files per DENTEX sub-set (bars) and the effect of de-duplication (title)", 5.6)
    R.fig(FIG / "fig_class_distribution.png", "Finding labels in the disease sub-set and the classifier crops per split", 5.6)

    # =====================================================================================================================
    R.ch("System Design")
    R.h2("4.1", "Proposed System Architecture")
    R.ps(
        "DentaMind AI follows a three-tier architecture, shown in Fig. 4.1. The client tier is a React single-page "
        "application with pages for X-ray analysis, reports and review, plus research pages that can be switched on in the "
        "settings. Requests pass through the Vite development proxy, which adds the API token on the server side so that it "
        "never reaches the browser, to a FastAPI application that listens only on 127.0.0.1. The application tier contains "
        "the analysis pipeline service, the report service and the review and registry services. The machine-learning core is "
        "a Python package (dentexmodel) with the four networks and the uncertainty measures. All state is kept on the local "
        "disk: an SQLite database for analyses, reports and reviews, the checkpoint folder with hashes and sidecars, the "
        "DENTEX images with the split manifest, and the evaluation reports with the test-set ledger.",
        "The design keeps three boundaries explicit. Trained networks (grey boxes in the figure) are separated from ordinary "
        "code, so the deterministic logic around them can be unit-tested. The report generator reads only stored evidence and "
        "never the image, so a report cannot contain anything the pipeline did not produce. Model promotion is a recorded "
        "human decision, not an automatic side effect of training.")
    R.fig(FIG / "diagram_architecture.png", "Overall system architecture of DentaMind AI", 4.15, rotate=True)
    R.h2("4.2", "System Block Diagram")
    R.ps(
        "Fig. 4.2 shows the inference pipeline as a block diagram, in the order implemented in the pipeline service. The input "
        "radiograph is loaded in grayscale and replicated to three channels so that it matches the ImageNet and COCO "
        "pre-trained backbones. The detector proposes tooth boxes with a score of at least 0.3. The numbering detector, "
        "trained with 32 FDI classes, runs on the same image and its boxes are matched to the detected teeth at an IoU of at "
        "least 0.5; unmatched teeth stay unnumbered. The segmentation network predicts an outline for each tooth, again "
        "matched by overlap. Each detected box is then cropped with 10 % padding, resized to 224 × 224 pixels, normalised with "
        "ImageNet statistics and classified by the ResNet-50 into the four findings.",
        "Uncertainty is estimated by repeating the classification, detection and segmentation on the horizontally flipped "
        "image. The normalised entropy of the classifier output and the Jensen–Shannon divergence between the original and "
        "flipped predictions are computed for each tooth, together with the outline and box instability. The flags and the "
        "abstention rule are applied, and the structured result is stored. The report generator later turns the stored "
        "evidence into a draft, which a person reviews.")
    R.fig(FIG / "diagram_inference_pipeline.png", "Block diagram of the AI inference pipeline", 4.15, rotate=True)
    R.h2("4.3", "System Workflow")
    R.ps(
        "Two workflows surround the inference pipeline. The training and evaluation workflow in Fig. 4.3 starts from the raw "
        "archives. The dataset audit hashes every image, groups identical films and records their sub-sets. The annotated "
        "unique radiographs are then split into train (794), validation (113), calibration (113) and test (113) sets, and the "
        "leakage checker verifies the result before any training starts. Each split has one purpose. Training uses the train "
        "split. Epoch selection and all model comparisons use the validation split. The uncertainty thresholds are chosen on "
        "the calibration split. The test split is evaluated at most once per checkpoint, every use is appended to a "
        "hash-chained ledger, and its results are never used to choose a model, a threshold or a promotion.",
        "The human-review workflow in Fig. 4.4 starts from the per-region output. Regions with any flag go to the "
        "“needs review” group, but regions without flags remain open to review as well. A reviewer can confirm the candidate "
        "class, correct it, reject it, set or clear the tooth number, or mark the whole image for specialist review or as "
        "unusable. Each decision is stored as a new revision that keeps the previous model output, records the reviewer and "
        "a self-declared qualification, and refuses identical resubmissions. A second person approves or rejects the "
        "decision. Approved decisions mark the report as reviewed, and they can become training data only if the image is "
        "unassigned and is not a copy of any labelled radiograph, so reviewed images cannot leak into validation or test "
        "data. The clinician, not the software, remains responsible for any diagnosis.")
    R.fig(FIG / "diagram_training_evaluation.png", "Training and evaluation workflow with split roles", 4.15, rotate=True)
    R.fig(FIG / "diagram_human_review.png", "Human-review workflow for AI findings", 4.15, rotate=True)
    R.h2("4.4", "Mathematical Model")
    R.p("This section defines the quantities used by the system and in the evaluation; symbols are listed in the nomenclature.")
    R.h3("4.4.1", "Detection and Overlap Measures")
    R.p("A predicted region A and a ground-truth region B are compared with the intersection over union, and two masks are "
        f"also compared with the Dice coefficient (Eq. {R.next_eq()}):")
    R.eq(mtxt("IoU") + mr("=") + mf(mr("|A∩B|"), mr("|A∪B|")) + mr(",   ") + mtxt("Dice") + mr("=") + mf(mr("2|A∩B|"), mr("|A|+|B|")))
    R.p("A prediction counts as a true positive if it matches an unmatched ground-truth region with IoU ≥ 0.5 (greedy "
        "one-to-one matching by score). Precision, recall and the F1-score then follow:")
    R.eq(mi_prf())
    R.p("Average precision (AP) is the area under the precision–recall curve of one class at a fixed IoU threshold; AP50 "
        "uses IoU 0.5, and mAP averages AP over IoU thresholds from 0.5 to 0.95 in steps of 0.05, as in the COCO protocol "
        "[@lin2014coco].")
    R.h3("4.4.2", "Classification and Macro-Averaged Metrics")
    R.p("For K = 4 classes, the per-class precision, recall and F1 are computed one class against the rest, and the macro "
        "average gives every class the same weight regardless of its frequency:")
    R.eq(msub(mtxt("F1"), mtxt("macro")) + mr("=") + mf(mr("1"), mr("K")) + msum(mr("k=1"), mr("K"), msub(mtxt("F1"), mr("k"))))
    R.p("Macro-F1 is the primary metric for the classifier because accuracy is dominated by the Caries class, which makes "
        "up 62 % of the validation crops.")
    R.h3("4.4.3", "Uncertainty Measures")
    R.p("Let p = (p~1~, …, p~K~) be the softmax output for a crop and q the output for its horizontally flipped copy. The "
        "normalised entropy and the flip disagreement are")
    R.eq(msub(mr("H"), mr("n")) + mdel(mr("p")) + mr("=−") + mf(mr("1"), mfunc("log", mr("K"))) + msum(mr("k=1"), mr("K"), msub(mr("p"), mr("k")) + mfunc("log", msub(mr("p"), mr("k")))))
    R.eq(msub(mr("D"), mtxt("JS")) + mdel(mr("p,q")) + mr("=") + mf(mr("1"), mfunc("log", mr("2"))) + mdel(
        msub(mr("H"), mr("e")) + mdel(mf(mr("p+q"), mr("2"))) + mr("−") + mf(msub(mr("H"), mr("e")) + mdel(mr("p")) + mr("+") + msub(mr("H"), mr("e")) + mdel(mr("q")), mr("2")), "[", "]"))
    R.p("where H~e~ is the Shannon entropy in natural logarithms. A region is shown as “no reliable class candidate” when "
        "H~n~ ≥ 0.3966 and is flagged as unstable under flip when D~JS~ ≥ 0.0762. Both thresholds maximise Youden’s index "
        "[@youden1950] for detecting classifier errors on the calibration split:")
    R.eq(mr("J") + mr("=") + mtxt("sensitivity") + mr("+") + mtxt("specificity") + mr("−1"))
    R.h3("4.4.4", "Calibration")
    R.p("Calibration is measured by the expected calibration error over M = 10 equal-width confidence bins B~m~ [@guo2017], and "
        "temperature scaling divides the logits z by a scalar T fitted on the calibration split:")
    R.eq(mtxt("ECE") + mr("=") + msum(mr("m=1"), mr("M"), mf(mr("|") + msub(mr("B"), mr("m")) + mr("|"), mr("N")) + mdel(
        mtxt("acc") + mdel(msub(mr("B"), mr("m"))) + mr("−") + mtxt("conf") + mdel(msub(mr("B"), mr("m"))), "|", "|")) + mr(",   ") +
        msub(mover_p(), mr("k")) + mr("=") + mf(msup(mr("e"), msub(mr("z"), mr("k")) + mr("/T")), msum(mr("j"), None, msup(mr("e"), msub(mr("z"), mr("j")) + mr("/T")))))
    R.h3("4.4.5", "Training Objectives")
    R.p("The detection and segmentation networks minimise the standard multi-task losses of Faster R-CNN and Mask R-CNN, "
        "the sum of the region-proposal, classification, box-regression and (for Mask R-CNN) mask terms [@ren2015; @he2017mask]. "
        "The classifier minimises a class-weighted cross-entropy with inverse-frequency weights over the N training crops, and "
        "the focal loss with focusing parameter γ [@lin2017focal] was evaluated as an alternative:")
    R.eq(msub(mr("w"), mr("c")) + mr("=") + mf(mr("N"), mr("K") + msub(mr("n"), mr("c"))) + mr(",   ") + msub(mtxt("L"), mtxt("FL")) + mr("=−") +
         msup(mdel(mr("1−") + msub(mr("p"), mr("t"))), mr("γ")) + mfunc("log", msub(mr("p"), mr("t"))))
    R.p("With the 2,520 training crops described in Section 5.2, the weights are 0.41 for Caries, 1.44 for Deep Caries, 1.53 "
        "for Impacted and 5.25 for Periapical Lesion. The experiment trainer used in Section 7.6 caps the weights at 5.")


def mi_prf():
    return (mtxt("P") + mr("=") + mf(mtxt("TP"), mtxt("TP") + mr("+") + mtxt("FP")) + mr(",   ") +
            mtxt("R") + mr("=") + mf(mtxt("TP"), mtxt("TP") + mr("+") + mtxt("FN")) + mr(",   ") +
            mtxt("F1") + mr("=") + mf(mr("2") + mtxt("PR"), mtxt("P") + mr("+") + mtxt("R")))


def mover_p():
    return f'<m:acc><m:accPr><m:chr m:val="̂"/></m:accPr><m:e>{mr("p")}</m:e></m:acc>'
