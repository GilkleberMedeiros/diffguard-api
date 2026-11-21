import re

from attr import dataclass
from simhash import Simhash
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.dtos import Document, DocumentChunk
from app.services.ml_models import MLModelsService


@dataclass
class ChunkPair:
  original_chunk: DocumentChunk
  revised_chunk: DocumentChunk

@dataclass
class DocumentsRevision: 
  """
  **pairs**: Pairs of text chunks from original and revised document that are basically the same 
  the same text with minimal changes. \n
  **added**: Chunks of text that weren't present on original document but were added on 
  revised version. \n
  **removed**: Chunks of text that were present on original document but got removed 
  from revised version. \n 
  """

  pairs: list[ChunkPair]
  added: list[DocumentChunk]
  removed: list[DocumentChunk]



class ContradictionAnalysisService:

  @staticmethod
  def structurally_split_document(doc: Document):
    text_splitter = RecursiveCharacterTextSplitter(
      chunk_size=1500,
      chunk_overlap=200,
      separators=[
        "\n\nCLÁUSULA",
        "\n\nARTIGO",
        "\n\nSEÇÃO",
        "\n\n",
        "\n",
        " ",
        ""
      ]
    )

    chunks = text_splitter.split_text(doc.page_content)
    doc.chunks = [ 
      DocumentChunk(metadata={"chunk_index": i}, page_content=chunks[i]) 
      for i in range(len(chunks)) 
    ]
    return doc

  @staticmethod
  def classify_chunks(original_doc: Document, revised_doc: Document):
    """
    Classifica os chunks comparando os documentos. Pode classificar os chunks em 
    pares (par entre chunk do documento original e chunk do documento revisado), 
    adicionados (chunks de texto adicionado no documento revisado que não 
    estavam presentes no doc original) e removidos (chunks de texto presentes no 
    documento original, mas removidos no doc revisado).  

    1. Realiza o hash de todos os chunks (dos dois documentos). 
    2. Faz uma pesquisa, verificando cada chunk do documento original contra 
    cada outro chunk do documento revisado. 
    3. Se a pesquisa encontrar um chunk do documento revisado que possui 70% 
    ou mais de similaridade de palavras com o chunk do documento original, o 
    algoritmo salva eles como pares (Não para a análise quando acha 70% de 
    similaridade, continua até achar o mais similar). Se, mesmo assim, a pesquisa não 
    encontrar nenhuma par para um chunk Y do documento original, considerar 
    aquele chunk como deletado. Os chunks que sobrarem no documento revisado 
    (não tiverem formado par), considerar como adicionados. 
    """
    MINIMUM_CHUNK_SIMILARITY = 70 # (%)
    HASH_BITS_SIZE = 64
    pairs = []
    added = []
    removed = []

    def tokenizer(texto: str):
      text = re.findall(r"\w+", texto.lower())
      return list(filter(None, text))

    if original_doc.chunks is None or revised_doc.chunks is None:
      raise Exception("A classificação de chunks precisa que os documentos contenham seus respectivos chunks!")

    o_doc = [ 
      (chunk, Simhash(tokenizer(chunk.page_content))) 
      for chunk in original_doc.chunks 
    ]
    r_doc = [ 
      (chunk, Simhash(tokenizer(chunk.page_content))) 
      for chunk in revised_doc.chunks 
    ]

    r_doc_chunks_non_paired = list(range(len(r_doc)))
    for chunk in o_doc:
      most_similar_chunk_idx = None
      most_similar_chunk_similarity = -1
      for idx in range(len(r_doc)):
        r_chunk = r_doc[idx]
        distance = chunk[1].distance(r_chunk[1])
        similarity = 100 - ((distance / HASH_BITS_SIZE) * 100)
        if (similarity > most_similar_chunk_similarity and 
            similarity >= MINIMUM_CHUNK_SIMILARITY):
          most_similar_chunk_idx = idx 
          most_similar_chunk_similarity = similarity

      # Consider as removed
      if most_similar_chunk_idx is None:
        removed.append(chunk[0])
        continue

      # Remove r_doc chunk idx from non paired IDXs list
      if most_similar_chunk_idx in r_doc_chunks_non_paired:
        r_doc_chunks_non_paired.remove(most_similar_chunk_idx)

      # Add Pair
      r_chunk = r_doc[most_similar_chunk_idx]
      pairs.append(ChunkPair(chunk[0], r_chunk[0]))

    # Consider as added
    for non_paired_idx in r_doc_chunks_non_paired:
      added.append(r_doc[non_paired_idx][0])
    
    return DocumentsRevision(pairs, added, removed)

  @staticmethod
  def delta_filter(original_doc: list[DocumentChunk], revised_doc: list[DocumentChunk]) -> list[int]:
    """
    Retorna uma lista de índices que corresponde aos índices dos chunks do documento 
    revisado que são diferentes dos mesmos chunks (com mesmo índice) do documento original.
    """
    if len(original_doc) != len(revised_doc):
      raise Exception("Filtro delta não consegue processar listas com tamanhos diferentes!")

    diff_idxs = []

    for idx in range(len(original_doc)):
      o_chunk = original_doc[idx]
      r_chunk = revised_doc[idx]
      if o_chunk.page_content != r_chunk.page_content:
        diff_idxs.append(idx)

    return diff_idxs

  @staticmethod
  def get_chunks_references(
    revised_doc: list[DocumentChunk], 
    mod_or_added_chunks: list[DocumentChunk]
  ) -> list[tuple[DocumentChunk, list[DocumentChunk]]]: 
    """
    Dado os chunks de texto que foram modificados (ou adicionados) do documento 
    original para a versão revisada: Procure, em todo o texto do 
    documento revisado refências aos chunks modificados (ou adicionados) ou trechos  
    aos quais os chunks modificados (ou adicionados) fazem referência. 

    :returns: Cada chunk modificado acompanhado de uma lista de chunks referenciados. 
    """
    from langchain_chroma import Chroma

    embedder = MLModelsService.get_main_embeddings_model()

    # Constroí Vector Store temporário eliminando chunks duplicados
    texts = []
    metadatas = []
    mod_or_added_texts = { chunk.page_content for chunk in mod_or_added_chunks }
    for chunk in revised_doc:
      if chunk.page_content not in mod_or_added_texts:
        texts.append(chunk.page_content)
        metadatas.append(chunk.metadata)
      
    vstore = Chroma.from_texts(texts=texts, embedding=embedder, metadatas=metadatas)

    # Realizar as buscas por referências cruzadas
    k = 7
    mapped_references = []
    for chunk in mod_or_added_chunks:
      results = vstore.similarity_search_with_score(chunk.page_content, k)
      results = [ 
        DocumentChunk.from_lc_document(r[0])
        for r in results 
      ]
      mapped_references.append(tuple([chunk, results]))

    return mapped_references

  @staticmethod
  def build_context_windows(
    mapped_references: list[tuple[DocumentChunk, list[DocumentChunk]]], 
    window_size: int | None = 1
  ): 
    """
    Constrói as janelas de contexto contendo os chunks alterados/adicionados e 
    referências à serem enviadas ao modelo llm para análise. 

    #### As janelas de contexto retornadas seguem o seguinte formato: \n
    \"""\n
    \## Trecho Alterado #1\n
    Trecho/Chunk do texto do documento revisado que foi alterado ou 
    adicionado quando comparado com equivalente do documento original. \n\n

    \### Trechos que fazem referência ou são referenciados pelo Trecho 
    Alterado #1: \n\n

    \----------\n\n

    \##### Referência #1\n
    Trecho referencidado no trecho alterado que pode estar desatualizado. \n\n

    \##### Referência #2\n
    ... \n\n

    \n======================================== (Se window_size > 1)\n\n

    \## Trecho Alterado #2\n
    ...\n
    \"""

    :param mapped_references: O chunks alterados/adicionados com suas referências mapeadas.
    :param window_size: Determina Quantos chunks (+ suas referências) serão colocados 
    em cada janela. 

    :returns: Lista contendo as janelas em formato string com chunks e  
    referências formatadas.  
    """

    windows = []
    step = window_size if window_size > 1 else len(mapped_references)
    for idx in range(0, len(mapped_references), step):
      maps = mapped_references[idx:idx+step]

      window = ""
      for i in range(len(maps)):
        window += f"## Trecho Alterado #{i+1}\n"
        window += maps[i][0].page_content + "\n\n"

        refs = maps[i][1]
        for j in range(len(refs)): 
          window += f"### Trechos que fazem referência ou são referenciados pelo Trecho Alterado #{i+1}:\n\n"
          window += "----------\n\n"
          window += f"##### Referência #{j+1}\n"
          window += refs[j].page_content + "\n\n"

        if len(maps) > 1:
          window += "\n========================================\n\n"

      windows.append(window)

    return windows
