from flask import Flask, render_template_string, request
from flask_sqlalchemy import SQLAlchemy
import os, feedparser, random, requests
from datetime import datetime
from dateutil import parser as date_parser
from bs4 import BeautifulSoup

app = Flask(__name__)

# Database
db_uri = os.environ.get('DATABASE_URL') or 'sqlite:///posts.db'
if db_uri.startswith('postgres://'):
    db_uri = db_uri.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(600))
    excerpt = db.Column(db.Text)
    link = db.Column(db.String(600), unique=True)
    image = db.Column(db.String(800), default="https://via.placeholder.com/800x500/0f172a/f8fafc?text=NaijaBuzz")
    category = db.Column(db.String(100))
    pub_date = db.Column(db.String(100))

with app.app_context():
    db.create_all()

CATEGORIES = {
    "all": "All News", "naija news": "Naija News", "gossip": "Gossip", "football": "Football",
    "sports": "Sports", "entertainment": "Entertainment", "lifestyle": "Lifestyle",
    "education": "Education", "tech": "Tech", "viral": "Viral", "world": "World"
}

# 20+ UNBLOCKABLE SOURCES — RSSHUB + DIRECT OPEN FEEDS
FEEDS = [
    # Naija News (8)
    ("naija news", "https://rsshub.app/punchng/feed"),
    ("naija news", "https://rsshub.app/vanguardngr/feed"),
    ("naija news", "https://rsshub.app/premiumtimes/feed"),
    ("naija news", "https://rsshub.app/thenation/feed"),
    ("naija news", "https://rsshub.app/dailypost/feed"),
    ("naija news", "https://rsshub.app/thisday/feed"),
    ("naija news", "https://rsshub.app/saharareporters/feed"),
    ("naija news", "https://rsshub.app/thecable/feed"),
    # Gossip (3)
    ("gossip", "https://rsshub.app/lindaikejisblog/feed"),
    ("gossip", "https://rsshub.app/bellanaija/feed"),
    ("gossip", "https://rsshub.app/gistlover/feed"),
    # Football & Sports (4)
    ("football", "https://rsshub.app/goal/nigeria"),
    ("football", "https://rsshub.app/allnigeriasoccer/feed"),
    ("sports", "https://rsshub.app/completesports/feed"),
    ("sports", "https://rsshub.app/afcon"),
    # Entertainment (3)
    ("entertainment", "https://rsshub.app/pulse/feed"),
    ("entertainment", "https://rsshub.app/notjustok/feed"),
    ("entertainment", "https://rsshub.app/bbnaija"),
    # Tech & Viral (3)
    ("tech", "https://rsshub.app/techcabal/feed"),
    ("viral", "https://rsshub.app/legit/feed"),
    ("viral", "https://rsshub.app/trending/nigeria"),
    # World & Lifestyle (2)
    ("world", "https://rsshub.app/bbc/africa"),
    ("lifestyle", "https://rsshub.app/sisiyemmie/feed"),
]

def extract_image(entry):
    default = "https://via.placeholder.com/800x500/0f172a/f8fafc?text=NaijaBuzz"
    candidates = set()

    # RSS enclosures/media
    if hasattr(entry, 'media_content'):
        for m in entry.media_content:
            url = m.get('url')
            if url: candidates.add(url)
    if hasattr(entry, 'enclosures'):
        for e in entry.enclosures:
            if e.url: candidates.add(e.url)

    # HTML fields
    html = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
    if html:
        soup = BeautifulSoup(html, 'html.parser')
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if src:
                if src.startswith('//'): src = 'https:' + src
                candidates.add(src)

    for url in candidates:
        url = re.sub(r'\?.*$', '', url)
        if url.lower().endswith(('.jpg','.jpeg','.png','.webp','.gif')):
            return url
    return default

def time_ago(date_str):
    if not date_str: return "Just now"
    try:
        dt = date_parser.parse(date_str)
        now = datetime.now()
        diff = now - dt
        if diff.days >= 30: return dt.strftime("%b %d")
        elif diff.days >= 1: return f"{diff.days}d ago"
        elif diff.seconds >= 7200: return f"{diff.seconds//3600}h ago"
        elif diff.seconds >= 3600: return "1h ago"
        elif diff.seconds >= 120: return f"{diff.seconds//60}m ago"
        else: return "Just now"
    except:
        return "Recently"

app.jinja_env.filters['time_ago'] = time_ago

@app.route('/')
def index():
    selected = request.args.get('cat', 'all').lower()
    if selected == 'all':
        posts = Post.query.order_by(Post.pub_date.desc()).limit(90).all()
    else:
        posts = Post.query.filter(Post.category.ilike(selected)).order_by(Post.pub_date.desc()).limit(90).all()
    return render_template_string(HTML, posts=posts, categories=CATEGORIES, selected=selected)

@app.route('/generate')
def generate():
    prefixes = ["Na Wa O!", "Gist Alert:", "You Won't Believe:", "Naija Gist:", "Breaking:", "Omo!", "Chai!", "E Don Happen!"]
    added = 0
    random.shuffle(FEEDS)
    for cat, url in FEEDS:
        try:
            f = feedparser.parse(url)
            for e in f.entries[:15]:
                if not getattr(e, 'link', None) or Post.query.filter_by(link=e.link).first():
                    continue
                image = extract_image(e)
                title = random.choice(prefixes) + " " + BeautifulSoup(e.title, 'html.parser').get_text()
                content = getattr(e, "summary", "") or getattr(e, "description", "") or ""
                excerpt = BeautifulSoup(content, 'html.parser').get_text()[:340] + "..."
                pub_date = getattr(e, "published", datetime.now().isoformat())
                db.session.add(Post(title=title, excerpt=excerpt, link=e.link,
                                  image=image, category=cat, pub_date=pub_date))
                added += 1
        except: continue
    if added: db.session.commit()
    return f"NaijaBuzz UPDATED! Added {added} fresh stories!"

HTML = '''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NaijaBuzz - Nigeria News, Football, Gossip & Entertainment</title>
<meta name="description" content="Latest Naija news, BBNaija, Premier League, Tech & World updates - updated every 5 mins!">
<link rel="canonical" href="https://blog.naijabuzz
