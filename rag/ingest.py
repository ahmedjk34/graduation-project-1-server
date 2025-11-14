# server/rag/ingest.py
from pypdf._page import PageObject


import os
from typing import List, Tuple, Dict
from pypdf import PdfReader
import chromadb
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    SentenceTransformersTokenTextSplitter,
)
from config import CHROMA_PATH, COLLECTION_NAME, EMBED_MODEL_NAME
from .embeddings import LocalEmbeddingFunction


# Extracts raw text from PDF files while preserving page numbers
# Needed to track source pages for citations later
def extract_pdf_text(file_path: str) -> List[Tuple[int, str]]:
    # 1. Read PDF file
    reader = PdfReader(file_path)
    pages = []
    # 2. Extract text from each page, track page numbers
    for i, page in enumerate[PageObject](reader.pages, start=1):
        txt = page.extract_text() or ""
        txt = txt.strip()
        # 3. Only include non-empty pages
        if txt:
            pages.append((i, txt))
    return pages


# Splits text into optimal chunks using two-stage strategy 
# Coarse character-level split preserves semantic boundaries, fine token-level split optimizes for embeddings
def chunck_pages(pages: List[Tuple[int, str]]) -> List[Dict]:
    # 1. Setup character-level splitter
    # [https://docs.langchain.com/oss/javascript/integrations/splitters/index#text-splitters]
    # Splits by separators in order: paragraphs (\n\n), lines (\n), sentences (. ), words ( ), then characters.
    char_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ". ", " ", ""],
        chunk_size=1000,
        chunk_overlap=80,
    )
    # 2. Setup token-level splitter (fine, optimizes for embedding model)
    # [Note: this specific splitter is used since it can take a model name as an argument and use it to tokenize the text]
    token_splitter = SentenceTransformersTokenTextSplitter(
        model_name=EMBED_MODEL_NAME,
        tokens_per_chunk=256,
        chunk_overlap=0,
    )

    chunks: List[Dict] = []
    # 3. Process each page through both splitters
    for page_num, text in pages:
        # 4. First pass: character-level splitting
        coarse = char_splitter.split_text(text)
        for t in coarse:
            # 5. Second pass: token-level splitting
            fine = token_splitter.split_text(t)
            for piece in fine:
                piece = piece.strip()
                # 6. Skip empty chunks, preserve page number
                if not piece:
                    continue
                chunks.append({"page": page_num, "text": piece})

    return chunks


# Main ingestion pipeline: processes PDFs, chunks text, stores in ChromaDB
# Handles full directory of PDFs and returns summary statistics
def ingest_directory(data_dir: str = "./data") -> Dict:
    # 1. Initialize ChromaDB client with persistent storage
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    # 2. Get or create collection with local embedding function
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=LocalEmbeddingFunction(),
    )

    total_chunks = 0
    files_indexed = []

    # 3. Process each PDF file in directory
    for fname in sorted(os.listdir(data_dir)):
        if not fname.lower().endswith(".pdf"):
            continue

        path = os.path.join(data_dir, fname)
        print(f"Processing file {fname}")
        # 4. Extract text from PDF
        pages = extract_pdf_text(path)
        if not pages:
            print(f"Warning: No text extracted from {fname}")
            continue
        # 5. Chunk the extracted text
        chunks = chunck_pages(pages)
        if not chunks:
            print(f"Warning: No chunks created from {fname}")
            continue

        # 6. Prepare data structures for ChromaDB upsert
        ids, docs, metas = [], [], []
        for i, c in enumerate(chunks):
            # 7. Create unique ID, store text and metadata
            ids.append(f"{fname}::p{c['page']}::c{i}")
            docs.append(c["text"])
            metas.append({
                "source": fname,
                "page": c["page"]
            })

        # 8. Upsert to ChromaDB and track statistics
        if ids:
            collection.upsert(ids=ids, documents=docs, metadatas=metas)
            total_chunks += len(ids)
            files_indexed.append({
                "file": fname,
                "pages": len(pages),
                "chunks": len(ids)
            })
            print(f"Indexed {fname}: {len(pages)} pages → {len(ids)} chunks")

    # 9. Return ingestion summary
    return {
        "collection": COLLECTION_NAME,
        "storage_path": CHROMA_PATH,
        "files_indexed": files_indexed,
        "total_chunks": total_chunks,
        "count_in_collection": collection.count(),
    }
