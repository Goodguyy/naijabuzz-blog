# main.py - NaijaBuzz 100% AUTOMATIC & FIXED (Deploy & Forget Forever)
from flask import Flask, render_template_string, request
from flask_sqlalchemy import SQLAlchemy
import os, feedparser, random, threading, time
from datetime import datetime
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

# Database - Render.com compatible
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
    image = db.Column(db.String(800), default="https://via.placeholder.com/800x500/0f172a/f8fafc?text=NaijaBuzz%20•%20No%20Image")
    category = db.Column(db.String(100))
    pub_date = db.Column(db.String(100))

with app.app_context():
    db.create_all()

CATEGORIES = {
    "all": "All News", "naija news": "Naija News", "gossip": "Gossip", "football": "Football",
    "sports": "Sports", "entertainment": "Entertainment", "lifestyle": "Lifestyle",
    "education": "Education", "tech": "Tech", "viral": "Viral", "world": "World"
}

FEEDS = [
    ("naija news", "https://punchng.com/feed/"), ("naija news", "https://vanguardngr.com/feed"),
    ("naija news", "https://premiumtimesng.com/feed"), ("naija news", "https://thenationonlineng.net/feed/"),
    ("gossip", "https://lindaikeji.blogspot.com/feeds/posts/default"), ("gossip", "https://bellanaija.com/feed/"),
    ("football", "https://www.goal.com/en-ng/feeds/news"), ("football", "https://allnigeriasoccer.com/feed"),
    ("sports", "https://www.completesports.com/feed/"), ("world", "https://bbc.com/news/world/rss.xml"),
    ("tech", "https://techcabal.com/feed/"), ("viral", "https://legit.ng/rss"),
    ("entertainment", "https://pulse.ng/rss"), ("entertainment", "https://notjustok.com/feed/"),
    ("lifestyle", "https://sisiyemmie.com/feed"), ("education", "https://myschoolgist.com/feed"),
]

def extract_best_image(entry):
    default = "https://via.placeholder.com/800x500/0f172a/f8fafc?text=NaijaBuzz%20•%20No%20Image"
    candidates = set()
    for field in ['summary', 'content', 'description', 'summary_detail']:
        if hasattr(entry, field):
            val = getattr(entry, field)
            html = val.get('value', '') if isinstance(val, dict) else str(val)
            soup = BeautifulSoup(html, 'html.parser')
            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                if src:
                    if src.startswith('//'): src = 'https:' + src
                    candidates.add(src)
    for url in candidates:
        if url.lower().endswith(('.jpg','.jpeg','.png','.webp','.gif')) or url.startswith('http'):
            return url
    return default

# MAGIC: Auto-refresh every 12 minutes FOREVER (even on free Render)
def auto_refresh_forever():
    while True:
        time.sleep(720)  # 12 minutes
        with app.app_context():
            generate()

@app.before_first_request
def start_background():
    thread = threading.Thread(target=auto_refresh_forever, daemon=True)
    thread.start()

# Your /generate route (manual or auto)
@app.route('/generate')
def generate():
    prefixes = ["Na Wa O!", "Gist Alert:", "You Won't Believe:", "Naija Gist:", "Breaking:", "Omo!", "Chai!", "E Don Happen!"]
    added = 0
    seen = {p.link for p in Post.query.with_entities(Post.link).all()}
    random.shuffle(FEEDS)
    for cat, url in FEEDS[:10]:
        try:
            f = feedparser.parse(url)
            for e in f.entries[:8]:
                if not hasattr(e, 'link') or e.link in seen: continue
                image = extract_best_image(e)
                raw_title = BeautifulSoup(e.title, 'html.parser').get_text()
                title = random.choice(prefixes) + " " + raw_title
                content = getattr(e, "summary", "") or getattr(e, "description", "") or ""
                excerpt = BeautifulSoup(content, 'html.parser').get_text()[:340] + "..."
                pub_date = getattr(e, "published", datetime.utcnow().isoformat())
                db.session.add(Post(title=title, excerpt=excerpt, link=e.link,
                                  image=image, category=cat.lower(), pub_date=pub_date))
                seen.add(e.link)
                added += 1
        except: continue
    if added:
        db.session.commit()
    return f"Added {added} fresh stories! Site is now on autopilot!"

@app.route('/')
def index():
    selected = request.args.get('cat', 'all').lower()
    q = Post.query.order_by(Post.pub_date.desc())
    if selected != 'all' and selected in CATEGORIES:
        q = q.filter(Post.category.ilike(f"%{selected}%"))
    posts = q.limit(90).all()
    return render_template_string(HTML_TEMPLATE, posts=posts, categories=CATEGORIES, selected=selected)

HTML_TEMPLATE = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>NaijaBuzz - Nigeria News, Football, Gossip & World Updates</title>
<meta name="description" content="Latest Naija news, BBNaija gist, Premier League, Tech & World news - updated every few minutes!">
<meta name="robots" content="index, follow"><link rel="canonical" href="https://blog.naijabuzz.com">
<style>:root{--bg:#0f172a;--card:#1e293b;--text:#e2e8f0;--accent:#00d4aa;--border:#334155;}
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);line-height:1.6;}
header{background:var(--card);padding:1.5rem;text-align:center;box-shadow:0 4px 20px rgba(0,0,0,0.5);}
h1{font-size:2.3rem;font-weight:900;color:var(--accent);}
.tagline{font-size:1.1rem;opacity:0.9;margin-top:0.5rem;}
.tabs-container{position:sticky;top:0;z-index:100;background:var(--card);padding:1rem 0;overflow-x:auto;box-shadow:0 4px 20px rgba(0,0,0,0.5);}
.tabs{display:flex;gap:12px;padding:0 1rem;max-width:1400px;margin:0 auto;}
.tab{padding:12px 22px;background:var(--bg);color:var(--text);border-radius:50px;font-weight:700;text-decoration:none;transition:0.3s;}
.tab:hover,.tab.active{background:var(--accent);color:#000;}
.container{max-width:1400px;margin:2rem auto;padding:0 1rem;}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:1.8rem;}
.card{background:var(--card);border-radius:16px;overflow:hidden;transition:0.3s;box-shadow:0 10px 30px rgba(0,0,0,0.4);}
.card:hover{transform:translateY(-10px);}
.card img{width:100%;height:220px;object-fit:cover;}
.card-content{padding:1.5rem;}
.card h2{font-size:1.35rem;line-height:1.3;margin:0 0 0.8rem;}
.card h2 a{color:var(--text);text-decoration:none;font-weight:700;}
.card h2 a:hover{color:var(--accent);}
.meta{font-size:0.85rem;color:var(--accent);font-weight:700;margin-bottom:0.6rem;text-transform:uppercase;}
.excerpt{color:#94a3b8;font-size:0.98rem;}
.readmore{display:inline-block;margin-top:1rem;padding:10px 22px;background:var(--accent);color:#000;font-weight:bold;border-radius:50px;text-decoration:none;}
.readmore:hover{background:#22d3ee;}
.placeholder{background:linear-gradient(45deg,#1e293b,#334155);height:220px;display:flex;align-items:center;justify-content:center;color:#64748b;}
footer{text-align:center;padding:3rem;color:#64748b;background:var(--card);margin-top:4rem;}
@media(max-width:768px){.grid{grid-template-columns:1fr;}}
</style></head><body>
<header><h1>NaijaBuzz</h1><div class="tagline">Fresh Naija News • Football • Gossip • Entertainment • Updated Live</div></header>
<div class="tabs-container"><div class="tabs">
{% for key, name in categories.items() %}
<a href="?cat={{key}}" class="tab {{'active' if selected == key else ''}}">{{name}}</a>
{% endfor %}
</div></div>
<div class="container"><div class="grid">
{% for p in posts %}
<div class="card">
<a href="{{p.link}}" target="_blank" rel="noopener">
{% if 'placeholder.com' in p.image %}<div class="placeholder"><div>NaijaBuzz<br><small>No Image</small></div></div>
{% else %}<img src="{{p.image}}" alt="{{p.title}}" loading="lazy">{% endif %}
</a>
<div class="card-content">
<div class="meta">{{p.category.upper()}}</div>
<h2><a href="{{p.link}}" target="_blank" rel="noopener">{{p.title}}</a></h2>
{% if p.excerpt %}<p class="excerpt">{{p.excerpt}}</p>{% endif %}
<a href="{{p.link}}" target="_blank" rel="noopener" class="readmore">Read Full Story</a>
</div></div>
{% endfor %}
</div></div>
<footer>© 2025 NaijaBuzz • Auto-updated every 12 minutes • Never dies again!</footer>
</body></html>"""

@app.route('/robots.txt')
def robots(): return "User-agent: *\nAllow: /\nDisallow: /generate\nSitemap: https://blog.naijabuzz.com/sitemap.xml", 200, {'Content-Type': 'text/plain'}

@app.route('/sitemap.xml')
def sitemap():
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += '  <url><loc>https://blog.naijabuzz.com/</loc><changefreq>hourly</changefreq><priority>1.0</priority></url>\n'
    for k in CATEGORIES:
        if k != "all": xml += f'  <url><loc>https://blog.naijabuzz.com/?cat={k}</loc><changefreq>daily</changefreq><priority>0.8</priority></url>\n'
    xml += '</urlset>'
    return xml, 200, {'Content-Type': 'application/xml'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
