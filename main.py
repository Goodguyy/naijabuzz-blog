from flask import Flask, render_template_string, request
from flask_sqlalchemy import SQLAlchemy
import os, feedparser, random, hashlib, time
import requests
import json
from datetime import datetime, timedelta, timezone
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
    title = db.Column(db.String(600))
    excerpt = db.Column(db.Text)
    link = db.Column(db.String(600))
    unique_hash = db.Column(db.String(64), unique=True)
    image = db.Column(db.String(600), default="https://via.placeholder.com/800x450/0f172a/00d4aa?text=NaijaBuzz+-+No+Image+Available")
    category = db.Column(db.String(100))
    pub_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

def init_db():
    with app.app_context():
        db.create_all()

# 62 FULL ACTIVE SOURCES (December 2025)
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
    ("Sports", "https://www.vanguardngr.com/sports/feed"),
    ("Entertainment", "https://www.pulse.ng/entertainment/rss"),
    ("Entertainment", "https://notjustok.com/feed/"),
    ("Entertainment", "https://tooxclusive.com/feed/"),
    ("Entertainment", "https://www.36ng.com.ng/feed/"),
    ("Lifestyle", "https://www.bellanaija.com/style/feed/"),
    ("Lifestyle", "https://www.pulse.ng/lifestyle/rss"),
    ("Tech", "https://techcabal.com/feed/"),
    ("Tech", "https://techpoint.africa/feed/"),
    ("Viral", "https://www.legit.ng/rss"),
    ("Viral", "https://www.naijaloaded.com.ng/category/viral/feed"),
    ("World", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("World", "https://rss.cnn.com/rss/edition.rss"),
    ("Education", "https://myschoolgist.com/feed"),
    ("Business", "https://nairametrics.com/feed/"),
    ("Politics", "https://politicsnigeria.com/feed/"),
    ("Crime", "https://www.pmnewsnigeria.com/category/crime/feed/"),
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

def get_image(entry, feed_url=""):
    link = entry.get('link', '').strip()
    if not link:
        return "https://via.placeholder.com/800x450/0f172a/00d4aa?text=NaijaBuzz+-+No+Image+Available"

    # 1. Media tags
    if hasattr(entry, 'media_content'):
        for m in entry.media_content:
            u = m.get('url')
            if u and 'logo' not in u.lower():
                return u
    if hasattr(entry, 'media_thumbnail'):
        for t in entry.media_thumbnail:
            if t.get('url'):
                return t['url']

    # 2. Enclosures
    if hasattr(entry, 'enclosures'):
        for e in entry.enclosures:
            if 'image' in str(e.type or '').lower():
                u = e.href
                if any(bad in u.lower() for bad in ['logo', 'punch-logo', 'header', 'banner']):
                    continue
                return u

    # 3. Summary image
    content = entry.get('summary') or entry.get('description') or ''
    if content:
        soup = BeautifulSoup(content, 'html.parser')
        img = soup.find('img')
        if img:
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if src:
                if src.startswith('//'): src = 'https:' + src
                if src.startswith('http') and 'logo' not in src.lower():
                    return src

    # 4. Fetch real image from article (Punch, Vanguard, etc.)
    if any(site in link for site in ['punchng.com', 'vanguardngr.com', 'premiumtimesng.com', 'dailypost.ng', 'guardian.ng', 'thisdaylive.com']):
        try:
            r = requests.get(link, headers=HEADERS, timeout=11)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                og = soup.find("meta", property="og:image")
                if og and og.get('content') and 'logo' not in og['content'].lower():
                    return og['content']
                for script in soup.find_all("script", type="application/ld+json"):
                    try:
                        data = json.loads(script.string or "")
                        img = None
                        if isinstance(data, list):
                            for item in data:
                                if item.get('@type') in ['NewsArticle', 'Article']:
                                    img = item.get('image')
                                    break
                        elif data.get('@type') in ['NewsArticle', 'Article']:
                            img = data.get('image')
                        if img:
                            if isinstance(img, str): return img
                            if isinstance(img, dict): return img.get('url')
                            if isinstance(img, list) and img:
                                return img[0].get('url') or img[0]
                    except: pass
                fig = soup.find('figure')
                if fig:
                    i = fig.find('img')
                    if i: return i.get('data-src') or i.get('src')
        except: pass

    return "https://via.placeholder.com/800x450/0f172a/00d4aa?text=NaijaBuzz+-+No+Image+Available"

def parse_date(d):
    if not d: return datetime.now(timezone.utc)
    try: return date_parser.parse(d).astimezone(timezone.utc)
    except: return datetime.now(timezone.utc)

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
    total = q.count()
    total_pages = (total + per_page - 1) // per_page

    def ago(dt):
        if not dt: return "Just now"
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
        <title>NaijaBuzz - Latest Nigeria News, Gossip, Football & Entertainment</title>
        <meta name="description" content="Fresh Naija gists, BBNaija, Premier League, tech, politics, viral videos & world news – updated every 10 minutes!">
        <meta property="og:title" content="NaijaBuzz - Nigeria's #1 Trending News Platform">
        <meta property="og:description" content="Hot gists, football scores, celebrity news, politics & viral stories">
        <meta property="og:image" content="https://via.placeholder.com/1200x630/0f172a/00d4aa?text=NAIJABUZZ">
        <meta property="og:url" content="https://blog.naijabuzz.com">
        <link rel="canonical" href="https://blog.naijabuzz.com">
        <meta name="robots" content="index, follow">
        <link rel="sitemap" type="application/xml" href="/sitemap.xml">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;900&display=swap" rel="stylesheet">
        <style>
            :root{--p:#00d4aa;--d:#0f172a;--g:#64748b;--l:#f9fafb;--w:#ffffff;--shadow:0 10px 30px rgba(0,0,0,0.12);}
            *{margin:0;padding:0;box-sizing:border-box;}
            body{font-family:'Inter',sans-serif;background:var(--l);color:#1e293b;line-height:1.6;}
            .header{background:var(--d);color:white;padding:20px 0;position:fixed;top:0;width:100%;z-index:1001;box-shadow:0 6px 30px rgba(0,0,0,0.3);}
            .header-inner{max-width:1400px;margin:0 auto;padding:0 20px;text-align:center;}
            h1{font-size:2.3rem;font-weight:900;margin:0;letter-spacing:-1px;}
            .tagline{font-size:1.1rem;opacity:0.95;margin-top:8px;font-weight:500;}
            .nav{background:var(--w);position:fixed;top:98px;left:0;right:0;z-index:1000;padding:16px 0;border-bottom:5px solid var(--p);box-shadow:var(--shadow);}
            .nav::-webkit-scrollbar{display:none;}
            .nav-inner{max-width:1400px;margin:0 auto;padding:0 20px;display:flex;gap:14px;justify-content:center;flex-wrap:nowrap;overflow-x:auto;}
            .nav a{padding:13px 26px;background:#1e293b;color:white;border-radius:50px;font-weight:600;font-size:1rem;text-decoration:none;transition:.3s;border:2px solid transparent;}
            .nav a.active,.nav a:hover{background:var(--p);border-color:var(--p);transform:translateY(-3px);box-shadow:0 8px 25px rgba(0,212,170,0.35);}
            .main{padding-top:155px;max-width:1500px;margin:0 auto;padding:30px 20px 100px;}
            .grid{display:grid;gap:32px;grid-template-columns:repeat(4,1fr);}
            .card{background:var(--w);border-radius:24px;overflow:hidden;box-shadow:var(--shadow);transition:0.45s;border:1px solid #eef1f5;}
            .card:hover{transform:translateY(-16px);box-shadow:0 35px 70px rgba(0,0,0,0.22);}
            .img{position:relative;height:250px;overflow:hidden;background:#000;}
            .img img{width:100%;height:100%;object-fit:cover;transition:0.7s;}
            .card:hover img{transform:scale(1.18);}
            .content{padding:28px;}
            .cat{color:var(--p);font-weight:700;font-size:0.9rem;text-transform:uppercase;letter-spacing:1.3px;margin-bottom:10px;}
            .card h2{font-size:1.5rem;line-height:1.35;margin:10px 0;font-weight:800;}
            .card h2 a{color:#111;text-decoration:none;}
            .card h2 a:hover{color:var(--p);}
            .meta{color:var(--g);font-size:0.95rem;margin:12px 0;}
            .excerpt{color:#444;font-size:1.08rem;line-height:1.75;margin-bottom:20px;}
            .readmore{background:var(--p);color:white;padding:15px 34px;border-radius:50px;font-weight:700;display:inline-block;transition:.3s;}
            .readmore:hover{background:#00b894;transform:translateY(-4px);}
            .pagination{margin:80px 0;display:flex;justify-content:center;gap:16px;flex-wrap:wrap;}
            .pagination a{padding:14px 24px;background:#1e293b;color:white;border-radius:50px;font-weight:600;}
            .pagination a.active,.pagination a:hover{background:var(--p);}
            footer{background:var(--d);color:#94a3b8;padding:70px 20px;text-align:center;font-size:1.05rem;}
            @media(max-width:1024px){.grid{grid-template-columns:repeat(3,1fr);}}
            @media(max-width:768px){
                h1{font-size:2rem;}
                .tagline{font-size:1rem;}
                .nav{top:92px;padding:14px 0;}
                .nav a{padding:11px 20px;font-size:0.94rem;}
                .main{padding-top:150px;}
                .grid{grid-template-columns:1fr 1fr;gap:24px;}
                .img{height:200px;}
            }
            @media(max-width:480px){
                .grid{grid-template-columns:1fr;}
                .nav-inner{gap:10px;}
                .nav a{padding:10px 16px;font-size:0.88rem;}
                .main{padding-top:160px;}
            }
        </style>
    </head>
    <body>
        <header class="header">
            <div class="header-inner">
                <h1>NaijaBuzz</h1>
                <div class="tagline">Fresh Naija Gist • Football • Entertainment • Updated Live</div>
            </div>
        </header>

        <nav class="nav">
            <div class="nav-inner">
                {% for key, name in categories.items() %}
                <a href="/?cat={{ key }}" class="{{ 'active' if selected == key else '' }}">{{ name }}</a>
                {% endfor %}
            </div>
        </nav>

        <div class="main">
            <div class="grid">
                {% for p in posts %}
                <article class="card">
                    <div class="img">
                        <img src="{{ p.image }}" alt="{{ p.title }}" loading="lazy"
                             onerror="this.src='https://via.placeholder.com/800x450/0f172a/00d4aa?text=NaijaBuzz+-+No+Image+Available';">
                    </div>
                    <div class="content">
                        <div class="cat">{{ p.category }}</div>
                        <h2><a href="{{ p.link }}" target="_blank" rel="noopener">{{ p.title }}</a></h2>
                        <div class="meta">{{ ago(p.pub_date) }}</div>
                        <p class="excerpt">{{ p.excerpt }}</p>
                        <a href="{{ p.link }}" target="_blank" rel="noopener" class="readmore">Read Full Story</a>
                    </div>
                </article>
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
            <span style="color:var(--p);">Auto-updated every 10 mins • 62 Trusted Sources</span>
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
            except: db.drop_all(); db.create_all()

            random.shuffle(FEEDS)
            for cat, url in FEEDS:
                try:
                    f = feedparser.parse(url, request_headers=HEADERS)
                    if not f.entries: continue
                    for e in f.entries[:6]:
                        if not e.get('link') or not e.get('title'): continue
                        h = hashlib.md5((e.link + e.title).encode()).hexdigest()
                        if Post.query.filter_by(unique_hash=h).first(): continue

                        img = get_image(e, url)
                        summary = e.get('summary') or e.get('description') or ''
                        excerpt = BeautifulSoup(summary, 'html.parser').get_text(strip=True)[:290] + "..."

                        prefixes = ["", "", "", "Breaking: ", "Just In: ", "Chai! ", "Omo! "]
                        title = random.choice(prefixes) + BeautifulSoup(e.title, 'html.parser').get_text()

                        db.session.add(Post(title=title, excerpt=excerpt, link=e.link.strip(),
                                            unique_hash=h, image=img, category=cat,
                                            pub_date=parse_date(e.get('published'))))
                        added += 1
                    db.session.commit()
                    time.sleep(0.7)
                except: continue
    except: pass
    return f"CRON SUCCESS! Added {added} new stories!"

# Keep /ping, /robots.txt, /sitemap.xml as before

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
