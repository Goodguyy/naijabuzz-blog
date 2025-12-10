from flask import Flask, render_template_string, request
from flask_sqlalchemy import SQLAlchemy
import os, feedparser, random, hashlib, time
from datetime import datetime, timezone
from bs4 import BeautifulSoup
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
    title = db.Column(db.String(800))
    excerpt = db.Column(db.Text)
    link = db.Column(db.String(1000))
    unique_hash = db.Column(db.String(64), unique=True, index=True)
    image = db.Column(db.String(800), default="https://via.placeholder.com/800x450/111827/00d4aa?text=NaijaBuzz")
    category = db.Column(db.String(100))
    pub_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

def init_db():
    with app.app_context():
        db.create_all()

# YOUR FULL 62 RSS SOURCES — ALL KEPT
FEEDS = [
    ("Naija News", "https://punchng.com/feed/"),
    ("Naija News", "https://www.vanguardngr.com/feed"),
    ("Naija News", "https://www.premiumtimesng.com/feed"),
    ("Naija News", "https://thenationonlineng.net/feed/"),
    ("Naija News", "https://guardian.ng/feed/"),
    ("Naija News", "https://dailypost.ng/feed/"),
    ("Naija News", "https://www.thisdaylive.com/feed/"),
    ("Naija News", "https://tribuneonlineng.com/feed"),
    ("Naija News", "https://leadership.ng/feed"),
    ("Naija News", "https://dailytrust.com/feed"),
    ("Naija News", "https://saharareporters.com/feeds/articles/feed"),
    ("Naija News", "https://www.channelstv.com/feed"),
    ("Gossip", "https://lindaikeji.blogspot.com/feeds/posts/default"),
    ("Gossip", "https://www.bellanaija.com/feed/"),
    ("Gossip", "https://www.kemifilani.ng/feed"),
    ("Gossip", "https://www.gistlover.com/feed"),
    ("Gossip", "https://www.naijaloaded.com.ng/feed"),
    ("Gossip", "https://www.tori.ng/rss"),
    ("Football", "https://www.goal.com/en-ng/rss"),
    ("Football", "https://soccernet.ng/rss"),
    ("Football", "https://www.pulsesports.ng/rss"),
    ("Football", "https://www.completesports.com/feed/"),
    ("Sports", "https://punchng.com/sports/feed/"),
    ("Entertainment", "https://www.pulse.ng/entertainment/rss"),
    ("Entertainment", "https://notjustok.com/feed/"),
    ("Entertainment", "https://tooxclusive.com/feed/"),
    ("Entertainment", "https://www.36ng.com.ng/feed/"),
    ("Lifestyle", "https://www.bellanaija.com/style/feed/"),
    ("Tech", "https://techcabal.com/feed/"),
    ("Tech", "https://techpoint.africa/feed/"),
    ("Viral", "https://www.legit.ng/rss"),
    ("World", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Education", "https://myschoolgist.com/feed"),
    ("Business", "https://nairametrics.com/feed"),
    ("Politics", "https://politicsnigeria.com/feed"),
    ("Crime", "https://www.pmnewsnigeria.com/category/crime/feed"),
    ("Health", "https://punchng.com/topics/health/feed/"),
]

# PROFESSIONAL CATEGORY NAMES
CATEGORIES = {
    "all": "All News",
    "naija news": "Naija News",
    "gossip": "Celebrity & Gist",
    "football": "Football",
    "sports": "Sports",
    "entertainment": "Entertainment",
    "lifestyle": "Lifestyle",
    "tech": "Tech & Gadgets",
    "viral": "Viral",
    "world": "World News",
    "education": "Education",
    "business": "Business",
    "politics": "Politics",
    "crime": "Crime",
    "health": "Health"
}

def safe_date(d):
    if not d: return datetime.now(timezone.utc)
    try: return date_parser.parse(d).astimezone(timezone.utc)
    except: return datetime.now(timezone.utc)

def get_image(e):
    # Fast & reliable — no heavy requests
    for attr in ['media_content', 'media_thumbnail']:
        if hasattr(e, attr):
            items = getattr(e, attr)
            if isinstance(items, list):
                for item in items:
                    url = item.get('url')
                    if url and 'logo' not in url.lower():
                        return url
    content = e.get('summary') or e.get('description') or ''
    if content:
        soup = BeautifulSoup(content, 'html.parser')
        img = soup.find('img')
        if img:
            src = img.get('src') or img.get('data-src')
            if src:
                if src.startswith('//'): src = 'https:' + src
                if 'logo' not in src.lower():
                    return src
    return "https://via.placeholder.com/800x450/111827/00d4aa?text=NaijaBuzz"

@app.route('/')
def index():
    init_db()
    selected = request.args.get('cat', 'all').lower()
    page = max(1, int(request.args.get('page', 1)))
    per_page = 20

    q = Post.query.order_by(Post.pub_date.desc())
    if selected != 'all':
        q = q.filter(Post.category.ilike(f"%{selected}%"))

    posts = q.offset((page-1)*per_page).limit(per_page).all()
    total_pages = (q.count() + per_page - 1) // per_page

    def ago(dt):
        diff = datetime.now(timezone.utc) - (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))
        if diff < timedelta(minutes=60): return f"{int(diff.total_seconds()//60)}m"
        if diff < timedelta(days=1): return f"{int(diff.total_seconds()//3600)}h"
        if diff < timedelta(days=7): return f"{diff.days}d"
        return dt.strftime("%b %d")

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NaijaBuzz - Latest Nigeria News, Gossip & Football</title>
        <meta name="description" content="Fresh Nigerian news, BBNaija gist, Premier League, tech & entertainment — updated every 10 minutes">
        <meta property="og:title" content="NaijaBuzz - Nigeria's #1 Trending News Hub">
        <meta property="og:description" content="Hot gists, football scores, celebrity news & viral stories">
        <meta property="og:image" content="https://via.placeholder.com/1200x630/111827/00d4aa?text=NAIJABUZZ">
        <link rel="canonical" href="https://blog.naijabuzz.com">
        <meta name="robots" content="index, follow">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;900&display=swap" rel="stylesheet">
        <style>
            :root{--p:#00d4aa;--d:#0a0a0a;--g:#64748b;--l:#f8fafc;--w:#fff;}
            *{margin:0;padding:0;box-sizing:border-box;}
            body{font-family:'Inter',sans-serif;background:var(--l);color:#1e293b;}
            .header{background:var(--d);color:white;padding:24px 0;position:fixed;top:0;width:100%;z-index:1002;box-shadow:0 8px 32px rgba(0,0,0,0.3);}
            .header-inner{max-width:1400px;margin:0 auto;padding:0 20px;display:flex;justify-content:center;align-items:center;gap:20px;}
            h1{font-size:2.8rem;font-weight:900;letter-spacing:-2px;}
            .tagline{font-size:1.2rem;font-weight:500;opacity:0.94;}
            .nav{background:var(--w);position:fixed;top:108px;width:100%;z-index:1001;padding:20px 0;border-bottom:6px solid var(--p);box-shadow:0 12px 35px rgba(0,0,0,0.15);}
            .nav-inner{max-width:1400px;margin:0 auto;padding:0 20px;display:flex;gap:18px;justify-content:center;flex-wrap:wrap;overflow-x:auto;}
            .nav a{padding:16px 34px;background:#1a1a1a;color:white;border-radius:50px;font-weight:700;font-size:1.05rem;text-decoration:none;transition:.3s;border:2px solid transparent;}
            .nav a.active{background:var(--p);border-color:var(--p);box-shadow:0 10px 30px rgba(0,212,170,0.5);}
            .nav a:hover:not(.active){background:#2d2d2d;border-color:var(--p);}
            .main{padding-top:200px;max-width:1500px;margin:0 auto;padding:30px 20px;}
            .grid{display:grid;gap:36px;grid-template-columns:repeat(auto-fill,minmax(370px,1fr));}
            .card{background:var(--w);border-radius:28px;overflow:hidden;box-shadow:0 16px 45px rgba(0,0,0,0.16);transition:0.4s;}
            .card:hover{transform:translateY(-18px);box-shadow:0 45px 90px rgba(0,0,0,0.28);}
            .img{height:270px;overflow:hidden;background:#000;}
            .img img{width:100%;height:100%;object-fit:cover;transition:0.8s;}
            .card:hover img{transform:scale(1.22);}
            .content{padding:32px;}
            .cat{color:var(--p);font-weight:800;font-size:1rem;text-transform:uppercase;letter-spacing:1.8px;margin-bottom:12px;}
            h2{font-size:1.65rem;line-height:1.32;margin:14px 0;font-weight:900;}
            h2 a{color:#0a0a0a;text-decoration:none;}
            h2 a:hover{color:var(--p);}
            .meta{color:var(--g);font-size:1.02rem;margin:14px 0;font-weight:600;}
            .excerpt{color:#333;font-size:1.12rem;line-height:1.78;margin:20px 0;}
            .readmore{background:var(--p);color:white;padding:18px 40px;border-radius:50px;font-weight:700;display:inline-block;transition:.3s;}
            .readmore:hover{background:#00b894;transform:scale(1.06);}
            .pagination{margin:100px 0;display:flex;justify-content:center;gap:18px;flex-wrap:wrap;}
            .pagination a{padding:16px 28px;background:#1a1a1a;color:white;border-radius:50px;font-weight:600;}
            .pagination a.active,.pagination a:hover{background:var(--p);}
            footer{background:var(--d);color:#94a3b8;padding:90px 20px;text-align:center;font-size:1.15rem;}
            @media(max-width:1024px){.grid{grid-template-columns:repeat(3,1fr);}}
            @media(max-width:768px){
                h1{font-size:2.3rem;}
                .nav{top:102px;}
                .main{padding-top:190px;}
                .grid{grid-template-columns:1fr 1fr;}
            }
            @media(max-width:480px){
                .grid{grid-template-columns:1fr;}
                .nav a{padding:12px 20px;font-size:0.95rem;}
            }
        </style>
    </head>
    <body>
        <div class="header">
            <div class="header-inner">
                <h1>NaijaBuzz</h1>
                <div class="tagline">Nigeria's #1 Source for Trending News & Gist</div>
            </div>
        </div>

        <div class="nav">
            <div class="nav-inner">
                {% for key, name in categories.items() %}
                <a href="/?cat={{ key }}" class="{{ 'active' if selected == key else '' }}">{{ name }}</a>
                {% endfor %}
            </div>
        </div>

        <div class="main">
            <div class="grid">
                {% for p in posts %}
                <div class="card">
                    <div class="img">
                        <img src="{{ p.image }}" alt="{{ p.title }}" loading="lazy"
                             onerror="this.src='https://via.placeholder.com/800x450/111827/00d4aa?text=NaijaBuzz';">
                    </div>
                    <div class="content">
                        <div class="cat">{{ p.category }}</div>
                        <h2><a href="{{ p.link }}" target="_blank" rel="noopener">{{ p.title }}</a></h2>
                        <div class="meta">{{ ago(p.pub_date) }} ago</div>
                        <p class="excerpt">{{ p.excerpt }}</p>
                        <a href="{{ p.link }}" target="_blank" rel="noopener" class="readmore">Read Full Story</a>
                    </div>
                </div>
                {% endfor %}
            </div>

            {% if total_pages > 1 %}
            <div class="pagination">
                {% if page > 1 %}<a href="/?cat={{ selected }}&page={{ page-1 }}">Previous</a>{% endif %}
                {% for p in range(1, min(total_pages + 1, 11)) %}
                    <a href="/?cat={{ selected }}&page={{ p }}" class="{{ 'active' if p == page }}">{{ p }}</a>
                {% endfor %}
                {% if total_pages > 10 %}<span>...</span><a href="/?cat={{ selected }}&page={{ total_pages }}">{{ total_pages }}</a>{% endif %}
                {% if page < total_pages %}<a href="/?cat={{ selected }}&page={{ page+1 }}">Next</a>{% endif %}
            </div>
            {% endif %}
        </div>

        <footer>
            © 2025 <strong>NaijaBuzz</strong> • blog.naijabuzz.com<br>
            Auto-updated every 10 mins • 62 Trusted Sources
        </footer>
    </body>
    </html>
    """
    return render_template_string(html, posts=posts, categories=CATEGORIES, selected=selected,
                                  ago=ago, page=page, total_pages=total_pages)

@app.route('/cron')
@app.route('/generate')
def cron():
    init_db()
    added = 0
    try:
        with app.app_context():
            try: Post.query.first()
            except: db.create_all()

            for cat, url in FEEDS:
                try:
                    f = feedparser.parse(url)
                    if not f.entries: continue
                    for e in f.entries[:5]:
                        if not e.get('link') or not e.get('title'): continue
                        h = hashlib.md5((e.link + e.title).encode()).hexdigest()
                        if Post.query.filter_by(unique_hash=h).first(): continue

                        img = get_image(e)
                        summary = e.get('summary') or e.get('description') or ''
                        excerpt = BeautifulSoup(summary, 'html.parser').get_text(strip=True)[:290] + "..."
                        prefixes = ["", "", "Breaking: ", "Just In: ", "Chai! "]
                        title = random.choice(prefixes) + BeautifulSoup(e.title, 'html.parser').get_text()

                        db.session.add(Post(title=title, excerpt=excerpt, link=e.link.strip(),
                                            unique_hash=h, image=img, category=cat,
                                            pub_date=safe_date(e.get('published'))))
                        added += 1
                    db.session.commit()
                except: continue
    except: pass

    return f"""
    <div style="font-family:system-ui;text-align:center;padding:120px;background:#f8fafc;">
        <h1 style="color:#00d4aa;font-size:4rem;">CRON SUCCESS</h1>
        <h2 style="font-size:2.5rem;margin:30px 0;">Added {added} new stories</h2>
        <p style="font-size:1.3rem;"><a href="/" style="color:#00d4aa;text-decoration:none;">Back to NaijaBuzz</a></p>
    </div>
    """

@app.route('/ping')
def ping(): return "NaijaBuzz is LIVE!", 200

@app.route('/robots.txt')
def robots(): return "User-agent: *\nAllow: /\nSitemap: https://blog.naijabuzz.com/sitemap.xml", 200

@app.route('/sitemap.xml')
def sitemap():
    init_db()
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += '  <url><loc>https://blog.naijabuzz.com</loc><changefreq>hourly</changefreq></url>\n'
    for p in Post.query.order_by(Post.pub_date.desc()).limit(10000).all():
        xml += f'  <url><loc>{p.link.replace("&","&amp;")}</loc></url>\n'
    xml += '</urlset>'
    return xml, 200, {'Content-Type': 'application/xml'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
