from flask import Flask, render_template_string, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
import os, feedparser, random
from datetime import datetime
from bs4 import BeautifulSoup

app = Flask(__name__)

# Database
db_uri = os.environ.get('DATABASE_URL')
if db_uri and db_uri.startswith('postgres://'):
    db_uri = db_uri.replace('postgres://', 'postgresql://', 1)
elif not db_uri:
    db_uri = 'sqlite:///posts.db'
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(600))
    excerpt = db.Column(db.Text)
    link = db.Column(db.String(600), unique=True)
    image = db.Column(db.String(600), default="https://via.placeholder.com/800x450/1e1e1e/ffffff?text=NaijaBuzz.com%0ANo+Image+Available")
    category = db.Column(db.String(100))
    pub_date = db.Column(db.String(100))

with app.app_context():
    db.create_all()

CATEGORIES = {
    "all": "All News",
    "naija news": "Naija News",
    "gossip": "Gossip",
    "football": "Football",
    "sports": "Sports",
    "entertainment": "Entertainment",
    "lifestyle": "Lifestyle",
    "education": "Education",
    "tech": "Tech",
    "viral": "Viral",
    "world": "World"
}

@app.route('/')
def index():
    selected = request.args.get('cat', 'all').lower()
    if selected == 'all':
        posts = Post.query.order_by(Post.pub_date.desc()).limit(90).all()
    else:
        posts = Post.query.filter(Post.category.ilike(f"%{selected}%")).order_by(Post.pub_date.desc()).limit(90).all()

    html = """
    <!DOCTYPE html>
    <html lang="en" manifest="/manifest.json">
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
        <meta property="og:image" content="https://via.placeholder.com/800x450/1e1e1e/ffffff?text=NaijaBuzz.com%0ANo+Image+Available">
        <meta name="theme-color" content="#00d4aa">
        <!-- Favicon & PWA Icons -->
        <link rel="icon" href="https://i.ibb.co/7Y4pY3v/naijabuzz-favicon.png" type="image/png">
        <link rel="apple-touch-icon" href="https://i.ibb.co/7Y4pY3v/naijabuzz-favicon.png">
        <link rel="manifest" href="/manifest.json">
        <style>
            :root{--primary:#00d4aa;--dark:#1a1a1a;--light:#f8f9fa;--text:#2c2c2c;--accent:#00a890;--gray:#f1f1f1;}
            *{box-sizing:border-box;}
            body{font-family:'Segoe UI',Arial,sans-serif;background:var(--light);margin:0;color:var(--text);line-height:1.6;}
            header{background:var(--dark);color:white;text-align:center;padding:22px 15px;position:sticky;top:0;z-index:10;box-shadow:0 4px 15px rgba(0,0,0,0.15);}
            h1{margin:0;font-size:34px;font-weight:900;letter-spacing:1.2px;color:white;}
            .tagline{font-size:18px;margin-top:8px;opacity:0.95;color:#e8fff9;}
            .tabs-container{background:#fff;padding:14px 0;overflow-x:auto;white-space:nowrap;-webkit-overflow-scrolling:touch;box-shadow:0 4px 15px rgba(0,0,0,0.1);position:sticky;top:82px;z-index:9;}
            .tabs{display:inline-flex;gap:12px;padding:0 15px;}
            .tab{padding:11px 22px;background:#2c2c2c;color:white;border-radius:30px;font-weight:600;font-size:14.5px;text-decoration:none;transition:0.3s;border:2px solid transparent;}
            .tab:hover{background:var(--accent);}
            .tab.active{background:var(--primary);border-color:var(--primary);font-weight:700;}
            .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:32px;max-width:1400px;margin:40px auto;padding:0 20px;}
            .card{background:#fff;border-radius:22px;overflow:hidden;box-shadow:0 12px 40px rgba(0,0,0,0.12);transition:all 0.4s ease;border:1px solid #eee;}
            .card:hover{transform:translateY(-12px);box-shadow:0 30px 60px rgba(0,0,0,0.22);}
            .img-container{position:relative;width:100%;height:260px;background:#1e1e1e;display:flex;align-items:center;justify-content:center;overflow:hidden;}
            .card img{width:100%;height:260px;object-fit:cover;position:absolute;top:0;left:0;border-radius:22px 22px 0 0;transition:opacity 0.4s;}
            .placeholder-text{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:white;font-size:19px;font-weight:800;text-align:center;line-height:1.4;z-index:2;display:none;pointer-events:none;}
            .no-image .placeholder-text{display:block;}
            .no-image img{display:none;}
            .content{padding:24px;}
            .card h2{font-size:22px;line-height:1.35;margin:0 0 12px 0;font-weight:700;}
            .card h2 a{color:#1a1a1a;text-decoration:none;transition:0.3s;}
            .card h2 a:hover{color:var(--primary);}
            .meta{font-size:14px;color:var(--primary);font-weight:700;margin-bottom:10px;text-transform:uppercase;letter-spacing:0.6px;}
            .card p{color:#444;font-size:16px;line-height:1.6;margin:0 0 16px 0;}
            .readmore{background:var(--primary);color:white;padding:13px 26px;border-radius:12px;text-decoration:none;font-weight:700;display:inline-block;font-size:15px;transition:0.3s;}
            .readmore:hover{background:var(--accent);transform:scale(1.05);}
            footer{text-align:center;padding:60px 20px;color:#666;font-size:15px;background:#fff;margin-top:50px;border-top:1px solid #eee;}
            @media(max-width:1024px){.grid{grid-template-columns:repeat(2,1fr);}}
            @media(max-width:768px){.grid{grid-template-columns:repeat(2,1fr);gap:24px;}}
            @media(max-width:480px){.grid{grid-template-columns:1fr;}}
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
                        <div class="meta">{{ p.category }} • {{ p.pub_date[:16] }}</div>
                        <p>{{ p.excerpt|safe }}</p>
                        <a href="{{ p.link }}" target="_blank" class="readmore">Read Full Story →</a>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div class="card"><p style="text-align:center;padding:100px;font-size:22px;color:var(--primary);">
                    No stories yet — check back soon!
                </p></div>
            {% endif %}
        </div>
        <footer>© 2025 NaijaBuzz • blog.naijabuzz.com • Auto-updated every few minutes</footer>
    </body>
    </html>
    """
    return render_template_string(html, posts=posts, categories=CATEGORIES, selected=selected)

# PWA Manifest
@app.route('/manifest.json')
def manifest():
    return {
        "name": "NaijaBuzz",
        "short_name": "NaijaBuzz",
        "description": "Latest Naija news, gossip, football & entertainment",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#1e1e1e",
        "theme_color": "#00d4aa",
        "icons": [
            {"src": "https://i.ibb.co/7Y4pY3v/naijabuzz-favicon.png", "sizes": "192x192", "type": "image/png"},
            {"src": "https://i.ibb.co/7Y4pY3v/naijabuzz-favicon.png", "sizes": "512x512", "type": "image/png"}
        ]
    }, 200, {'Content-Type': 'application/json'}

@app.route('/robots.txt')
def robots():
    return "User-agent: *\nAllow: /\nSitemap: https://blog.naijabuzz.com/sitemap.xml", 200, {'Content-Type': 'text/plain'}

@app.route('/sitemap.xml')
def sitemap():
    base_url = "https://blog.naijabuzz.com"
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += f'  <url><loc>{base_url}</loc><changefreq>hourly</changefreq><priority>1.0</priority></url>\n'
    for cat_key in CATEGORIES.keys():
        if cat_key != "all":
            xml += f'  <url><loc>{base_url}/?cat={cat_key}</loc><changefreq>daily</changefreq><priority>0.9</priority></url>\n'
    posts = Post.query.all()
    for p in posts:
        safe_link = p.link.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        date_str = p.pub_date[:10] if p.pub_date and len(p.pub_date) >= 10 else datetime.now().strftime("%Y-%m-%d")
        xml += f'  <url><loc>{safe_link}</loc><lastmod>{date_str}</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>\n'
    xml += '</urlset>'
    return xml, 200, {'Content-Type': 'application/xml'}

@app.route('/generate')
def generate():
    feeds = [
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
    prefixes = ["Na Wa O!", "Gist Alert:", "You Won't Believe:", "Naija Gist:", "Breaking:", "Omo!", "Chai!", "E Don Happen!"]
    added = 0
    with app.app_context():
        random.shuffle(feeds)
        for cat, url in feeds:
            try:
                f = feedparser.parse(url)
                for e in f.entries[:12]:
                    if Post.query.filter_by(link=e.link).first():
                        continue
                    img = "https://via.placeholder.com/800x450/1e1e1e/ffffff?text=NaijaBuzz.com%0ANo+Image+Available"
                    content = getattr(e, "summary", "") or getattr(e, "description", "") or ""
                    if content:
                        soup = BeautifulSoup(content, 'html.parser')
                        img_tag = soup.find('img')
                        if img_tag and img_tag.get('src'):
                            img = img_tag['src']
                            if img.startswith('//'): img = 'https:' + img
                    title = random.choice(prefixes) + " " + e.title
                    excerpt = BeautifulSoup(content, 'html.parser').get_text()[:340] + "..."
                    pub_date = getattr(e, "published", datetime.now().isoformat())
                    db.session.add(Post(title=title, excerpt=excerpt, link=e.link, image=img, category=cat, pub_date=pub_date))
                    added += 1
            except: continue
        db.session.commit()
    return f"NaijaBuzz healthy! Added {added} fresh stories!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
