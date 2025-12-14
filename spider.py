import praw
import re
import os
import time
import json
import prawcore
from collections import deque
from dotenv import load_dotenv
from colorama import Fore, init

init(autoreset=True)
load_dotenv()

# ==========================================
# CONFIGURATION
# ==========================================
CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
USER_AGENT = os.getenv('REDDIT_USER_AGENT')

START_SUBREDDIT = "GamingLaptops"
TARGET_SUBREDDIT_COUNT = 20

# SETTINGS
VALIDATION_LIMIT = 50 
HARVEST_LIMIT = 1000 

# VOCABULARY FOR VALIDATION
# Positive words (Laptop indicators)
LAPTOP_KEYWORDS = {
    'battery', 'hinge', 'screen', 'keyboard', 'touchpad', 'trackpad', 
    'thermal', 'paste', 'laptops', 'wattage', 'charger', 'lid', 'ips', 
    'oled', 'backlight', 'gaming laptop', 'notebook', 'mobility', 'portability'
}

# Negative words (Desktop/Console indicators) - NEW FEATURE
DESKTOP_KEYWORDS = {
    'desktop', 'tower', 'monitor', 'buildapc', 'atx', 'itx', 'motherboard', 
    'ps5', 'xbox', 'console', 'controller', 'tv', 'cabinet', 'water cooling',
    'desk setup', 'battlestation', 'mousepad'
}

class SubredditSpider:
    def __init__(self):
        self.reddit = praw.Reddit(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            user_agent=USER_AGENT,
            requestor_kwargs={'timeout': 60}
        )
        self.queue = deque([START_SUBREDDIT])
        self.visited = set([START_SUBREDDIT.lower()])
        self.approved_subs = []
        self.link_pattern = re.compile(r"r/([a-zA-Z0-9_]+)")

    def validate_relevance(self, sub_name):
        print(f"  [?] Validating r/{sub_name}...", end="")
        try:
            sub = self.reddit.subreddit(sub_name)
            # Basic size check
            try:
                if sub.subscribers < 10000:
                    print(f"{Fore.RED} Too small. Skip.")
                    return False
            except:
                return False # If we can't read subscriber count, skip

            score = 0
            
            # 1. Check Description
            desc = (sub.public_description or "") + (sub.title or "")
            desc_lower = desc.lower()
            
            if any(k in desc_lower for k in LAPTOP_KEYWORDS):
                score += 5
            if any(k in desc_lower for k in DESKTOP_KEYWORDS):
                score -= 5  # Penalize for desktop keywords in description

            # 2. Check Recent Posts
            for post in sub.hot(limit=VALIDATION_LIMIT):
                text = (post.title + " " + (post.selftext or "")).lower()
                
                # Add points for laptop words
                for word in LAPTOP_KEYWORDS:
                    if word in text:
                        if word == 'laptop' or word == 'laptops':
                            score += 2 # Extra points for strong indicators
                        score += 1
                        break # Count only once per post
                
                # Subtract points for desktop words
                for word in DESKTOP_KEYWORDS:
                    if word in text:
                        score -= 2 # Stronger penalty to filter noise
                        break
            
            # Threshold
            if score > 5:
                print(f"{Fore.GREEN} PASS (Score: {score})")
                return True
            else:
                print(f"{Fore.RED} FAIL (Score: {score})")
                return False

        except Exception as e:
            print(f"{Fore.RED} Error validating: {e}")
            return False

    def harvest_and_expand(self, sub_name):
        print(f"{Fore.CYAN}  -> Harvesting r/{sub_name} (Limit: {HARVEST_LIMIT})...")
        
        subreddit = self.reddit.subreddit(sub_name)
        new_links_found = set()
        
        # MEMORY OPTIMIZATION: Write to file directly
        # We use .jsonl format (one valid JSON object per line)
        filename = f"data/raw/{sub_name}.jsonl" 

        retries = 3
        while retries > 0:
            try:
                # Open file in append mode
                with open(filename, "w", encoding="utf-8") as f:
                    count = 0
                    
                    # We iterate directly; no huge list in memory
                    for post in subreddit.hot(limit=HARVEST_LIMIT):
                        count += 1
                        if count % 50 == 0:
                            print(f"     ...processed {count} posts")

                        # Collect Post Data
                        post_obj = {
                            "id": post.id,
                            "title": post.title,
                            "body": post.selftext,
                            "url": post.url,
                            "comments": []
                        }

                        # Scan for links
                        if post.selftext:
                            body_links = self.link_pattern.findall(post.selftext)
                            new_links_found.update(body_links)

                        # Collect Comments
                        try:
                            # Using replace_more(limit=0) keeps it fast
                            post.comments.replace_more(limit=0)
                            for comment in post.comments[:10]:
                                comment_obj = {
                                    "body": comment.body,
                                    "author": str(comment.author),
                                    "score": comment.score
                                }
                                post_obj["comments"].append(comment_obj)
                                
                                if comment.body:
                                    comment_links = self.link_pattern.findall(comment.body)
                                    new_links_found.update(comment_links)
                        except Exception:
                            pass 

                        # WRITE TO FILE IMMEDIATELY
                        json.dump(post_obj, f, ensure_ascii=False)
                        f.write("\n") # Newline for next object

                break # Loop finished successfully

            except (prawcore.exceptions.RequestException, prawcore.exceptions.ServerError) as e:
                retries -= 1
                print(f"{Fore.RED}     Network Error. Retrying... ({retries} left)")
                time.sleep(5)
            
            except Exception as e:
                print(f"{Fore.RED}     Critical Error: {e}")
                return False

        if retries == 0:
            print(f"{Fore.RED}     Failed to harvest r/{sub_name}.")
            return False

        print(f"{Fore.GREEN}     Saved data to {filename}")

        # Process found links for queue
        print(f"{Fore.BLUE}     Found {len(new_links_found)} potential links.")
        for link in new_links_found:
            clean_link = link.strip().lower()
            if clean_link in self.visited:
                continue
            self.visited.add(clean_link)
            self.queue.append(link)

        return True

    def run(self):
        print(f"{Fore.YELLOW}Starting Spider. Goal: {TARGET_SUBREDDIT_COUNT} Subreddits.")
        
        while self.queue and len(self.approved_subs) < TARGET_SUBREDDIT_COUNT:
            current_sub = self.queue.popleft()
            
            # Explicit ignore list
            if current_sub.lower() in ['gaming', 'pcgaming', 'techsupport', 'buildapc', 'pcmasterrace']: 
                continue

            print(f"\n{Fore.MAGENTA}Processing: r/{current_sub}")
            
            if self.validate_relevance(current_sub):
                self.approved_subs.append(current_sub)
                self.harvest_and_expand(current_sub)
                print(f"{Fore.YELLOW}Progress: {len(self.approved_subs)}/{TARGET_SUBREDDIT_COUNT} found.")
            
            time.sleep(2)

        print(f"\n{Fore.GREEN}DONE! Found subreddits: {self.approved_subs}")

if __name__ == "__main__":
    spider = SubredditSpider()
    spider.run()