#Model setting
EMBEDDING_MODEL = "text-embedding-3-large"
QUERY_MODEL = "gpt-4o-mini"
GENERATION_MODEL = "gpt-4o"

# Vector store setting
CHROMA_DB_PATH = "./app/chroma_db"

# Retriever setting
SEARCH_TYPE = "mmr"
MMR_DIVERSITY_LAMBDA = 0.7
MMR_FETCH_K = 20 #Initial docs before applying MMR
SEARCH_K = 2 #Final docs after applying el MVR