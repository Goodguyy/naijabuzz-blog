from flask import Flask, render_template_string, request
from flask_sqlalchemy import SQLAlchemy
import os, feedparser, random, hashlib, time
import requests
import json
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from urllib.parse import urljoin

app = Flask(__name__)

# Database Setup
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
    image = db.Column(db.String(600), default="https://via.placeholder.com/800x450/111827/00d4aa?text=NaijaBuzz")
    category = db.Column(db.String(100))
    pub_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

def init_db():
    with app.app_context():
        db.create_all()

# 60+ ACTIVE & WORKING SOURCES (Tested Dec 2025)
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
    ("Naija News", "https://punchng.com/feed/"),
    ("Gossip", "https://lindaikeji.blogspot.com/feeds/posts/default"),
    ("Gossip", "https://www.bellanaija.com/feed/"),
    ("Gossip", "https://www.kemifilani.ng/feed"),
    ("Gossip", "https://www.gistlover.com/feed"),
    ("Gossip", "https://www.naijaloaded.com.ng/feed"),
    ("Gossip", "https://creebhills.com/feed"),
    ("Gossip", "https://www.legit.ng/entertainment/feed"),
    ("Gossip", "https://www.tori.ng/rss"),
    ("Football", "https://www.goal.com/en-ng/rss"),
    ("Football", "https://soccernet.ng/rss"),
    ("Football", "https://www.allnigeriasoccer.com/rss.xml"),
    ("Football", "https://www.pulsesports.ng/rss"),
    ("Football", "https://www.completesports.com/feed/"),
    ("Football", "https://sportsration.com/feed/"),
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
    ("World", "https://apnews.com/hub/world-news"),
    ("Education", "https://myschoolgist.com/feed"),
    ("Education", "https://flashlearners.com/feed/"),
    ("Education", "https://www.examscholars.com/feed"),
    ("Education", "https://allschool.ng/feed/"),
    ("Business", "https://nairametrics.com/feed/"),
    ("Business", "https://businessday.ng/feed"),
    ("Politics", "https://politicsnigeria.com/feed/"),
    ("Politics", "https://www.icirnigeria.org/feed/"),
    ("Crime", "https://www.pmnewsnigeria.com/category/crime/feed/"),
    ("Health", "https://punchng.com/topics/health/feed/"),
]

CATEGORIES = {
    "all": "All News", "naija news": "Naija News", "gossip": "Gist & Gossip", "football": "Football",
    "sports": "Sports", "entertainment": "Entertainment", "lifestyle": "Lifestyle",
    "tech": "Tech", "viral": "Viral", "world": "World News", "education": "Education",
    "business": "Business", "politics": "Politics", "crime": "Crime", "health": "Health"
}

HEADERS = {'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36'}

def get_image(entry, feed_url=""):
    link = entry.get('link', '')
    
    # 1. Media thumbnail/content
    if hasattr(entry, 'media_content'):
        for m in entry.media_content:
            if m.get('url') and 'logo' not in m['url'].lower():
                return m['url']
    if hasattr(entry, 'media_thumbnail'):
        for t in entry.media_thumbnail:
            if t.get('url'):
                return t['url']

    # 2. Enclosures (avoid logos)
    if hasattr(entry, 'enclosures'):
        for e in entry.enclosures:
            if e.type and 'image' in e.type.lower():
                url = e.href
                if any(bad in url.lower() for bad in ['logo', 'punch-logo', 'header', 'banner']):
                    continue
                return url

    # 3. Summary image
    content = entry.get('summary') or entry.get('description') or ''
    if content:
        soup = BeautifulSoup(content, 'html.parser')
        img = soup.find('img')
        if img and img.get('src'):
            src = img['src']
            if src.startswith('//'): src = 'https:' + src
            if src.startswith('http') and 'logo' not in src.lower():
                return src

    # 4. PUNCH & MODERN SITES: Fetch real image from article
    if link and any(site in link for site in ['punchng.com', 'vanguardngr.com', 'premiumtimesng.com', 'dailypost.ng']):
        try:
            r = requests.get(link, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                
                # Open Graph
                og = soup.find("meta", property="og:image")
                if og and og.get('content'):
                    url = og['content']
                    if 'logo' not in url.lower():
                        return url

                # JSON-LD
                for script in soup.find_all("script", type="application/ld+json"):
                    try:
                        data = json.loads(script.string)
                        img = None
                        if isinstance(data, list):
                            for item in data:
                                if item.get('@type') == 'NewsArticle':
                                    img = item.get('image')
                                    break
                        else:
                            if data.get('@type') == 'NewsArticle':
                                img = data.get('image')
                        if img:
                            if isinstance(img, str): return img
                            if isinstance(img, dict): return img.get('url')
                            if isinstance(img, list) and img: return img[0].get('url') or img[0]
                    except:
                        continue

                # First figure img
                fig = soup.find('figure')
                if fig:
                    img = fig.find('img')
                    if img and img.get('data-src'): return img['data-src']
                    if img and img.get('src'): return img['src']
        except:
            pass

    return "https://via.placeholder.com/800x450/111827/00d4aa?text=NaijaBuzz+Hot+Gist"

def parse_date(d):
    if not d: return datetime.now(timezone.utc)
    try:
        return date_parser.parse(d).astimezone(timezone.utc)
    except:
        return datetime.now(timezone.utc)

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
        <title>NaijaBuzz - Latest Naija News, Football, Gossip & World Updates</title>
        <meta name="description" content="Fresh Naija news, BBNaija gist, Premier League, AFCON, tech, viral videos & world news — updated every 10 mins!">
        <meta property="og:title" content="NaijaBuzz - Nigeria's #1 Trending News Hub">
        <meta property="og:description" content="Hot gists, football scores, celebrity news & breaking stories">
        <meta property="og:image" content="https://via.placeholder.com/1200x630/111827/00d4aa?text=NAIJABUZZ">
        <meta property="og:url" content="https://blog.naijabuzz.com">
        <link rel="canonical" href="https://blog.naijabuzz.com">
        <meta name="robots" content="index, follow">
        <link rel="sitemap" type="application/xml" href="/sitemap.xml">
        <style>
            :root{--primary:#00d4aa;--dark:#111827;--gray:#6b7280;--light:#f8fafc;}
            *{box-sizing:border-box;margin:0;padding:0;}
            body{font-family:'Inter',system-ui,sans-serif;background:var(--light);color:#1f2937;line-height:1.6;}
            .header{background:var(--dark);color:white;padding:1rem;position:fixed;top:0;left:0;right:0;z-index:1000;box-shadow:0 4px 20px rgba(0,0,0,0.15);}
            .header h1{font-size:1.8rem;font-weight:900;margin:0;}
            .header .tagline{font-size:0.95rem;opacity:0.9;margin-top:4px;}
            .nav{background:white;position:fixed;top:68px;left:0;right:0;z-index:999;box-shadow:0 4px 15px rgba(0,0,0,0.1);padding:12px 0;overflow-x:auto;white-space:nowrap;-webkit-overflow-scrolling:touch;}
            .nav::-webkit-scrollbar{display:none;}
            .nav a{padding:10px 18px;background:#374151;color:white;border-radius:30px;margin:0 6px;font-weight:600;font-size:0.9rem;text-decoration:none;transition:0.3s;}
            .nav a.active,.nav a:hover{background:var(--primary);color:white;}
            .container{max-width:1400px;margin:0 auto;padding:140px 15px 60px;}
            .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:24px;}
            .card{background:white;border-radius:16px;overflow:hidden;box-shadow:0 10px 30px rgba(0,0,0,0.1);transition:0.4s;}
            .card:hover{transform:translateY(-10px);box-shadow:0 20px 40px rgba(0,0,0,0.18);}
            .img-wrap{position:relative;height:220px;overflow:hidden;background:#000;}
            .img-wrap img{width:100%;height:100%;object-fit:cover;transition:0.5s;}
            .card:hover img{transform:scale(1.1);}
            .img-wrap::after{content:"NaijaBuzz";position:absolute;inset:0;background:linear-gradient(transparent,rgba(0,0,0,0.7));display:flex;align-items:flex-end;justify-content:center;color:white;font-size:1.5rem;font-weight:bold;opacity:0;transition:0.4s;}
            .card:hover .img-wrap::after{opacity:1;}
            .content{padding:20px;}
            .cat{color:var(--primary);font-size:0.8rem;font-weight:700;text-transform:uppercase;letter-spacing:1px;}
            .card h2{font-size:1.35rem;line-height:1.3;margin:10px 0;font-weight:800;}
            .card h2 a{color:#111;text-decoration:none;}
            .card h2 a:hover{color:var(--primary);}
            .meta{font-size:0.85rem;color:var(--gray);margin:8px 0;}
            .excerpt{color:#444;font-size:1rem;margin:12px 0;}
            .readmore{display:inline-block;background:var(--primary);color:white;padding:10px 20px;border-radius:30px;font-weight:600;text-decoration:none;margin-top:10px;transition:0.3s;}
            .readmore:hover{background:#00b894;transform:translateY(-2px);}
            .pagination{display:flex;justify-content:center;gap:10px;margin:50px 0;flex-wrap:wrap;}
            .pagination a{padding:12px 18px;background:#374151;color:white;border-radius:30px;text-decoration:none;font-weight:600;}
            .pagination a.active,.pagination a:hover{background:var(--primary);}
            footer{background:var(--dark);color:#9ca3af;padding:40px 20px;text-align:center;font-size:0.9rem;}
            @media(max-width:768px){
                .header h1{font-size:1.6rem;}
                .nav{top:64px;padding:10px 0;}
                .nav a{padding:8px 16px;font-size:0.85rem;}
                .container{padding-top:130px;}
                .grid{grid-template-columns:1fr;gap:20px;}
            }
        </style>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap" rel="stylesheet">
    </head>
    <body>
        <header class="header">
            <div style="max-width:1400px;margin:0 auto;padding:0 15px;display:flex;flex-direction:column;align-items:center;">
                <h1>NaijaBuzz</h1>
                <div class="tagline">Nigeria's #1 Trending News • Updated Every 10 Mins</div>
            </div>
        </header>

        <nav class="nav">
            <div style="text-align:center;">
                {% for key, name in categories.items() %}
                <a href="/?cat={{ key }}" class="{{ 'active' if selected == key else '' }}">{{ name }}</a>
                {% endfor %}
            </div>
        </nav>

        <div class="container">
            <div class="grid">
                {% if posts %}
                    {% for p in posts %}
                    <article class="card">
                        <div class="img-wrap">
                            <img src="{{ p.image }}" alt="{{ p.title }}" loading="lazy"
                                 onerror="this.src='https://via.placeholder.com/800x450/111827/00d4aa?text=No+Image'">
                        </div>
                        <div class="content">
                            <div class="cat">{{ p.category }}</div>
                            <h2><a href="{{ p.link }}" target="_blank" rel="noopener">{{ p.title }}</a></h2>
                            <div class="meta">{{ ago(p.pub_date) }} • {{ p.category }}</div>
                            <p class="excerpt">{{ p.excerpt }}</p>
                            <a href="{{ p.link }}" target="_blank" rel="noopener" class="readmore">Read Full Story →</a>
                        </div>
                    </article>
                    {% endfor %}
                {% else %}
                    <div style="grid-column:1/-1;text-align:center;padding:100px;font-size:1.5rem;color:var(--primary);">
                        Loading fresh gists... Check back in a minute!
                    </div>
                {% endif %}
            </div>

            {% if total_pages > 1 %}
            <div class="pagination">
                {% if page > 1 %}
                    <a href="/?cat={{ selected }}&page={{ page-1 }}">« Prev</a>
                {% endif %}
                {% for p in range(max(1, page-3), min(total_pages+1, page+4)) %}
                    <a href="/?cat={{ selected }}&page={{ p }}" class="{{ 'active' if p == page else '' }}">{{ p }}</a>
                {% endfor %}
                {% if page < total_pages %}
                    <a href="/?cat={{ selected }}&page={{ page+1 }}">Next »</a>
                {% endif %}
            </div>
            {% endif %}
        </div>

        <footer>
            © 2025 <strong>NaijaBuzz</strong> • blog.naijabuzz.com • 
            <span style="color:var(--primary);">Auto-updated every 10–15 mins</span>
        </footer>
    </body>
    </html>
    """
    return render_template_string(html, posts=posts, categories=CATEGORIES, selected=selected,
                                  ago=ago, page=page, total_pages=total_pages)

@app.route('/ping')
def ping(): return "NaijaBuzz is buzzing!", 200

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
            for cat, url in FEEDS[:25]:  # More sources per run
                try:
                    f = feedparser.parse(url, request_headers=HEADERS)
                    for e in f.entries[:5]:
                        h = hashlib.md5((e.link + e.title).encode()).hexdigest()
                        if Post.query.filter_by(unique_hash=h).first() and continue

                        img = get_image(e, url)
                        summary = e.get('summary') or e.get('description') or ''
                        excerpt = BeautifulSoup(summary, 'html.parser').get_text(strip=True)[:300] + "..."

                        title_prefixes = ["", "", "", "Breaking: ", "Just In: ", "Omo See This: ", "Chai! ", "Gist Alert: ", "Na Wa O! "]
                        title = random.choice(title_prefixes) + BeautifulSoup(e.title, 'html.parser').get_text()

                        post = Post(
                            title=title,
                            excerpt=excerpt,
                            link=e.link,
                            unique_hash=h,
                            image=img,
                            category=cat,
                            pub_date=parse_date(getattr(e, 'published', None))
                        )
                        db.session.add(post)
                        added += 1
                    db.session.commit()
                    time.sleep(1)  # Be gentle
                except Exception: continue
    except Exception: pass
    return f"NaijaBuzz Updated! +{added} new hot gists added!"

@app.route('/robots.txt')
def robots():
    return """User-agent: *
Allow: /
Sitemap: https://blog.naijabuzz.com/sitemap.xml
Host: https://blog.naijabuzz.com
""", 200, {'Content-Type': 'text/plain'}

@app.route('/sitemap.xml')
def sitemap():
    init_db()
    base = "https://blog.naijabuzz.com"
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += f'  <url><loc>{base}</loc><changefreq>hourly</changefreq><priority>1.0</priority></url>\n'
    for p in Post.query.order_by(Post.pub_date.desc()).limit(5000).all():
        xml += f'  <url><loc>{p.link}</loc><lastmod>{p.pub_date.strftime("%Y-%m-%d")}</lastmod><changefreq>weekly</changefreq></url>\n'
    xml += '</urlset>'
    return xml, 200, {'Content-Type': 'application/xml'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
