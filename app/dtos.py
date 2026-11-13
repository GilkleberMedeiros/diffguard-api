from pydantic import BaseModel, Field



class DocumentChunk(BaseModel):
  content: str = Field(min_length=1)

  metadata: dict[str, any]


class Document(BaseModel):
  content: str = Field(min_length=1)
  chunks: list[DocumentChunk] | None = None

  metadata: dict[str, any]

