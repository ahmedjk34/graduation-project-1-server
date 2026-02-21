#The goal of this file is to store all the configuration for the project in one place, so that it is easy to change and manage.

import os
from dotenv import load_dotenv


load_dotenv()


GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Model used for LLM generation
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# ChromaDB Configuration
CHROMA_PATH = "./chroma_storage"
COLLECTION_NAME = "najah-circuits"

# Embedding Model Configuration
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


# For system prompts, import from rag.prompts

# How to write a 16 bit variable in PIC18 Assembly