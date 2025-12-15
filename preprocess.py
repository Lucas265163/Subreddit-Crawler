import os
import sys
import re
import html
import unicodedata
import json
import spacy
import random
import pandas as pd  # Added pandas
from tqdm import tqdm
from glob import glob

# --- Configuration ---
DATA_RAW_DIR = 'data/raw'
DATA_PROCESSED_DIR = 'data/preprocessed'

# Ensure output directory exists
os.makedirs(DATA_PROCESSED_DIR, exist_ok=True)

def load_spacy_model():
    """Safely load the spacy model."""
    try:
        return spacy.load("en_core_web_sm", disable=["parser", "ner"])
    except OSError:
        print("Error: spaCy model 'en_core_web_sm' not found.")
        print("Please run: python -m spacy download en_core_web_sm")
        sys.exit(1)

# Initialize global resources
nlp = load_spacy_model()

def clean_text_logic(text, without_stopwords=False):
    """
    Core text cleaning logic.
    Returns a list of clean tokens (lemmas).
    """
    if not text or not isinstance(text, str):
        return []

    # 1. Basic Decode
    text = html.unescape(text)
    text = unicodedata.normalize('NFKD', text)
    
    # 2. Regex Cleaning
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\/r\/(\w+)', r'\1', text)
    text = re.sub(r'r\/(\w+)', r'\1', text)
    text = re.sub(r'\/u\/(\w+)', r'\1', text)
    text = re.sub(r'u\/(\w+)', r'\1', text)
    
    # Keep only letters and spaces
    text = re.sub("[^A-Za-z]+", ' ', text).lower()
    
    # 3. NLP Processing
    doc = nlp(text)
    
    processed_words = []
    
    for token in doc:
        if token.is_space: continue
        if without_stopwords and token.is_stop: continue
        
        lemma = token.lemma_
        
        if 2 < len(lemma):
            processed_words.append(lemma)

    return processed_words

def process_single_file(filepath):
    """
    Reads a JSONL file, cleans it, and returns a flattened list.
    """
    filename = os.path.basename(filepath)
    # Removing 'data_r_' prefix if your spider saves it that way
    subreddit_name = filename.replace(".jsonl", "")
    
    processed_data_batch = []
    
    print(f"Reading: {filename}...")

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in tqdm(f, desc=f"Parsing {subreddit_name}"):
            try:
                raw_obj = json.loads(line)
            except json.JSONDecodeError:
                continue 
            
            # 1. Process Main Post
            if raw_obj.get('body'):
                clean_tokens = clean_text_logic(raw_obj['body'])
                if clean_tokens:
                    processed_data_batch.append({
                        "id": raw_obj.get('id'),
                        "type": "submission",
                        "subreddit": subreddit_name,
                        "author": "OP",
                        "score": 0,
                        "original_text": raw_obj['body'], 
                        "full_text_length": len(raw_obj['body']),
                        "processed_tokens": " ".join(clean_tokens) # Join as string for CSV
                    })

            # 2. Process Comments
            for comment in raw_obj.get('comments', []):
                if not comment.get('body'): continue
                
                if comment.get('author') in ["AutoModerator"]:
                    continue

                clean_tokens = clean_text_logic(comment['body'])
                if clean_tokens:
                    processed_data_batch.append({
                        "id": raw_obj.get('id'),
                        "type": "comment",
                        "subreddit": subreddit_name,
                        "author": comment.get('author'),
                        "score": comment.get('score', 0),
                        "original_text": comment['body'][:300],
                        "full_text_length": len(comment['body']),
                        "processed_tokens": " ".join(clean_tokens)
                    })

    return subreddit_name, processed_data_batch

def save_csv(subreddit_name, data):
    """Saves the data list as a CSV file."""
    if not data:
        print(f"No valid data found for {subreddit_name}")
        return

    output_path = os.path.join(DATA_PROCESSED_DIR, f"{subreddit_name}.csv")
    
    df = pd.DataFrame(data)
    # Using utf-8-sig so Excel opens it correctly with special characters
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"Saved {len(data)} rows to {output_path}")

def create_labeling_sample(all_samples, n=500):
    """Creates a random sample file for manual labeling."""
    if not all_samples:
        return

    sample_size = min(len(all_samples), n)
    final_sample = random.sample(all_samples, sample_size)
    
    df_sample = pd.DataFrame(final_sample)
    
    # Add an empty column for you to fill in
    df_sample['relevant'] = '' 
    
    # Reorder columns to put the label and text first
    cols = ['relevant', 'original_text', 'subreddit', 'score', 'type', 'processed_tokens']
    # Add any other columns that might exist
    cols = [c for c in cols if c in df_sample.columns] + [c for c in df_sample.columns if c not in cols]
    
    df_sample = df_sample[cols]
    
    output_path = "data/labelled/labeling_sample_500.csv"
    df_sample.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\n[SUCCESS] Created labeling file: {output_path}")
    print("-> Open this file in Excel. Fill 'relevant_label' with 1 (Relevant) or 0 (Irrelevant).")

def main():
    jsonl_files = glob(os.path.join(DATA_RAW_DIR, "*.jsonl"))
    
    if not jsonl_files:
        print(f"No .jsonl files found in {DATA_RAW_DIR}")
        return

    print(f"Found {len(jsonl_files)} files to process.")

    # We will collect a random subset from each file to form our labeling pool
    sampling_pool = []

    for filepath in jsonl_files:
        sub_name, data = process_single_file(filepath)
        
        # 1. Save full processed data as CSV
        save_csv(sub_name, data)
        
        # 2. Add to sampling pool (take up to 100 random items per file to avoid memory issues)
        if data:
            batch_sample = random.sample(data, min(len(data), 100))
            sampling_pool.extend(batch_sample)

    # 3. Create the final 500-item sample
    create_labeling_sample(sampling_pool, n=500)

if __name__ == "__main__":
    main()