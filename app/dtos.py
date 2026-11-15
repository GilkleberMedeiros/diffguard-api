from typing import Literal

from langchain_core.documents import Document as LCDocument


class DocumentChunk(LCDocument):
  """
  Document Chunk.
  """
  type: Literal["DocumentChunk"] = "DocumentChunk"

  @classmethod
  def from_lc_document(cls, doc: LCDocument): 
    return cls(id=doc.id, metadata=doc.metadata, page_content=doc.page_content, type="DocumentChunk")

class Document(LCDocument):
  """
  Full Document
  """
  chunks: list[DocumentChunk] | None = None

  @classmethod
  def from_lc_document(cls, doc: LCDocument, chunks: list[DocumentChunk] | None = None): 
    return cls(
      id=doc.id, 
      metadata=doc.metadata, 
      page_content=doc.page_content, 
      type=doc.type, chunks=chunks
    )


