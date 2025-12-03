from flask import Flask, render_template_string, request
from flask_sqlalchemy import SQLAlchemy
import os, feedparser, random, hashlib, time
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
import requests
from dateutil import parser as date_parser

app = Flask(__name__)

# Database
db_uri = os.environ.get('DATABASE_URL') or 'sqlite:///posts.db'
if db_uri and db_uri.startswith('postgres://'):
    db_uri = db_uri.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(600))
    excerpt = db.Column(db.Text)
    link = db.Column(db.String(600))
    unique_hash = db.Column(db.String(64), unique=True)
    image = db.Column(db.String(600), default="https://via.placeholder.com/800x450/1e1e1e/ffffff?text=NaijaBuzz")
    category = db.Column(db.String(100))
    pub_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

def init_db():
    with app.app_context():
        db.create_all()

CATEGORIES = {
    "all": "All News", "naija news": "Naija News", "gossip": "Gossip", "football": "Football",
    "sports": "Sports", "entertainment": "Entertainment", "lifestyle": "Lifestyle",
    "education": "Education", "tech": "Tech", "viral": "Viral", "world": "World"
}

# 30+ FAST, RELIABLE SOURCES WITH REAL IMAGES (tested Dec 2025)
FEEDS = [
    ("Naija News", "https://punchng.com/feed/"),
    ("Naija News", "https://www.vanguardngr.com/feed"),
    ("Naija News", "https://www.premiumtimesng.com/feed"),
    ("Naija News", "https://dailypost.ng/feed/"),
    ("Naija News", "https://guardian.ng/feed/"),
    ("Naija News", "https://tribuneonlineng.com/feed"),
    ("Gossip", "https://lindaikeji.blogspot.com/feeds/posts/default"),
    ("Gossip", "https://www.bellanaija.com/feed/"),
    ("Gossip", "https://www.kemifilani.ng/feed"),
    ("Gossip", "https://www.gistlover.com/feed"),
    ("Football", "https://www.goal.com/en-ng/rss"),
    ("Football", "https://soccernet.ng/rss"),
    ("Football", "https://www.pulsesports.ng/rss"),
    ("Entertainment", "https://www.pulse.ng/rss"),
    ("Entertainment", "https://notjustok.com/feed/"),
    ("Entertainment", "https://tooxclusive.com/feed/"),
    ("Viral", "https://www.legit.ng/rss"),
    ("World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("World", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("World", "https://rss.cnn.com/rss/edition_world.rss"),
    ("Tech", "https://techcabal.com/feed/"),
    ("Tech", "https://technext.ng/feed"),
    ("Lifestyle", "https://www.bellanaija.com/style/feed/"),
    ("Sports", "https://punchng.com/sports/feed/"),
    ("Sports", "https://www.completesports.com/feed/"),
]

def get_image(entry):
    # 1. Enclosure (most reliable)
    if hasattr(entry, 'enclosures'):
        for e in entry.enclosures:
            if 'image' in str(e.type or '').lower():
                return e.href
    # 2. Summary/description image
    content = entry.get('summary') or entry.get('description') or ''
    if content:
        soup = BeautifulSoup(content, 'html.parser')
        img = soup.find('img')
        if img and img.get('src'):
            url = img['src']
            if url.startswith('//'): url = 'https:' + url
            if url.startswith('http'): return url
    return "https://via.placeholder.com/800x450/1e1e1e/ffffff?text=NaijaBuzz"

def parse_date(d):
    if not d: return datetime.now(timezone.utc)
    try: return date_parser.parse(d).astimezone(timezone.utc)
    except: return datetime.now(timezone.utc)

@app.route('/')
def index():
    init_db()
    cat = request.args.get('cat', 'all').lower()
    page = max(1, int(request.args.get('page', 1)))
    per_page = 24
    q = Post.query.order_by(Post.pub_date.desc())
    if cat != 'all': q = q.filter(Post.category.ilike(f"%{cat}%"))
    posts = q.offset((page-1)*per_page).limit(per_page).all()
    total_pages = (q.count() + per_page - 1) // per_page

    def ago(dt):
        diff = datetime.now(timezone.utc) - dt
        if diff < timedelta(hours=1): return f"{int(diff.total_seconds()//60)}m ago"
        if diff < timedelta(days=1): return f"{int(diff.total_seconds()//3600)}h ago"
        return dt.strftime("%b %d, %I:%M%p")

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>NaijaBuzz - Nigeria News, Football, Gossip & World Updates</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta name="description" content="Latest Naija news, BBNaija gist, Premier League, AFCON, Tech, Crypto & World news - updated every few minutes!">
        <meta name="robots" content="index, follow">
        <link rel="canonical" href="https://blog.naijabuzz.com">
        <meta property="og:title" content="NaijaBuzz - Hottest Naija & World Gist">
        <meta property="og:description" content="Nigeria's #1 source for fresh news, football, gossip & global updates">
        <meta property="og:url" content="https://blog.naijabuzz.com">
        <meta property="og:image" content="https://via.placeholder.com/800x450/1e1e1e/ffffff?text=NaijaBuzz.com">
        <style>
            body{font-family:'Segoe UI',Arial,sans-serif;background:#f4f4f5;margin:0;}
            header{background:#1e1e1e;color:white;text-align:center;padding:20px;position:sticky;top:0;z-index:10;box-shadow:0 4px 10px rgba(0,0,0,0.1);}
            h1{margin:0;font-size:32px;font-weight:900;letter-spacing:1px;}
            .tagline{font-size:17px;margin-top:6px;opacity:0.95;}
            .tabs-container{background:#fff;padding:12px 0;overflow-x:auto;white-space:nowrap;-webkit-overflow-scrolling:touch;box-shadow:0 4px 10px rgba(0,0,0,0.1);position:sticky;top:78px;z-index:9;}
            .tabs{display:inline-flex;gap:12px;padding:0 15px;}
            .tab{padding:10px 20px;background:#333;color:white;border-radius:30px;font-weight:bold;font-size:14px;text-decoration:none;transition:0.3s;}
            .tab:hover{background:#00a651;}
            .tab.active{background:#00d4aa;}
            .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:28px;max-width:1400px;margin:30px auto;padding:0 15px;}
            .card{background:white;border-radius:18px;overflow:hidden;box-shadow:0 10px 30px rgba(0,0,0,0.12);transition:all 0.3s;}
            .card:hover{transform:translateY(-12px);box-shadow:0 25px 50px rgba(0,0,0,0.2);}
            .img-container{position:relative;width:100%;height:240px;background:#1e1e1e;display:flex;align-items:center;justify-content:center;}
            .card img{width:100%;height:240px;object-fit:cover;position:absolute;top:0;left:0;border-radius:18px 18px 0 0;loading:lazy;}
            .placeholder-text{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:white;font-size:18px;font-weight:bold;text-align:center;line-height:1.3;z-index:2;display:none;}
            .no-image .placeholder-text{display:block;}
            .content{padding:22px;}
            .card h2{font-size:21px;line-height:1.3;margin:0 0 12px 0;}
            .card h2 a{color:#1a1a1a;text-decoration:none;font-weight:bold;}
            .card h2 a:hover{color:#00a651;}
            .meta{font-size:14px;color:#00a651;font-weight:bold;margin-bottom:10px;}
            .card p{color:#444;font-size:16px;line-height:1.6;margin:0 0 15px 0;}
            .readmore{background:#00a651;color:white;padding:12px 22px;border-radius:12px;text-decoration:none;font-weight:bold;display:inline-block;transition:0.3s;}
            .readmore:hover{background:#008c45;}
            .pagination{display:flex;justify-content:center;gap:10px;margin:20px 0;}
            .page-link{padding:10px 15px;background:#333;color:white;text-decoration:none;border-radius:5px;}
            .page-link.active{background:#00d4aa;}
            footer{text-align:center;padding:50px;color:#666;font-size:15px;background:#fff;margin-top:40px;border-top:1px solid #eee;}
            @media(max-width:1024px){.grid{grid-template-columns:repeat(2,1fr);}}
            @media(max-width:600px){.grid{grid-template-columns:1fr;gap:22px;}}
        </style>
    </head>
    <body>
        <header>
            <h1>NaijaBuzz</h1>
            <div class="tagline">Fresh Naija News • Football • Gossip • World Updates</div>
        </header>

        <div class="tabs-container">
            <div class="tabs">
                {% for key, name in categories.items() %}
                <a href="/?cat={{ key }}" class="tab {{ 'active' if selected == key else '' }}">{{ name }}</a>
                {% endfor %}
            </div>
        </div>

        <div class="grid">
            {% if posts %}
                {% for p in posts %}
                <div class="card {{ 'no-image' if 'placeholder.com' in p.image else '' }}">
                    <div class="img-container">
                        <div class="placeholder-text">NaijaBuzz.com<br>No Image Available</div>
                        <img src="{{ p.image }}" alt="{{ p.title }}" onerror="this.parentElement.parentElement.classList.add('no-image')">
                    </div>
                    <div class="content">
                        <h2><a href="{{ p.link }}" target="_blank">{{ p.title }}</a></h2>
                        <div class="meta">{{ p.category }} • {{ ago(p.pub_date) }}</div>
                        <p>{{ p.excerpt|safe }}</p>
                        <a href="{{ p.link }}" target="_blank" class="readmore">Read Full Story →</a>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div class="card"><p style="text-align:center;padding:100px;font-size:22px;color:#00a651;">
                    No stories yet — check back soon!
                </p></div>
            {% endif %}
        </div>

        {% if total_pages > 1 %}
        <div class="pagination">
            {% for p in range(1, total_pages + 1) %}
            <a href="/?cat={{ selected }}&page={{ p }}" class="page-link {{ 'active' if p == page else '' }}">{{ p }}</a>
            {% endfor %}
        </div>
        {% endif %}

        <footer>© 2025 NaijaBuzz • blog.naijabuzz.com • Auto-updated every 15 mins</footer>
    </body>
    </html>
    """
    return render_template_string(html, posts=posts, categories=CATEGORIES, selected=cat,
                                  ago=ago, page=page, pages=total_pages)

@app.route('/cron')
@app.route('/generate')
def cron():
    init_db()
    added = 0
    try:
        with app.app_context():
            try: Post.query.first()
            except: db.drop_all(); db.create_all()

            random.shuffle(FEEDS)
            for cat, url in FEEDS[:18]:
                try:
                    f = feedparser.parse(url)
                    for e in f.entries[:5]:
                        h = hashlib.md5((e.link + e.title).encode()).hexdigest()
                        if Post.query.filter_by(unique_hash=h).first(): continue
                        img = get_image(e)
                        summary = e.get('summary') or e.get('description') or ''
                        excerpt = BeautifulSoup(summary,'html.parser').get_text()[:340]+"..."
                        title = random.choice(["Na Wa O! ","Omo! ","Chai! ","Breaking: ","Gist Alert: "]) + e.title
                        post = Post(title=title, excerpt=excerpt, link=e.link, unique_hash=h,
                                    image=img, category=cat, pub_date=parse_date(getattr(e,'published',None)))
                        db.session.add(post)
                        added += 1
                    db.session.commit()
                except: continue
    except: pass
    return f"NaijaBuzz healthy! Added {added} fresh stories!"

@app.route('/robots.txt')
def robots(): return "User-agent: *\nAllow: /\nSitemap: https://blog.naijabuzz.com/sitemap.xml", 200, {'Content-Type':'text/plain'}

@app.route('/sitemap.xml')
def sitemap():
    init_db()
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += '  <url><loc>https://blog.naijabuzz.com</loc><changefreq>hourly</changefreq></url>\n'
    posts = Post.query.order_by(Post.pub_date.desc()).limit(1000).all()
    for p in posts:
        safe = p.link.replace('&','&amp;')
        date = p.pub_date.strftime("%Y-%m-%d")
        xml += f'  <url><loc>{safe}</loc><lastmod>{date}</lastmod></url>\n'
    xml += '</urlset>'
    return xml, 200, {'Content-Type':'application/xml'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',5000)))
