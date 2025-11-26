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
    image = db.Column(db.String(600), default="https://via.placeholder.com/800x450/1a1a1a/ffffff?text=NaijaBuzz%0ANo+Image")
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
        <style>
            body{font-family:'Segoe UI',Arial,sans-serif;background:#f0f2f5;margin:0;}
            header{background:#1a1a1a;color:white;text-align:center;padding:20px;position:sticky;top:0;z-index:10;box-shadow:0 2px 10px rgba(0,0,0,0.1);}
            h1{margin:0;font-size:28px;font-weight:bold;}
            .tabs-container{background:#fff;padding:10px 0;overflow-x:auto;white-space:nowrap;-webkit-overflow-scrolling:touch;box-shadow:0 4px 10px rgba(0,0,0,0.1);position:sticky;top:66px;z-index:9;}
            .tabs{display:inline-flex;gap:10px;padding:0 15px;}
            .tab{padding:10px 18px;background:#2c2c2c;color:white;border-radius:25px;font-weight:bold;font-size:14px;text-decoration:none;transition:0.3s;}
            .tab:hover{background:#444;}
            .tab.active{background:#00d4aa;}
            .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:25px;max-width:1400px;margin:20px auto;padding:0 15px;}
            .card{background:white;border-radius:18px;overflow:hidden;box-shadow:0 8px 25px rgba(0,0,0,0.12);transition:0.3s;}
            .card:hover{transform:translateY(-8px);box-shadow:0 20px 40px rgba(0,0,0,0.18);}
            .card img{width:100%;height:220px;object-fit:cover;}
            .content{padding:18px;}
            .card h2{font-size:19px;line-height:1.3;margin:0 0 10px 0;}
            .card h2 a{color:#1a1a1a;text-decoration:none;font-weight:bold;}
            .card h2 a:hover{color:#00d4aa;}
            .meta{font-size:13px;color:#00d4aa;font-weight:bold;margin-bottom:8px;}
            .card p{color:#444;font-size:15px;line-height:1.5;margin:0;}
            .readmore{background:#00d4aa;color:white;padding:10px 18px;border-radius:10px;text-decoration:none;font-weight:bold;display:inline-block;margin-top:12px;font-size:14px;}
            footer{text-align:center;padding:40px;color:#666;font-size:14px;background:#fff;margin-top:30px;}
            @media(max-width:1024px){.grid{grid-template-columns:repeat(2,1fr);}}
            @media(max-width:600px){.grid{grid-template-columns:1fr;gap:20px;}}
        </style>
    </head>
    <body>
        <header>
            <h1>NaijaBuzz</h1>
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
                <div class="card">
                    <img src="{{ p.image }}" alt="{{ p.title }}" onerror="this.src='https://via.placeholder.com/800x450/1a1a1a/ffffff?text=NaijaBuzz%0ANo+Image'">
                    <div class="content">
                        <h2><a href="{{ p.link }}" target="_blank">{{ p.title }}</a></h2>
                        <div class="meta">{{ p.category }} • {{ p.pub_date[:16] }}</div>
                        <p>{{ p.excerpt|safe }}</p>
                        <a href="{{ p.link }}" target="_blank" class="readmore">Read Full Story →</a>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div class="card"><p style="text-align:center;padding:100px;font-size:22px;color:#00d4aa;">
                    No stories yet in this category — check back soon!
                </p></div>
            {% endif %}
        </div>
        <footer>© 2025 NaijaBuzz • www.naijabuzz.com • Auto-updated every few minutes</footer>
    </body>
    </html>
    """
    return render_template_string(html, posts=posts, categories=CATEGORIES, selected=selected)

@app.route('/robots.txt')
def robots():
    return "User-agent: *\nAllow: /\nSitemap: https://www.naijabuzz.com/sitemap.xml", 200, {'Content-Type': 'text/plain'}

@app.route('/sitemap.xml')
def sitemap():
    posts = Post.query.all()
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += '  <url><loc>https://www.naijabuzz.com</loc><changefreq>hourly</changefreq><priority>1.0</priority></url>\n'
    for p in posts:
        safe_link = p.link.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        date_str = p.pub_date[:10] if p.pub_date and len(p.pub_date) >= 10 else datetime.now().strftime("%Y-%m-%d")
        xml += f'  <url><loc>{safe_link}</loc><lastmod>{date_str}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>\n'
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
                    img = "https://via.placeholder.com/800x450/1a1a1a/ffffff?text=NaijaBuzz%0ANo+Image"
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
