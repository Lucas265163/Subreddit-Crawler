import pandas as pd
import json
import os

# CONFIGURATION
INPUT_FILE = "data/raw/GamingLaptops.jsonl" 
OUTPUT_CSV = "data/labeling_task.csv"
SAMPLE_SIZE = 100

def create_sample_for_labeling():
    data = []
    
    # Load Data
    print(f"Loading data from {INPUT_FILE}...")
    if not os.path.exists(INPUT_FILE):
        print("File not found!")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                # We assume the file structure is the one from the previous step
                # (The flattened one or the one with 'processed_body'/'processed_comments')
                item = json.loads(line)
                
                # Let's extract Post Bodies and Comments to a flat list
                # STRATEGY: Flatten structure for the CSV
                
                # Add the main post
                if item.get("processed_body"):
                    # Join list of words back to string for readability in Excel
                    text_str = " ".join(item["processed_body"]) 
                    data.append({
                        "id": item.get("id"),
                        "type": "post",
                        "text": text_str,
                        "original_length": len(text_str)
                    })
                
                # Add the comments
                for comment in item.get("processed_comments", []):
                    text_str = " ".join(comment["processed_text"])
                    data.append({
                        "id": item.get("id"), # Parent ID
                        "type": "comment",
                        "text": text_str,
                        "original_length": len(text_str)
                    })
                    
            except json.JSONDecodeError:
                continue

    # Convert to Pandas DataFrame
    df = pd.DataFrame(data)
    
    # Filter out very short texts (garbage)
    df = df[df['original_length'] > 20] 

    # Random Sample
    print(f"Total rows available: {len(df)}")
    print(f"Sampling {SAMPLE_SIZE} random rows...")
    df_sample = df.sample(n=min(SAMPLE_SIZE, len(df)), random_state=42)

    # Add an empty 'label' column for you to fill
    # We can use a heuristic to pre-fill it to save you time!
    # 1 = Relevant (Laptop), 0 = Irrelevant (Desktop/Spam)
    df_sample['relevant_label'] = '' 

    # Save to CSV
    df_sample.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig') # utf-8-sig for Excel compatibility
    print(f"Done! Open '{OUTPUT_CSV}' in Excel/Google Sheets.")

if __name__ == "__main__":
    create_sample_for_labeling()
