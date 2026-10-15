"""Builds documents/final_capstone/DentaMind_AI_Capstone_Report.docx (Word then updates fields and exports the PDF).

All numbers in tables are read from the project's evaluation reports at build time; narrative numbers were transcribed from
the same reports. Citations are written as [@key] and numbered in order of first appearance (IEEE style).
Run with the system Python 3.13 (Pillow):  python documents/final_capstone/build/build_report.py
"""
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).parent))
import docx_lib as dl  # noqa: E402
from references import REFS  # noqa: E402

BUILD = Path(__file__).resolve().parent
BASE = BUILD.parent                      # documents/final_capstone
ROOT = BASE.parents[1]                   # project root
FIG = BASE / "figures"
TITLE = "DentaMind AI: AI-Assisted Dental X-ray Analysis System"


def J(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


class Report:
    def __init__(self):
        self.d = dl.Doc()
        self.cite_order = []
        self.chapter = 0
        self.n_fig = 0
        self.n_tab = 0
        self.n_eq = 0
        self.figs, self.tabs = [], []
        self.sections = []

    # ----- citations -----
    def _cite(self, text):
        def rep(m):
            keys = [k.strip().lstrip("@") for k in m.group(1).split(";")]
            nums = []
            for k in keys:
                if k not in REFS:
                    raise KeyError(f"unknown reference key {k}")
                if k not in self.cite_order:
                    self.cite_order.append(k)
                nums.append(self.cite_order.index(k) + 1)
            return ", ".join(f"[{n}]" for n in nums)
        return re.sub(r"\[(@[^\]]+)\]", rep, text)

    # ----- structure -----
    def section(self, kind):
        self.sections.append((len(self.d.body), kind))

    def front_title(self, text, new_page=True):
        # pageBreakBefore instead of a separate break paragraph (a break paragraph after a TOC field produced an empty page)
        self.d.add(dl.para(text, "FrontTitle", extra_ppr="<w:pageBreakBefore/>" if new_page else ""))

    def ch(self, title):
        self.chapter += 1
        self.n_fig = self.n_tab = self.n_eq = 0
        # chapter 1 already starts on a new page through the section break
        self.d.add(dl.para(f"CHAPTER {self.chapter}", "ChapterLabel", extra_ppr='<w:pageBreakBefore w:val="0"/>' if self.chapter == 1 else ""))
        self.d.add(dl.para(f"{self.chapter}. {title.upper()}", "Heading1"))

    def h1_plain(self, title):
        """Heading-1 entry without a chapter number (References, Appendices) on a new page."""
        self.d.add(dl.para(title.upper(), "Heading1", extra_ppr="<w:pageBreakBefore/>"))

    def h2(self, num, title):
        self.d.add(dl.para(f"{num} {title.upper()}", "Heading2"))

    def h3(self, num, title):
        self.d.add(dl.para(f"{num} {title}", "Heading3"))

    def p(self, text, style=None):
        self.d.add(dl.para(self._cite(text), style))

    def ps(self, *texts):
        for t in texts:
            self.p(t)

    def fig(self, path, caption, width_in=5.6, legend=None, rotate=False):
        """rotate=True: wide diagrams are turned 90 degrees and given a page of their own so that their text stays legible."""
        self.n_fig += 1
        num = f"{self.chapter}.{self.n_fig}"
        width_in = min(width_in, 5.8)                 # never wider than the text block (149.6 mm = 5.89 in)
        if rotate:
            src = Path(path)
            path = FIG / f"{src.stem}_rotated.png"
            with Image.open(src) as im:
                im.rotate(90, expand=True).save(path)
            self.d.add(dl.para("", "Figure", extra_ppr="<w:pageBreakBefore/>"))
        self.d.image(path, width_in)
        self.d.add(dl.para(f"Fig. {num} {self._cite(caption)}", "FigureCaption"))
        if legend:
            self.d.add(dl.para(self._cite(legend), "TableNote", align="center"))
        self.figs.append((num, caption))
        return num

    def next_fig(self):
        return f"{self.chapter}.{self.n_fig + 1}"

    def next_tab(self):
        return f"{self.chapter}.{self.n_tab + 1}"

    def tab(self, caption, header, rows, widths, note=None, align_num=None, font=20, bold_first_col=False):
        self.n_tab += 1
        num = f"{self.chapter}.{self.n_tab}"
        self.d.add(dl.para(f"Table {num} {self._cite(caption)}", "TableCaption"))
        rows = [[self._cite(str(c)) for c in r] for r in rows]
        self.d.table(header, rows, widths, font_half_pts=font, align_num=align_num, bold_first_col=bold_first_col)
        self.d.add(dl.para(self._cite(note), "TableNote") if note else dl.empty("TableNote"))
        self.tabs.append((num, caption))
        return num

    def eq(self, omml):
        self.n_eq += 1
        num = f"{self.chapter}.{self.n_eq}"
        self.d.add(dl.equation(omml, num))
        return num

    def next_eq(self):
        return f"{self.chapter}.{self.n_eq + 1}"


def gray_copy(src, name):
    """The college format asks for black-and-white illustrations: screenshots are converted to grayscale copies."""
    out = FIG / name
    with Image.open(ROOT / src) as im:
        ImageOps.grayscale(im).save(out)
    return out


def front_matter(R):
    d = R.d
    # ---------------- cover ----------------
    R.section("cover")
    for _ in range(2):
        d.add(dl.empty("Cover"))
    cover = [("GROUP ID: __________", 24), ("A PROJECT REPORT ON", 24), ("", 24),
             (TITLE.upper(), 32), ("", 24),
             ("SUBMITTED TO THE PIMPRI CHINCHWAD COLLEGE OF ENGINEERING", 24), ("AN AUTONOMOUS INSTITUTE, PUNE", 24),
             ("IN THE FULFILLMENT OF THE REQUIREMENTS", 24), ("FOR THE AWARD OF THE DEGREE", 24), ("OF", 24),
             ("B. TECH. IN COMPUTER SCIENCE AND ENGINEERING (AI & ML)", 24), ("FOR THE SUBJECT", 24),
             ("GENERATIVE AI MDM CAPSTONE PROJECT", 24), ("UNDER THE DEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING (AI & ML)", 24),
             ("", 24), ("SUBMITTED BY", 24)]
    for t, sz in cover:
        d.add(dl.para(t, "Cover", rpr=f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>') if t else dl.empty("Cover"))
    for _ in range(4):
        d.add(dl.para("STUDENT NAME ____________________    PRN: __________", "Cover"))
    for t in ["", "UNDER THE GUIDANCE OF", "PROF. ____________________ (GUIDE NAME)", "", "",
              "DEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING (AI & ML)",
              "PCET’S PIMPRI CHINCHWAD COLLEGE OF ENGINEERING",
              "Sector No. 26, Pradhikaran, Nigdi, Pimpri-Chinchwad, PUNE – 411044", "2026-2027"]:
        d.add(dl.para(t, "Cover") if t else dl.empty("Cover"))

    # ---------------- certificate (front section, Roman numbering starts) ----------------
    R.section("front")          # the section break itself starts a new page
    for t in ["PCET’S PIMPRI CHINCHWAD COLLEGE OF ENGINEERING", "Sector No. 26, Pradhikaran, Nigdi, Pimpri-Chinchwad, PUNE 411044", "2026-2027"]:
        d.add(dl.para(t, "Cover"))
    d.add(dl.empty("Cover"))
    d.add(dl.para("CERTIFICATE", "FrontTitle"))
    d.add(dl.para("This is to certify that the project report entitled", "BodyNoIndent", align="center"))
    d.add(dl.para(f"“{TITLE.upper()}”", "Cover"))
    d.add(dl.para("Submitted by", "BodyNoIndent", align="center"))
    for _ in range(4):
        d.add(dl.para("STUDENT NAME ____________________    PRN: __________", "Cover"))
    d.add(dl.empty("Cover"))
    d.add(dl.para("are bonafide students of this institute and the work has been carried out by them under the supervision of "
                  "Prof. ____________________ and it is approved for the partial fulfillment of the requirement of Pimpri Chinchwad "
                  "College of Engineering, an autonomous institute, for the award of the B. Tech. degree in Computer Science and "
                  "Engineering (AI & ML).", "BodyNoIndent"))
    for _ in range(2):
        d.add(dl.empty("BodyNoIndent"))
    tabs = f'<w:tabs><w:tab w:val="right" w:pos="{dl.TEXT_W}"/></w:tabs>'
    for line in ["(Prof. ____________________)\t(Prof. Dr. Anuradha Thakare)", "Guide\tHead,",
                 "Department of CSE (AI & ML)\tDepartment of CSE (AI & ML)"]:
        d.add(dl.para(line.replace("\t", "\u0009"), "BodyNoIndent", extra_ppr=tabs).replace(
            '<w:t xml:space="preserve">', '<w:t xml:space="preserve">', 1).replace("\u0009", '</w:t></w:r><w:r><w:tab/></w:r><w:r><w:t xml:space="preserve">'))
    d.add(dl.empty("BodyNoIndent"))
    d.add(dl.para("Place: Pune", "BodyNoIndent"))
    d.add(dl.para("Date: ____________", "BodyNoIndent"))

    # ---------------- acknowledgement ----------------
    R.front_title("ACKNOWLEDGEMENT")
    R.ps(
        "We express our sincere gratitude to our project guide, Prof. ____________________, for steady guidance, critical "
        "questions and patient reviews throughout this capstone project. The habit of asking “how do we know this number is "
        "true?” shaped the way the evaluation in this report was designed.",
        "We thank Prof. Dr. Anuradha Thakare, Head of the Department of Computer Science and Engineering (AI & ML), and the "
        "faculty and staff of Pimpri Chinchwad College of Engineering for the academic environment, laboratory access and "
        "encouragement that made this work possible.",
        "We acknowledge the organisers of the DENTEX challenge for releasing a public, hierarchically annotated panoramic X-ray "
        "dataset, and the developers of PyTorch, torchvision, FastAPI and React, whose open-source software this project is "
        "built on.",
        "Finally, we thank our families and friends for their support and patience during the long training runs and evaluations.")
    d.add(dl.empty("BodyNoIndent"))
    d.add(dl.para("Student names: ____________________", "BodyNoIndent", align="right"))

    # ---------------- abstract ----------------
    R.front_title("ABSTRACT")
    R.ps(
        "Panoramic dental radiographs are among the most frequently acquired images in dentistry, yet reading them is slow and "
        "subtle findings are easily overlooked. This project presents DentaMind AI, a locally deployed research prototype that "
        "analyses a panoramic X-ray end to end. A Faster R-CNN detector locates every tooth, a second Faster R-CNN assigns FDI "
        "tooth numbers, a Mask R-CNN outlines each tooth, and a ResNet-50 classifier suggests the closest of four findings "
        "(Caries, Deep Caries, Impacted and Periapical Lesion) for every detected tooth. Horizontal-flip test-time augmentation "
        "and normalised predictive entropy provide an uncertainty signal; regions above a threshold chosen on a held-out "
        "calibration split are shown as “no reliable class candidate” and routed to a human reviewer. The generative component "
        "converts the structured model evidence into draft reports in English, Hindi and Marathi. Every draft is checked by an "
        "automatic validator that rejects unsupported tooth numbers, numbers, finding names and clinical phrases, and the system "
        "keeps a revisioned, second-person-approved review trail.",
        "The models were trained on the public DENTEX dataset after a pixel-hash audit reduced 3,653 files to 2,716 unique "
        "radiographs and the 1,133 annotated films were split per unique radiograph into train (794), validation (113), "
        "calibration (113) and test (113) sets. On the validation split, tooth detection reached precision 0.962 and recall "
        "0.984 (AP50 0.978), FDI numbering was exactly correct for 93.6 % of matched teeth, and finding classification on "
        "ground-truth tooth boxes reached accuracy 0.825 and macro-F1 0.718. When the classifier receives the detector’s own "
        "crops, macro-F1 falls to 0.649 on the same 323 teeth and to 0.634 end to end, mainly because of the rare Deep Caries "
        "and Periapical Lesion classes. On the historical test split, which was used once per checkpoint and is logged in a "
        "hash-chained ledger, detection recall was 0.974, segmentation Dice 0.873 and classification macro-F1 0.646.",
        "Five class-imbalance remedies (weighted sampling, oversampling, focal loss, square-root class weights and "
        "minority-only augmentation) were compared under a pre-registered rule across five seeds; none produced a gain beyond "
        "seed-to-seed variation without reducing minority-class recall, so none was promoted. The main limitations are the "
        "absence of a healthy-tooth class, low rare-class performance, sensitivity to crop placement and the lack of independent "
        "external validation. DentaMind AI is a research prototype and has not been clinically validated.")
    R.p("**Keywords:** panoramic radiograph, dental AI, tooth detection, FDI numbering, Mask R-CNN, uncertainty estimation, "
        "report generation, human-in-the-loop, data leakage, class imbalance.", "BodyNoIndent")

    # ---------------- TOC + lists ----------------
    R.front_title("TABLE OF CONTENTS")
    d.add(dl.toc_paragraph('TOC \\o "1-3" \\h \\z \\u'))
    R.front_title("LIST OF FIGURES")
    d.add(dl.toc_paragraph('TOC \\h \\z \\t "Figure Caption,1"'))
    R.front_title("LIST OF TABLES")
    d.add(dl.toc_paragraph('TOC \\h \\z \\t "Table Caption,1"'))

    R.front_title("LIST OF ABBREVIATIONS")
    abbr = [("AI", "Artificial Intelligence"), ("AMP", "Automatic Mixed Precision"), ("AP / AP50", "Average Precision / AP at IoU 0.5"),
            ("API", "Application Programming Interface"), ("AUROC", "Area Under the ROC Curve"), ("CNN", "Convolutional Neural Network"),
            ("CUDA", "Compute Unified Device Architecture (NVIDIA)"), ("DENTEX", "Dental Enumeration and Diagnosis Benchmark (MICCAI 2023)"),
            ("ECE", "Expected Calibration Error"), ("FDI", "Fédération Dentaire Internationale (two-digit tooth notation, ISO 3950)"),
            ("FN / FP / TP", "False Negative / False Positive / True Positive"), ("FPN", "Feature Pyramid Network"),
            ("GPU", "Graphics Processing Unit"), ("IoU", "Intersection over Union"), ("JSON", "JavaScript Object Notation"),
            ("LLM", "Large Language Model"), ("mAP", "mean Average Precision (IoU 0.5 to 0.95)"),
            ("MICCAI", "Medical Image Computing and Computer-Assisted Intervention"), ("OPG", "Orthopantomogram (panoramic radiograph)"),
            ("R-CNN", "Region-based Convolutional Neural Network"), ("REST", "Representational State Transfer"),
            ("ROC", "Receiver Operating Characteristic"), ("SD", "Standard Deviation"), ("SHA-256", "Secure Hash Algorithm, 256-bit"),
            ("TTA", "Test-Time Augmentation"), ("UI", "User Interface")]
    d.table(["ABBREVIATION", "ILLUSTRATION"], [list(a) for a in abbr], [0.3, 0.7])

    R.front_title("NOMENCLATURE")
    sym = [("TP, FP, FN", "True positives, false positives and false negatives at a stated IoU threshold"),
           ("P, R, F1", "Precision, recall and F1-score"), ("K", "Number of finding classes (K = 4)"),
           ("p~k~", "Softmax probability of class k for a tooth crop"), ("H~n~", "Normalised predictive entropy, 0 (certain) to 1 (uniform)"),
           ("D~JS~", "Jensen–Shannon divergence between predictions on a crop and on its horizontal flip"),
           ("T", "Temperature used in temperature scaling"), ("J", "Youden’s index, sensitivity + specificity − 1"),
           ("A, B", "Predicted and ground-truth regions (boxes or masks)"), ("n~c~, N", "Training crops of class c, and all training crops"),
           ("w~c~", "Class weight of class c in the weighted cross-entropy loss"), ("γ", "Focusing parameter of the focal loss"),
           ("B~m~", "Set of predictions whose confidence falls in calibration bin m")]
    d.table(["SYMBOL", "MEANING"], [list(s) for s in sym], [0.25, 0.75])


def references(R):
    R.h1_plain("References")
    for i, k in enumerate(R.cite_order, 1):
        R.d.add(dl.para(f"[{i}] {REFS[k]}", "Reference"))
    unused = [k for k in REFS if k not in R.cite_order]
    if unused:
        print("NOTE unused references (not printed):", unused)


def appendices(R):
    R.h1_plain("Appendix A: Paper Publication Details")
    R.ps("No paper based on this project had been submitted or published when this report was prepared. If the group submits "
         "a paper, a patent application or receives event participation certificates, the conference or journal name, the "
         "reviewers’ comments, the certificate and the paper should be inserted here, as required by the report format.",
         "Suggested scope for a future paper: the end-to-end evaluation of a closed-set dental finding classifier on detector "
         "crops versus ground-truth crops, together with the pre-registered negative result of the class-imbalance experiments.")
    R.h1_plain("Appendix B: Plagiarism Report")
    R.ps("The plagiarism (similarity) report must be generated by the group with the institute-approved similarity-check tool, "
         "verified by the guide, and attached here. The format requires a similarity index below 15 %. This page is a "
         "placeholder: no similarity percentage is claimed in this document.")


def main():
    R = Report()
    front_matter(R)
    R.section("main")           # new page via the section break; Chapter 1 starts at page 1
    import content_a, content_b                     # noqa: E402  (chapters 1-4, 5-8)
    content_a.write(R, J, FIG, gray_copy)
    content_b.write(R, J, FIG, gray_copy)
    references(R)
    appendices(R)
    out = BASE / "DentaMind_AI_Capstone_Report.docx"
    R.d.save(out, R.sections, TITLE, "DentaMind AI capstone group")
    # citation map for the slides
    cmap = {k: i + 1 for i, k in enumerate(R.cite_order)}
    (BUILD / "citation_map.json").write_text(json.dumps(cmap, indent=1), encoding="utf-8")
    slides = (BUILD / "slides.json").read_text(encoding="utf-8")
    missing = set()

    def rep(m):
        k = m.group(1)
        if k not in cmap:
            missing.add(k)
            return m.group(0)
        return f"[{cmap[k]}]"
    slides = re.sub(r"\[@([A-Za-z0-9_]+)\]", rep, slides)
    if missing:
        raise SystemExit(f"slides cite keys not used in the report: {sorted(missing)}")
    (BUILD / "slides_resolved.json").write_text(slides, encoding="utf-8")
    print("wrote", out, "| figures", sum(1 for _ in R.figs), "| tables", len(R.tabs), "| references", len(R.cite_order))


if __name__ == "__main__":
    main()
