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
VALIDATION_LIMIT = 20 
HARVEST_LIMIT = 1000 

# VOCABULARY FOR VALIDATION
LAPTOP_KEYWORDS = {
    'battery', 'hinge', 'screen', 'keyboard', 'touchpad', 'trackpad', 
    'thermal', 'paste', 'undervolt', 'wattage', 'charger', 'lid', 'ips', 
    'oled', 'backlight', 'gaming laptop', 'notebook'
}

class SubredditSpider:
    def __init__(self):
        # 1. INCREASE TIMEOUT via 'requestor_kwargs'
        self.reddit = praw.Reddit(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            user_agent=USER_AGENT,
            requestor_kwargs={'timeout': 60} # Wait 60 seconds before crashing
        )
        self.queue = deque([START_SUBREDDIT])
        self.visited = set([START_SUBREDDIT.lower()])
        self.approved_subs = []
        self.link_pattern = re.compile(r"r/([a-zA-Z0-9_]+)")

    def validate_relevance(self, sub_name):
        print(f"  [?] Validating r/{sub_name}...", end="")
        try:
            sub = self.reddit.subreddit(sub_name)
            if sub.subscribers < 100:
                print(f"{Fore.RED} Too small. Skip.")
                return False

            score = 0
            desc = (sub.public_description or "") + (sub.title or "")
            if any(k in desc.lower() for k in LAPTOP_KEYWORDS):
                score += 5
            
            for post in sub.hot(limit=VALIDATION_LIMIT):
                text = (post.title + " " + post.selftext).lower()
                for word in LAPTOP_KEYWORDS:
                    if word in text:
                        score += 1
            
            if score > 5:
                print(f"{Fore.GREEN} PASS (Score: {score})")
                return True
            else:
                print(f"{Fore.RED} FAIL (Score: {score})")
                return False

        except Exception as e:
            print(f"{Fore.RED} Error: {e}")
            return False

    def harvest_and_expand(self, sub_name):
        print(f"{Fore.CYAN}  -> Harvesting r/{sub_name} (Limit: {HARVEST_LIMIT})...")
        
        subreddit = self.reddit.subreddit(sub_name)
        harvested_posts = []
        new_links_found = set()

        # 2. RETRY LOOP
        retries = 3
        while retries > 0:
            try:
                # Iterate through posts
                # Note: We use list() to force the download safely inside the try block
                # Converting generator to list might be heavy, so we iterate carefully.
                count = 0
                for post in subreddit.hot(limit=HARVEST_LIMIT):
                    count += 1
                    
                    # Progress indicator every 50 posts
                    if count % 50 == 0:
                        print(f"     ...downloaded {count} posts")

                    # Collect Post Data
                    post_obj = {
                        "id": post.id,
                        "title": post.title,
                        "body": post.selftext,
                        "url": post.url,
                        "comments": []
                    }
                    
                    # Search for links in Post Body
                    body_links = self.link_pattern.findall(post.selftext)
                    new_links_found.update(body_links)

                    # Collect Comments
                    # Wrap comment loading in try/except too
                    try:
                        post.comments.replace_more(limit=0)
                        for comment in post.comments[:10]:
                            comment_obj = {
                                "body": comment.body,
                                "author": str(comment.author),
                                "score": comment.score
                            }
                            post_obj["comments"].append(comment_obj)
                            
                            # Search for links in Comments
                            comment_links = self.link_pattern.findall(comment.body)
                            new_links_found.update(comment_links)
                    except Exception:
                        pass # Skip broken comments, keep the post

                    harvested_posts.append(post_obj)

                # Success! Break the retry loop
                break 

            except (prawcore.exceptions.RequestException, prawcore.exceptions.ServerError) as e:
                retries -= 1
                print(f"{Fore.RED}     Network Error ({e}). Retrying... ({retries} left)")
                time.sleep(5) # Wait 5 seconds before retrying
            
            except Exception as e:
                print(f"{Fore.RED}     Critical Error harvesting: {e}")
                return False

        if retries == 0:
            print(f"{Fore.RED}     Failed to harvest r/{sub_name} after 3 attempts.")
            return False

        # Save Data
        self.save_to_json(sub_name, harvested_posts)
        
        # Process found links
        print(f"{Fore.BLUE}     Found {len(new_links_found)} potential links.")
        
        for link in new_links_found:
            clean_link = link.strip().lower()
            if clean_link in self.visited:
                continue
            self.visited.add(clean_link)
            self.queue.append(link)

        return True

    def save_to_json(self, sub_name, data):
        filename = f"data_r_{sub_name}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"{Fore.GREEN}     Saved {len(data)} posts to {filename}")

    def run(self):
        print(f"{Fore.YELLOW}Starting Spider. Goal: {TARGET_SUBREDDIT_COUNT} Subreddits.")
        
        while self.queue and len(self.approved_subs) < TARGET_SUBREDDIT_COUNT:
            current_sub = self.queue.popleft()
            
            if current_sub.lower() in ['gaming', 'pcgaming', 'techsupport', 'buildapc']: 
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