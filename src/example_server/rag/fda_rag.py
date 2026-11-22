from functools import lru_cache
import re
import math
from pathlib import Path

import pymupdf as fitz
import requests
from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

PDF_URL = "https://www.fda.gov/media/167056/download"

WEB_URL = (
    "https://www.fda.gov/drugs/"
    "food-and-drug-administration-overdose-prevention-framework/"
    "opioid-medications"
)
DATA_DIR = Path(__file__).resolve().parents[3] / "data"

PDF_PATH = DATA_DIR / "opioid_label_updates.pdf"


def chunk_text(text, max_words=180, overlap=35):
    words = text.split()
    step = max_words - overlap

    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + max_words])
        if chunk:
            yield chunk


def pdf_chunks(pdf_path):
    """Page-aware passages with explicit table headings and page provenance."""
    document = fitz.open(str(pdf_path))
    chunks = []
    try:
        for page_num, page in enumerate(document, start=1):
            text = page.get_text("text", sort=True)
            text = re.sub(r"[ \t]+", " ", text)
            if not text.strip():
                continue
            table_headers = re.findall(r"Table\s+\d+\s*:\s*[^\n]{0,100}", text, re.I)
            heading = " | ".join(table_headers[:4]) or "FDA opioid label updates"
            words = text.split()
            max_words, overlap = 230, 65
            for start in range(0, len(words), max_words - overlap):
                segment = words[start:start + max_words]
                if not segment:
                    break
                chunks.append({
                    "text": " ".join(segment), "page": page_num,
                    "table_heading": heading,
                    "source": PDF_URL, "source_type": "pdf",
                    "title": "FDA Opioid Label Updates",
                })
                if start + max_words >= len(words):
                    break
    finally:
        document.close()
    return chunks


def download_pdf():
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"FDA PDF not found at: {PDF_PATH}")
    return pdf_chunks(PDF_PATH)


def download_webpage():
    """Scrape the FDA Opioid Medications webpage."""

    headers = {"User-Agent": "FDA-Research-RAG/1.0", "Accept": "text/html"}

    response = requests.get(WEB_URL, headers=headers, timeout=30)

    print("Requested URL:", WEB_URL)
    print("Final URL:", response.url)
    print("HTTP status:", response.status_code)

    response.raise_for_status()

    # Detect FDA website protection redirects
    if (
        "abuse-detection" in response.url.lower()
        or "apology_objects" in response.url.lower()
    ):
        raise RuntimeError(
            "FDA blocked automated webpage access. Cannot safely scrape this page."
        )

    soup = BeautifulSoup(response.text, "html.parser")

    main = soup.find("main") or soup.find("article")

    if main is None:
        raise ValueError("FDA article content could not be located.")

    # Remove non-article content
    for element in main.select("script, style, nav, footer, header, form, aside"):
        element.decompose()

    # Extract paragraphs and headings
    elements = main.find_all(["h1", "h2", "h3", "p", "li"])

    paragraphs = [
        element.get_text(" ", strip=True)
        for element in elements
        if element.get_text(" ", strip=True)
    ]

    text = "\n".join(paragraphs)

    if len(text) < 200:
        raise ValueError("Insufficient FDA article content extracted.")

    chunks = []

    for chunk in chunk_text(text):
        chunks.append(
            {
                "text": chunk,
                "page": None,
                "source": WEB_URL,
                "source_type": "web",
                "title": "FDA Opioid Medications",
            }
        )

    print("Webpage chunks created:", len(chunks))

    return chunks


@lru_cache(maxsize=2)
def build_indexes(source_type):

    if source_type == "pdf":
        chunks = download_pdf()

    elif source_type == "web":
        chunks = download_webpage()

    else:
        raise ValueError(f"Unsupported source type: {source_type}")

    if not chunks:
        raise ValueError(f"No content extracted from {source_type}")

    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))

    matrix = vectorizer.fit_transform([chunk["text"] + " " + chunk.get("table_heading", "") for chunk in chunks])

    return chunks, vectorizer, matrix


def _rank_matches(query, chunks, vectorizer, matrix, top_k=5):
    """Hybrid lexical/TF-IDF retrieval, with coverage across distinct pages."""
    import numpy as np
    query_vector = vectorizer.transform([query])
    tfidf = cosine_similarity(query_vector, matrix)[0]
    terms = set(re.findall(r"[a-z][a-z0-9-]{2,}", query.lower()))
    stop = {"what", "which", "does", "about", "from", "with", "the", "and", "are", "for", "fda", "pdf", "opioid", "label", "updates", "document", "say", "recommendation"}
    terms -= stop
    # Preserve exact multiword medical terms as a tie-breaker.
    phrases = [phrase for phrase in ("accidental ingestion", "dose escalation", "hyperalgesia", "allodynia", "neonatal opioid withdrawal", "respiratory depression", "safe storage", "disposal") if phrase in query.lower()]
    scored = []
    for idx, chunk in enumerate(chunks):
        body = (chunk["text"] + " " + chunk.get("table_heading", "")).lower()
        covered = sum(bool(re.search(r"\b" + re.escape(t) + r"\b", body)) for t in terms)
        coverage = covered / len(terms) if terms else 0.0
        phrase = sum(p in body for p in phrases) / len(phrases) if phrases else 0.0
        score = 0.72 * float(tfidf[idx]) + 0.20 * coverage + 0.08 * phrase
        if score > 0:
            scored.append((score, idx))
    scored.sort(reverse=True)
    chosen = []
    page_counts = {}
    limit = max(1, min(int(top_k), 10))
    # Prefer distinct pages when candidates have comparable scores.
    while scored and len(chosen) < limit:
        best_position = max(range(len(scored)), key=lambda j: scored[j][0] - 0.045 * page_counts.get(chunks[scored[j][1]].get("page"), 0))
        score, idx = scored.pop(best_position)
        chunk = chunks[idx]
        chosen.append({**chunk, "score": round(score, 4), "chunk_id": idx})
        page_counts[chunk.get("page")] = page_counts.get(chunk.get("page"), 0) + 1
    return chosen


def search_pdf_file(pdf_path, query, top_k=5):
    """Use the same retrieval logic for the evaluation evidence baseline."""
    chunks = pdf_chunks(pdf_path)
    if not chunks:
        return []
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    matrix = vectorizer.fit_transform([c["text"] + " " + c.get("table_heading", "") for c in chunks])
    return _rank_matches(query, chunks, vectorizer, matrix, top_k)


def search_fda_source(query, source_type, top_k=5):
    if not query.strip():
        return {"success": False, "error": "Search query cannot be empty."}
    if source_type not in ("pdf", "web"):
        return {"success": False, "error": "Invalid source type."}
    try:
        chunks, vectorizer, matrix = build_indexes(source_type)
        matches = _rank_matches(query, chunks, vectorizer, matrix, top_k)
        return {"success": True, "query": query, "matches": matches,
                "message": "No relevant passages found." if not matches else None}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
