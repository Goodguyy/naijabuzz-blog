# main.py - NaijaBuzz FINAL BULLETPROOF VERSION (2025) - ZERO ERRORS
from flask import Flask, render_template_string, request
from flask_sqlalchemy import SQLAlchemy
import os, feedparser, random, re
from datetime import datetime, timezone
from bs4 import BeautifulSoup

app = Flask(__name__)

# Database
db_uri = os.environ.get('DATABASE_URL')
if db_uri and db_uri.startswith('postgres://'):
    db_uri = db_uri.replace('postgres://', 'postgresql://', 1)
app.config.update(
    SQLALCHEMY_DATABASE_URI=db_uri or 'sqlite:///posts.db',
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True, "pool_recycle": 300}
)
db = SQLAlchemy(app)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(600))
    excerpt = db.Column(db.Text)
    link = db.Column(db.String(600), unique=True)
    image = db.Column(db.String(800), default="https://via.placeholder.com/800x500/0f172a/f8fafc?text=NaijaBuzz")
    category = db.Column(db.String(100))
    pub_date = db.Column(db.DateTime, index=True)

with app.app_context():
    db.create_all()

CATEGORIES = {
    "all": "All News", "naija news": "Naija News", "gossip": "Gossip", "football": "Football",
    "sports": "Sports", "entertainment": "Entertainment", "lifestyle": "Lifestyle",
    "education": "Education", "tech": "Tech", "viral": "Viral", "world": "World"
}

FEEDS = [
    ("Naija News", "https://punchng.com/feed/"),
    ("Naija News", "https://vanguardngr.com/feed"),
    ("Naija News", "https://premiumtimesng.com/feed"),
    ("Naija News", "https://thenationonlineng.net/feed/"),
    ("Gossip", "https://lindaikeji.blogspot.com/feeds/posts/default"),
    ("Gossip", "https://bellanaija.com/feed/"),
    ("Football", "https://www.goal.com/en-ng/feeds/news"),
    ("Football", "https://allnigeriasoccer.com/feed"),
    ("Sports", "https://www.completesports.com/feed/"),
    ("World", "https://bbc.com/news/world/rss.xml"),
    ("Tech", "https://techcabal.com/feed/"),
    ("Viral", "https://legit.ng/rss"),
    ("Entertainment", "https://pulse.ng/rss"),
    ("Entertainment", "https://notjustok.com/feed/"),
    ("Lifestyle", "https://sisiyemmie.com/feed"),
    ("Education", "https://myschoolgist.com/feed"),
]

def extract_image(entry):
    default = "https://via.placeholder.com/800x500/0f172a/f8fafc?text=NaijaBuzz"
    candidates = set()
    html = ""
    for field in ['summary', 'content', 'description', 'summary_detail']:
        if hasattr(entry, field):
            val = getattr(entry, field)
            html += val.get('value', '') if isinstance(val, dict) else str(val)
    if html:
        soup = BeautifulSoup(html, 'html.parser')
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if src:
                if src.startswith('//'): src = 'https:' + src
                if src.startswith('http'):
                    candidates.add(src)
    for url in candidates:
        url = re.sub(r'\?.*$', '', url)
        if url.lower().endswith(('.jpg','.jpeg','.png','.webp','.gif')):
            return url
    return default

def time_ago(dt):
    if not dt: return "Just now"
    now = datetime.now(timezone.utc)
    diff = now - dt
    if diff.days >= 30: return dt.strftime("%b %d")
    elif diff.days >= 1: return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds >= 7200: return f"{diff.seconds // 3600} hours ago"
    elif diff.seconds >= 3600: return "1 hour ago"
    elif diff.seconds >= 120: return f"{diff.seconds // 60} minutes ago"
    elif diff.seconds >= 60: return "1 minute ago"
    else: return "Just now"

app.jinja_env.filters['time_ago'] = time_ago

@app.route('/')
def index():
    cat = request.args.get('cat', 'all').lower()
    q = Post.query.order_by(Post.pub_date.desc())
    if cat != 'all' and cat in CATEGORIES:
        q = q.filter(Post.category.ilike(f"%{cat}%"))
    posts = q.limit(90).all()
    return render_template_string(HTML, posts=posts, categories=CATEGORIES, selected=cat)

@app.route('/generate')
def generate():
    prefixes = ["Na Wa O!", "Gist Alert:", "You Won't Believe:", "Naija Gist:", "Breaking:", "Omo!", "Chai!", "E Don Happen!"]
    added = 0
    random.shuffle(FEEDS)
    for cat, url in FEEDS:
        try:
            feed = feedparser.parse(url, request_headers={'User-Agent': 'NaijaBuzzBot/3.0'})
            for e in feed.entries[:10]:
                if not hasattr(e, 'link') or Post.query.filter_by(link=e.link).first():
                    continue
                pub_date = datetime.now(timezone.utc)
                if hasattr(e, 'published_parsed') and e.published_parsed:
                    pub_date = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
                image = extract_image(e)
                title = random.choice(prefixes) + " " + BeautifulSoup(e.title, 'html.parser').get_text()[:200]
                content = getattr(e, "summary", "") or getattr(e, "description", "") or ""
                excerpt = BeautifulSoup(content, 'html.parser').get_text()[:340] + "..."
                db.session.add(Post(title=title, excerpt=excerpt, link=e.link,
                                  image=image, category=cat, pub_date=pub_date))
                added += 1
        except: continue
    if added: db.session.commit()
    return f"NaijaBuzz FRESH! Added {added} new stories!", 200

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
    .card img{width:100%;height:220px;object-fit:cover;}
    .card-content{padding:1.5rem;}
    .card h2{font-size:1.35rem;line-height:1.3;margin:0 0 0.8rem;}
    .card h2 a{color:var(--text);text-decoration:none;font-weight:700;}
    .card h2 a:hover{color:var(--accent);}
    .meta{font-size:0.85rem;color:var(--accent);font-weight:700;text-transform:uppercase;margin-bottom:0.5rem;}
    .time{font-size:0.8rem;color:#94a3b8;margin-bottom:0.8rem;}
    .excerpt{color:#94a3b8;}
    .readmore{display:inline-block;margin-top:1rem;padding:10px 22px;background:var(--accent);color:#000;font-weight:bold;border-radius:50px;text-decoration:none;}
    .readmore:hover{background:var(--accent2);}
    .placeholder{height:220px;background:linear-gradient(45deg,#1e293b,#334155);display:flex;align-items:center;justify-content:center;color:#64748b;}
    footer{text-align:center;padding:3rem;color:#64748b;background:var(--card);margin-top:4rem;}
    @media(max-width:768px){.grid{grid-template-columns:1fr;}}
</style></head><body>
<header><h1>NaijaBuzz</h1><div class="tagline">Fresh Naija News • Football • Gossip • Entertainment • Updated LIVE</div></header>
<div class="nav"><div class="nav-inner">
{% for k, v in categories.items() %}
<a href="?cat={{k}}" class="{{'active' if selected==k else ''}}">{{v}}</a>
{% endfor %}
</div></div>
<div class="container"><div class="grid">
{% for p in posts %}
<article class="card" itemscope itemtype="https://schema.org/NewsArticle">
<a href="{{p.link}}" target="_blank" rel="noopener">
{% if 'placeholder.com' in p.image %}
<div class="placeholder"><div>NaijaBuzz</div></div>
{% else %}
<img src="{{p.image}}" alt="{{p.title}}" loading="lazy" itemprop="image">
<div class="placeholder" style="display:none"><div>NaijaBuzz</div></div>
{% endif %}
</a>
<div class="card-content">
<div class="meta">{{p.category.upper()}}</div>
<h2 itemprop="headline"><a href="{{p.link}}" target="_blank" rel="noopener" itemprop="url">{{p.title}}</a></h2>
<div class="time"><time datetime="{{p.pub_date.isoformat()}}" itemprop="datePublished">{{p.pub_date|time_ago}}</time></div>
{% if p.excerpt %}<p class="excerpt" itemprop="description">{{p.excerpt}}</p>{% endif %}
<a href="{{p.link}}" target="_blank" rel="noopener" class="readmore">Read Full Story</a>
</div>
</article>
{% endfor %}
</div></div>
<footer>© 2025 NaijaBuzz • Always fresh • Real images • Made in Nigeria</footer>
</body></html>"""

@app.route('/robots.txt')
def robots(): return "User-agent: *\nAllow: /\nSitemap: https://blog.naijabuzz.com/sitemap.xml", 200, {'Content-Type': 'text/plain'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
