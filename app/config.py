from dotenv import load_dotenv
import os

load_dotenv()

VLLM_URL = os.getenv("LLM_URL") or os.getenv("VLLM_URL")
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen")
CHROMA_PATH = os.getenv("CHROMA_PATH", "data/vectordb")
COLLECTION = "recipes"