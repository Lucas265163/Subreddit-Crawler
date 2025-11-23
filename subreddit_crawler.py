import praw
import json
import os
from dotenv import load_dotenv
from colorama import Fore, init

# Initialize colorama
init(autoreset=True)

# Load environment variables from .env file
load_dotenv()

# ==========================================
# CONFIGURATION
# ==========================================
CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
USER_AGENT = os.getenv('REDDIT_USER_AGENT')

SEEDS = ['GamingLaptops', 'Laptops']

# Keywords for filtering 
POSITIVE_KEYWORDS = ['laptop', 'notebook', 'gaming laptop']
NEGATIVE_KEYWORDS = ['handheld', 'console', 'desktop', 'buildapc', 'ally']

# ==========================================
# LOGIC
# ==========================================

def get_reddit_instance():
    if not CLIENT_ID or not CLIENT_SECRET:
        print(Fore.RED + "Error: Credentials not found in .env file!")
        exit()
        
    return praw.Reddit(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        user_agent=USER_AGENT,
        requestor_kwargs={'timeout': 45}
    )

def analyze_relevance(subreddit):
    """Determines if a subreddit is relevant based on description."""
    score = 0
    # Combine title and description, handle None types
    text_blob = (str(subreddit.public_description) + " " + str(subreddit.title)).lower()

    for word in NEGATIVE_KEYWORDS:
        if word in text_blob:
            score -= 5
    for word in POSITIVE_KEYWORDS:
        if word in text_blob:
            score += 2
            
    return score > 0

def harvest_comments(reddit, subreddit_name, limit=10):
    """
     crawls posts and comments from a specific subreddit.
    """
    print(f"{Fore.CYAN}  -> Harvesting top {limit} posts from r/{subreddit_name}...")
    subreddit = reddit.subreddit(subreddit_name)
    
    harvested_data = []
    
    try:
        # Get 'Hot' posts
        for i, post in enumerate(subreddit.hot(limit=limit), 1):
            if i % 5 == 0:
                print(f"    Processing post {i}/{limit}...", end='\r')

            post_data = {
                "title": post.title,
                "url": post.url,
                "score": post.score,
                "id": post.id,
                "body": post.selftext,
                "comments": []
            }
            
            # Load comments (handling the "Load More" button logic automatically)
            post.comments.replace_more(limit=0) # limit=0 saves time by ignoring deep nested threads
            
            for comment in post.comments.list()[:20]: # Limit to top 20 comments per post
                comment_data = {
                    "body": comment.body,
                    "author": str(comment.author),
                    "score": comment.score
                }
                post_data["comments"].append(comment_data)
                
            harvested_data.append(post_data)
            
    except Exception as e:
        print(f"{Fore.RED}  Error harvesting r/{subreddit_name}: {e}")
        
    return harvested_data

def main():
    reddit = get_reddit_instance()
    
    # 1. DISCOVERY PHASE
    print(f"{Fore.YELLOW}Step 1: Discovering Subreddits...")
    target_subreddits = set()
    
    # Simple seed expansion
    for seed in SEEDS:
        # Add the seed itself
        target_subreddits.add(seed)
        
        # Try to find variations (simple search)
        # In a real app, you might make this recursive
        print(f"Searching for variations of '{seed}'...")
        for sub in reddit.subreddits.search(seed, limit=5):
            if analyze_relevance(sub):
                target_subreddits.add(sub.display_name)
                print(f"{Fore.GREEN}  Found relevant: {sub.display_name}")

    # 2. HARVESTING PHASE
    print(f"\n{Fore.YELLOW}Step 2: Harvesting Data...")
    final_database = {}

    try:
        for sub_name in target_subreddits:
            print(f"Processing r/{sub_name}...")
            posts = harvest_comments(reddit, sub_name, limit=100) # Reduced to 100 for testing (1000 takes ~15 mins)
            if posts:
                final_database[sub_name] = posts
    except KeyboardInterrupt:
        print(f"\n{Fore.RED}Interrupted by user! Saving collected data...")

    # 3. SAVING PHASE
    print(f"\n{Fore.YELLOW}Step 3: Saving to JSON...")
    output_file = "gaming_laptop_data.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(final_database, f, indent=4, ensure_ascii=False)
        
    print(f"{Fore.GREEN}Success! Data saved to {output_file}")

if __name__ == "__main__":
    main()