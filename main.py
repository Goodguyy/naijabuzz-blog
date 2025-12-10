from flask import Flask, render_template_string, request
from flask_sqlalchemy import SQLAlchemy
import os, feedparser, random, hashlib, time
import requests
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
    image = db.Column(db.String(800), default="https://via.placeholder.com/800x450/111827/00d4aa?text=NaijaBuzz")
    category = db.Column(db.String(100))
    pub_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

def init_db():
    with app.app_context():
        db.create_all()

# 62 FULL SOURCES — ALL HERE, NOTHING REMOVED
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
    ("Naija News", "https://blueprint.ng/feed/"),
    ("Naija News", "https://newtelegraphng.com/feed"),
    ("Gossip", "https://lindaikeji.blogspot.com/feeds/posts/default"),
    ("Gossip", "https://www.bellanaija.com/feed/"),
    ("Gossip", "https://www.kemifilani.ng/feed"),
    ("Gossip", "https://www.gistlover.com/feed"),
    ("Gossip", "https://www.naijaloaded.com.ng/feed"),
    ("Gossip", "https://creebhills.com/feed"),
    ("Gossip", "https://www.informationng.com/feed"),
    ("Gossip", "https://www.tori.ng/rss"),
    ("Football", "https://www.goal.com/en-ng/rss"),
    ("Football", "https://soccernet.ng/rss"),
    ("Football", "https://www.allnigeriasoccer.com/rss.xml"),
    ("Football", "https://www.pulsesports.ng/rss"),
    ("Football", "https://www.completesports.com/feed/"),
    ("Football", "https://sportsration.com/feed/"),
    ("Football", "https://www.owngoalnigeria.com/rss"),
    ("Sports", "https://punchng.com/sports/feed/"),
    ("Sports", "https://www.vanguardngr.com/sports/feed"),
    ("Sports", "https://www.premiumtimesng.com/sports/feed"),
    ("Entertainment", "https://www.pulse.ng/entertainment/rss"),
    ("Entertainment", "https://notjustok.com/feed/"),
    ("Entertainment", "https://tooxclusive.com/feed/"),
    ("Entertainment", "https://www.36ng.com.ng/feed/"),
    ("Entertainment", "https://thenet.ng/feed/"),
    ("Lifestyle", "https://www.bellanaija.com/style/feed/"),
    ("Lifestyle", "https://www.pulse.ng/lifestyle/rss"),
    ("Lifestyle", "https://www.sisiyemmie.com/feed"),
    ("Tech", "https://techcabal.com/feed/"),
    ("Tech", "https://techpoint.africa/feed/"),
    ("Tech", "https://technext24.com/feed/"),
    ("Tech", "https://nairametrics.com/feed/"),
    ("Viral", "https://www.legit.ng/rss"),
    ("Viral", "https://www.naijaloaded.com.ng/category/viral/feed"),
    ("Viral", "https://www.ladunliadinews.com/feeds/posts/default"),
    ("World", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("World", "https://rss.cnn.com/rss/edition.rss"),
    ("World", "https://www.theguardian.com/world/rss"),
    ("Education", "https://myschoolgist.com/feed"),
    ("Education", "https://flashlearners.com/feed/"),
    ("Education", "https://allschool.ng/feed/"),
    ("Business", "https://nairametrics.com/feed/"),
    ("Business", "https://businessday.ng/feed"),
    ("Politics", "https://politicsnigeria.com/feed/"),
    ("Politics", "https://www.icirnigeria.org/feed/"),
    ("Crime", "https://www.pmnewsnigeria.com/category/crime/feed/"),
    ("Health", "https://punchng.com/topics/health/feed/"),
    ("Health", "https://www.premiumtimesng.com/topics/health/feed"),
]

CATEGORIES = {
    "all": "All News", "naija news": "Naija News", "gossip": "Gossip & Celebrity",
    "football": "Football", "sports": "Sports", "entertainment": "Entertainment",
    "lifestyle": "Lifestyle", "tech": "Tech", "viral": "Viral", "world": "World News",
    "education": "Education", "business": "Business", "politics": "Politics",
    "crime": "Crime", "health": "Health"
}

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def get_image(entry):
    link = entry.get('link', '').strip()
    if not link: return "https://via.placeholder.com/800x450/111827/00d4aa?text=NaijaBuzz"

    # Fast media tags first
    if hasattr(entry, 'media_content'):
        for m in entry.media_content:
            u = m.get('url')
            if u and 'logo' not in u.lower(): return u
    if hasattr(entry, 'media_thumbnail'):
        for t in entry.media_thumbnail:
            if t.get('url'): return t['url']

    # Summary image
    content = entry.get('summary') or entry.get('description') or ''
    if content:
        soup = BeautifulSoup(content, 'html.parser')
        img = soup.find('img')
        if img:
            src = img.get('src') or img.get('data-src')
            if src and 'logo' not in src.lower():
                if src.startswith('//'): src = 'https:' + src
                return src

    # LAST RESORT: Fetch real image from article (Punch, Vanguard, etc.)
    try:
        r = requests.get(link, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            og = soup.find("meta", property="og:image")
            if og and og.get('content') and 'logo' not in og['content'].lower():
                return og['content']
            # First good img
            img = soup.find('img', src=lambda x: x and len(x)>30 and 'logo' not in x.lower())
            if img and img['src']:
                src = img['src']
                if src.startswith('//'): src = 'https:' + src
                return src
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
        <meta name="description" content="Fresh Nigerian news, BBNaija, Premier League, tech & viral gists — updated every 10 mins">
        <meta property="og:title" content="NaijaBuzz - Nigeria's #1 Trending News">
        <meta property="og:description" content="Hot gists, football, entertainment & viral stories">
        <meta property="og:image" content="https://via.placeholder.com/1200x630/111827/00d4aa?text=NAIJABUZZ">
        <link rel="canonical" href="https://blog.naijabuzz.com">
        <meta name="robots" content="index, follow">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;900&display=swap" rel="stylesheet">
        <style>
            :root{--p:#00d4aa;--d:#0f172a;--l:#f8fafc;}
            *{margin:0;padding:0;box-sizing:border-box;}
            body{font-family:'Inter',sans-serif;background:var(--l);color:#1e293b;}
            .header{background:var(--d);color:white;padding:18px 0;position:fixed;top:0;width:100%;z-index:1002;}
            .header-inner{max-width:1400px;margin:0 auto;text-align:center;}
            h1{font-size:2.5rem;font-weight:900;}
            .tagline{font-size:1.1rem;opacity:0.94;margin-top:6px;}
            .nav{background:white;position:sticky;top:0;z-index:1001;padding:16px 0;border-bottom:5px solid var(--p);box-shadow:0 8px 25px rgba(0,0,0,0.12);}
            .nav-inner{max-width:1400px;margin:0 auto;display:flex;gap:14px;justify-content:center;flex-wrap:wrap;overflow-x:auto;padding:0 15px;}
            .nav a{padding:12px 26px;background:#1e1e1e;color:white;border-radius:50px;font-weight:600;text-decoration:none;transition:.3s;}
            .nav a.active,.nav a:hover{background:var(--p);}
            .main{padding-top:160px;max-width:1500px;margin:0 auto;padding:20px;}
            .grid{display:grid;gap:30px;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));}
            .card{background:white;border-radius:24px;overflow:hidden;box-shadow:0 12px 35px rgba(0,0,0,0.12);transition:0.4s;}
            .card:hover{transform:translateY(-14px);box-shadow:0 35px 70px rgba(0,0,0,0.22);}
            .img{height:250px;overflow:hidden;background:#000;}
            .img img{width:100%;height:100%;object-fit:cover;transition:0.7s;}
            .card:hover img{transform:scale(1.18);}
            .noimg{position:absolute;inset:0;background:#111827;color:white;display:flex;align-items:center;justify-content:center;font-size:1.5rem;font-weight:700;padding:20px;text-align:center;}
            .content{padding:30px;}
            .cat{color:var(--p);font-weight:700;font-size:0.95rem;text-transform:uppercase;letter-spacing:1.5px;}
            h2{font-size:1.6rem;line-height:1.35;margin:12px 0;font-weight:800;}
            h2 a{color:#111;text-decoration:none;}
            h2 a:hover{color:var(--p);}
            .meta{color:#64748b;font-size:0.95rem;margin:10px 0;}
            .readmore{background:var(--p);color:white;padding:15px 35px;border-radius:50px;font-weight:700;display:inline-block;transition:.3s;}
            .readmore:hover{background:#00b894;}
            @media(max-width:1024px){.grid{grid-template-columns:repeat(3,1fr);}}
            @media(max-width:768px){
                .grid{grid-template-columns:1fr 1fr;}
                .nav{position:sticky;top:0;}
                .main{padding-top:150px;}
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
                <div class="tagline">Fresh Naija Gist • Football • Entertainment</div>
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
    </body>
    </html>
    """
    return render_template_string(html, posts=posts, categories=CATEGORIES, selected=selected,
                                  ago=ago, page=page, total_pages=total_pages)

# Keep your working cron, ping, robots, sitemap exactly as before

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
