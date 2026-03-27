import json
import os
from typing import Any

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from langchain_community.chat_models import ChatOllama
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage

from printmeup import printmeup as pm
from rag.vector_store import init_vector_store_manager
from rag.web_scrape_processor import WebScrapeProcessor

_vsm = None
_retriever = None


def _ensure_runtime() -> tuple[Any, Any]:
    global _vsm, _retriever

    if _vsm is None or _retriever is None:
        _vsm, _retriever = init_vector_store_manager()

    return _vsm, _retriever


def _parse_json(request) -> dict:
    if not request.body:
        return {}

    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        raise ValueError("Request body must be valid JSON")


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


@csrf_exempt
@require_http_methods(["GET"])
def health(request):
    return JsonResponse({"status": "ok", "service": "acu-chatbot-api"})


@csrf_exempt
@require_http_methods(["POST"])
def ingest(request):
    try:
        payload = _parse_json(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        vsm, _ = _ensure_runtime()

        documents_payload = payload.get("documents", [])
        if documents_payload:
            documents: list[Document] = []
            for index, item in enumerate(documents_payload, start=1):
                content = str(item.get("content", "")).strip()
                if not content:
                    continue
                documents.append(
                    Document(
                        page_content=content,
                        metadata={
                            "title": item.get("title", f"Custom Document {index}"),
                            "source": item.get("source", "manual_input"),
                            "ingestion_type": "api_payload",
                        },
                    )
                )

            if not documents:
                return JsonResponse(
                    {"error": "No valid documents found in payload"},
                    status=400,
                )

            ok = vsm.add_documents(documents)
            return JsonResponse(
                {
                    "status": "ingested" if ok else "failed",
                    "documents_received": len(documents_payload),
                    "documents_ingested": len(documents),
                    "mode": "payload",
                },
                status=200 if ok else 500,
            )

        processor = WebScrapeProcessor()
        chunks, doc_count = processor.process_all_documents()
        ok = vsm.add_chunks(chunks)

        return JsonResponse(
            {
                "status": "ingested" if ok else "failed",
                "documents_ingested": doc_count,
                "chunks_ingested": len(chunks),
                "mode": "demo_seed",
            },
            status=200 if ok else 500,
        )
    except Exception as exc:
        pm.err(e=exc, m="Ingest endpoint failed")
        return JsonResponse(
            {
                "error": "Ingestion failed",
                "details": str(exc),
            },
            status=500,
        )


@csrf_exempt
@require_http_methods(["POST"])
def chat(request):
    try:
        payload = _parse_json(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    question = str(payload.get("question", "")).strip()
    if not question:
        return JsonResponse({"error": "question is required"}, status=400)

    try:
        _, retriever = _ensure_runtime()

        docs = retriever.invoke(question)
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
                        f"Question: {question}\n\n"
                        f"Context:\n{context_text}\n\n"
                        "Provide a helpful answer and refer to source names naturally."
                    )
                ),
            ]
        )
        answer_text = str(getattr(response, "content", "")).strip()

        return JsonResponse(
            {
                "question": question,
                "answer": answer_text,
                "sources": sources,
            }
        )
    except Exception as exc:
        pm.err(e=exc, m="Chat endpoint failed")
        return JsonResponse(
            {
                "error": "LLM service unavailable or request failed",
                "details": str(exc),
            },
            status=503,
        )
