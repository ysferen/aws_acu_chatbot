import os
import re
import hashlib

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from printmeup import printmeup as pm


class WebScrapeProcessor:
    
    def __init__(self):
        self.default_chunk_size = int(os.getenv("CHUNK_SIZE", "600"))
        self.default_chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "120"))
        self.min_content_length = int(os.getenv("MIN_CONTENT_LENGTH", "40"))

    def _normalize_text(self, text: str) -> str:
        # Remove control chars and collapse whitespace to keep embeddings stable.
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", str(text))
        return re.sub(r"\s+", " ", cleaned).strip()

    def _normalize_source(self, source: str) -> str:
        normalized = str(source).strip()
        return normalized or "manual_input"

    def _content_fingerprint(self, source: str, content: str) -> str:
        return hashlib.sha256(f"{source}|{content.lower()}".encode("utf-8")).hexdigest()

    def build_documents_from_payload(self, items: list[dict]) -> tuple[list[Document], dict]:
        """Validate, clean, and deduplicate ingestion payload into LangChain documents."""
        stats = {
            "received": len(items),
            "accepted": 0,
            "skipped_non_dict": 0,
            "skipped_empty": 0,
            "skipped_too_short": 0,
            "skipped_duplicate": 0,
        }

        documents: list[Document] = []
        seen_fingerprints: set[str] = set()

        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                stats["skipped_non_dict"] += 1
                continue

            cleaned_content = self._normalize_text(item.get("content", ""))
            if not cleaned_content:
                stats["skipped_empty"] += 1
                continue

            if len(cleaned_content) < self.min_content_length:
                stats["skipped_too_short"] += 1
                continue

            source = self._normalize_source(item.get("source", "manual_input"))
            fingerprint = self._content_fingerprint(source, cleaned_content)
            if fingerprint in seen_fingerprints:
                stats["skipped_duplicate"] += 1
                continue
            seen_fingerprints.add(fingerprint)

            title = self._normalize_text(item.get("title", "")) or f"Custom Document {index}"
            documents.append(
                Document(
                    page_content=cleaned_content,
                    metadata={
                        "title": title,
                        "source": source,
                        "ingestion_type": "api_payload",
                    },
                )
            )

        stats["accepted"] = len(documents)
        return documents, stats

    def _build_demo_documents(self) -> list[Document]:
        # Demo-safe starter set for first-stage ingestion.
        raw_docs = [
            {
                "title": "ACU General Overview",
                "source": "https://www.acibadem.edu.tr",
                "content": (
                    "Acibadem University is a foundation university in Istanbul. "
                    "The university provides undergraduate and graduate education in multiple disciplines "
                    "with a strong focus on health sciences and technology."
                ),
            },
            {
                "title": "Admission and Application Context",
                "source": "https://www.acibadem.edu.tr/en/prospective-students",
                "content": (
                    "Prospective students can find admission-related announcements, application details, "
                    "and program-specific requirements on the official university website."
                ),
            },
            {
                "title": "Bologna Information System",
                "source": "https://obs.acibadem.edu.tr",
                "content": (
                    "The Bologna information system provides curriculum data, course descriptions, "
                    "credit information, and learning outcomes for academic programs."
                ),
            },
            {
                "title": "Campus and Student Life",
                "source": "https://www.acibadem.edu.tr/en/life-at-acibadem",
                "content": (
                    "Campus life pages include information on student services, social opportunities, "
                    "and support resources available at Acibadem University."
                ),
            },
        ]

        documents: list[Document] = []
        for item in raw_docs:
            cleaned = self._normalize_text(item["content"])
            documents.append(
                Document(
                    page_content=cleaned,
                    metadata={
                        "title": item["title"],
                        "source": item["source"],
                        "ingestion_type": "demo_seed",
                    },
                )
            )
        return documents

    def split_documents_into_chunks(self, documents: list[Document]) -> list[Document]:
        """Split documents into chunks."""
        pm.deb(f"Splitting {len(documents)} documents into chunks...")
        if not documents:
            return []

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.default_chunk_size,
            chunk_overlap=self.default_chunk_overlap,
        )
        chunks = splitter.split_documents(documents)
        pm.deb(f"{len(chunks)} chunks created")
        return chunks

    def process_all_documents(self) -> tuple[list[Document], int]:
        """Process all documents and return list of chunks and document count."""
        documents = self._build_demo_documents()
        chunks = self.split_documents_into_chunks(documents)
        return chunks, len(documents)