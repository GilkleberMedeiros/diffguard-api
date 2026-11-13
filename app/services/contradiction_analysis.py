import re

from attr import dataclass
from simhash import Simhash
from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class ChunkPair:
  original_chunk: str
  revised_chunk: str

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
  added: list[str]
  removed: list[str]



class ContradictionAnalysisService:

  @staticmethod
  def structurally_split_document(doc: str) -> list[str]:
    text_splitter = RecursiveCharacterTextSplitter(
      chunk_size=1500,
      chunk_size_alignment=False,
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

    chunks = text_splitter.split_text(doc)
    return chunks

  @staticmethod
  def classify_chunks(original_doc: list[str], revised_doc: list[str]):
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
      return list(filter(text))

    o_doc = [ (chunk, Simhash(tokenizer(chunk))) for chunk in original_doc ]
    r_doc = [ (chunk, Simhash(tokenizer(chunk))) for chunk in revised_doc ]

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

      # Remove r_doc chunk idx from non paired IDXs list
      r_doc_chunks_non_paired.remove(most_similar_chunk_idx)

      # Add Pair
      r_chunk = r_doc[most_similar_chunk_idx]
      pairs.append(ChunkPair(chunk[0], r_chunk[0]))

    # Consider as added
    for non_paired_idx in r_doc_chunks_non_paired:
      added.append(r_doc[non_paired_idx][0])
    
    return DocumentsRevision(pairs, added, removed)

  @staticmethod
  def delta_filter(original_doc: list[str], revised_doc: list[str]) -> list[int]:
    """
    Retorna uma lista de índices que corresponde aos índices dos chunks do documento 
    revisado que são diferentes dos mesmos chunks (mesmo índice) do documento original.
    """
    if len(original_doc) != len(revised_doc):
      raise Exception("Filtro delta não consegue processar listas com tamanhos diferentes!")

    diff_idxs = []

    for idx in range(len(original_doc)):
      o_chunk = original_doc[idx]
      r_chunk = revised_doc[idx]
      if o_chunk != r_chunk:
        diff_idxs.append(idx)

    return diff_idxs
