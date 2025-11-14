# [https://console.groq.com/docs/quickstart]
# [https://console.groq.com/docs/api-reference#chat-create]
# [https://docs.trychroma.com/docs/overview/getting-started]

# IMPORTANT NOTE: Presistant CLient was used here since it's best for local db usage, MIGHT switch to another client in case we deploy
# [https://docs.trychroma.com/docs/run-chroma/persistent-client]

from typing import List, Dict, Any, Tuple
import chromadb
from groq import Groq
from config import (
    CHROMA_PATH, COLLECTION_NAME, EMBED_MODEL_NAME,
    GROQ_API_KEY, GROQ_MODEL, CIRCUIT_TUTOR_SYSTEM_PROMPT
)
from .embeddings import LocalEmbeddingFunction

#Initializtion
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)


# Get or create collection with local embedding function
collection = chroma_client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=LocalEmbeddingFunction(),
)


# Generates alternative query formulations using Groq LLM
# Improves retrieval recall by searching with multiple phrasings of the same question
def expand_query_via_groq(query: str, n: int = 4) -> List[str]:
    # 1. Check if Groq client is available
    if groq_client is None:
        return []
    # 2. Build system prompt for query reformulation
    system_prompt = (
        "Generate up to {n} concise, single-topic search reformulations for retrieving "
        "relevant material about electrical/digital circuits. One per line, no numbering."
    ).format(n=n)
    # 3. Call Groq API to generate alternative queries
    try:
        resp = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            temperature=0.2,
        )
        # 4. Parse line-separated queries from response
        text = resp.choices[0].message.content.strip()
        alts = [line.strip() for line in text.split("\n") if line.strip()]
        return alts[:n]
    except Exception as e:
        print(f"Query expansion failed: {e}")
        return []


# Retrieves relevant context chunks from ChromaDB using query embeddings
# Supports multi-query expansion and deduplication for better recall
def retrieve_context(
    question: str,
    top_k: int = 5,
    use_query_expansion: bool = True,
) -> Tuple[List[Dict], List[str]]:
    # 1. Build query list (original + expansions if enabled)
    queries = [question]
    if use_query_expansion:
        expanded = expand_query_via_groq(question, n=4)
        queries.extend(expanded)
    # 2. Query ChromaDB with all queries in parallel
    results = collection.query(
        query_texts=queries,
        n_results=top_k,
        include=["documents", "metadatas"],
    )
    # 3. Flatten and deduplicate results by (source, page, text)
    seen = set()
    contexts: List[Dict[str, Any]] = []
    for docs, metas in zip(
        results.get("documents", []),
        results.get("metadatas", [])
    ):
        for d, m in zip(docs, metas):
            # 4. Check for duplicates before adding
            key = (m.get("source"), m.get("page"), d)
            if key in seen:
                continue
            seen.add(key)
            # 5. Store context with metadata for citations
            contexts.append({
                "text": d,
                "source": m.get("source"),
                "page": m.get("page")
            })
    # 6. Return top contexts (allow extra for reranking flexibility)
    return contexts[:top_k * 2], queries


# Constructs prompt messages for Groq API with retrieved context and citation instructions
# Formats contexts with source/page metadata and instructs model to cite sources
def build_prompt(question: str, contexts: List[Dict]) -> List[Dict]:
    # 1. Format contexts with numbered citations
    lines = []
    for i, c in enumerate(contexts, start=1):
        src = c.get("source", "unknown")
        page = c.get("page", "?")
        lines.append(f"[{i}] (source: {src}, p.{page})\n{c['text']}")
    context_block = "\n\n".join(lines)
    # 2. Build citation instructions for the model
    instructions = (
        "Use only the CONTEXT to answer. If the answer is not in the CONTEXT, "
        "say you don't know. Cite with the bracketed indices like [1], [2], etc., "
        "mapping to the sources in CONTEXT."
    )
    # 3. Construct message list: system prompt, context, and user question
    system_msg = {"role": "system", "content": CIRCUIT_TUTOR_SYSTEM_PROMPT}
    context_msg = {"role": "system", "content": f"CONTEXT:\n{context_block}"}
    user_msg = {
        "role": "user",
        "content": f"{instructions}\n\nQuestion: {question}"
    }
    return [system_msg, context_msg, user_msg]


# Generates grounded answer using Groq API with retrieved context
# Validates inputs and handles errors gracefully
def generate_answer(question: str, contexts: List[Dict]) -> Dict:
    # 1. Validate Groq client availability
    if groq_client is None:
        return {"error": "GROQ_API_KEY is missing or invalid."}
    # 2. Validate context is not empty
    if not contexts:
        return {"error": "No context retrieved for question."}
    # 3. Build prompt with context and citation instructions
    messages = build_prompt(question, contexts)
    # 4. Call Groq API to generate answer
    try:
        resp = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.2,
        )
        # 5. Extract answer from response
        answer = resp.choices[0].message.content
        return {"answer": answer}
    except Exception as e:
        return {"error": f"Groq API error: {str(e)}"}

