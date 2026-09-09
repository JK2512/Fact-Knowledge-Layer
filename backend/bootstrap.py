"""
Production Database Bootstrap Mechanism for Fact Knowledge Layer.

Automatically populates empty SQLite databases on first startup (e.g. Render / Docker deployments)
by ingesting committed starter PDFs through the existing extraction and linking pipeline.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import List, Callable, Dict, Any

from backend.config import BASE_DIR, UPLOAD_DIR, DATA_DIR
from backend.database import get_all_documents

logger = logging.getLogger(__name__)


def find_starter_pdfs() -> List[Path]:
    """Discover starter PDF files committed in the repository."""
    search_dirs = [
        BASE_DIR / "starter-datasets",
        DATA_DIR / "uploads",
    ]

    found_files: Dict[str, Path] = {}

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for root, _, files in os.walk(str(search_dir)):
            for f in sorted(files):
                if f.lower().endswith(".pdf"):
                    filename = f
                    full_path = Path(root) / f
                    # Prefer files from starter-datasets if duplicates exist
                    if filename not in found_files or "starter-datasets" in str(full_path):
                        found_files[filename] = full_path

    # Return sorted by filename for deterministic processing order
    sorted_paths = [found_files[k] for k in sorted(found_files.keys())]
    return sorted_paths


def bootstrap_database_if_empty(process_pdf_fn: Callable[[str, str], Dict[str, Any]]) -> bool:
    """
    Safely bootstrap starter PDFs into the database if the database is currently empty.
    
    Idempotent: If documents already exist in the database, no action is taken.
    """
    # Ensure directories exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    existing_docs = get_all_documents()
    if existing_docs:
        logger.info("Database already contains %d documents. Skipping bootstrap.", len(existing_docs))
        return False

    starter_pdfs = find_starter_pdfs()
    if not starter_pdfs:
        logger.warning("Database is empty, but no starter PDFs were found in repository.")
        return False

    logger.info("Empty database detected. Starting automatic production bootstrap with %d starter PDFs...", len(starter_pdfs))

    existing_filenames = {d["filename"] for d in get_all_documents()}
    ingested_count = 0

    for pdf_path in starter_pdfs:
        filename = pdf_path.name
        if filename in existing_filenames:
            logger.info("Skipping %s (already in database)", filename)
            continue

        dest_path = UPLOAD_DIR / filename
        if pdf_path.resolve() != dest_path.resolve():
            try:
                shutil.copy2(str(pdf_path), str(dest_path))
            except Exception as e:
                logger.error("Failed to copy starter PDF %s to upload dir: %s", filename, e)
                # Fallback to original path if copy fails
                dest_path = pdf_path

        try:
            logger.info("Bootstrapping starter document: %s", filename)
            result = process_pdf_fn(str(dest_path), filename)
            existing_filenames.add(filename)
            ingested_count += 1
            logger.info(
                "Successfully bootstrapped %s: %d facts, %d relationships",
                filename,
                result.get("facts_extracted", 0),
                result.get("relationships_detected", 0),
            )
        except Exception as e:
            logger.exception("Failed to bootstrap starter PDF %s: %s", filename, e)

    logger.info("Production bootstrap completed. Ingested %d starter documents.", ingested_count)
    return True
