import os
from pathlib import Path
import re

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from printmeup import printmeup as pm


class WebScrapeProcessor:
    
    def __init__(self):
        self.default_chunk_size = int(os.getenv("CHUNK_SIZE", "600"))
        self.default_chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "120"))

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

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