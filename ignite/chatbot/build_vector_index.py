import os
import json

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

DATA_FILE = os.path.join(os.path.dirname(__file__), 'iiitdmj_rag_data.json')
INDEX_DIR = os.path.join(os.path.dirname(__file__), 'faiss_index')
EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'


def build():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        chunks = json.load(f)

    docs = [
        Document(
            page_content=chunk['content'],
            metadata={
                'id': chunk.get('id', ''),
                'source': chunk.get('source', ''),
                'section': chunk.get('section', ''),
                'url': chunk.get('url', ''),
                'page': chunk.get('page', ''),
            },
        )
        for chunk in chunks
    ]

    print(f"Embedding {len(docs)} chunks with {EMBEDDING_MODEL} (first run downloads the model)...")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        encode_kwargs={'normalize_embeddings': True},
    )

    vectorstore = FAISS.from_documents(docs, embeddings)
    vectorstore.save_local(INDEX_DIR)
    print(f"Saved FAISS index with {len(docs)} vectors to {INDEX_DIR}")


if __name__ == '__main__':
    build()
