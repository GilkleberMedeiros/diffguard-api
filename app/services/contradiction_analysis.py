import re

from attr import dataclass
from simhash import Simhash
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.dtos import Document, DocumentChunk
from app.schemas.response import ContradictionResult
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

  SYSTEM_PROMPT = """Você é o motor central de auditoria lógica e detecção de contradições do DiffGuard, especializado em análise crítica de documentos técnicos, contratos, normas e trabalhos acadêmicos (TCCs).

  Sua missão é realizar uma análise rigorosa, cética e minuciosa dos blocos de alteração fornecidos. Cada bloco contém um **Trecho Alterado** e suas respectivas **Referências** (trechos inalterados do documento que possuem dependência explícita ou semântica com ele).

  DIRETRIZES DE ANÁLISE:
  1. **Rigor Lógico e Ceticismo:** Não assuma que a alteração é válida ou coerente. Procure ativamente por brechas, inversões de obrigações (ex: "deve" vs. "não deve"), conflitos de prazos, valores numéricos, escopos, condições ou penalidades entre o Trecho Alterado e cada uma das Referências listadas.
  2. **Conflitos Múltiplos:** Se um mesmo Trecho Alterado entrar em conflito com mais de uma Referência diferente, você deve gerar um item separado no JSON para cada conflito detectado. O mesmo vale para conflitos de Trechos Alterados diferentes.
  3. **Classificação de Severidade:**
    - `"high"`: Incompatibilidade direta que gera quebra de contrato, violação de norma regulamentadora, anulação de obrigações fundamentais ou impossibilidade lógica/técnica de execução.
    - `"medium"`: Ambiguidade severa ou desalinhamento de prazos, marcos ou valores que exige reescrita urgente para evitar litígios ou falhas sistêmicas.
    - `"low"`: Desalinhamento menor de terminologia ou inconsistência formal que não altera a essência jurídica ou técnica, mas prejudica a clareza.
  4. **Ausência de Conflitos:** Se, após analisar criticamente um Trecho Alterado e suas referências, você não encontrar nenhum conflito relevante (pelo menos de nível `"low"`), **não crie itens falsos**. 

  RETORNO ESPERADO:
  Siga o schema JSON estruturado informado abaixo. As tuplas descrevem os campos. Caso não encontre conflitos, retorne total_conflicts como 0 e items como uma lista vazia. 
  Nos campos changed_section e intact_section você deve copiar todo o texto das seções ao invés de apenas parte do texto. 
  Também, não faça referência aos identificadores do trechos (Trecho Alterado #x) e referências (Referência #x) informados no prompt que você recebeu.  
  {{
    "total_conflcts": (type: int),
    "items": [
      {{ 
        "conflict_id": (type: str, description: Identificador único do conflito (ex: 'c1').),
        "severity": (type: str[high | medium | low], description: Gravidade do conflito.), 
        "changed_section": (type: str, description: Seção alterada que originou o conflito.),
        "intact_section": (type: str, description: Seção intacta que entra em conflito."), 
        "description": (type: str, description: Descrição da natureza da contradição.),
        "recommendation": (type: str, description: Sugestão de resolução do conflito.) 
      }}
    ]
  }}
  """

  @staticmethod
  def analysis(original_document: Document, revised_document: Document, language: str):
    cls = ContradictionAnalysisService
    original_document = cls.structurally_split_document(original_document)
    revised_document = cls.structurally_split_document(revised_document)

    classified = cls.classify_chunks(original_document, revised_document)

    if len(classified.added) == 0 and len(classified.pairs) == 0:
      raise Exception("A classificação de chunks não classificou nenhum chunk como pares ou adicionados.")

    o_pairs = []
    r_pairs = []
    for pair in classified.pairs:
      o_pairs.append(pair.original_chunk)
      r_pairs.append(pair.revised_chunk)

    diff_pairs_idxs = cls.delta_filter(o_pairs, r_pairs)

    to_context_windows = []
    for idx in diff_pairs_idxs:
      to_context_windows.append(r_pairs[idx])

    to_context_windows.extend(classified.added)

    if len(to_context_windows) <= 0:
      raise Exception("Nenhum chunk para formação das janelas de contexto após filtragem.")

    to_context_windows = cls.get_chunks_references(revised_document.chunks, to_context_windows)
    
    if len(to_context_windows) <= 0:
      raise Exception("Nenhum chunk para formação das janelas de contexto após mapeamento das referências.")
    
    context_windows = cls.build_context_windows(to_context_windows)
    
    raw_system_prompt = cls.SYSTEM_PROMPT

    raw_user_prompt = """Analise os seguintes blocos de alterações e suas referências cruzadas em busca de contradições lógicas (os textos estão na seguinte língua {language}):

    {context_window}
    """.format({"language": language, "context_window": "{context_window}"})

    prompt = ChatPromptTemplate.from_messages([
      ("system", raw_system_prompt), 
      ("user", raw_user_prompt)
    ])
    llm = MLModelsService.get_main_llm_model()
    parser = JsonOutputParser(pydantic_object=ContradictionResult)
    chain = prompt | llm | parser
    result = ContradictionResult(total_conflicts=0)
    conflict_id_counter = 0
    for context in context_windows:
      r = chain.invoke({"context_window": context})

      if  hasattr(r, "model_dump"):
        r = r.model_dump()

      for conflict in r["items"]:
        conflict["conflict_id"] = f"c{conflict_id_counter}"
        result.items.append(conflict)
        result.total_conflicts += 1
        conflict_id_counter += 1

    return result

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
