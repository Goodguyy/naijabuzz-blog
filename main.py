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

# 20+ UNBLOCKABLE SOURCES — GOOGLE RSS + DIRECT OPEN FEEDS (TESTED LIVE)
FEEDS = [
    # Naija News (8)
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:punchng.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:vanguardngr.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:premiumtimesng.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:thenationonlineng.net&hl=en-NG&gl=NG&ceid=NG:en"),
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:dailypost.ng&hl=en-NG&gl=NG&ceid=NG:en"),
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:saharareporters.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:thecable.ng&hl=en-NG&gl=NG&ceid=NG:en"),
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:thisdaylive.com&hl=en-NG&gl=NG&ceid=NG:en"),
    # Gossip (3)
    ("gossip", "https://news.google.com/rss/search?q=when:24h+site:lindaikejisblog.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("gossip", "https://news.google.com/rss/search?q=when:24h+site:bellanaija.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("gossip", "https://news.google.com/rss/search?q=when:24h+gossip+OR+bbnaija&hl=en-NG&gl=NG&ceid=NG:en"),
    # Football & Sports (4)
    ("football", "https://news.google.com/rss/search?q=when:24h+super+eagles+OR+premier+league+nigeria&hl=en-NG&gl=NG&ceid=NG:en"),
    ("football", "https://news.google.com/rss/search?q=when:24h+site:goal.com+nigeria&hl=en-NG&gl=NG&ceid=NG:en"),
    ("sports", "https://news.google.com/rss/search?q=when:24h+afcon+OR+nigeria+sports&hl=en-NG&gl=NG&ceid=NG:en"),
    ("sports", "https://news.google.com/rss/search?q=when:24h+site:completesports.com&hl=en-NG&gl=NG&ceid=NG:en"),
    # Entertainment (3)
    ("entertainment", "https://news.google.com/rss/search?q=when:24h+bbnaija+OR+nollywood&hl=en-NG&gl=NG&ceid=NG:en"),
    ("entertainment", "https://news.google.com/rss/search?q=when:24h+site:pulse.ng&hl=en-NG&gl=NG&ceid=NG:en"),
    ("entertainment", "https://news.google.com/rss/search?q=when:24h+site:notjustok.com&hl=en-NG&gl=NG&ceid=NG:en"),
    # Tech & Viral (3)
    ("tech", "https://news.google.com/rss/search?q=when:24h+site:techcabal.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("viral", "https://news.google.com/rss/search?q=when:24h+site:legit.ng&hl=en-NG&gl=NG&ceid=NG:en"),
    ("viral", "https://news.google.com/rss/search?q=when:24h+trending+nigeria&hl=en-NG&gl=NG&ceid=NG:en"),
    # World & Lifestyle (2)
    ("world", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"),
    ("lifestyle", "https://news.google.com/rss/search?q=when:24h+fashion+OR+wedding+nigeria&hl=en-NG&gl=NG&ceid=NG:en"),
    # Education (1)
    ("education", "https://news.google.com/rss/search?q=when:24h+jamb+OR+waec+OR+university+nigeria&hl=en-NG&gl=NG&ceid=NG:en"),
]

def extract_image(entry):
    default = "https://via.placeholder.com/800x500/0f172a/f8fafc?text=NaijaBuzz"
    candidates = set()

    # Google thumbnails (fast)
    if hasattr(entry, 'media_content'):
        for m in entry.media_content:
            url = m.get('url')
            if url: candidates.add(url)
    if hasattr(entry, 'enclosures'):
        for e in entry.enclosures:
            if e.url: candidates.add(e.url)

    # Real article page (timeout 5s to avoid Render crash)
    if not candidates and getattr(entry, 'link', None):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            r = requests.get(entry.link, headers=headers, timeout=5)
            soup = BeautifulSoup(r.text, 'html.parser')
            # og:image
            og = soup.find("meta", property="og:image")
            if og and og.get("content"):
                candidates.add(og["content"])
            # First large img
            for img in soup.find_all('img', src=True):
                src = img['src']
                if src and ('large' in src or 'featured' in src or src.endswith(('.jpg', '.jpeg', '.png'))):
                    if src.startswith('//'): src = 'https:' + src
                    candidates.add(src)
        except:
            pass

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
<link rel="canonical" href="https://blog.naijabuzz.com"><link rel="icon" href="https://i.ibb.co/7Y4pY3v/naijabuzz-favicon.png">
<style>
    :root{--bg:#0f172a;--card:#1e293b;--text:#e2e8f0;--accent:#00d4aa;--accent2:#22d3ee;}
    *{margin:0;padding:0;box-sizing:border-box;}
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);}
    header{background:var(--card);padding:1.5rem;text-align:center;box-shadow:0 4px 20px rgba(0,0,0,0.5);}
    h1{font-size:2.4rem;color:var(--accent);font-weight:900;}
    .tagline{font-size:1.1rem;opacity:0.9;}
    .nav{position:sticky;top:0;z-index:100;background:var(--card);padding:1rem 0;overflow-x:auto;box-shadow:0 4px 20px rgba(0,0,0,0.5);}
    .nav-inner{max-width:1400px;margin:0 auto;padding:0 1rem;display:flex;gap:12px;}
    .nav a{padding:12px 20px;background:var(--bg);color:var(--text);text-decoration:none;border-radius:50px;font-weight:700;transition:0.3s;}
    .nav a:hover,.nav a.active{background:var(--accent);color:#000;}
    .container{max-width:1400px;margin:2rem auto;padding:0 1rem;}
    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:1.8rem;}
    .card{background:var(--card);border-radius:16px;overflow:hidden;transition:0.3s;box-shadow:0 10px 30px rgba(0,
