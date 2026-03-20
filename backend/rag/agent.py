import os
from typing import Annotated

from langchain.agents import create_agent
from langchain_community.chat_models import ChatOllama
from langchain_core.vectorstores import VectorStoreRetriever
from langchain.tools import tool

from .. import printmeup as pm

DEFAULT_ACADEMIC_AGENT_MODEL_ID = os.getenv("ACADEMIC_AGENT_MODEL_ID", "qwen2.5:3b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")

SYSTEM_PROMPT = """You are a academic information assistant.

Answer clearly and safely.
If tool output includes retrieved chunks, synthesize them into a coherent response.
Always include a short Sources section when sources are available.
Do not mention internal tools.
"""


_retriever: VectorStoreRetriever | None = None
_latest_sources: list[dict] | None = None


def set_retriever(retriever: VectorStoreRetriever | None) -> None:
	global _retriever
	_retriever = retriever


def get_retriever() -> VectorStoreRetriever | None:
	return _retriever


def _store_sources(sources: list[dict] | None) -> None:
	global _latest_sources
	_latest_sources = sources


def get_latest_sources() -> list[dict] | None:
	return _latest_sources


@tool
def search_academic_documents(
	query: Annotated[str, "academic question or topic to search for"],
) -> str:
	"""Search web-scraped academic knowledge using the configured retriever."""
	retriever = get_retriever()

	if retriever is None:
		return "academic document search is currently unavailable."

	try:
		pm.inf(f"Searching academic documents for: {query}")
		docs = retriever.invoke(query)

		if not docs:
			_store_sources(None)
			return "No relevant academic documents found for your query."

		_store_sources(
			[
				{
					"source": doc.metadata.get("source", doc.metadata.get("url", "Unknown")),
					"page": doc.metadata.get("page", ""),
					"content": doc.page_content[:200],
				}
				for doc in docs[:3]
			]
		)

		# Return raw chunks so the agent model can synthesize one final answer.
		result_parts = ["RETRIEVED academic DOCUMENTS:\n"]
		for i, doc in enumerate(docs[:5], 1):
			source_name = doc.metadata.get("source", doc.metadata.get("url", "Unknown"))
			page = doc.metadata.get("page", "")
			source_label = f"{source_name} (Page {page})" if page else str(source_name)
			result_parts.append(f"[Document {i} - {source_label}]")
			result_parts.append(doc.page_content)
			result_parts.append("")

		result_parts.append("SOURCES:")
		src_idx = 1
		seen_listed: set[str] = set()
		for doc in docs[:5]:
			source_name = doc.metadata.get("source", doc.metadata.get("url", "Unknown"))
			page = doc.metadata.get("page", "")
			key = f"{source_name}_{page}"
			if key in seen_listed:
				continue
			seen_listed.add(key)
			label = f"{source_name} (Page {page})" if page else str(source_name)
			result_parts.append(f"{src_idx}. {label}")
			src_idx += 1

		return "\n".join(result_parts)
	except Exception as e:
		pm.err(e=e, m=f"Error searching documents for '{query}'")
		return f"Error searching documents: {str(e)}"


def create_academic_agent(
	model_id: str = DEFAULT_ACADEMIC_AGENT_MODEL_ID,
	retriever: VectorStoreRetriever | None = None,
):
	"""Create a minimal academic agent with one RAG tool."""
	if retriever is not None:
		set_retriever(retriever)

	model = ChatOllama(
		model=model_id,
		base_url=OLLAMA_BASE_URL,
		temperature=0,
	)


	agent = create_agent(
		model=model,
		tools=[search_academic_documents],
		system_prompt=SYSTEM_PROMPT,
	)
	pm.suc("academic agent created")
	return agent
