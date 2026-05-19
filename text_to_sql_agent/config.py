DEFAULT_MODEL_NAME = "gemini-2.5-flash"
DEFAULT_OLLAMA_MODEL = "gemma3"
DEFAULT_PROVIDER = "gemini"
DEFAULT_MAX_ROWS = 1_000
DEFAULT_SQLITE_PROGRESS_STEPS = 100_000
DEFAULT_RAG_TOP_K = 6
DEFAULT_RAG_NEIGHBORS = 1
DEFAULT_RAG_SEMANTIC_WEIGHT = 3.0
DEFAULT_RAG_EMBEDDING_WEIGHT = 5.0
DEFAULT_VALUE_HINT_LIMIT = 6
DEFAULT_VALUE_HINT_MAX_CARDINALITY = 20

RAG_SYNONYMS = {
    "client": ["customer", "customers"],
    "clients": ["customer", "customers"],
    "buyer": ["customer", "customers"],
    "buyers": ["customer", "customers"],
    "income": ["revenue", "amount", "sales"],
    "revenue": ["amount", "sales", "total"],
    "sale": ["sales", "amount"],
    "sales": ["sale", "amount", "revenue"],
    "spend": ["amount", "sales"],
    "course": ["courses", "class"],
    "classes": ["courses", "course"],
    "student": ["students", "learner"],
    "patients": ["patient", "healthcare"],
    "patient": ["patients", "healthcare"],
    "region": ["location", "area"],
}

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from", "how", "in",
    "is", "it", "me", "of", "on", "or", "per", "show", "the", "to", "total",
    "what", "which", "with",
}
