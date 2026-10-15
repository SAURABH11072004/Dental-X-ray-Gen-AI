# Repository audit (start of this development round)

**Original repository** (CCB computer-vision template): Jupyter notebooks for DENTEX classification, detection/segmentation and Grad-CAM, a Dockerfile (CUDA + Jupyter + detectron2), docker-compose files, Label Studio submodule/config, pinned `requirements.txt`/Pipfile, a PyScaffold skeleton in `src/dentexmodel` with one placeholder test, and no application layer. No dataset was committed.

**Kept unchanged**: notebooks, original Dockerfile/compose files, Pipfile, `requirements.txt`, Label Studio folders, docs scaffold.

**Added**: `src/dentexmodel/*` (config, data discovery/validation/splits/manifest/preprocess, uncertainty, active learning, evaluation, annotation, reporting, inference registry and lazy torch wrappers, training prerequisites and job manager, pipeline orchestrator), `backend/` (52 routes), `frontend/` (12 pages), `configs/`, `scripts/`, `tests/`, packaging extras, `Dockerfile.backend`, `frontend/Dockerfile`, `docker-compose.dentamind.yml`.

**Known gaps** are listed in `docs/TODO_DATASET_DEPENDENT.md`. The original `Dockerfile` uses a `.git` bind mount that fails outside a git checkout; it was left as is.
