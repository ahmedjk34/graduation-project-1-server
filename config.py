#The goal of this file is to store all the configuration for the project in one place, so that it is easy to change and manage.

import os
from dotenv import load_dotenv


load_dotenv()


GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Model used for LLM generation
GROQ_MODEL = "openai/gpt-oss-120b"

# ChromaDB Configuration
CHROMA_PATH = "./chroma_storage"
COLLECTION_NAME = "najah-circuits"

# Embedding Model Configuration
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Initial system prompt for chatbot / tutor
CIRCUIT_TUTOR_SYSTEM_PROMPT = (
    "You are a domain-specific AI tutor for electrical & digital circuits. "
    "Answer with clear, step-by-step reasoning, and only use the provided context. "
    "If the answer is not contained in the context, say you don't know. "
    "Cite sources as [source: <filename>, p.<page>] where relevant. "
    "Prefer correctness and safety; include equations/diagrams when helpful."
)

