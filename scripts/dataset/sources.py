"""Registry of dataset sources: the ones actually used, and every external candidate that was investigated.

Every fact below was checked on 2026-10-16 against the source itself (HF API listing, archive central directory, downloaded label
files, dataset landing pages). "not verified" means exactly that. Nothing here is a guess at a URL or a count.

    python scripts/dataset/sources.py        # -> reports/dataset_source_inventory.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dsutil import write_csv  # noqa: E402

HF = "https://huggingface.co/datasets/ibrahimhamamci/DENTEX/resolve/main/DENTEX/"

# Files we download. sha256 = the Git-LFS object id published by the Hugging Face API (it is the SHA-256 of the file).
DOWNLOADS = {
    "dentex_hf_validation_labels": {"url": HF + "validation_triple.json", "dest": "data/raw/external/dentex_hf/validation_triple.json",
                                    "bytes": 64409, "sha256": "d058afd35d2849923c7c045e61fd3e05d231dcf74d55009993fff88bd9b6f5a2",
                                    "sha256_origin": "computed after download (small non-LFS file; HF publishes only a git blob id)"},
    "dentex_hf_validation_images": {"url": HF + "validation_data.zip", "dest": "data/raw/external/dentex_hf/archives/validation_data.zip",
                                    "bytes": 149512256, "sha256": "6370bb4f1024bd610cde13242a465cb2eff195fc02f56ac22126555e7edc7bc3",
                                    "sha256_origin": "HF LFS oid", "local_equivalent": "data/validation_data/quadrant_enumeration_disease/xrays"},
    "dentex_hf_test": {"url": HF + "test_data.zip", "dest": "data/raw/external/dentex_hf/archives/test_data.zip",
                       "bytes": 764834414, "sha256": "ed396d6daa133264ddb0ecdbed3f963868d2a31344ba0fab929a6a1773d82ce2",
                       "sha256_origin": "HF LFS oid", "extract_to": "data/raw/external/dentex_hf/test_data"},
    "dentex_hf_training": {"url": HF + "training_data.zip", "dest": None, "bytes": 10927391529,
                           "sha256": "18b2a2dbc5a2b10b0cc6a7677c46a382f4709ab8c9c3bb94f57b74e38e11ffd3", "sha256_origin": "HF LFS oid",
                           "note": "never downloaded whole; the Kaggle notebook fetches only training_data/quadrant-enumeration-disease/ "
                                   "by HTTP range (CRC-32 per member + SHA-256 per image against the manifest)"},
}

COLS = ["source_id", "name", "url", "paper_or_docs", "access", "license", "image_type", "images_confirmed", "annotation_format",
        "classes", "annotation_level", "supports_target_classes", "status", "contributed_training_findings", "limitations"]

INVENTORY = [
    {"source_id": "dentex_train_disease", "name": "DENTEX training data, quadrant-enumeration-disease subset (already local)",
     "url": HF + "training_data.zip", "paper_or_docs": "Hamamci et al., DENTEX, arXiv:2305.19112",
     "access": "public, no login", "license": "CC BY-NC-SA 4.0", "image_type": "panoramic",
     "images_confirmed": "705 (678 with findings, 27 without)", "annotation_format": "COCO JSON, categories_1/2/3",
     "classes": "Caries, Deep Caries, Impacted, Periapical Lesion", "annotation_level": "box + polygon per (tooth, finding), FDI",
     "supports_target_classes": "all four (defines them)", "status": "in use (baseline data)",
     "contributed_training_findings": "see class_imbalance_before.csv", "limitations": "no patient ids; class definitions not published in detail"},
    {"source_id": "dentex_official_val", "name": "DENTEX official validation set (labels released after the challenge)",
     "url": HF + "validation_triple.json ; " + HF + "validation_data.zip", "paper_or_docs": "arXiv:2305.19112; HF dataset card",
     "access": "public, no login", "license": "CC BY-NC-SA 4.0", "image_type": "panoramic", "images_confirmed": "50 images, 50 label entries",
     "annotation_format": "COCO JSON, same categories_1/2/3 ids and names as the training file",
     "classes": "Caries 101, Deep Caries 32, Impacted 40, Periapical Lesion 9 (182 findings, 46 images with findings)",
     "annotation_level": "box + polygon per (tooth, finding), FDI", "supports_target_classes": "all four, identical taxonomy",
     "status": "downloaded and integrated (Experiment D)", "contributed_training_findings": "see class_imbalance_after.csv",
     "limitations": "20/50 images are byte-identical to DENTEX quadrant / enumeration radiographs (they inherit that split); small"},
    {"source_id": "dentex_official_test", "name": "DENTEX official test set (test_data.zip)", "url": HF + "test_data.zip",
     "paper_or_docs": "arXiv:2305.19112; HF dataset card", "access": "public, no login", "license": "CC BY-NC-SA 4.0",
     "image_type": "panoramic", "images_confirmed": "250 images + 250 Labelme JSON (archive SHA-256 verified)",
     "annotation_format": "Labelme polygons, label '<code>-<turkish name>-<FDI>'",
     "classes": "0-saglam 91, 1-curuk 747, 2-kuretaj 265, 3-kanal 161, 5-cekim 29, 6-gomulu 221, 7-lezyon 75 (shapes)",
     "annotation_level": "polygon per (tooth, label)", "supports_target_classes": "NOT mapped: different, treatment-oriented taxonomy",
     "status": "downloaded, inventoried, not used for training or evaluation", "contributed_training_findings": "0",
     "limitations": "on test_181 (byte-identical to training train_332) the Turkish labels disagree with the English ones; "
                    "95/250 images are byte-identical to DENTEX training-subset radiographs"},
    {"source_id": "dental_opg_xray_mendeley", "name": "Dental OPG XRAY Dataset (Mendeley c4hhrkxytw v4)",
     "url": "https://data.mendeley.com/datasets/c4hhrkxytw/4", "paper_or_docs": "dataset page only, no journal paper cited",
     "access": "public download", "license": "CC BY 4.0", "image_type": "panoramic (captured with an Android phone camera, per the page)",
     "images_confirmed": "not downloaded; page states 232 originals + 604 augmented", "annotation_format": "JSON (page)",
     "classes": "Healthy Teeth, Caries, Impacted Teeth, Broken Down Crown/Root, Infection, Fractured Teeth",
     "annotation_level": "boxes (object-detection folder)", "supports_target_classes": "Impacted only (semantic); Caries not split by depth; "
     "'Infection' undefined", "status": "rejected", "contributed_training_findings": "0",
     "limitations": "phone photographs of films (strong domain shift); augmented copies mixed in; minority classes not supported"},
    {"source_id": "four_dental_diseases_mendeley", "name": "Four common dental diseases (Mendeley wxv6h9p39g v1)",
     "url": "https://data.mendeley.com/datasets/wxv6h9p39g/1", "paper_or_docs": "dataset page only", "access": "public download",
     "license": "CC BY 4.0", "image_type": "OPG (panoramic)", "images_confirmed": "not downloaded; page states 4000 original + 10000 augmented",
     "annotation_format": "JSON (page)", "classes": "Cavities, Damage/Broken, Infection, Wisdom teeth",
     "annotation_level": "boxes (page)", "supports_target_classes": "none exactly: Cavities not split by depth, Infection undefined, "
     "wisdom tooth != impacted", "status": "rejected", "contributed_training_findings": "0",
     "limitations": "taxonomy incompatible; augmented images mixed with originals"},
    {"source_id": "children_panoramic_scidata2023", "name": "Children's dental panoramic radiographs (Sci Data 2023)",
     "url": "https://doi.org/10.6084/m9.figshare.c.6317013.v1", "paper_or_docs": "Zhang et al., Sci Data 2023 (PMC10267170)",
     "access": "public (figshare)", "license": "article CC BY 4.0; data licence not stated in the article",
     "image_type": "panoramic, children aged 2-13", "images_confirmed": "not downloaded; article: 100 + 93 child images",
     "annotation_format": "Labelme JSON", "classes": "Caries, Periapical infection, Pulpitis, Deep sulcus, developmental abnormalities, Others",
     "annotation_level": "lesion boxes", "supports_target_classes": "none exactly (caries not split by depth; 'periapical infection' "
     "undefined vs DENTEX)", "status": "rejected", "contributed_training_findings": "0",
     "limitations": "paediatric mixed dentition: large domain shift vs DENTEX (patients >= 12)"},
    {"source_id": "tufts_dental_database", "name": "Tufts Dental Database", "url": "https://tdd.ece.tufts.edu/",
     "paper_or_docs": "Panetta et al., IEEE JBHI 2022", "access": "registration / request form required",
     "license": "not verified (behind access form)", "image_type": "panoramic", "images_confirmed": "not accessed; paper: 1000",
     "annotation_format": "not verified", "classes": "abnormality descriptions in five levels (not the DENTEX four)",
     "annotation_level": "abnormality masks + text (paper)", "supports_target_classes": "unknown without access",
     "status": "not accessed (manual registration needed)", "contributed_training_findings": "0",
     "limitations": "requires the user to request access; mapping to the four classes would need clinical review"},
    {"source_id": "odontoai", "name": "OdontoAI", "url": "not verified in this session", "paper_or_docs": "Silva et al. (OdontoAI)",
     "access": "not verified", "license": "not verified", "image_type": "panoramic", "images_confirmed": "not accessed",
     "annotation_format": "tooth instance segmentation + FDI", "classes": "teeth only (no diagnoses in the public release, per literature)",
     "annotation_level": "tooth masks", "supports_target_classes": "no finding labels",
     "status": "rejected for the classifier (could serve detection/numbering only)", "contributed_training_findings": "0",
     "limitations": "a 2024 BMC Oral Health study added diagnosis labels to OdontoAI; its data-availability statement could not be "
                    "retrieved (publisher page blocked automated access), so no released labels are assumed"},
]


def main(out="reports/dataset_source_inventory.csv"):
    write_csv(out, INVENTORY, COLS)
    print(f"wrote {out} ({len(INVENTORY)} sources)")


if __name__ == "__main__":
    main(*sys.argv[1:])
