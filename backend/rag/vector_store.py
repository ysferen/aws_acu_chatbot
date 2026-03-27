from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_community.embeddings import OllamaEmbeddings
from typing import List
import os

from printmeup import printmeup as pm
from .web_scrape_processor import WebScrapeProcessor 

VECTOR_STORE_PERSIST_DIR = os.getenv("VECTOR_STORE_PERSIST_DIR", "chromadb-data")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_EMBEDDING_MODEL_ID = os.getenv(
    "OLLAMA_EMBEDDING_MODEL_ID",
    "nomic-embed-text-v2-moe"
)


class VectorStoreManager:
    def __init__(
        self,
        persist_directory: str = VECTOR_STORE_PERSIST_DIR,
        embedding_model_id: str = OLLAMA_EMBEDDING_MODEL_ID,
    ):
        self.persist_directory = persist_directory
        self.embeddings = OllamaEmbeddings(
            base_url=OLLAMA_BASE_URL,
            model=embedding_model_id,
        )
        self.web_scrape_processor = WebScrapeProcessor()
        self.vectorstore = self.get_vector_store()

    def load_vectorstore(self) -> Chroma | None:
        """Load existing vector store from persist directory."""
        try:
            if os.path.exists(self.persist_directory):
                pm.deb(
                    f"Loading existing Chroma database from {self.persist_directory}..."
                )
                self.vectorstore = Chroma(
                    persist_directory=self.persist_directory,
                    embedding_function=self.embeddings,
                )
                pm.inf("Existing vector store loaded")
                return self.vectorstore
            else:
                pm.deb(f"No existing vector store found at {self.persist_directory}")
                return None
        except Exception as e:
            pm.err(e)
            return None

    def create_vectorstore(self, chunks: List[Document] | None = None) -> Chroma:
        """Create vector store from chunks."""
        doc_count = None
        if not chunks or len(chunks) == 0:
            chunks, doc_count = self.web_scrape_processor.process_all_documents()

        if not chunks:
            raise ValueError("No chunks were produced for vector store creation")

        if doc_count is not None:
            pm.inf(
                f"Creating new vector store at {self.persist_directory} with {len(chunks)} chunks from {doc_count} documents"
            )
        else:
            pm.inf(
                f"Creating new vector store at {self.persist_directory} with {len(chunks)} chunks"
            )

        self.vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=self.persist_directory,
        )
        pm.suc("New vector store created")
        return self.vectorstore

    def get_vector_store(self) -> Chroma:
        """Get vector store, loading existing or creating new if needed."""
        vectorstore = self.load_vectorstore()
        if vectorstore:
            return vectorstore
        else:
            return self.create_vectorstore()

    def add_chunks(self, chunks: List[Document]) -> bool:
        """Add new chunks to the existing vector store (incremental).

        Args:
            chunks: List of chunk objects to add.
        Returns:
            True if successful, False otherwise.
        """
        if not chunks:
            pm.war("No chunks to add to vector store")
            return False

        try:
            pm.deb(f"Adding {len(chunks)} new chunks to existing vector store...")
            self.vectorstore.add_documents(chunks)
            pm.deb(f"{len(chunks)} chunks added to vector store")
            return True
        except Exception as e:
            pm.err(e=e, m="Failed to add documents to vector store")
            return False

    def add_documents(self, documents: List[Document]) -> bool:
        pm.deb(f"Adding {len(documents)} new documents to vector store...")
        return self.add_chunks(self.web_scrape_processor.split_documents_into_chunks(documents))

    def similarity_search(self, query: str, k: int = 4) -> List[Document] | None:
        """Perform a similarity search on the vector store.

        Args:
            query (str): The query string to search for.
            k (int, optional): The number of similar documents to return. Defaults to 4.
        Returns:
            List[Document] | None: List of similar documents or None if vector store is not loaded.
        """

        return self.vectorstore.similarity_search(query, k=k)

    def get_retriever(self, k: int = 4) -> VectorStoreRetriever:
        return self.vectorstore.as_retriever(
            search_type="similarity", search_kwargs={"k": k}
        )

# * Django way
def init_vector_store_manager():
    vsm = VectorStoreManager(
        persist_directory=VECTOR_STORE_PERSIST_DIR,
        embedding_model_id=OLLAMA_EMBEDDING_MODEL_ID,
    )
    return vsm, vsm.get_retriever(k=3)

# * FastAPI way
# async def init_vector_store_manager(app):
#     loop = asyncio.get_event_loop()
#     vsm = await loop.run_in_executor(
#         None,
#         VectorStoreManager,
#         VECTOR_STORE_PERSIST_DIR,
#         HGF_EMBEDDING_MODEL_ID,
#     )
#     app.state.vsm = vsm
#     app.state.retriever = vsm.get_retriever(k=3)
#     pm.suc("Vector store initialized")
