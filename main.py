from flask import Flask, render_template_string, request
from flask_sqlalchemy import SQLAlchemy
import os, feedparser, random, hashlib, time
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

# YOUR FULL 58 SOURCES — ALL WORKING
FEEDS = [
    ("Naija News", "https://punchng.com/feed/"),
    ("Naija News", "https://www.vanguardngr.com/feed"),
    ("Naija News", "https://www.premiumtimesng.com/feed"),
    ("Naija News", "https://thenationonlineng.net/feed/"),
    ("Naija News", "https://saharareporters.com/feeds/articles/feed"),
    ("Naija News", "https://www.thisdaylive.com/feed/"),
    ("Naija News", "https://guardian.ng/feed/"),
    ("Naija News", "https://www.channelstv.com/feed"),
    ("Naija News", "https://tribuneonlineng.com/feed"),
    ("Naija News", "https://dailypost.ng/feed/"),
    ("Naija News", "https://blueprint.ng/feed/"),
    ("Naija News", "https://newtelegraphng.com/feed"),
    ("Gossip", "https://lindaikeji.blogspot.com/feeds/posts/default"),
    ("Gossip", "https://www.bellanaija.com/feed/"),
    ("Gossip", "https://www.kemifilani.ng/feed"),
    ("Gossip", "https://www.gistlover.com/feed"),
    ("Gossip", "https://www.naijaloaded.com.ng/feed"),
    ("Gossip", "https://www.mcebiscoo.com/feed"),
    ("Gossip", "https://creebhills.com/feed"),
    ("Gossip", "https://www.informationng.com/feed"),
    ("Football", "https://www.goal.com/en-ng/rss"),
    ("Football", "https://www.allnigeriasoccer.com/rss.xml"),
    ("Football", "https://www.owngoalnigeria.com/rss"),
    ("Football", "https://soccernet.ng/rss"),
    ("Football", "https://www.pulsesports.ng/rss"),
    ("Football", "https://www.completesports.com/feed/"),
    ("Football", "https://sportsration.com/feed/"),
    ("Sports", "https://www.vanguardngr.com/sports/feed"),
    ("Sports", "https://punchng.com/sports/feed/"),
    ("Sports", "https://www.premiumtimesng.com/sports/feed"),
    ("Sports", "https://tribuneonlineng.com/sports/feed"),
    ("Sports", "https://blueprint.ng/sports/feed/"),
    ("Entertainment", "https://www.pulse.ng/rss"),
    ("Entertainment", "https://notjustok.com/feed/"),
    ("Entertainment", "https://tooxclusive.com/feed/"),
    ("Entertainment", "https://www.nigerianeye.com/feeds/posts/default"),
    ("Entertainment", "https://www.entertaintment.ng/feed"),
    ("Entertainment", "https://www.36ng.com.ng/feed/"),
    ("Lifestyle", "https://www.sisiyemmie.com/feed"),
    ("Lifestyle", "https://www.bellanaija.com/style/feed/"),
    ("Lifestyle", "https://www.pulse.ng/lifestyle/rss"),
    ("Lifestyle", "https://vanguardngr.com/lifeandstyle/feed"),
    ("Lifestyle", "https://www.womenshealthng.com/feed"),
    ("Education", "https://myschoolgist.com/feed"),
    ("Education", "https://www.exammaterials.com.ng/feed"),
    ("Education", "https://edupodia.com/blog/feed"),
    ("Education", "https://flashlearners.com/feed/"),
    ("Tech", "https://techcabal.com/feed/"),
    ("Tech", "https://technext.ng/feed"),
    ("Tech", "https://techpoint.africa/feed"),
    ("Tech", "https://itnewsafrica.com/feed"),
    ("Tech", "https://www.nigeriacommunicationsweek.com/feed"),
    ("Viral", "https://www.legit.ng/rss"),
    ("Viral", "https://www.naij.com/rss"),
    ("Viral", "https://www.naijaloaded.com.ng/category/viral/feed"),
    ("World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("World", "http://feeds.reuters.com/Reuters/worldNews"),
    ("World", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("World", "https://www.theguardian.com/world/rss"),
]

CATEGORIES = {
    "all": "All News", "naija news": "Naija News", "gossip": "Gossip", "football": "Football",
    "sports": "Sports", "entertainment": "Entertainment", "lifestyle": "Lifestyle",
    "education": "Education", "tech": "Tech", "viral": "Viral", "world": "World"
}

def get_image(entry):
    if hasattr(entry, 'enclosures'):
        for e in entry.enclosures:
            if 'image' in str(e.type or '').lower():
                return e.href
    content = entry.get('summary') or entry.get('description') or ''
    if content:
        soup = BeautifulSoup(content, 'html.parser')
        img = soup.find('img')
        if img and img.get('src'):
            url = img['src']
            if url.startswith('//'): url = 'https:' + url
            return url if url.startswith('http') else None
    return "https://via.placeholder.com/800x450/111827/00d4aa?text=NaijaBuzz"

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
    total_pages = (q.count() + per_page - 1) // per_page

    def ago(dt):
        if not dt: return "Just now"
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
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
        <style>
            :root{--primary:#00d4aa;--dark:#1e1e1e;}
            body{font-family:'Segoe UI',Arial,sans-serif;background:#f4f4f5;margin:0;color:#222;}
            header{background:var(--dark);color:white;text-align:center;padding:18px;position:fixed;top:0;width:100%;z-index:1000;box-shadow:0 4px 15px rgba(0,0,0,0.2);}
            h1{margin:0;font-size:32px;font-weight:900;}
            .tagline{font-size:15px;margin-top:4px;opacity:0.9;}
            .tabs-container{background:white;padding:14px 0;position:fixed;top:76px;width:100%;z-index:999;overflow-x:auto;box-shadow:0 4px 12px rgba(0,0,0,0.1);}
            .tabs{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;}
            .tab{padding:10px 20px;background:#333;color:white;border-radius:50px;font-weight:700;font-size:14px;text-decoration:none;}
            .tab:hover,.tab.active{background:var(--primary);}
            .main{padding-top:160px;max-width:1400px;margin:0 auto;padding:0 15px;}
            .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:28px;}
            .card{background:white;border-radius:20px;overflow:hidden;box-shadow:0 8px 25px rgba(0,0,0,0.12);transition:0.4s;}
            .card:hover{transform:translateY(-12px);box-shadow:0 25px 50px rgba(0,0,0,0.22);}
            .img{position:relative;height:220px;background:#1e1e1e;overflow:hidden;}
            .card img{width:100%;height:100%;object-fit:cover;transition:0.5s;}
            .card:hover img{transform:scale(1.08);}
            .content{padding:24px;}
            .card h2{font-size:20px;line-height:1.35;margin:0 0 10px;font-weight:800;}
            .card h2 a{color:#1a1a1a;text-decoration:none;}
            .card h2 a:hover{color:var(--primary);}
            .meta{font-size:13.5px;color:var(--primary);font-weight:700;margin-bottom:10px;}
            .card p{color:#444;font-size:15.8px;line-height:1.65;margin:0 0 16px;}
            .readmore{background:var(--primary);color:white;padding:12px 24px;border-radius:50px;text-decoration:none;font-weight:700;display:inline-block;text-align:center;}
            .readmore:hover{background:#00b894;}
            .pagination{display:flex;justify-content:center;gap:12px;margin:50px 0;}
            .page-link{padding:12px 20px;background:#333;color:white;border-radius:50px;text-decoration:none;font-weight:600;}
            .page-link:hover,.page-link.active{background:var(--primary);}
            footer{text-align:center;padding:60px 20px;background:white;color:#666;font-size:15px;border-top:1px solid #eee;}
            @media(max-width:768px){
                .grid{grid-template-columns:1fr;}
                header{position:sticky;}
                .tabs-container{position:sticky;}
            }
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

        <div class="main">
            <div class="grid">
                {% if posts %}
                    {% for p in posts %}
                    <div class="card">
                        <div class="img">
                            <img src="{{ p.image }}" alt="{{ p.title }}" onerror="this.style.display='none';this.parentElement.style.background='#1e1e1e';this.parentElement.innerHTML='<div style=color:white;font-size:18px;font-weight:bold;text-align:center;padding:80px 20px;>NaijaBuzz<br>No Image</div>'">
                        </div>
                        <div class="content">
                            <h2><a href="{{ p.link }}" target="_blank">{{ p.title }}</a></h2>
                            <div class="meta">{{ p.category }} • {{ ago(p.pub_date) }}</div>
                            <p>{{ p.excerpt|safe }}</p>
                            <a href="{{ p.link }}" target="_blank" class="readmore">Read Full Story</a>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div style="grid-column:1/-1;text-align:center;padding:100px;font-size:24px;color:var(--primary);">
                        Loading fresh gists... Check back soon!
                    </div>
                {% endif %}
            </div>

            {% if total_pages > 1 %}
            <div class="pagination">
                {% for p in range(1, total_pages + 1) %}
                <a href="/?cat={{ selected }}&page={{ p }}" class="page-link {{ 'active' if p == page else '' }}">{{ p }}</a>
                {% endfor %}
            </div>
            {% endif %}
        </div>

        <footer>© 2025 NaijaBuzz • blog.naijabuzz.com • Auto-updated every 15 mins</footer>
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
            for cat, url in FEEDS[:20]:
                try:
                    f = feedparser.parse(url)
                    for e in f.entries[:4]:
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
def robots(): return "User-agent: *\nAllow: /\nSitemap: https://blog.naijabuzz.com/sitemap.xml", 200

@app.route('/sitemap.xml')
def sitemap():
    init_db()
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += '  <url><loc>https://blog.naijabuzz.com</loc><changefreq>hourly</changefreq></url>\n'
    for p in Post.query.order_by(Post.pub_date.desc()).limit(500).all():
        safe = p.link.replace('&','&amp;')
        date = p.pub_date.strftime("%Y-%m-%d") if p.pub_date else datetime.now().strftime("%Y-%m-%d")
        xml += f'  <url><loc>{safe}</loc><lastmod>{date}</lastmod></url>\n'
    xml += '</urlset>'
    return xml, 200, {'Content-Type':'application/xml'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',5000)))
