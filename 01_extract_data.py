"""
Step 1: Setup & Data Ingestion
Script: 01_extract_data.py

Downloads the Kaggle dataset 'thoughtvector/customer-support-on-twitter' via kagglehub,
filters for @AmazonHelp tweets, reconstructs full inbound -> outbound conversation threads,
filters for English language using langdetect (confidence >= 0.85),
and exports clean English threads to amazon_support_data.csv.

Subsample & Chunking Strategy:
To meet the <15 min execution constraint and operate safely within resource limits,
this script processes twcs.csv in streaming chunks (100,000 rows per chunk) and limits
the extracted dataset to max_threads clean English threads.
"""

import os
import sys
import argparse
import kagglehub
import pandas as pd
from langdetect import detect_langs, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException

# Enforce deterministic language detection results
DetectorFactory.seed = 42

def is_english_text(text: str, confidence_threshold: float = 0.85) -> bool:
    """
    Checks if text is written in English with confidence >= threshold using langdetect.
    Drops short/ambiguous/non-English text safely without throwing exceptions.
    """
    try:
        if not text or len(text.strip()) < 15:
            return False
        langs = detect_langs(text)
        if langs:
            top_lang = langs[0]
            # Must be 'en' and meet probability threshold
            return top_lang.lang == 'en' and top_lang.prob >= confidence_threshold
    except LangDetectException:
        # Fails on text with no features (symbols/numbers only)
        return False
    except Exception:
        return False
    return False

def extract_amazon_threads(max_threads: int = 300, chunk_size: int = 100000) -> tuple[pd.DataFrame, dict]:
    print("Downloading dataset using kagglehub...")
    dataset_dir = kagglehub.dataset_download("thoughtvector/customer-support-on-twitter")
    print(f"Dataset downloaded to: {dataset_dir}")
    
    csv_file = None
    for root, dirs, files in os.walk(dataset_dir):
        for f in files:
            if f.endswith(".csv"):
                csv_file = os.path.join(root, f)
                break
    
    if not csv_file:
        raise FileNotFoundError("Could not find twcs.csv in downloaded dataset.")
        
    print(f"Reading dataset from: {csv_file}")
    
    amazon_outbounds = []
    needed_inbound_ids = set()
    
    print("Pass 1: Scanning dataset for @AmazonHelp responses...")
    chunk_count = 0
    for chunk in pd.read_csv(csv_file, chunksize=chunk_size, low_memory=False):
        chunk_count += 1
        amz_chunk = chunk[(chunk['author_id'] == 'AmazonHelp') & (chunk['in_response_to_tweet_id'].notna())]
        
        for _, row in amz_chunk.iterrows():
            try:
                inbound_id = int(float(row['in_response_to_tweet_id']))
                outbound_id = int(float(row['tweet_id']))
                outbound_text = str(row['text']).strip()
                outbound_created = str(row['created_at'])
                
                amazon_outbounds.append({
                    'outbound_id': outbound_id,
                    'inbound_id': inbound_id,
                    'outbound_text': outbound_text,
                    'outbound_created_at': outbound_created
                })
                needed_inbound_ids.add(inbound_id)
            except (ValueError, TypeError):
                continue
                
        # Scan sufficient candidates to ensure we hit max_threads clean English threads
        if len(amazon_outbounds) >= max_threads * 10:
            print(f"Collected candidate pool of {len(amazon_outbounds)} AmazonHelp responses after {chunk_count} chunks.")
            break
            
    print(f"Found {len(amazon_outbounds)} AmazonHelp response tweets referencing {len(needed_inbound_ids)} unique inbound tweet IDs.")
    
    print("Pass 2: Retrieving customer inbound tweets matching referenced IDs...")
    inbound_tweets = {}
    
    for chunk in pd.read_csv(csv_file, chunksize=chunk_size, low_memory=False):
        chunk['tweet_id_clean'] = pd.to_numeric(chunk['tweet_id'], errors='coerce')
        matched = chunk[chunk['tweet_id_clean'].isin(needed_inbound_ids)]
        
        for _, row in matched.iterrows():
            t_id = int(row['tweet_id_clean'])
            inbound_tweets[t_id] = {
                'inbound_text': str(row['text']).strip(),
                'inbound_created_at': str(row['created_at']),
                'author_id': str(row['author_id'])
            }
            
        if len(inbound_tweets) >= len(needed_inbound_ids):
            break

    print(f"Retrieved {len(inbound_tweets)} inbound customer tweets. Applying English language filter...")
    
    threads = []
    thread_count = 0
    total_candidates_evaluated = 0
    dropped_non_english = 0
    
    for outb in amazon_outbounds:
        inb_id = outb['inbound_id']
        if inb_id in inbound_tweets:
            inb_data = inbound_tweets[inb_id]
            if inb_data['author_id'] == 'AmazonHelp':
                continue
                
            inb_text = " ".join(inb_data['inbound_text'].split())
            outb_text = " ".join(outb['outbound_text'].split())
            
            if len(inb_text) < 15 or len(outb_text) < 15:
                continue
                
            total_candidates_evaluated += 1
            
            # Language Filter Check
            if not is_english_text(inb_text, confidence_threshold=0.85):
                dropped_non_english += 1
                continue
                
            thread_count += 1
            threads.append({
                'thread_id': f"amz_thread_{thread_count:04d}",
                'inbound_text': inb_text,
                'outbound_text': outb_text,
                'inbound_created_at': inb_data['inbound_created_at']
            })
            
            if len(threads) >= max_threads:
                break
                
    df_threads = pd.DataFrame(threads)
    stats = {
        'total_candidates_evaluated': total_candidates_evaluated,
        'dropped_non_english': dropped_non_english,
        'final_english_count': len(df_threads)
    }
    return df_threads, stats

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        
    parser = argparse.ArgumentParser(description="Extract AmazonHelp Twitter support threads.")
    parser.add_argument("--max_threads", type=int, default=300, help="Maximum number of clean English threads to extract (default: 300)")
    parser.add_argument("--output", type=str, default="amazon_support_data.csv", help="Output CSV filepath")
    args = parser.parse_args()
    
    print(f"=== Step 1: Data Ingestion & Language Filtering for AmazonHelp ===")
    df, stats = extract_amazon_threads(max_threads=args.max_threads)
    
    df.to_csv(args.output, index=False, encoding='utf-8')
    print(f"\nSuccessfully saved {len(df)} clean English threads to '{args.output}'.")
    
    df['inbound_len'] = df['inbound_text'].str.len()
    df['outbound_len'] = df['outbound_text'].str.len()
    
    avg_inbound_len = df['inbound_len'].mean()
    avg_outbound_len = df['outbound_len'].mean()
    
    df['parsed_date'] = pd.to_datetime(df['inbound_created_at'], format='mixed', errors='coerce')
    min_date = df['parsed_date'].min()
    max_date = df['parsed_date'].max()
    
    print("\n" + "="*50)
    print("        SUMMARY STATISTICAL REPORT (ENGLISH ONLY)        ")
    print("="*50)
    print(f"Total Candidate Threads Evaluated:   {stats['total_candidates_evaluated']}")
    print(f"Dropped (Non-English / Low Conf):    {stats['dropped_non_english']}")
    print(f"Final Reconstructed English Threads: {stats['final_english_count']}")
    print(f"Average Inbound Message Length:      {avg_inbound_len:.1f} chars")
    print(f"Average Outbound Message Length:     {avg_outbound_len:.1f} chars")
    if pd.notna(min_date) and pd.notna(max_date):
        print(f"Date Range:                          {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}")
    else:
        print(f"Date Range:                          {df['inbound_created_at'].min()} to {df['inbound_created_at'].max()}")
    print("="*50)
    print("\nSample Clean English Thread:")
    sample = df.iloc[0]
    print(f"Thread ID: {sample['thread_id']}")
    print(f"Inbound:  {sample['inbound_text']}")
    print(f"Outbound: {sample['outbound_text']}")

if __name__ == "__main__":
    main()

