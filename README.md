# Subreddit Semantic Crawler & Analyzer

## Project Overview

This project is a specialized data pipeline designed to **crawl, clean, and classify** Reddit discussions from GamingLaptops-focused subreddits.

Unlike generic scrapers, this tool implements an **intelligent relevance filter** using Natural Language Processing (NLP). It automatically distinguishes between high-quality user reviews/discussions and "noise" (memes, tech support spam, or desktop-related content) to build a clean dataset for sentiment analysis.

### Key Features
*   **Intelligent Spider:** Custom PRAW-based crawler with **negative keyword filtering** to avoid irrelevant subreddits (e.g., distinguishing Laptops from Desktop PC content).
*   **Memory-Efficient:** Uses **JSONL streaming** to handle large datasets without RAM overflow.
*   **Noise Filtering Pipeline:**
    *   **TF-IDF + Logistic Regression Model** to classify comments as "Relevant" or "Irrelevant".
    *   Achieved **~82% Accuracy** on the test set.
    *   Effectively filters out bots, spam, and off-topic discussions.
*   **Automated Labeling Workflow:** Includes scripts to generate random sampling batches for efficient manual labeling (Active Learning workflow).

---

## Tech Stack

*   **Data Collection:** `PRAW` (Python Reddit API Wrapper), `deque` (BFS Crawling strategy)
*   **Preprocessing:** `spaCy` (Lemmatization), `Pandas`, `Regex`
*   **Machine Learning:** `Scikit-Learn` (TF-IDF Vectorizer, Logistic Regression)
*   **Data Format:** JSONL (Raw), CSV (Processed/Labeled)

---

## Repository Structure

```text
├── data/
│   ├── raw/                 # Raw JSONL files from the spider
│   ├── preprocessed/        # Cleaned CSV files (Lemmatized)
│   ├── relevant_comments/   # FINAL DATA: Filtered by ML model
│   └── labeling_sample.csv  # The manually labeled dataset for training
├── notebook/
│   └── test.ipynb       
├── spider.py            # Main crawler script
├── preprocess.py        # Cleaning & Flattening logic
├── create_labeling.py   # Generates sample data for manual labeling
├── train_filter.py      # Trains the LR model & filters data
├── README.md
└── requirements.txt