from langchain_core.documents import Document

from .. import printmeup as pm


class WebScrapeProcessor:
    
    def __init__(self):
        pass

    def split_documents_into_chunks(self, documents: list[Document]) -> list[Document]:
        """Split documents into chunks."""
        pm.deb(f"Splitting {len(documents)} documents into chunks...")
        chunks = [] # TODO: Implement chunking logic here
        pm.deb(f"{len(chunks)} chunks created")
        return chunks

    def process_all_documents(self) -> tuple[list[Document], int]:
        """Process all documents and return list of chunks and document count."""
        documents = [] # TODO: Implement document retrieval logic here
        chunks = self.split_documents_into_chunks(documents)
        return chunks, len(chunks)