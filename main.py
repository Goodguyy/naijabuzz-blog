from flask import Flask, render_template_string, request
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
        <meta property="og:image" content="https://via.placeholder.com/800x450/1e1e1e/ffffff?text=NaijaBuzz.com%0ANo+Image+Available">
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
            .card img{width:100%;height:240px;object-fit:cover;position:absolute;top:0;left:0;border-radius:18px 18px 0 0;}
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
                        <div class="meta">{{ p.category }} • {{ p.pub_date[:16] }}</div>
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
        <footer>© 2025 NaijaBuzz • blog.naijabuzz.com • Auto-updated every few minutes</footer>
    </body>
    </html>
    """
    return render_template_string(html, posts=posts, categories=CATEGORIES, selected=selected)

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
