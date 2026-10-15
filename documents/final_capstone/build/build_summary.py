"""Short plain-language project summary: what we built, data, preprocessing, techniques, tech stack, deployment, results.
Numbers come from the same evaluation reports as the full capstone report.
Run with the system Python 3.13:  python documents/final_capstone/build/build_summary.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import docx_lib as dl  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
FIG = BASE / "figures"
J = lambda p: json.loads((ROOT / p).read_text(encoding="utf-8"))

d = dl.Doc()


def h(t):
    d.add(dl.para(t.upper(), "Heading2"))


def p(t):
    d.add(dl.para(t, "BodyNoIndent"))


def tab(caption, header, rows, widths, align=None):
    d.add(dl.para(caption, "TableCaption"))
    d.table(header, rows, widths, font_half_pts=20, align_num=align or set())
    d.add(dl.empty("TableNote"))


def fig(path, caption, w=5.8):
    d.image(path, w)
    d.add(dl.para(caption, "FigureCaption"))


ev = {f"{m}_{s}": J(f"Data/reports/eval_dentex_{m}_v1_{s}.json")["metrics"]
      for m in ["teeth_detection", "teeth_segmentation", "fdi_numbering", "findings_classification"] for s in ["val", "test"]}
e2e = J("Data/reports/end_to_end_validation_evaluation.json")
dv, dt = ev["teeth_detection_val"]["detection"], ev["teeth_detection_test"]["detection"]
sv, st = ev["teeth_segmentation_val"]["segmentation"], ev["teeth_segmentation_test"]["segmentation"]
nv, nt = ev["fdi_numbering_val"]["numbering"]["numbering"], ev["fdi_numbering_test"]["numbering"]["numbering"]
cv, ct = ev["findings_classification_val"]["classification"], ev["findings_classification_test"]["classification"]
f3 = lambda v: f"{v:.3f}"

d.add(dl.para("DentaMind AI: Project Summary", "FrontTitle"))
d.add(dl.para("What we built, which data we used, how we built it, why we chose each part, and what the results are", "BodyNoIndent", align="center"))
d.add(dl.para("Research prototype. Not clinically validated, not for diagnosis.", "BodyNoIndent", align="center", rpr="<w:b/>"))

h("1. What we are building")
p("DentaMind AI looks at a panoramic dental X-ray (the wide image showing all teeth) and helps a dentist review it. For one "
  "X-ray it: (1) finds every tooth, (2) gives each tooth its standard FDI number (11 to 48), (3) draws the outline of each "
  "tooth, (4) suggests the closest of four findings for each tooth: Caries, Deep Caries, Impacted or Periapical Lesion, "
  "(5) marks teeth where the AI is unsure, and (6) writes a draft report in English, Hindi or Marathi. A person must "
  "review everything; the AI never makes the final decision.")
fig(FIG / "screenshot_analysis_gray.png", "The X-ray Analysis page: 27 teeth found, numbered and outlined on test image val_0")

h("2. Dataset")
p("We used the public DENTEX dataset from the MICCAI 2023 challenge. It contains panoramic X-rays labelled in three "
  "levels: some only with the jaw quadrant, some also with tooth numbers, and some also with findings.")
tab("DENTEX in numbers (from our dataset audit)", ["Item", "Count"],
    [["Image files on disk", "3,653"], ["Unique X-rays after removing duplicates", "2,716"], ["Unique X-rays with labels", "1,133"],
     ["X-rays with tooth outlines and numbers", "634 (18,095 teeth)"], ["X-rays with findings", "705 (3,529 findings)"],
     ["Findings: Caries / Deep Caries / Impacted / Periapical Lesion", "2,189 / 578 / 604 / 158"],
     ["Unlabelled X-rays", "1,598"]], [0.65, 0.35], align={1})
p("Two facts about this data shaped the whole project. The classes are imbalanced: Periapical Lesion is only about 7 % of "
  "findings. And DENTEX labels only teeth that have a finding; healthy teeth are never labelled, so our model has no "
  "“healthy” class.")

h("3. Preprocessing")
for t in [
    "**Duplicate removal.** The same X-ray appears in several DENTEX folders (638 groups of copies). We hashed the pixels of "
    "every image and treated identical images as one X-ray. Why: otherwise the same X-ray could end up in both training and "
    "testing, which makes results look better than they are.",
    "**Splitting.** The 1,133 labelled X-rays were split per unique X-ray into train 794, validation 113, calibration 113 and "
    "test 113. Validation is for choosing models, calibration for setting the “unsure” threshold, and test for a final check "
    "only. An automatic check (18 tests) confirms no X-ray is shared between splits; 17 pass, and 1 is an informational warning.",
    "**Image preparation.** Each X-ray is loaded in grayscale and copied into 3 channels, because the pre-trained networks expect "
    "colour images.",
    "**Tooth crops for the finding classifier.** Each tooth box is enlarged by 10 %, cut out, resized to 224 × 224 pixels and "
    "normalised. This gave 2,520 training crops (1,550 / 438 / 412 / 120).",
    "**Augmentation.** Horizontal flips and contrast changes for the classifier. No flips for tooth numbering, because flipping "
    "swaps left and right tooth numbers."]:
    p(t)

h("4. AI techniques and why we chose them")
tab("Models and techniques", ["Part", "Technique", "Why we chose it"],
    [["Find teeth", "Faster R-CNN (ResNet-50 + FPN), pre-trained on COCO", "Proven, accurate two-stage detector; works well with a small dataset through transfer learning"],
     ["Number teeth", "Second Faster R-CNN with 32 FDI classes", "Same reliable detector; matched to found teeth at overlap ≥ 0.5"],
     ["Outline teeth", "Mask R-CNN", "Adds a pixel mask to each detected tooth"],
     ["Suggest finding", "ResNet-50 on tooth crops, pre-trained on ImageNet, class-weighted loss", "Simple, strong image classifier; class weights help the rare classes"],
     ["Know when unsure", "Flip test-time augmentation + normalised entropy; threshold 0.397 chosen on the calibration split", "A classifier always gives an answer; this tells the user when the answer is unreliable"],
     ["Write the report", "Template generator from the model results + automatic validator", "Text can only state what the models found; the validator blocks invented teeth, numbers or diagnosis words"],
     ["Human review", "Confirm / correct / reject, with a second-person approval", "Keeps a person responsible for every finding"]],
    [0.18, 0.4, 0.42])
p("The “generative AI” part is the report writer. We chose fixed templates instead of a chatbot-style language model, because "
  "studies show such models can leave out or invent findings. An optional language-model connection exists in the code but "
  "was not switched on.")

h("5. Technology stack")
tab("Tools we used", ["Layer", "Technology", "Why"],
    [["AI / training", "Python 3.13, PyTorch 2.6, torchvision 0.21, CUDA 12.4", "Standard deep-learning tools with ready Faster/Mask R-CNN and ResNet"],
     ["Backend API", "FastAPI 0.143 + Uvicorn", "Fast, simple Python web API that can call the models directly"],
     ["Database", "SQLite", "No server to install; stores analyses, reports and reviews in one file"],
     ["Frontend", "React 18, Vite 5, Tailwind CSS, Recharts", "Quick, modern web interface with charts"],
     ["Testing", "pytest (233 automated tests)", "Catches mistakes in data handling, reports, security and reviews"],
     ["Hardware", "NVIDIA RTX 3050 laptop GPU, 4 GB", "What we had; it limited batch sizes (1–2 for detectors)"]],
    [0.18, 0.4, 0.42])

h("6. How it is built and deployed")
p("The system runs locally on one computer; it is not hosted on the internet. The backend (FastAPI) starts with "
  "uvicorn on 127.0.0.1:8000 and loads the four trained models onto the GPU. The web interface runs on the Vite server at "
  "localhost:5173. Its proxy forwards requests to the backend and adds a secret API token on the server side, so the token "
  "never reaches the browser. The API listens only on the local address, needs the token and limits request rates. Every "
  "model file is stored with a SHA-256 hash and a description file. A new model is used only after a person approves it with "
  "a validation report, and the switch can be undone. Why this design: it is private (X-rays never leave the machine), "
  "simple to run for a student project, and safe for a prototype that is not ready for real patients.")
p("Speed: one full analysis with the uncertainty checks took 4.4 s for a 2872 × 1504 X-ray on the laptop GPU.")

h("7. Results")
p("“Validation” results come from the split used to choose models (slightly optimistic). “Test” results come from the "
  "held-back test split, which was used only once per model.")
tab("Main results", ["Task", "Metric", "Validation", "Test"],
    [["Find teeth", "Precision / recall", f"{f3(dv['operating_point']['precision'])} / {f3(dv['operating_point']['recall'])}", f"{f3(dt['operating_point']['precision'])} / {f3(dt['operating_point']['recall'])}"],
     ["Outline teeth", "Mask AP50 / Dice", f"{f3(sv['mask_ap50'])} / –", f"{f3(st['mask_ap50'])} / {f3(st['mean_dice_matched'])}"],
     ["Number teeth", "Exact FDI number correct", f"{nv['exact_accuracy_among_matched']:.1%}", f"{nt['exact_accuracy_among_matched']:.1%}"],
     ["Suggest finding", "Accuracy / macro-F1", f"{f3(cv['accuracy'])} / {f3(cv['macro_f1'])}", f"{f3(ct['accuracy'])} / {f3(ct['macro_f1'])}"],
     ["Suggest finding", "Macro precision / recall", f"{f3(cv['macro_precision'])} / {f3(cv['macro_recall'])}", f"{f3(ct['macro_precision'])} / {f3(ct['macro_recall'])}"]],
    [0.22, 0.3, 0.24, 0.24], align={2, 3})
rows = [[c, f"{cv['per_class'][c]['f1']:.2f}", f"{ct['per_class'][c]['f1']:.2f}"] for c in ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]]
tab("Finding F1-score per class", ["Finding", "Validation F1", "Test F1"], rows, [0.4, 0.3, 0.3], align={1, 2})
p("**What this means.** Finding, numbering and outlining teeth work well. Suggesting the finding is the weak part. Impacted "
  "teeth and Caries are recognised well, but Deep Caries is often confused with Caries, and Periapical Lesion has very few "
  f"examples (9 in validation, 13 in test). In the full app the classifier uses the detector’s own boxes. There, macro-F1 on "
  f"validation drops to {e2e['matched@0.5']['B_detector_boxes']['macro_f1']:.3f} on the same teeth and to "
  f"{e2e['end_to_end@0.5']['macro_f1']:.3f} end to end, because small shifts in the box change about 10 % of predictions.")
fig(FIG / "fig_classifier_per_class.png", "Per-class precision, recall and F1 of the finding classifier (validation vs test)", 5.0)
p("**What we tried that did not help.** We tested five fixes for class imbalance (weighted sampler, oversampling, focal "
  "loss, square-root class weights, extra augmentation for rare classes), each with 5 random seeds. None beat the original "
  "model by more than the normal seed-to-seed variation, and most made the rare classes worse, so we kept the original "
  "model. Training on jittered crops and a different training recipe also did not pass our rules.")
p("**Uncertainty works as a warning signal.** On the test split the AI flags 54 % of crops as “needs review”. These flagged "
  "crops contain 87 % of all mistakes: the error rate is 34 % for flagged crops and 6 % for the rest.")

h("8. Main limitations")
for t in ["No “healthy” class: every detected tooth gets one of four findings, so many teeth are shown as “no reliable class candidate”.",
          "Few examples of Deep Caries and Periapical Lesion, so results for these are weak and uncertain.",
          "Tested only on one public dataset; no other clinics or machines, and no patient IDs.",
          "Hindi and Marathi report wording has not been checked by dental professionals. Not clinically validated."]:
    d.add(dl.para("• " + t, "BodyNoIndent", align="left"))



out = BASE / "DentaMind_AI_Project_Summary.docx"
d.save(out, [(0, "main")], "DentaMind AI: Project Summary", "DentaMind AI capstone group")
print("wrote", out)
