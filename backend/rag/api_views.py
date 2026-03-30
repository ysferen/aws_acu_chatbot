import os
from typing import Any

from langchain_community.chat_models import ChatOllama
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage

from rag.vector_store import init_vector_store_manager
from rag.web_scrape_processor import WebScrapeProcessor

_vsm = None
_retriever = None


def _ensure_runtime() -> tuple[Any, Any]:
    global _vsm, _retriever

    if _vsm is None or _retriever is None:
        _vsm, _retriever = init_vector_store_manager()

    return _vsm, _retriever


def _docs_to_sources(docs: list[Document]) -> list[dict]:
    sources: list[dict] = []
    seen: set[str] = set()
    for doc in docs[:5]:
        source_name = str(doc.metadata.get("source", doc.metadata.get("url", "Unknown")))
        page = str(doc.metadata.get("page", ""))
        key = f"{source_name}:{page}"
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            {
                "source": source_name,
                "page": page,
                "content": doc.page_content[:200],
            }
        )
    return sources


def health_status() -> dict:
    return {"status": "ok", "service": "acu-chatbot-api"}


def ingest_documents(documents_payload: list[dict]) -> dict:
    vsm, _ = _ensure_runtime()
    if not isinstance(documents_payload, list):
        raise ValueError("documents must be a list")

    processor = WebScrapeProcessor()
    documents, stats = processor.build_documents_from_payload(documents_payload)

    if not documents:
        raise ValueError("No valid documents found in payload")

    ok = vsm.add_documents(documents)
    return {
        "status": "ingested" if ok else "failed",
        "documents_received": len(documents_payload),
        "documents_ingested": len(documents),
        "documents_skipped": len(documents_payload) - len(documents),
        "ingest_stats": stats,
        "mode": "payload",
    }


def ingest_demo_seed() -> dict:
    vsm, _ = _ensure_runtime()
    processor = WebScrapeProcessor()
    chunks, doc_count = processor.process_all_documents()
    ok = vsm.add_chunks(chunks)

    return {
        "status": "ingested" if ok else "failed",
        "documents_ingested": doc_count,
        "chunks_ingested": len(chunks),
        "mode": "demo_seed",
    }


def generate_chat_answer(question: str) -> dict:
    cleaned_question = str(question).strip()
    if not cleaned_question:
        raise ValueError("question is required")

    _, retriever = _ensure_runtime()
    docs = retriever.invoke(cleaned_question)
    sources = _docs_to_sources(docs)

    context_blocks: list[str] = []
    for idx, doc in enumerate(docs[:5], start=1):
        source_name = doc.metadata.get("source", doc.metadata.get("url", "Unknown"))
        context_blocks.append(f"[Source {idx}] {source_name}\n{doc.page_content}")

    context_text = "\n\n".join(context_blocks) if context_blocks else "No relevant sources found."

    model = ChatOllama(
        model=os.getenv("ACADEMIC_AGENT_MODEL_ID", "qwen2.5:3b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
        temperature=0,
    )

    response = model.invoke(
        [
            SystemMessage(
                content=(
                    "You are an academic assistant for Acibadem University. "
                    "Answer using the provided context. If context is insufficient, say that clearly. "
                    "Keep the answer concise and factual."
                )
            ),
            HumanMessage(
                content=(
                    f"Question: {cleaned_question}\n\n"
                    f"Context:\n{context_text}\n\n"
                    "Provide a helpful answer and refer to source names naturally."
                )
            ),
        ]
    )
    answer_text = str(getattr(response, "content", "")).strip()

    return {
        "question": cleaned_question,
        "answer": answer_text,
        "sources": sources,
    }

