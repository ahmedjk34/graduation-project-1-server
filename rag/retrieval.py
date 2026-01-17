# [https://console.groq.com/docs/quickstart]
# [https://console.groq.com/docs/api-reference#chat-create]
# [https://docs.trychroma.com/docs/overview/getting-started]

# IMPORTANT NOTE: Persistent Client was used here since it's best for local db usage
# Might switch to another client in case we deploy

# UPDATE 1: for new context retrieval with slides in mind

# CONTEXT RETRIEVAL LOGIC OVERVIEW
# This module handles retrieval of relevant content from documents (PDFs and slides)
# for question-answering tasks. Different document types are processed differently:
#
# 1. Regular PDFs / Books / Manuals:
#    - Each page becomes a "page" chunk.
#      - chunk_type = "page"
#      - Metadata includes: page number, source
#    - Retrieval is per page. No neighbor expansion.
#
# 2. Presentations (PPTX / PDF slides):
#    a) Slide chunks:
#       - chunk_type = "slide"
#       - Metadata: slide_number, deck_id, source
#       - Used for precise retrieval.
#       - Neighbor expansion optionally includes previous/next slides for context.
#
#    b) Window chunks:
#       - chunk_type = "window"
#       - Represents a range of slides: start_slide → end_slide
#       - Combines text of multiple slides for broader context.
#       - No neighbor expansion. Lower granularity, more topic coverage.
#
# 3. Retrieval Process:
#    - Step 1: Query ChromaDB for all chunk types (slide, window, page)
#    - Step 2: Deduplicate results
#    - Step 3: Expand neighboring slides if enabled (only for slide chunks)
#    - Step 4: Sort slide chunks by slide number for sequential context
#    - Step 5: Combine contexts into a structured prompt with citations
#
# TL;DR:
#    - Slides → precise, sequential context, neighbor-aware
#    - Slide windows → broader context, multiple slides, no neighbors
#    - Pages → per-page retrieval, used as-is


from typing import List, Dict, Any, Tuple, Optional
import logging
import json
import chromadb
from flask import Response

logger = logging.getLogger(__name__)
from config import (
    CHROMA_PATH, COLLECTION_NAME, EMBED_MODEL_NAME,
    GROQ_API_KEY, GROQ_MODEL
)
from .prompts import CIRCUIT_TUTOR_SYSTEM_PROMPT, QUERY_EXPANSION_SYSTEM_PROMPT, QUERY_REFORMULATION_SYSTEM_PROMPT
from .embeddings import LocalEmbeddingFunction
from utils.llm_utils import create_groq_client
from utils.conversation_storage import get_storage
from utils.conversation_builder import build_conversation_messages

# Initialize clients
groq_client = create_groq_client(GROQ_API_KEY)
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

# Get or create collection
collection = chroma_client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=LocalEmbeddingFunction(),
)


# Generates alternative query phrasings using Groq
# Helps find documents that use different wording
# Enhanced with context-awareness: uses conversation history for better query expansion
def expand_query_via_groq(
    query: str, 
    n: int = 4,
    conversation_history: Optional[List[Dict]] = None,
    rollup_memory: Optional[str] = None
) -> List[str]:
    if groq_client is None:
        return []
    
    # 1. Build context section for prompt
    context_section = ""
    if rollup_memory:
        context_section += f"\n\nPrevious conversation context:\n{rollup_memory}\n"
    
    if conversation_history:
        # Take last 4 non-system messages for context (to avoid token bloat)
        recent_messages = [msg for msg in conversation_history[-6:] if msg.get("role") != "system"][-4:]
        if recent_messages:
            context_section += "\nRecent conversation:\n"
            for msg in recent_messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")[:200]  # Truncate long messages
                context_section += f"{role.title()}: {content}\n"
    
    # 2. Build prompt for query reformulation with context
    # Add instruction if context is provided
    if context_section.strip():
        context_section += "\n\nIf conversation context is provided above, use it to make queries more specific and relevant to the ongoing conversation."
    
    system_prompt = QUERY_EXPANSION_SYSTEM_PROMPT.format(n=n, context_section=context_section)
    
    # 3. Call Groq to generate alternatives
    try:
        resp = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            temperature=0.2,
        )
        # 4. Parse line-separated queries
        text = resp.choices[0].message.content.strip()
        alts = [line.strip() for line in text.split("\n") if line.strip()]
        return alts[:n]
    except Exception as e:
        logger.warning(f"Query expansion failed: {e}")
        return []


# Reformulates contextual or ambiguous questions using conversation history
# Converts questions like "What was my previous question?" or "Which is better?" into standalone queries
def reformulate_query_with_context(
    question: str,
    conversation_history: Optional[List[Dict]] = None,
    rollup_memory: Optional[str] = None
) -> str:
    # 1. Return question as-is if no context provided
    if not conversation_history and not rollup_memory:
        return question
    
    # 2. Check if question needs reformulation based on common contextual phrases
    question_lower = question.lower().strip()
    needs_reformulation_phrases = [
        "previous", "first", "earlier", "before", "repeat",
        "which is better", "compare", "what was", "what were",
        "what did i ask", "what did i say", "earlier question",
        "my question", "that question", "the question"
    ]
    
    needs_reformulation = any(phrase in question_lower for phrase in needs_reformulation_phrases)
    
    if not needs_reformulation:
        return question
    
    # 3. Build context text from rollup memory and recent messages
    context_text = ""
    if rollup_memory:
        context_text += f"Previous conversation summary:\n{rollup_memory}\n\n"
    
    if conversation_history:
        # Get recent conversation messages (last 8 messages, excluding system messages)
        recent_messages = [msg for msg in conversation_history[-8:] if msg.get("role") != "system"]
        if recent_messages:
            context_text += "Recent conversation:\n"
            for msg in recent_messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")[:300]  # Truncate to avoid token bloat
                context_text += f"{role.title()}: {content}\n"
    
    if not context_text.strip():
        return question
    
    # 4. Validate Groq client is available
    if groq_client is None:
        logger.warning("Groq client not available, skipping query reformulation")
        return question
    
    # 5. Build reformulation prompt with context
    reformulation_prompt = f"""User's current question: {question}

{context_text}

Reformulate the user's question into a standalone, specific query that can be answered using retrieved documents.
If the question refers to something in the conversation history, replace it with the actual content.
Return ONLY the reformulated question, nothing else (no explanations, no quotes, no additional text)."""
    
    # 6. Call Groq to reformulate the question
    try:
        resp = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": QUERY_REFORMULATION_SYSTEM_PROMPT},
                {"role": "user", "content": reformulation_prompt},
            ],
            temperature=0.2,
        )
        
        reformulated = resp.choices[0].message.content.strip()
        
        # 7. Clean up response (remove quotes, take first line only)
        reformulated = reformulated.strip('"\'')
        reformulated = reformulated.split('\n')[0].strip()
        
        # 8. Validate reformulation and return
        if not reformulated or reformulated.lower() == question.lower():
            return question
        
        return reformulated
        
    except Exception as e:
        logger.warning(f"Query reformulation failed: {e}, using original question")
        return question


# Retrieves relevant chunks from ChromaDB
# Supports query expansion and neighbor expansion for slides
# If deck_ids is provided, filters results to only include chunks from those decks
# Enhanced with context-awareness: uses conversation history for better query expansion
def retrieve_context(
    question: str, 
    top_k: int = 5, 
    use_query_expansion: bool = True,
    neighbor_expansion: bool = True, 
    neighbor_range: int = 1,
    deck_ids: Optional[List[str]] = None,
    conversation_history: Optional[List[Dict]] = None,
    rollup_memory: Optional[str] = None
) -> Tuple[List[Dict], List[str]]:
    # 1. Build query list (original + expansions)
    queries = [question]
    if use_query_expansion:
        expanded = expand_query_via_groq(
            question, 
            n=4,
            conversation_history=conversation_history,
            rollup_memory=rollup_memory
        )
        queries.extend(expanded)
    
    # 2. Build where clause if deck_ids provided (for deck-specific RAG)
    where_clause = None
    if deck_ids:
        # Filter to only include slides/windows from specified decks
        # For deck-specific modes, we only want slides/windows from those decks
        where_clause = {
            "$and": [
                {"deck_id": {"$in": deck_ids}},
                {"chunk_type": {"$in": ["slide", "window"]}}
            ]
        }
    
    # 3. Query ChromaDB with all queries (with optional deck filtering)
    results = collection.query(
        query_texts=queries,
        n_results=top_k,
        where=where_clause,
        include=["documents", "metadatas"],
    )
    
    # 3. Flatten and deduplicate results
    seen = set()
    contexts = []
    slide_hits = []
    
    for docs, metas in zip(results.get("documents", []), results.get("metadatas", [])):
        for d, m in zip(docs, metas):
            # 4. Create deduplication key based on chunk type
            chunk_type = m.get("chunk_type")

            # We have three types of chunks: slide, window, and page
            # Slide chunks are chunks that are a single slide
            # Window chunks are chunks that are a range of slides
            # Page chunks are chunks that are a single page [usually from a scientific paper / book / IC manual]
            if chunk_type == "slide":
                key = (m.get("source"), m.get("deck_id"), m.get("slide_number"), chunk_type, d)
                slide_hits.append(m)
            elif chunk_type == "window":
                key = (m.get("source"), m.get("deck_id"), m.get("start_slide"), m.get("end_slide"), chunk_type, d)
            else:
                key = (m.get("source"), m.get("page"), d)
            
            if key in seen:
                continue
            seen.add(key)
            
            # 5. Build context dict with metadata
            context = {"text": d, "source": m.get("source")}
            
            if chunk_type == "slide":
                context["slide_number"] = m.get("slide_number")
                context["chunk_type"] = "slide"
            elif chunk_type == "window":
                context["start_slide"] = m.get("start_slide")
                context["end_slide"] = m.get("end_slide")
                context["chunk_type"] = "window"
            else:
                context["page"] = m.get("page")
            
            contexts.append(context)
    
    # 6. Expand neighbors for slide chunks if enabled
    if neighbor_expansion and slide_hits:
        neighbor_contexts = expand_slide_neighbors(slide_hits, neighbor_range)
        for ctx in neighbor_contexts:
            key = (ctx.get("source"), ctx.get("deck_id"), ctx.get("slide_number"), "slide", ctx.get("text"))
            if key not in seen:
                seen.add(key)
                contexts.append(ctx)
    
    # 7. Sort slide chunks by slide number
    slide_contexts = [c for c in contexts if c.get("chunk_type") == "slide"]
    other_contexts = [c for c in contexts if c.get("chunk_type") != "slide"]
    
    slide_contexts.sort(key=lambda x: (x.get("source", ""), x.get("slide_number", 0)))
    sorted_contexts = slide_contexts + other_contexts
    
    return sorted_contexts[:top_k * 2], queries


# Fetches neighboring slides for slide chunk hits
# Helps provide context when topics span multiple slides
def expand_slide_neighbors(slide_hits: List[Dict[str, Any]], neighbor_range: int = 1) -> List[Dict[str, Any]]:
    neighbor_contexts = []
    
    # 1. Group hits by deck_id
    from collections import defaultdict
    deck_slides = defaultdict(set)
    
    for hit in slide_hits:
        deck_id = hit.get("deck_id") or hit.get("source")
        slide_num = hit.get("slide_number")
        if deck_id and slide_num:
            deck_slides[deck_id].add(slide_num)
    
    # 2. Calculate which neighbor slides we need
    for deck_id, slide_numbers in deck_slides.items():
        all_needed_slides = set()
        for slide_num in slide_numbers:
            for offset in range(-neighbor_range, neighbor_range + 1):
                neighbor_slide = slide_num + offset
                if neighbor_slide > 0:
                    all_needed_slides.add(neighbor_slide)
        
        all_needed_slides -= slide_numbers
        
        if not all_needed_slides:
            continue
        
        # 3. Fetch neighbor slides from ChromaDB
        try:
            all_deck_results = collection.get(
                where={
                    "$and": [
                        {"deck_id": deck_id},
                        {"chunk_type": "slide"}
                    ]
                },
                include=["documents", "metadatas"]
            )
            
            if all_deck_results.get("documents"):
                for doc, meta in zip(all_deck_results.get("documents", []), all_deck_results.get("metadatas", [])):
                    slide_num = meta.get("slide_number")
                    if slide_num and slide_num in all_needed_slides:
                        neighbor_contexts.append({
                            "text": doc,
                            "source": meta.get("source"),
                            "deck_id": meta.get("deck_id"),
                            "slide_number": slide_num,
                            "chunk_type": "slide",
                        })
        except Exception as e:
            logger.warning(f"Metadata filtering failed: {e}")
            try:
                # Fallback: fetch all and filter client-side
                all_results = collection.get(include=["documents", "metadatas"])
                if all_results.get("documents"):
                    for doc, meta in zip(all_results.get("documents", []), all_results.get("metadatas", [])):
                        if (meta.get("deck_id") == deck_id and meta.get("chunk_type") == "slide"):
                            slide_num = meta.get("slide_number")
                            if slide_num and slide_num in all_needed_slides:
                                neighbor_contexts.append({
                                    "text": doc,
                                    "source": meta.get("source"),
                                    "deck_id": meta.get("deck_id"),
                                    "slide_number": slide_num,
                                    "chunk_type": "slide",
                                })
            except Exception as e2:
                logger.error(f"Failed to fetch slide neighbors: {e2}")
    
    return neighbor_contexts


# Gets ALL slides from one or more specific decks (no semantic search)
# Returns all slides sorted by deck_id and slide number
# Used for quiz generation where we need comprehensive content
def get_all_slides_from_decks(deck_ids: List[str]) -> List[Dict]:
    all_slides = []
    
    # 1. Query ChromaDB for all slide chunks from each deck
    for deck_id in deck_ids:
        try:
            results = collection.get(
                where={
                    "$and": [
                        {"deck_id": deck_id},
                        {"chunk_type": "slide"}
                    ]
                },
                include=["documents", "metadatas"]
            )
            
            # 2. Process results into structured format
            for doc, meta in zip(results.get("documents", []), results.get("metadatas", [])):
                all_slides.append({
                    "text": doc,
                    "source": meta.get("source"),
                    "deck_id": meta.get("deck_id"),
                    "slide_number": meta.get("slide_number"),
                    "slide_title": meta.get("slide_title", ""),
                    "chunk_type": "slide"
                })
        except Exception as e:
            logger.error(f"Failed to fetch slides for deck {deck_id}: {e}")
            continue
    
    # 3. Sort by deck_id then slide number to maintain order
    all_slides.sort(key=lambda x: (x.get("deck_id", ""), x.get("slide_number", 0)))
    return all_slides


def build_slides_context(slides: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for slide in slides:
        text = (slide.get("text") or "").strip()
        if text:
            parts.append(text)
    return "\n\n---\n\n".join(parts).strip()


# Formats contexts into prompt for Groq
# Includes source citations (page numbers or slide numbers)
def build_prompt(question: str, contexts: List[Dict], session_id: Optional[str] = None, 
                messages_array: Optional[List[Dict]] = None) -> List[Dict]:
    # 1. Format contexts with numbered citations
    lines = []
    for i, c in enumerate(contexts, start=1):
        src = c.get("source", "unknown")
        if c.get("chunk_type") == "slide":
            slide_num = c.get("slide_number", "?")
            lines.append(f"[{i}] (source: {src}, slide {slide_num})\n{c['text']}")
        elif c.get("chunk_type") == "window":
            start_slide = c.get("start_slide", "?")
            end_slide = c.get("end_slide", "?")
            lines.append(f"[{i}] (source: {src}, slides {start_slide}-{end_slide})\n{c['text']}")
        else:
            page = c.get("page", "?")
            lines.append(f"[{i}] (source: {src}, p.{page})\n{c['text']}")
    
    context_block = "\n\n".join(lines)
    
    # 2. Build citation instructions
    instructions = (
        "Use only the CONTEXT to answer. If the answer is not in the CONTEXT, "
        "say you don't know. Cite with the bracketed indices like [1], [2], etc., "
        "mapping to the sources in CONTEXT."
    )
    
    # 3. Build base messages (system prompt + context)
    base_messages = [
        {"role": "system", "content": CIRCUIT_TUTOR_SYSTEM_PROMPT},
        {"role": "system", "content": f"CONTEXT:\n{context_block}"}
    ]
    
    # 4. Build conversation messages with rollup memory (handles session management)
    # Note: We pass question as user_message for incremental mode, and the shared function
    # will remove it from the end if present, so we can safely add the formatted version
    messages = build_conversation_messages(
        session_id=session_id,
        user_message=question if not messages_array else None,
        messages_array=messages_array,
        base_messages=base_messages
    )
    
    # 5. Add formatted question as user message (with instructions)
    # If messages_array was provided, the raw question may already be in messages from session.messages
    # The shared function removes the raw question in incremental mode, but if messages_array
    # was provided and includes the raw question, we need to replace it with the formatted version
    # Remove the last message if it's a raw user message matching the question
    if messages and messages[-1].get("role") == "user" and messages[-1].get("content") == question:
        messages.pop()
    
    # Add formatted question with instructions
    messages.append({
        "role": "user",
        "content": f"{instructions}\n\nQuestion: {question}"
    })
    
    return messages


# Generates answer using Groq with retrieved context
# Returns answer or error dict
def generate_answer(question: str, contexts: List[Dict], metadata: Dict = None,
                   session_id: Optional[str] = None, messages_array: Optional[List[Dict]] = None):
    if groq_client is None:
        return {"error": "GROQ_API_KEY is missing or invalid."}
    
    if not contexts:
        return {"error": "No context retrieved for question."}

    print("Question is: ", question, "\n\n")
    
    # 1. Build prompt with conversation history support
    messages = build_prompt(question, contexts, session_id=session_id, messages_array=messages_array)
    
    # 2. Call Groq API
    try:
        resp = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.2,
            stream=True,
        )
    except Exception as e:
        return {"error": f"Groq API error: {str(e)}"}
    
    # Accumulator for storing full assistant response
    assistant_response = ""
    
    def SSE():
        nonlocal assistant_response
        # Send metadata first if provided
        if metadata:
            yield f"event: metadata\ndata: {json.dumps(metadata)}\n\n"
        
        try:
            for chunk in resp:
                content = getattr(getattr(chunk.choices[0], "delta", None), "content", None)
                if content:
                    # Convert em-spaces to newlines as safety measure
                    content = content.replace('\u2003', '\n')
                    assistant_response += content
                    yield f"data: {json.dumps(content)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {str(e)}\n\n"
        finally:
            # Store assistant response in session if session_id is provided
            if session_id and assistant_response:
                storage = get_storage()
                # Question is already stored in build_prompt for incremental mode
                storage.add_message(session_id, "assistant", assistant_response)
            
            yield "event: done\ndata: [DONE]\n\n"

    return Response(
        SSE(),
        mimetype='text/event-stream',
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )