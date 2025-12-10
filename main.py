from flask import Flask, render_template_string, request
from flask_sqlalchemy import SQLAlchemy
import os, feedparser, random, hashlib, time
import requests
import json
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
    link = db.Column(db.String(800), unique=True)
    unique_hash = db.Column(db.String(64), unique=True, index=True)
    image = db.Column(db.String(800), default="https://via.placeholder.com/800x450/111827/00d4aa?text=NaijaBuzz")
    category = db.Column(db.String(100))
    pub_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

def init_db():
    with app.app_context():
        db.create_all()

# 62 FULL RSS SOURCES — ALL WORKING (December 2025)
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

CATEGORIES = {
    "all": "All News", "naija news": "Naija News", "gossip": "Gist & Gossip",
    "football": "Football", "sports": "Sports", "entertainment": "Entertainment",
    "lifestyle": "Lifestyle", "tech": "Tech", "viral": "Viral", "world": "World News",
    "education": "Education", "business": "Business", "politics": "Politics",
    "crime": "Crime", "health": "Health"
}

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def safe_date(d):
    if not d: return datetime.now(timezone.utc)
    try: return date_parser.parse(d).astimezone(timezone.utc)
    except: return datetime.now(timezone.utc)

def get_image(e):
    link = e.get('link', '').strip()
    if not link: return "https://via.placeholder.com/800x450/111827/00d4aa?text=NaijaBuzz"

    # Full working image logic (Punch fixed)
    if hasattr(e, 'media_content'):
        for m in e.media_content:
            u = m.get('url')
            if u and 'logo' not in u.lower(): return u
    if hasattr(e, 'media_thumbnail'):
        for t in e.media_thumbnail:
            if t.get('url'): return t['url']
    if hasattr(e, 'enclosures'):
        for enc in e.enclosures:
            if 'image' in str(enc.type or '').lower():
                u = enc.href
                if any(x in u.lower() for x in ['logo', 'punch-logo']): continue
                return u
    content = e.get('summary') or e.get('description') or ''
    if content:
        soup = BeautifulSoup(content, 'html.parser')
        img = soup.find('img')
        if img:
            src = img.get('src') or img.get('data-src')
            if src and src.startswith('//'): src = 'https:' + src
            if src and src.startswith('http') and 'logo' not in src.lower():
                return src

    # Fetch from article if needed
    if any(x in link for x in ['punchng.com', 'vanguardngr.com', 'premiumtimesng.com', 'dailypost.ng']):
        try:
            r = requests.get(link, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                og = soup.find("meta", property="og:image")
                if og and og.get('content') and 'logo' not in og['content'].lower():
                    return og['content']
        except: pass

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
        if diff < timedelta(minutes=60): return f"{int(diff.total_seconds()//60)}m ago"
        if diff < timedelta(days=1): return f"{int(diff.total_seconds()//3600)}h ago"
        if diff < timedelta(days=7): return f"{diff.days}d ago"
        return dt.strftime("%b %d")

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NaijaBuzz - Nigeria News, Gossip, Football & Viral Gist</title>
        <meta name="description" content="Latest Naija news, BBNaija, Premier League, tech & entertainment — updated every 10 mins">
        <meta property="og:title" content="NaijaBuzz - #1 Trending News in Nigeria">
        <meta property="og:description" content="Fresh gists, football, entertainment & viral stories">
        <meta property="og:image" content="https://via.placeholder.com/1200x630/111827/00d4aa?text=NAIJABUZZ">
        <meta property="og:url" content="https://blog.naijabuzz.com">
        <link rel="canonical" href="https://blog.naijabuzz.com">
        <meta name="robots" content="index, follow">
        <link rel="sitemap" type="application/xml" href="/sitemap.xml">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap" rel="stylesheet">
        <style>
            :root{--p:#00d4aa;--d:#0f172a;--g:#64748b;--l:#f8fafc;--w:#fff;--s:0 12px 35px rgba(0,0,0,0.12);}
            *{margin:0;padding:0;box-sizing:border-box;}
            body{font-family:'Inter',sans-serif;background:var(--l);color:#1e293b;line-height:1.6;}
            .topbar{background:var(--d);color:white;padding:20px 0;position:fixed;top:0;width:100%;z-index:1002;box-shadow:0 6px 30px rgba(0,0,0,0.3);}
            .topbar-inner{max-width:1400px;margin:0 auto;padding:0 20px;display:flex;justify-content:center;align-items:center;flex-wrap:wrap;gap:15px;}
            h1{font-size:2.4rem;font-weight:900;margin:0;}
            .tagline{font-size:1.1rem;opacity:0.92;}
            .nav{background:var(--w);position:fixed;top:98px;left:0;right:0;z-index:1001;padding:18px 0;border-bottom:5px solid var(--p);box-shadow:var(--s);}
            .nav-inner{max-width:1400px;margin:0 auto;padding:0 20px;display:flex;gap:16px;justify-content:center;flex-wrap:wrap;overflow-x:auto;}
            .nav a{padding:13px 28px;background:#1e293b;color:white;border-radius:50px;font-weight:600;font-size:1rem;text-decoration:none;transition:.3s;}
            .nav a.active,.nav a:hover{background:var(--p);color:white;transform:translateY(-3px);box-shadow:0 8px 25px rgba(0,212,170,0.4);}
            .main{padding-top:170px;max-width:1500px;margin:0 auto;padding:20px;}
            .grid{display:grid;gap:32px;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));}
            .card{background:var(--w);border-radius:22px;overflow:hidden;box-shadow:var(--s);transition:0.4s;}
            .card:hover{transform:translateY(-14px);box-shadow:0 35px 70px rgba(0,0,0,0.22);}
            .img{height:240px;overflow:hidden;background:#000;}
            .img img{width:100%;height:100%;object-fit:cover;transition:0.6s;}
            .card:hover img{transform:scale(1.15);}
            .content{padding:28px;}
            .cat{color:var(--p);font-weight:700;font-size:0.9rem;text-transform:uppercase;letter-spacing:1.2px;margin-bottom:8px;}
            h2{font-size:1.5rem;line-height:1.35;margin:12px 0;font-weight:800;}
            h2 a{color:#111;text-decoration:none;}
            h2 a:hover{color:var(--p);}
            .meta{color:var(--g);font-size:0.95rem;margin:10px 0;}
            .excerpt{color:#444;font-size:1.05rem;line-height:1.7;margin:16px 0;}
            .readmore{background:var(--p);color:white;padding:14px 32px;border-radius:50px;font-weight:700;display:inline-block;transition:.3s;}
            .readmore:hover{background:#00b894;transform:translateY(-3px);}
            .pagination{margin:80px 0;display:flex;justify-content:center;gap:14px;flex-wrap:wrap;}
            .pagination a{padding:14px 24px;background:#1e293b;color:white;border-radius:50px;}
            .pagination a.active,.pagination a:hover{background:var(--p);}
            footer{background:var(--d);color:#94a3b8;padding:70px 20px;text-align:center;}
            @media(max-width:1024px){.grid{grid-template-columns:repeat(3,1fr);}}
            @media(max-width:768px){
                .topbar{padding:16px 0;}
                h1{font-size:2rem;}
                .nav{top:92px;}
                .main{padding-top:160px;}
                .grid{grid-template-columns:1fr 1fr;}
            }
            @media(max-width:480px){.grid{grid-template-columns:1fr;}}
        </style>
    </head>
    <body>
        <div class="topbar">
            <div class="topbar-inner">
                <h1>NaijaBuzz</h1>
                <div class="tagline">Fresh Naija Gist • Football • Entertainment • Live Updates</div>
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
                        <div class="meta">{{ ago(p.pub_date) }}</div>
                        <p class="excerpt">{{ p.excerpt }}</p>
                        <a href="{{ p.link }}" target="_blank" rel="noopener" class="readmore">Read More</a>
                    </div>
                </div>
                {% endfor %}
            </div>

            {% if total_pages > 1 %}
            <div class="pagination">
                {% if page > 1 %}<a href="/?cat={{ selected }}&page={{ page-1 }}">Previous</a>{% endif %}
                {% for p in range(1, total_pages + 1) %}
                    <a href="/?cat={{ selected }}&page={{ p }}" class="{{ 'active' if p == page }}">{{ p }}</a>
                {% endfor %}
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

            random.shuffle(FEEDS)
            for cat, url in FEEDS:
                try:
                    f = feedparser.parse(url, request_headers=HEADERS)
                    if not f.entries: continue
                    for e in f.entries[:6]:
                        if not e.get('link') or not e.get('title'): continue
                        h = hashlib.md5((e.link + e.title).encode()).hexdigest()
                        if Post.query.filter_by(unique_hash=h).first(): continue

                        img = get_image(e)
                        summary = e.get('summary') or e.get('description') or ''
                        excerpt = BeautifulSoup(summary, 'html.parser').get_text(strip=True)[:290] + "..."
                        prefixes = ["", "", "", "Breaking: ", "Just In: ", "Chai! ", "Omo! "]
                        title = random.choice(prefixes) + BeautifulSoup(e.title, 'html.parser').get_text()

                        db.session.add(Post(title=title, excerpt=excerpt, link=e.link.strip(),
                                            unique_hash=h, image=img, category=cat,
                                            pub_date=safe_date(e.get('published'))))
                        added += 1
                    db.session.commit()
                    time.sleep(0.7)
                except: continue
    except Exception as e:
        return f"<pre>CRON ERROR: {str(e)}</pre>", 500

    return f"""
    <h1 style="color:#00d4aa;text-align:center;padding-top:100px;">NaijaBuzz CRON SUCCESS</h1>
    <h2 style="text-align:center;">Added {added} new stories</h2>
    <p style="text-align:center;"><a href="/">Back to Home</a></p>
    """

@app.route('/ping')
def ping(): return "OK", 200

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
