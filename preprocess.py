import os
import sys
import re
import html
import unicodedata
import pickle
import json
import spacy
from tqdm import tqdm
from glob import glob

# --- Configuration ---
# Update these paths to match your project structure
DATA_RAW_DIR = 'data/raw'         # Where spider.py saved the .jsonl files
DATA_PROCESSED_DIR = 'data/preprocessed'

# Ensure base output directory exists
os.makedirs(DATA_PROCESSED_DIR, exist_ok=True)

def load_spacy_model():
    """Safely load the spacy model."""
    try:
        # We disable parser and ner for speed since we only need lemmatization
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
    
    # 2. Regex Cleaning (Remove URLs, Markdown, Reddit specific noise)
    text = re.sub(r'http\S+', '', text)                 # URLs
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)         # Images
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)     # Links [text](url) -> text
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)        # Bold
    text = re.sub(r'\/r\/(\w+)', r'\1', text)           # /r/subreddit -> subreddit
    text = re.sub(r'r\/(\w+)', r'\1', text)
    text = re.sub(r'\/u\/(\w+)', r'\1', text)           # /u/user -> user
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
        
        # Keep words greater than 2
        if 2 < len(lemma):
            processed_words.append(lemma)

    return processed_words

def process_single_file(filepath):
    """
    Reads a specific JSONL file, cleans it, and returns a flattened list of data.
    """
    filename = os.path.basename(filepath)
    subreddit_name = filename.replace("data_r_", "").replace(".jsonl", "")
    
    processed_data_batch = []
    
    print(f"Reading: {filename}...")

    with open(filepath, 'r', encoding='utf-8') as f:
        # Read line by line (each line is one Thread/Post)
        for line in tqdm(f, desc=f"Parsing {subreddit_name}"):
            try:
                raw_obj = json.loads(line)
            except json.JSONDecodeError:
                continue # Skip broken lines
            
            # 1. Process the "Main Post" (Submission)
            if raw_obj.get('body'):
                clean_tokens = clean_text_logic(raw_obj['body'])
                if clean_tokens:
                    processed_data_batch.append({
                        "id": raw_obj.get('id'),
                        "type": "submission",
                        "subreddit": subreddit_name,
                        "author": "OP", # Spider.py didn't save OP author in your previous code, check this!
                        "score": 0,     # Spider.py didn't save OP score in your previous code
                        "original_text": raw_obj['body'][:100] + "...", # Store snippet for reference
                        "processed_tokens": clean_tokens
                    })

            # 2. Process the "Comments"
            for comment in raw_obj.get('comments', []):
                if not comment.get('body'): continue
                
                # Filter AutoModerator
                if comment.get('author') in ["AutoModerator"]:
                    continue

                clean_tokens = clean_text_logic(comment['body'])
                if clean_tokens:
                    processed_data_batch.append({
                        "id": raw_obj.get('id'), # Link back to parent thread ID
                        "type": "comment",
                        "subreddit": subreddit_name,
                        "author": comment.get('author'),
                        "score": comment.get('score', 0),
                        "original_text": comment['body'][:100] + "...",
                        "processed_tokens": clean_tokens
                    })

    return subreddit_name, processed_data_batch

def save_data(subreddit_name, data):
    """Saves the processed list as a Pickle file."""
    if not data:
        print(f"No valid data found for {subreddit_name}")
        return

    output_path = os.path.join(DATA_PROCESSED_DIR, f"{subreddit_name}.pkl")
    
    print(f"Saving {len(data)} entries to {output_path}...")
    with open(output_path, "wb") as out_file:
        pickle.dump(data, out_file)
    print("Done.")

def main():
    # Find all .jsonl files in data/raw
    jsonl_files = glob(os.path.join(DATA_RAW_DIR, "*.jsonl"))
    
    if not jsonl_files:
        print(f"No .jsonl files found in {DATA_RAW_DIR}")
        return

    print(f"Found {len(jsonl_files)} files to process.")

    for filepath in jsonl_files:
        sub_name, data = process_single_file(filepath)
        save_data(sub_name, data)

if __name__ == "__main__":
    main()