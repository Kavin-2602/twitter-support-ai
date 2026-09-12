"""
Step 2: Build Retrieval & RAG Pipeline
Script: 02_rag_pipeline.py

Indexes inbound_text from amazon_support_data.csv paired with outbound_text resolutions.
Uses sentence-transformers ('all-MiniLM-L6-v2') and FAISS (IndexFlatIP with L2 normalized vectors).
Persists index and metadata to disk, auto-rebuilding if dataset CSV is modified.
Provides get_similar_resolutions(customer_query, top_k) and a sanity-check execution block.
"""

import os
import sys
import pickle
import argparse
import numpy as np
import pandas as pd
import faiss
from sentence_transformers import SentenceTransformer

# Reconfigure stdout to UTF-8 for Windows compatibility
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

INDEX_FILE = "index.faiss"
METADATA_FILE = "rag_metadata.pkl"
MODEL_NAME = "all-MiniLM-L6-v2"

class RAGPipeline:
    def __init__(self, csv_path: str = "amazon_support_data.csv", model_name: str = MODEL_NAME):
        self.csv_path = csv_path
        self.model_name = model_name
        self.model = None
        self.index = None
        self.metadata = []
        
    def load_model(self):
        if self.model is None:
            print(f"Loading embedding model '{self.model_name}'...")
            self.model = SentenceTransformer(self.model_name)
            
    def is_index_stale(self) -> bool:
        """Checks if index/metadata files are missing or older than the CSV data file."""
        if not os.path.exists(INDEX_FILE) or not os.path.exists(METADATA_FILE):
            return True
        csv_mtime = os.path.getmtime(self.csv_path)
        index_mtime = os.path.getmtime(INDEX_FILE)
        return csv_mtime > index_mtime

    def build_or_load_index(self, force_rebuild: bool = False):
        self.load_model()
        
        if not force_rebuild and not self.is_index_stale():
            print(f"Loading existing FAISS index from '{INDEX_FILE}'...")
            self.index = faiss.read_index(INDEX_FILE)
            with open(METADATA_FILE, "rb") as f:
                self.metadata = pickle.load(f)
            print(f"Index loaded successfully with {len(self.metadata)} vectors.")
            return

        print(f"Building new FAISS index from '{self.csv_path}'...")
        if not os.path.exists(self.csv_path):
            raise FileNotFoundError(f"Data file '{self.csv_path}' not found. Please run 01_extract_data.py first.")
            
        df = pd.read_csv(self.csv_path)
        if len(df) == 0:
            raise ValueError(f"Data file '{self.csv_path}' is empty.")
            
        print(f"Embedding {len(df)} inbound customer messages...")
        inbound_texts = df['inbound_text'].tolist()
        embeddings = self.model.encode(inbound_texts, show_progress_bar=True, convert_to_numpy=True)
        
        # L2-normalize embeddings for Cosine Similarity via Inner Product (IndexFlatIP)
        faiss.normalize_L2(embeddings)
        dimension = embeddings.shape[1]
        
        self.index = faiss.IndexFlatIP(dimension)
        self.index.add(embeddings)
        
        # Save metadata matching index position -> thread info
        self.metadata = []
        for idx, row in df.iterrows():
            self.metadata.append({
                'thread_id': row['thread_id'],
                'inbound_text': row['inbound_text'],
                'outbound_text': row['outbound_text'],
                'inbound_created_at': row.get('inbound_created_at', '')
            })
            
        # Persist index and metadata
        faiss.write_index(self.index, INDEX_FILE)
        with open(METADATA_FILE, "wb") as f:
            pickle.dump(self.metadata, f)
            
        print(f"Successfully built and persisted FAISS index ({self.index.ntotal} vectors) to '{INDEX_FILE}'.")

    def get_similar_resolutions(self, customer_query: str, top_k: int = 3) -> list[dict]:
        """
        Retrieves top_k most similar historical (inbound, outbound) thread pairs.
        Returns a list of dicts with keys: thread_id, inbound_text, outbound_text, similarity_score
        """
        if self.index is None or len(self.metadata) == 0:
            self.build_or_load_index()
            
        query_vector = self.model.encode([customer_query], convert_to_numpy=True)
        faiss.normalize_L2(query_vector)
        
        scores, indices = self.index.search(query_vector, top_k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            meta = self.metadata[idx]
            results.append({
                'thread_id': meta['thread_id'],
                'inbound_text': meta['inbound_text'],
                'outbound_text': meta['outbound_text'],
                'similarity_score': float(score)
            })
            
        return results

# Module-level convenience function matching requirement spec
_default_rag_pipeline = None

def get_similar_resolutions(customer_query: str, top_k: int = 3) -> list[dict]:
    global _default_rag_pipeline
    if _default_rag_pipeline is None:
        _default_rag_pipeline = RAGPipeline()
        _default_rag_pipeline.build_or_load_index()
    return _default_rag_pipeline.get_similar_resolutions(customer_query, top_k=top_k)

def main():
    parser = argparse.ArgumentParser(description="Run RAG Retrieval Pipeline & Sanity Check.")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild of FAISS index")
    parser.add_argument("--top_k", type=int, default=3, help="Top-k matches to retrieve")
    args = parser.parse_args()
    
    print("=== Step 2: RAG Pipeline Initialization ===")
    pipeline = RAGPipeline()
    pipeline.build_or_load_index(force_rebuild=args.rebuild)
    
    # Sanity-check test queries (realistic queries NOT present verbatim in dataset)
    sanity_queries = [
        "My order shows as delivered, but I haven't received the package anywhere. Can I get a replacement?",
        "I'm trying to stream Amazon Prime Video on my Fire TV stick, but it keeps buffering and gives a playback error.",
        "I opened my package today and the item inside was damaged and broken. How do I get a refund or return it?"
    ]
    
    print("\n" + "="*70)
    print("                RAG RETRIEVAL SANITY-CHECK EVALUATION               ")
    print("="*70)
    
    for i, q in enumerate(sanity_queries, 1):
        print(f"\n[Test Query {i}]: \"{q}\"")
        print("-" * 70)
        matches = pipeline.get_similar_resolutions(q, top_k=args.top_k)
        
        for rank, match in enumerate(matches, 1):
            print(f" Match #{rank} | Similarity Score: {match['similarity_score']:.4f} | ID: {match['thread_id']}")
            print(f"   Historical Customer: {match['inbound_text']}")
            print(f"   Historical Brand:    {match['outbound_text']}")
            print()
            
    print("="*70)
    print("Sanity check complete. Eyeball match quality above to verify retrieval accuracy.")

if __name__ == "__main__":
    main()
