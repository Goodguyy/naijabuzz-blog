# main.py - NaijaBuzz REBUILT FROM SCRATCH - 100% WORKING (2025)
from flask import Flask, render_template_string, request
from flask_sqlalchemy import SQLAlchemy
import os, feedparser, random
from datetime import datetime
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
    image = db.Column(db.String(800))
    category = db.Column(db.String(100))
    pub_date = db.Column(db.String(100))

with app.app_context():
    db.create_all()

CATEGORIES = {
    "all": "All News",
    "naija news": "Naija News",
    "gossip": "Gossip",
    "football": "Football",
    "sports": "Sports",
    "entertainment": "Entertainment",
    "lifestyle": "Lifestyle",
    "education": "Education",
    "tech": "Tech",
    "viral": "Viral",
    "world": "World"
}

FEEDS = [
    ("naija news", "https://punchng.com/feed/"),
    ("naija news", "https://vanguardngr.com/feed"),
    ("naija news", "https://premiumtimesng.com/feed"),
    ("naija news", "https://thenationonlineng.net/feed/"),
    ("gossip", "https://lindaikeji.blogspot.com/feeds/posts/default"),
    ("gossip", "https://bellanaija.com/feed/"),
    ("football", "https://www.goal.com/en-ng/feeds/news"),
    ("football", "https://allnigeriasoccer.com/feed"),
    ("sports", "https://www.completesports.com/feed/"),
    ("world", "https://bbc.com/news/world/rss.xml"),
    ("tech", "https://techcabal.com/feed/"),
    ("viral", "https://legit.ng/rss"),
    ("entertainment", "https://pulse.ng/rss"),
    ("entertainment", "https://notjustok.com/feed/"),
    ("lifestyle", "https://sisiyemmie.com/feed"),
    ("education", "https://myschoolgist.com/feed"),
]

def extract_image(entry):
    html = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
    if not html: return "https://via.placeholder.com/800x500/0f172a/f8fafc?text=NaijaBuzz"
    soup = BeautifulSoup(html, 'html.parser')
    img = soup.find('img')
    if img:
        src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
        if src:
            if src.startswith('//'): src = 'https:' + src
            return src
    return "https://via.placeholder.com/800x500/0f172a/f8fafc?text=NaijaBuzz"

def time_ago(date_str):
    if not date_str: return "Just now"
    try:
        dt = datetime.fromisoformat(date_str.replace('Z','+00:00'))
        diff = datetime.now() - dt
        if diff.days > 30: return dt.strftime("%b %d")
        if diff.days >= 1: return f"{diff.days}d ago"
        if diff.seconds >= 7200: return f"{diff.seconds//3600}h ago"
        if diff.seconds >= 3600: return "1h ago"
        if diff.seconds >= 120: return f"{diff.seconds//60}m ago"
        return "Just now"
    except:
        return date_str[:16] if len(date_str) >= 16 else "Recently"

app.jinja_env.filters['time_ago'] = time_ago

@app.route('/')
def index():
    cat = request.args.get('cat', 'all').lower()
    if cat == 'all':
        posts = Post.query.order_by(Post.pub_date.desc()).limit(90).all()
    else:
        posts = Post.query.filter(Post.category == cat).order_by(Post.pub_date.desc()).limit(90).all()
    return render_template_string(HTML, posts=posts, categories=CATEGORIES, selected=cat)

@app.route('/generate')
def generate():
    prefixes = ["Na Wa O!", "Gist Alert:", "You Won't Believe:", "Naija Gist:", "Breaking:", "Omo!", "Chai!", "E Don Happen!"]
    added = 0
    random.shuffle(FEEDS)
    for cat, url in FEEDS:
        try:
            f = feedparser.parse(url)
            for e in f.entries[:12]:
                if not e.link or Post.query.filter_by(link=e.link).first():
                    continue
                image = extract_image(e)
                title = random.choice(prefixes) + " " + BeautifulSoup(e.title, 'html.parser').get_text()
                content = getattr(e, "summary", "") or getattr(e, "description", "") or ""
                excerpt = BeautifulSoup(content, 'html.parser').get_text()[:340] + "..."
                pub_date = getattr(e, "published", datetime.now().isoformat())
                db.session.add(Post(title=title, excerpt=excerpt, link=e.link,
                                  image=image, category=cat, pub_date=pub_date))
                added += 1
        except: pass
    if added: db.session.commit()
    return f"NaijaBuzz UPDATED! Added {added} fresh stories!"

HTML = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
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
    .card{background:var(--card);border-radius:16px;overflow:hidden;transition:0.3s;box-shadow:0 10px 30px rgba(0,0,0,0.4);}
    .card:hover{transform:translateY(-10px);}
    .card img{width:100%;height:…
