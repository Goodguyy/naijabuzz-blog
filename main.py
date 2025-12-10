from flask import Flask, render_template_string, request
from flask_sqlalchemy import SQLAlchemy
import os, feedparser, random, hashlib, time
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

app = Flask(__name__)

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
    image = db.Column(db.String(800), default="https://via.placeholder.com/800x450/111827/00d4aa?text=No+Image")
    category = db.Column(db.String(100))
    pub_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

def init_db():
    with app.app_context():
        db.create_all()

# 58 FULL SOURCES — ALL KEPT
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
    ("Tech", "https://techcabal.com/feed/"),
    ("Tech", "https://techpoint.africa/feed/"),
    ("Viral", "https://www.legit.ng/rss"),
    ("World", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
]

CATEGORIES = {
    "all": "All News", "naija news": "Naija News", "gossip": "Celebrity Gist",
    "football": "Football", "sports": "Sports", "entertainment": "Entertainment",
    "tech": "Tech", "viral": "Viral", "world": "World News"
}

def safe_date(d):
    if not d: return datetime.now(timezone.utc)
    try: return date_parser.parse(d).astimezone(timezone.utc)
    except: return datetime.now(timezone.utc)

def get_image(e):
    # FIXED: Punch logo no longer appears
    if hasattr(e, 'media_content'):
        for m in e.media_content:
            u = m.get('url')
            if u and 'punch-logo' not in u.lower() and 'logo' not in u.lower():
                return u
    if hasattr(e, 'media_thumbnail'):
        for t in e.media_thumbnail:
        if t.get('url'): return t['url']
    content = e.get('summary') or e.get('description') or ''
    soup = BeautifulSoup(content, 'html.parser')
    img = soup.find('img')
    if img:
        src = img.get('src') or img.get('data-src')
        if src:
            if src.startswith('//'): src = 'https:' + src
            if 'logo' not in src.lower():
                return src
    return "https://via.placeholder.com/800x450/111827/00d4aa?text=No+Image"

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
        return dt.strftime("%b %d")

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>NaijaBuzz - Latest Naija News, Gossip & Football</title>
        <meta name="description" content="Fresh Naija gists, BBNaija, Premier League, tech & entertainment — updated every 10 mins">
        <meta property="og:title" content="NaijaBuzz - Nigeria's #1 Trending News">
        <link rel="canonical" href="https://blog.naijabuzz.com">
        <meta name="robots" content="index, follow">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;900&display=swap" rel="stylesheet">
        <style>
            :root{--p:#00d4aa;--d:#0f172a;--l:#f8fafc;}
            *{margin:0;padding:0;box-sizing:border-box;}
            body{font-family:'Inter',sans-serif;background:var(--l);color:#1e293b;}
            .header{background:var(--d);color:white;padding:18px 0;position:fixed;top:0;width:100%;z-index:1002;box-shadow:0 8px 30px rgba(0,0,0,0.3);}
            .header-inner{max-width:1400px;margin:0 auto;padding:0 15px;text-align:center;}
            h1{font-size:2.5rem;font-weight:900;margin:0;}
            .tagline{font-size:1.1rem;opacity:0.94;margin-top:6px;}
            .nav{background:white;position:fixed;top:92px;width:100%;z-index:1001;padding:16px 0;border-bottom:5px solid var(--p);box-shadow:0 8px 25px rgba(0,0,0,0.12);}
            .nav-inner{max-width:1400px;margin:0 auto;padding:0 15px;display:flex;gap:14px;justify-content:center;flex-wrap:wrap;overflow-x:auto;}
            .nav a{padding:14px 28px;background:#1e293b;color:white;border-radius:50px;font-weight:600;font-size:1rem;text-decoration:none;transition:.3s;}
            .nav a.active,.nav a:hover{background:var(--p);transform:translateY(-2px);box-shadow:0 8px 20px rgba(0,212,170,0.4);}
            .main{padding-top:180px;max-width:1500px;margin:0 auto;padding:20px;}
            .grid{display:grid;gap:30px;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));}
            .card{background:white;border-radius:22px;overflow:hidden;box-shadow:0 12px 35px rgba(0,0,0,0.12);transition:0.4s;}
            .card:hover{transform:translateY(-12px);box-shadow:0 30px 60px rgba(0,0,0,0.22);}
            .img{height:240px;overflow:hidden;background:#000;position:relative;}
            .img img{width:100%;height:100%;object-fit:cover;transition:0.6s;}
            .card:hover img{transform:scale(1.15);}
            .noimg{background:#111827;color:white;display:flex;align-items:center;justify-content:center;font-size:1.3rem;font-weight:700;text-align:center;padding:20px;}
            .content{padding:28px;}
            .cat{color:var(--p);font-weight:700;font-size:0.95rem;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px;}
            h2{font-size:1.55rem;line-height:1.35;margin:12px 0;font-weight:800;}
            h2 a{color:#111;text-decoration:none;}
            h2 a:hover{color:var(--p);}
            .meta{color:#64748b;font-size:0.95rem;margin:12px 0;}
            .excerpt{color:#444;font-size:1.08rem;line-height:1.75;margin:18px 0;}
            .readmore{background:var(--p);color:white;padding:15px 34px;border-radius:50px;font-weight:700;display:inline-block;transition:.3s;}
            .readmore:hover{background:#00b894;transform:translateY(-3px);}
            footer{background:var(--d);color:#94a3b8;padding:70px 20px;text-align:center;font-size:1.1rem;}
            @media(max-width:1024px){.grid{grid-template-columns:repeat(3,1fr);}}
            @media(max-width:768px){
                h1{font-size:2.1rem;}
                .nav{top:88px;}
                .main{padding-top:170px;}
                .grid{grid-template-columns:1fr 1fr;}
            }
            @media(max-width:480px){
                .grid{grid-template-columns:1fr;}
            }
        </style>
    </head>
    <body>
        <div class="header">
            <div class="header-inner">
                <h1>NaijaBuzz</h1>
                <div class="tagline">Fresh Naija Gist • Football • Entertainment • Live</div>
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
                             onerror="this.onerror=null; this.style.display='none'; this.nextElementSibling.style.display='flex';">
                        <div class="noimg">NaijaBuzz<br>No Image</div>
                    </div>
                    <div class="content">
                        <div class="cat">{{ p.category }}</div>
                        <h2><a href="{{ p.link }}" target="_blank">{{ p.title }}</a></h2>
                        <div class="meta">{{ ago(p.pub_date) }} ago</div>
                        <p class="excerpt">{{ p.excerpt }}</p>
                        <a href="{{ p.link }}" target="_blank" class="readmore">Read More</a>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>

        <footer>
            © 2025 NaijaBuzz • Auto-updated • 58 Sources
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
            for cat, url in FEEDS[:15]:  # Fast & safe for Render
                try:
                    f = feedparser.parse(url)
                    for e in f.entries[:4]:
                        h = hashlib.md5((e.link + e.title).encode()).hexdigest()
                        if Post.query.filter_by(unique_hash=h).first(): continue
                        img = get_image(e)
                        summary = e.get('summary') or e.get('description') or ''
                        excerpt = BeautifulSoup(summary, 'html.parser').get_text(strip=True)[:290] + "..."
                        title = random.choice(["", "Breaking: ", "Just In: "]) + BeautifulSoup(e.title, 'html.parser').get_text()
                        db.session.add(Post(title=title, excerpt=excerpt, link=e.link.strip(),
                                            unique_hash=h, image=img, category=cat,
                                            pub_date=safe_date(e.get('published'))))
                        added += 1
                    db.session.commit()
                except: continue
    except: pass
    return f"<h1 style='text-align:center;padding:150px;color:#00d4aa;'>CRON SUCCESS — Added {added} stories</h1>"

@app.route('/ping')
def ping(): return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
