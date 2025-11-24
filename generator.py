import feedparser
from main import app, db, Post
from datetime import datetime
import random

# Hot Naija news + celebrity gossip sources
feeds = [
    ("News", "https://punchng.com/feed/"),
    ("News", "https://www.vanguardngr.com/feed/"),
    ("News", "https://www.premiumtimesng.com/feed/"),
    ("Gossip", "https://www.lindaikejisblog.com/feed/"),
    ("Gossip", "https://www.bellanaija.com/feed/"),
    ("Gossip", "https://www.thecable.ng/feed/"),
    ("Gossip", "https://thenet.ng/feed/"),
]

buzz_prefixes = [
    "Na Wa O!",
    "Gist Alert:",
    "You Won’t Believe This:",
    "Naija Gist:",
    "Breaking:",
    "Hot Gist:",
    "See Wetin Happen:",
    "Omo!",
    "This One Loud O:",
    "Chai!"
]

def run():
    with app.app_context():
        added = 0
        for category, url in feeds:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:8]:  # 
