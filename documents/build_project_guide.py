"""Build documents/DentaMind_AI_Project_Guide.pdf - an illustrated team guide to the DentaMind AI project.

Uses reportlab + matplotlib (CPU only). Every number is copied from the project's own report files (cited in the PDF).
Run with a Python that has reportlab and matplotlib:
    C:\\Users\\chand\\AppData\\Local\\Programs\\Python\\Python313\\python.exe documents\\build_project_guide.py
"""
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,  # noqa: E402
                                TableStyle)

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
OUT = HERE / "DentaMind_AI_Project_Guide.pdf"
BLUE, ORANGE = "#2a78d6", "#eb6834"          # validated categorical slots 1-2 (dataviz reference palette)
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
NAVY, TEAL, PAPER = colors.HexColor("#15304B"), colors.HexColor("#0D7D7F"), colors.HexColor("#F5F7FA")

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], textColor=NAVY, fontSize=17, spaceBefore=6, spaceAfter=8)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], textColor=NAVY, fontSize=12.5, spaceBefore=10, spaceAfter=4)
P = ParagraphStyle("P", parent=ss["BodyText"], fontSize=9.6, leading=13.4, spaceAfter=5)
SMALL = ParagraphStyle("S", parent=P, fontSize=8.2, leading=11, textColor=colors.HexColor(INK2))
BUL = ParagraphStyle("B", parent=P, leftIndent=12, bulletIndent=2)
BOX = ParagraphStyle("BOX", parent=P, backColor=colors.HexColor("#FFF6E5"), borderColor=colors.HexColor("#E8B04A"),
                     borderWidth=0.6, borderPadding=6, spaceBefore=6, spaceAfter=10)
INFO = ParagraphStyle("INFO", parent=BOX, backColor=colors.HexColor("#E8F4F4"), borderColor=TEAL)


def para(t, st=P):
    return Paragraph(t, st)


def bullets(items):
    return [Paragraph(t, BUL, bulletText="\u2022") for t in items]


def table(rows, widths, header=True, zebra=True):
    data = [[Paragraph(str(c), ParagraphStyle("tc", parent=P, fontSize=8.4, leading=10.6, spaceAfter=0,
                                              textColor=colors.white if (header and i == 0) else colors.black))
             for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C9CED6")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        st.append(("BACKGROUND", (0, 0), (-1, 0), NAVY))
    if zebra:
        for i in range(1 if header else 0, len(rows)):
            if i % 2 == 0:
                st.append(("BACKGROUND", (0, i), (-1, i), PAPER))
    t.setStyle(TableStyle(st))
    return t


# ------------------------------------------------------------------------------------------------ diagrams (reportlab drawings)
def arrow(d, x1, y1, x2, y2, col=NAVY):
    d.add(Line(x1, y1, x2, y2, strokeColor=col, strokeWidth=1.2))
    import math
    a = math.atan2(y2 - y1, x2 - x1)
    s = 5
    d.add(Polygon([x2, y2, x2 - s * math.cos(a - 0.45), y2 - s * math.sin(a - 0.45), x2 - s * math.cos(a + 0.45), y2 - s * math.sin(a + 0.45)],
                  fillColor=col, strokeColor=col))


def box(d, x, y, w, h, title, lines=(), fill=colors.white, edge=NAVY):
    d.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=fill, strokeColor=edge, strokeWidth=1))
    d.add(String(x + w / 2, y + h - 13, title, fontName="Helvetica-Bold", fontSize=8.6, fillColor=NAVY, textAnchor="middle"))
    for i, ln in enumerate(lines):
        d.add(String(x + w / 2, y + h - 25 - i * 10, ln, fontName="Helvetica", fontSize=7.2, fillColor=colors.HexColor(INK2), textAnchor="middle"))


def architecture():
    d = Drawing(480, 230)
    box(d, 5, 150, 120, 70, "User (browser)", ("X-ray upload, review,", "reports, model registry"), fill=PAPER)
    box(d, 175, 150, 130, 70, "Frontend", ("React + Vite", "http://localhost:5173", "proxies /api, adds token"))
    box(d, 355, 150, 120, 70, "Backend API", ("FastAPI (uvicorn)", "http://127.0.0.1:8000", "token + loopback only"))
    box(d, 5, 20, 140, 95, "AI models (PyTorch)", ("tooth detector (Faster R-CNN)", "tooth segmenter (Mask R-CNN)", "FDI numbering (Faster R-CNN)",
                                                    "finding classifier (ResNet-50)", "Data/checkpoints"), fill=colors.HexColor("#E8F4F4"))
    box(d, 170, 20, 140, 95, "Data", ("DENTEX radiographs + COCO", "manifests, splits", "Data/processed, Data/splits",
                                      "reports in Data/reports"), fill=colors.HexColor("#E8F4F4"))
    box(d, 335, 20, 140, 95, "Storage & services", ("SQLite: images, analyses,", "reviews, reports, jobs", "test-set ledger, promotions",
                                                    "(Label Studio / LLM optional)"), fill=colors.HexColor("#E8F4F4"))
    arrow(d, 125, 185, 175, 185)
    arrow(d, 305, 185, 355, 185)
    arrow(d, 400, 150, 75, 115)
    arrow(d, 410, 150, 240, 115)
    arrow(d, 420, 150, 405, 115)
    return d


def pipeline():
    d = Drawing(480, 120)
    steps = [("1 Load", ("grayscale ->", "3 channels")), ("2 Detect", ("teeth boxes", "score >= 0.3")), ("3 Number", ("FDI tooth", "numbers")),
             ("4 Segment", ("tooth", "outlines")), ("5 Classify", ("closest finding", "per tooth crop")), ("6 Doubt", ("uncertainty", "& review flags")),
             ("7 Report", ("draft report", "EN / HI / MR"))]
    w, gap = 60, 8.3
    for i, (t, l) in enumerate(steps):
        x = 4 + i * (w + gap)
        box(d, x, 40, w, 60, t, l, fill=colors.HexColor("#E8F4F4") if i in (1, 4) else colors.white)
        if i:
            arrow(d, x - gap, 70, x, 70)
    d.add(String(240, 18, "Every output is a research draft: a person must review it. Nothing here is a diagnosis.",
                 fontName="Helvetica-Oblique", fontSize=7.6, fillColor=colors.HexColor(INK2), textAnchor="middle"))
    return d


def data_flow():
    d = Drawing(480, 150)
    box(d, 5, 70, 125, 70, "3,653 image files", ("3 annotated DENTEX subsets", "+ unlabeled pool", "+ 50 validation_data"), fill=PAPER)
    box(d, 175, 70, 125, 70, "2,716 unique films", ("identical copies grouped", "by pixel hash (SHA-256)"))
    box(d, 345, 70, 130, 70, "1,133 annotated", ("unique radiographs", "split by unique film", "(copies never cross)"))
    arrow(d, 130, 105, 175, 105)
    arrow(d, 300, 105, 345, 105)
    for i, (nm, n) in enumerate((("train", "794"), ("validation", "113"), ("calibration", "113"), ("test", "113"))):
        x = 175 + i * 76
        box(d, x, 2, 70, 45, nm, (f"{n} films",), fill=colors.HexColor("#E8F4F4"))
        arrow(d, 410, 70, x + 35, 47)
    return d


# ------------------------------------------------------------------------------------------------ charts (matplotlib, CPU)
def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8.5)
    ax.yaxis.grid(True, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)


def chart_class_counts():
    cls, n = ["Caries", "Deep Caries", "Impacted", "Periapical\nLesion"], [1550, 438, 412, 120]
    fig, ax = plt.subplots(figsize=(6.2, 2.7), dpi=200)
    bars = ax.bar(cls, n, color=BLUE, width=0.55, edgecolor="#fcfcfb", linewidth=1.5)
    for b, v in zip(bars, n):
        ax.text(b.get_x() + b.get_width() / 2, v + 25, f"{v:,}", ha="center", fontsize=8.5, color=INK)
    _style(ax)
    ax.set_ylabel("training tooth crops", fontsize=8.5, color=INK2)
    ax.set_title("Training crops per finding class (13 : 1 imbalance)", fontsize=9.5, color=INK, loc="left")
    fig.tight_layout()
    p = FIG / "class_counts.png"
    fig.savefig(p, facecolor="#fcfcfb")
    plt.close(fig)
    return p


def chart_gt_vs_det():
    cls = ["Caries", "Deep Caries", "Impacted", "Periapical\nLesion"]
    gt, det = [0.876, 0.456, 0.938, 0.600], [0.857, 0.411, 0.945, 0.381]      # same 323 matched teeth (end_to_end report)
    import numpy as np
    x = np.arange(4)
    fig, ax = plt.subplots(figsize=(6.2, 2.8), dpi=200)
    b1 = ax.bar(x - 0.19, gt, 0.36, color=BLUE, label="ground-truth boxes", edgecolor="#fcfcfb", linewidth=1.5)
    b2 = ax.bar(x + 0.19, det, 0.36, color=ORANGE, label="detector boxes (as in the app)", edgecolor="#fcfcfb", linewidth=1.5)
    for bs in (b1, b2):
        for b in bs:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.015, f"{b.get_height():.2f}", ha="center", fontsize=7.5, color=INK)
    ax.set_xticks(x, cls)
    ax.set_ylim(0, 1.05)
    _style(ax)
    ax.set_ylabel("F1 (validation)", fontsize=8.5, color=INK2)
    ax.legend(frameon=False, fontsize=8, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.13), labelcolor=INK)
    fig.tight_layout()
    p = FIG / "gt_vs_detector_f1.png"
    fig.savefig(p, facecolor="#fcfcfb")
    plt.close(fig)
    return p


def chart_experiments():
    names = ["C0 baseline\n(class weights)", "A sampler", "B oversample", "C focal loss", "D sqrt weights", "E minority aug"]
    mean = [0.764, 0.766, 0.774, 0.750, 0.742, 0.751]
    sd = [0.027, 0.009, 0.016, 0.022, 0.024, 0.020]
    fig, ax = plt.subplots(figsize=(6.2, 2.8), dpi=200)
    y = list(range(len(names)))[::-1]
    ax.axvspan(0.764 - 0.027, 0.764 + 0.027, color="#eef3fb", zorder=0)
    ax.axvline(0.764, color=INK2, linewidth=0.8, linestyle="--", zorder=1)
    ax.errorbar(mean, y, xerr=sd, fmt="o", color=BLUE, ecolor=BLUE, elinewidth=1.4, capsize=3, markersize=6, zorder=3)
    for m, yy in zip(mean, y):
        ax.text(m, yy + 0.25, f"{m:.3f}", ha="center", fontsize=7.5, color=INK)
    ax.set_yticks(y, names)
    ax.set_xlim(0.70, 0.82)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.xaxis.grid(True, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.set_xlabel("validation macro-F1, mean +/- SD over 5 seeds (shaded = baseline +/- 1 SD)", fontsize=8, color=INK2)
    fig.tight_layout()
    p = FIG / "imbalance_experiments.png"
    fig.savefig(p, facecolor="#fcfcfb")
    plt.close(fig)
    return p


# ------------------------------------------------------------------------------------------------ document
def on_page(c, doc):
    c.saveState()
    c.setFillColor(NAVY)
    c.rect(0, A4[1] - 0.55 * cm, A4[0], 0.55 * cm, fill=1, stroke=0)
    c.setFont("Helvetica", 7.5)
    c.setFillColor(colors.HexColor(INK2))
    c.drawString(1.8 * cm, 1.0 * cm, "DentaMind AI - project guide for the team - research software, not a diagnostic device")
    c.drawRightString(A4[0] - 1.8 * cm, 1.0 * cm, f"page {doc.page}")
    c.restoreState()


def build():
    FIG.mkdir(parents=True, exist_ok=True)
    f_counts, f_gtdet, f_exp = chart_class_counts(), chart_gt_vs_det(), chart_experiments()
    W = A4[0] - 3.6 * cm
    s = []
    # cover
    s += [Spacer(1, 3.2 * cm), para("DentaMind AI", ParagraphStyle("T", parent=H1, fontSize=30, leading=36, alignment=TA_CENTER)),
          para("Dental X-ray analysis research prototype", ParagraphStyle("ST", parent=P, fontSize=14, alignment=TA_CENTER, textColor=TEAL)),
          Spacer(1, 0.4 * cm), para("A complete guide for the project team: what it does, how it works, what the models achieve, "
                                    "what we tested, and what is still open.", ParagraphStyle("c", parent=P, alignment=TA_CENTER, fontSize=10.5)),
          Spacer(1, 1.2 * cm), pipeline(), Spacer(1, 1.4 * cm),
          para(f"Version of {date.today().strftime('%d %B %Y')}. All numbers are copied from the project's own report files "
               "(named on each page). Validation numbers are optimistic: the same split chose each model's best training epoch.",
               ParagraphStyle("c2", parent=SMALL, alignment=TA_CENTER)),
          para("<b>Research use only.</b> DentaMind AI is not a medical device, is not clinically validated, and must not guide "
               "treatment. Every output is an unconfirmed research draft until a named person reviews it.", BOX),
          PageBreak()]
    # contents
    toc = ["1. The project in one page", "2. How the system is built", "3. How an X-ray is analysed", "4. The data",
           "5. The four AI models", "6. How good are the models?", "7. Realistic performance in the app",
           "8. Experiments we ran to improve the classifier", "9. Research integrity: how we keep results honest",
           "10. Known limitations", "11. What to do next", "12. Running the project", "13. Glossary", "14. Where to find things"]
    s += [para("Contents", H1)] + [para(t) for t in toc] + [PageBreak()]
    # 1
    s += [para("1. The project in one page", H1),
          para("DentaMind AI looks at a <b>panoramic dental X-ray</b> (an OPG, the wide image that shows all teeth at once) and produces a "
               "structured, reviewable draft: where each tooth is, its tooth number, its outline, which of four findings it most resembles, "
               "how unsure the model is, and a draft report in English, Hindi or Marathi."),
          para("What it can do", H2)] + bullets([
              "<b>Find teeth</b> on the X-ray and draw a box and an outline around each one.",
              "<b>Suggest a tooth number</b> in the international FDI system (11-48). Unsure numbers are marked \"?\".",
              "<b>Name the closest trained finding</b> for each tooth: Caries, Deep Caries, Impacted or Periapical Lesion.",
              "<b>Show doubt</b>: uncertainty scores and image-quality warnings, with a list of regions a person should check.",
              "<b>Write a draft report</b> from the structured results, without any external service.",
              "<b>Support research work</b>: model registry, evaluation reports, active learning, reviewer workflow and audit trails."]) + [
          para("What it cannot do", H2)] + bullets([
              "<b>It cannot say a tooth is healthy.</b> The classifier only knows four findings, so it always picks one of them.",
              "It is <b>not a diagnosis</b> and has <b>not been clinically validated</b>. It was trained on one public dataset (DENTEX).",
              "It cannot prove that two different X-rays of the same patient were kept apart, because DENTEX has no patient IDs."]) + [
          para("Key numbers at a glance", H2),
          table([["Question", "Answer (source: Data/reports)"],
                 ["How well are teeth found?", "Recall 0.98-0.996, precision about 0.96 (validation); detection is reliable"],
                 ["How good are tooth outlines?", "Mask AP@0.5 0.97-0.98; Dice 0.87 on the test split"],
                 ["How accurate are tooth numbers?", "93.6 % (validation) / 96.8 % (test) of matched teeth exactly right"],
                 ["How accurate is the finding classifier?", "Accuracy 0.79 and macro-F1 0.63 end-to-end in the app (validation); "
                                                             "strong for Caries/Impacted, weak for Deep Caries and Periapical Lesion"],
                 ["Is the data split clean?", "17 of 18 leakage checks pass; 1 warning that cannot affect any metric"]], [5.2 * cm, W - 5.2 * cm]),
          PageBreak()]
    # 2
    s += [para("2. How the system is built", H1),
          para("Three parts run on one computer. The browser talks only to the frontend. The frontend forwards requests to the backend "
               "API and adds a secret token on the server side, so the token never reaches the browser. The backend loads the AI models, "
               "reads the data and stores results in a local SQLite database."),
          architecture(), Spacer(1, 6),
          table([["Part", "Technology", "Where", "Job"],
                 ["Frontend", "React 18, Vite, Tailwind", "frontend/", "Pages: X-ray analysis, review, reports, model registry, about & limitations"],
                 ["Backend", "Python 3.13, FastAPI, uvicorn", "backend/", "About 70 API routes; security (token, loopback-only, rate limit)"],
                 ["Core library", "Python, PyTorch 2.6, torchvision", "src/dentexmodel/", "Data handling, training, inference, evaluation, reports"],
                 ["Models", "Faster/Mask R-CNN, ResNet-50", "Data/checkpoints/", "4 trained checkpoints + metadata sidecars"],
                 ["Database", "SQLite", "runtime/dentamind.sqlite3", "Images, analyses, reviews, reports, jobs, promotions"],
                 ["Scripts", "Python", "scripts/", "Training, evaluation, audits, experiments"]],
                [2.2 * cm, 3.6 * cm, 3.6 * cm, W - 9.4 * cm]),
          para("Security in short: the API answers only on 127.0.0.1, every route except the health check needs the token "
               "(<i>runtime/api_token.txt</i>), and requests are rate-limited. There is no user login, so the app must stay on this computer.", INFO),
          PageBreak()]
    # 3
    s += [para("3. How an X-ray is analysed", H1), pipeline(), Spacer(1, 4)] + bullets([
              "<b>1 Load.</b> The image is read as grayscale and copied into three identical channels. It is not contrast-adjusted for the models.",
              "<b>2 Detect.</b> A Faster R-CNN finds every tooth. Boxes with a score below 0.3 are dropped.",
              "<b>3 Number.</b> A second Faster R-CNN predicts FDI tooth numbers; a number is attached to a box only if the two overlap well "
              "(IoU at least 0.5). Teeth without a match show \"R7\"-style region names instead of a number.",
              "<b>4 Segment.</b> A Mask R-CNN draws an outline for each tooth.",
              "<b>5 Classify.</b> Each detected box is cut out with 10 % padding, resized to 224 x 224 pixels, and a ResNet-50 names the "
              "<i>closest</i> of the four findings. This is shown with a \"~\" (for example \"~Caries\") because it is not a confirmed finding.",
              "<b>6 Doubt.</b> Entropy of the classifier and disagreement on a flipped copy flag teeth for review. Thresholds were chosen on "
              "the calibration split and are labelled provisional.",
              "<b>7 Report.</b> A template turns the structured results into a draft report in English, Hindi or Marathi. "
              "Hindi and Marathi wording has not been reviewed by a native-speaking dentist."]) + [
          para("Colours on the X-ray", H2),
          table([["Colour", "Label", "Meaning"],
                 ["Teal", "14", "Tooth number from the numbering model, consistent with its neighbours"],
                 ["Red", "14?", "Proposed number that needs checking (red means \"check the number\", not disease)"],
                 ["Grey", "R7", "Region without a tooth number; 7 is only the detection order"],
                 ["Orange", "-", "The region you selected"]], [2.2 * cm, 2 * cm, W - 4.2 * cm]),
          PageBreak()]
    # 4
    s += [para("4. The data", H1),
          para("The project uses <b>DENTEX</b>, a public dataset of panoramic X-rays. It comes as three annotated subsets with different "
               "labels, plus unlabeled images. The subsets overlap: the same X-ray often appears in two or three of them under different "
               "file names. We therefore count and split <b>unique radiographs</b> (identical pixels = same film), not files."),
          data_flow(), Spacer(1, 4),
          table([["Subset", "What is labelled", "Used to train"],
                 ["quadrant", "4 large quadrant regions per image (not teeth)", "not used as tooth ground truth"],
                 ["quadrant_enumeration", "every tooth: box, outline, FDI number", "detector, segmenter, numbering model"],
                 ["quadrant_enumeration_disease", "only diseased teeth, each with one of 4 findings", "finding classifier"],
                 ["unlabeled pool (1,598 files)", "nothing", "active-learning pool only"],
                 ["validation_data (50 files)", "nothing", "demo images only; never scored"]], [4.6 * cm, 6.2 * cm, W - 10.8 * cm]),
          para("Splits", H2),
          para("Train / validation / calibration / test are assigned per unique radiograph: <b>794 / 113 / 113 / 113</b>. Training uses "
               "<b>train</b>; <b>validation</b> chooses the best training epoch; <b>calibration</b> sets uncertainty thresholds; "
               "<b>test</b> is the final check (already used once, see section 9)."),
          para("The classifier's imbalance", H2), Image(str(f_counts), width=W * 0.92, height=W * 0.92 * 2.7 / 6.2),
          para("Caries has 13 times more examples than Periapical Lesion. The validation split has only 9 Periapical Lesion and 45 Deep "
               "Caries crops, so their scores move a lot with each tooth. Source: classifier sidecar <i>class_counts_train</i>.", SMALL),
          PageBreak()]
    # 5
    s += [para("5. The four AI models", H1),
          table([["Model", "Architecture", "Trained on", "Output"],
                 ["dentex_teeth_detection_v1", "Faster R-CNN ResNet-50 FPN (COCO start)", "440 train radiographs, all teeth", "one box per tooth"],
                 ["dentex_teeth_segmentation_v1", "Mask R-CNN ResNet-50 FPN (COCO start)", "440 train radiographs, tooth outlines", "outline per tooth"],
                 ["dentex_fdi_numbering_v1", "Faster R-CNN, 32 FDI classes", "440 train radiographs", "tooth number per box"],
                 ["dentex_findings_classification_v1", "ResNet-50 (ImageNet start)", "2,520 tooth crops, 476 radiographs", "closest of 4 findings"]],
                [5.6 * cm, 4.0 * cm, 3.9 * cm, W - 13.5 * cm]),
          para("Each checkpoint has a metadata file (sidecar) with its task, classes, training settings, data version and a SHA-256 hash. "
               "The app refuses to load a model whose file no longer matches its hash. All four are <b>legacy</b> for provenance: they were "
               "trained before we started recording exactly which images each model saw (section 9).", INFO),
          para("Training settings (classifier)", H2),
          para("ResNet-50, 15 epochs, batch 32, AdamW learning rate 3e-4, cosine schedule, inverse-frequency class weights, horizontal flip "
               "and mild contrast jitter, best epoch chosen by validation macro-F1 (epoch 5 for the deployed model). Re-running the production "
               "trainer today reproduced the deployed weights <b>bit for bit</b>."),
          PageBreak()]
    # 6
    s += [para("6. How good are the models?", H1),
          para("Validation = the split used to pick the best epoch (slightly optimistic). Test = historical final check on 2026-10-14. "
               "Sources: <i>Data/reports/eval_*_val.json</i> and <i>eval_*_test.json</i>."),
          para("Teeth: detection, outlines and numbers", H2),
          table([["Model / metric", "Validation", "Test"],
                 ["Detection precision / recall (score 0.3, IoU 0.5)", "0.962 / 0.984", "0.960 / 0.974"],
                 ["Detection box mAP / AP50", "0.560 / 0.978", "0.515 / 0.966"],
                 ["Segmentation precision / recall (box level)", "0.966 / 0.986", "0.962 / 0.980"],
                 ["Segmentation mask AP@0.5", "0.980", "0.974"],
                 ["Segmentation Dice / IoU (matched teeth)", "not recorded", "0.873 / 0.780"],
                 ["Numbering: exact FDI number among matched teeth", "93.6 %", "96.8 %"],
                 ["Numbering: correct quadrant", "99.7 %", "99.9 %"]], [8.6 * cm, 3.6 * cm, W - 12.2 * cm]),
          para("Findings: the classifier (ground-truth tooth boxes)", H2),
          table([["Metric", "Validation (331 crops)", "Test (354 crops)"],
                 ["Accuracy", "0.825", "0.785"], ["Macro precision / recall / F1", "0.693 / 0.763 / 0.718", "0.653 / 0.649 / 0.646"],
                 ["Caries P / R / F1", "0.885 / 0.863 / 0.874", "0.866 / 0.820 / 0.842"],
                 ["Deep Caries P / R / F1", "0.500 / 0.467 / 0.483", "0.414 / 0.500 / 0.453"],
                 ["Impacted P / R / F1", "0.919 / 0.944 / 0.932", "0.887 / 0.969 / 0.926"],
                 ["Periapical Lesion P / R / F1", "0.467 / 0.778 / 0.583", "0.444 / 0.308 / 0.364"]], [6.4 * cm, 5 * cm, W - 11.4 * cm]),
          para("<b>Reading this:</b> teeth are found, outlined and numbered well. The classifier is good for Caries and Impacted and weak for "
               "the two rare findings. On the test split it found only 4 of 13 periapical lesions.", BOX),
          PageBreak()]
    # 7
    s += [para("7. Realistic performance in the app", H1),
          para("The numbers above use the <i>true</i> tooth boxes. In the app the classifier receives the <i>detector's</i> boxes, which are "
               "slightly different. We measured both on the same 323 validation teeth (source: <i>end_to_end_validation_evaluation.md</i>)."),
          Image(str(f_gtdet), width=W * 0.92, height=W * 0.92 * 2.8 / 6.2),
          table([["Metric (validation)", "True boxes", "Detector boxes", "End-to-end (missed tooth = wrong)"],
                 ["Accuracy", "0.830", "0.811", "0.792"], ["Macro-F1", "0.717", "0.649", "0.634"],
                 ["Deep Caries recall", "0.439", "0.366", "0.333"], ["Periapical Lesion recall", "0.857 (6/7)", "0.571 (4/7)", "0.444 (4/9)"]],
                [5 * cm, 3 * cm, 3.4 * cm, W - 11.4 * cm]),
          para("Why the gap", H2)] + bullets([
              "<b>Small box shifts change predictions:</b> about 10 % of teeth get a different answer even when the detector box overlaps the "
              "true box by more than 90 %.",
              "<b>Some errors exist even with perfect boxes</b> (41 of 331 findings).",
              "<b>Two findings on one tooth:</b> 8 findings (including 4 of the 9 periapical lesions) sit on teeth that also carry another "
              "finding. A one-answer-per-tooth classifier can never get both right.",
              "<b>Missed teeth are rare:</b> only 4 findings were missed by the detector.",
              "<b>Most teeth have no recorded finding but still get a class</b> (1,580 of 1,903 detected teeth). They are not proven "
              "healthy, so we cannot count them as right or wrong, but users should know the app labels every tooth."]) + [PageBreak()]
    # 8
    s += [para("8. Experiments we ran to improve the classifier", H1),
          para("Every experiment used the same data, 5 random seeds (42-46) and rules written <b>before</b> seeing results: a method counts "
               "as better only if it beats the baseline in at least 4 of 5 seeds by more than 0.027 macro-F1 without hurting the rare classes."),
          para("A. Class-imbalance methods (validation, true boxes)", H2), Image(str(f_exp), width=W * 0.92, height=W * 0.92 * 2.8 / 6.2),
          para("None beat the baseline. Sampling and oversampling raised precision but lowered rare-class recall; focal loss and square-root "
               "weights were worse; minority-only augmentation cut Deep Caries recall in every seed. Tuning decision thresholds on validation "
               "looked better in-sample (+0.023) but was worse when checked properly (-0.005). Source: <i>docs/audit_evidence/ml_improvement/imbalance/report.md</i>.", SMALL),
          para("B. Crop-robustness (training on jittered boxes)", H2),
          para("To make the classifier tolerant of detector boxes, we trained on boxes jittered the way the detector really errs (measured on "
               "training images only). Detector-box macro-F1: <b>0.720 +/- 0.038</b> vs baseline <b>0.723 +/- 0.016</b>, better in only "
               "1 of 5 seeds: <b>did not pass</b>. It raised rare-class recall but lowered their precision. Source: <i>crop_robustness_experiment.md</i>."),
          para("C. Production recipe vs experiment recipe", H2),
          para("The deployed classifier scored below every run of the experiment recipe on detector boxes, so we ran a pre-registered "
               "comparison. Re-running the production trainer reproduced the deployed model <b>bit for bit</b>. Across 5 seeds the two recipes "
               "are equal: detector-box macro-F1 <b>0.722 +/- 0.045</b> (production) vs <b>0.724 +/- 0.015</b> (experiment); the experiment "
               "recipe won only 10 of 25 run pairs and did not pass. <b>The deployed model is simply the weakest of five runs</b> of its "
               "recipe (0.651; the others 0.718-0.776). Picking the best run by its validation score would be optimistic, so any "
               "replacement needs its own pre-registered selection and evaluation. Source: <i>training_recipe_comparison_results.md</i>.", INFO),
          PageBreak()]
    # 9
    s += [para("9. Research integrity: how we keep results honest", H1),
          table([["Protection", "What it does", "Enforced in code?"],
                 ["Duplicate-aware splits", "Identical films always land in the same split (checked by pixel hash)", "Yes"],
                 ["Leakage audit (18 checks)", "17 pass; 1 warning: 3 unlabeled demo files equal test films (never scored)", "Yes, re-runnable"],
                 ["Test-set ledger", "Every test evaluation needs a named person and a reason, is logged with hashes, one per model; "
                                     "the ledger is hash-chained so edits are detectable", "Yes (files can still be edited)"],
                 ["Training manifests", "New models record exactly which images they were trained on", "Yes, for new models"],
                 ["Model promotion", "Needs a validation report, a named approver and a written reason; rollback recorded", "Yes"],
                 ["Uploads vs reviews", "An upload identical to a labelled film can never feed training", "Yes"],
                 ["Patient separation", "Not possible: DENTEX has no patient IDs", "No - open limitation"]],
                [3.6 * cm, W - 7.2 * cm, 3.6 * cm]),
          para("<b>The internal test split has already been used</b> for all four current models (2026-10-14). Their test numbers are "
               "historical. An honest estimate for a future model needs a new, external test set (protocol in docs/RESEARCH_INTEGRITY.md).", BOX),
          PageBreak()]
    # 10-11
    s += [para("10. Known limitations", H1)] + bullets([
              "No \"healthy\" class: every tooth is given one of four findings.",
              "Deep Caries and Periapical Lesion are weak (end-to-end recall about 0.33 and 0.44 on validation).",
              "Few rare-class examples: 9 Periapical Lesion and 45 Deep Caries validation crops; results for them are noisy.",
              "A tooth can carry two findings, but the classifier gives one answer per tooth.",
              "One public dataset; no external test; behaviour on other scanners is unknown.",
              "Patient-level separation cannot be proven.",
              "The current models were trained before image-level training records existed (legacy provenance).",
              "Hindi/Marathi reports not reviewed by a native-speaking dentist; reviewer names are typed in, not verified.",
              "No user accounts: the app must run only on this computer."]) + [
          para("11. What to do next", H1)] + bullets([
              "<b>Decide how to replace the weak deployed run</b> (section 8C): a pre-registered rule for choosing among several runs, "
              "evaluated without reusing the validation numbers used to choose.",
              "<b>Collect more dentist-labelled Deep Caries and Periapical Lesion examples</b> - the step most likely to help.",
              "<b>Add a reliable \"no finding\" class</b>, which needs labels confirming that teeth have no finding.",
              "<b>Switch to a multi-label classifier</b> so a tooth can have two findings (for example Caries + Periapical Lesion).",
              "<b>Obtain an external test set</b> and evaluate one final model once."]) + [PageBreak()]
    # 12
    s += [para("12. Running the project", H1),
          para("Open two terminals in <b>D:\\Dentex-Gen Ai</b>:"),
          table([["What", "Command", "Then open"],
                 ["Backend API", ".venv\\Scripts\\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000", "http://127.0.0.1:8000/api/health"],
                 ["Frontend", "cd frontend  then  npm.cmd run dev", "http://localhost:5173/"]], [2.4 * cm, 9.6 * cm, W - 12 * cm]),
          Spacer(1, 6)] + bullets([
              "API documentation: http://127.0.0.1:8000/docs (needs the token from runtime\\api_token.txt).",
              "Run all unit tests: <i>.venv\\Scripts\\python.exe -m unittest discover -s tests</i> (233 tests).",
              "Re-run the leakage audit: <i>.venv\\Scripts\\python.exe scripts\\check_leakage.py</i>.",
              "Check the test-set ledger: <i>.venv\\Scripts\\python.exe scripts\\test_set_ledger.py --verify</i>.",
              "GPU note: the laptop GPU has 4 GB. Run one GPU job at a time; restart the backend before training so it releases GPU memory."]) + [
          para("13. Glossary", H1),
          table([["Term", "Meaning"],
                 ["OPG / panoramic X-ray", "One wide X-ray showing all teeth and both jaws"],
                 ["FDI number", "International tooth numbering: first digit = quadrant (1-4), second = tooth (1-8), e.g. 36"],
                 ["Bounding box", "A rectangle around a tooth"], ["IoU", "Overlap of two boxes: shared area / combined area (1 = identical)"],
                 ["Precision", "Of the items the model flagged, how many were right"], ["Recall", "Of the real items, how many the model found"],
                 ["F1", "One number combining precision and recall (their harmonic mean)"],
                 ["Macro-F1", "F1 averaged over the 4 classes equally, so rare classes count as much as common ones"],
                 ["Balanced accuracy", "Average recall over the classes"], ["AP / mAP", "Average precision over score thresholds (detection quality)"],
                 ["Dice", "Overlap of two outlines (1 = identical); similar to IoU"],
                 ["Train / validation / calibration / test", "Data for learning / choosing the epoch / setting thresholds / final check"],
                 ["Seed", "Starting value of the random generator; 5 seeds = 5 repeats to measure luck"],
                 ["Data leakage", "The same image (or patient) ending up in training and testing, which inflates results"],
                 ["Checkpoint / sidecar", "A saved trained model file / its metadata file"]], [4.4 * cm, W - 4.4 * cm]),
          PageBreak()]
    # 14
    s += [para("14. Where to find things", H1),
          table([["File or folder", "What is in it"],
                 ["README.md", "Project overview and setup"], ["docs/KNOWN_LIMITATIONS.md", "Full list of limitations"],
                 ["docs/RESEARCH_INTEGRITY.md", "Test-set use, provenance, promotion: what is enforced vs procedural"],
                 ["docs/MODEL_TRAINING.md", "How each model was trained"],
                 ["Data/reports/eval_*.json / .md", "Evaluation of each model on validation and test"],
                 ["Data/reports/end_to_end_validation_evaluation.md", "Detector -> classifier performance as in the app"],
                 ["Data/reports/crop_robustness_experiment.md", "Crop-jitter experiment"],
                 ["Data/reports/training_recipe_comparison_results.md", "Recipe comparison: protocol and results"],
                 ["Data/reports/leakage_check.md", "Leakage audit results"], ["Data/reports/test_set_ledger.json", "Record of every test-split use"],
                 ["docs/audit_evidence/ml_improvement/", "All experiment runs, per seed"],
                 ["documents/build_project_guide.py", "Rebuilds this PDF"]], [7.6 * cm, W - 7.6 * cm]),
          Spacer(1, 10),
          para("Questions about a number in this guide: open the source file named next to it - every figure here was copied from "
               "those files, not estimated.", INFO)]
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.6 * cm, bottomMargin=1.6 * cm,
                            title="DentaMind AI - Project Guide", author="DentaMind AI project", subject="Team guide")
    doc.build(s, onFirstPage=on_page, onLaterPages=on_page)
    print("wrote", OUT)


if __name__ == "__main__":
    build()
