import pandas as pd
import os
import pickle
from glob import glob
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.pipeline import Pipeline


# CONFIGURATION
LABELED_FILE = "data/labelled/labeling_sample_500.csv"   
PREPROCESSED_DIR = "data/preprocessed"          
OUTPUT_DIR = "data/relevant"          

os.makedirs(OUTPUT_DIR, exist_ok=True)

def train_model():
    """
    Loads the labeled data, trains a model, and returns the pipeline.
    """
    print(f"Loading Labeled Data from {LABELED_FILE}")
    
    df = pd.read_csv(LABELED_FILE)

    # 1. Clean the data
    # Drop rows where you forgot to label (NaN)
    df = df.dropna(subset=['relevant_label'])

    print(f"Training on {len(df)} labeled examples.")
    print(f"Class Balance: {df['relevant_label'].value_counts().to_dict()}") 

    # 2. Prepare Features (X) and Target (y)
    if 'processed_tokens' in df.columns and df['processed_tokens'].notna().all():
        X = df['processed_tokens'].astype(str)
        
    y = df['relevant_label']

    # 3. Split Data (80% Train, 20% Test)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # 4. Build Pipeline (TF-IDF + Logistic Regression)
    # n_gram_range=(1,2) includes "not good" as a feature, handling negation better
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(max_features=2000, ngram_range=(1, 2))),
        ('clf', LogisticRegression(class_weight='balanced')) 
    ])

    # 5. Train
    pipeline.fit(X_train, y_train)

    # 6. Evaluate
    print("\nModel Evaluation")
    y_pred = pipeline.predict(X_test)
    print(classification_report(y_test, y_pred))
    
    return pipeline

def filter_and_save_data(model):
    """
    Applies the trained model to all files in preprocessed folder.
    """
    print("\nFiltering All Data")
    
    files = glob(os.path.join(PREPROCESSED_DIR, "*.csv"))
    
    if not files:
        print("No CSV files found to filter!")
        return

    total_kept = 0
    total_discarded = 0

    for filepath in files:
        filename = os.path.basename(filepath)
        print(f"Processing: {filename}...", end="")

        try:
            # Load the big dataset
            df = pd.read_csv(filepath)
            
            # Handle empty files
            if df.empty:
                print(" Empty file.")
                continue

            # Select text column
            if 'processed_tokens' in df.columns:
                X_data = df['processed_tokens'].fillna("").astype(str)
            else:
                X_data = df['original_text'].fillna("").astype(str)

            # PREDICT
            # predictions will be an array of 0s and 1s
            predictions = model.predict(X_data)
            
            # Filter
            df_relevant = df[predictions == 1]
            
            # Stats
            kept = len(df_relevant)
            discarded = len(df) - kept
            total_kept += kept
            total_discarded += discarded
            
            print(f" Kept {kept}, Discarded {discarded}")

            # Save if we have data
            if not df_relevant.empty:
                save_path = os.path.join(OUTPUT_DIR, f"relevant_{filename}")
                df_relevant.to_csv(save_path, index=False, encoding='utf-8-sig')

        except Exception as e:
            print(f" Error: {e}")

    print(f"\nFILTERING COMPLETE")
    print(f"Total Comments Kept: {total_kept}")
    print(f"Total Noise Removed: {total_discarded}")
    print(f"Clean files saved to: {OUTPUT_DIR}")

if __name__ == "__main__":
    # 1. Train
    trained_model = train_model()
    
    # 2. Filter
    if trained_model:
        filter_and_save_data(trained_model)