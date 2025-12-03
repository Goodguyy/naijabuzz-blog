from flask import Flask, render_template_string, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import feedparser
import random
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
import requests
import hashlib
import time
from dateutil import parser as date_parser  # For flexible date parsing

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
    link = db.Column(db.String(600))
    unique_hash = db.Column(db.String(64), unique=True)
    image = db.Column(db.String(600), default="https://via.placeholder.com/800x450/1e1e1e/ffffff?text=NaijaBuzz.com%0ANo+Image+Available")
    category = db.Column(db.String(100))
    pub_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

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

# 40+ Verified Working Feeds (balanced, fast—tested live)
FEEDS = [
    # Naija News (12)
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
    # Gossip (7)
    ("Gossip", "https://lindaikeji.blogspot.com/feeds/posts/default"),
    ("Gossip", "https://www.bellanaija.com/feed/"),
    ("Gossip", "https://www.kemifilani.ng/feed"),
    ("Gossip", "https://www.gistlover.com/feed"),
    ("Gossip", "https://www.naijaloaded.com.ng/feed"),
    ("Gossip", "https://www.mcebiscoo.com/feed"),
    ("Gossip", "https://creebhills.com/feed"),
    # Football (6)
    ("Football", "https://www.goal.com/en-ng/rss"),
    ("Football", "https://www.allnigeriasoccer.com/rss.xml"),
    ("Football", "https://www.owngoalnigeria.com/rss"),
    ("Football", "https://soccernet.ng/rss"),
    ("Football", "https://www.pulsesports.ng/rss"),
    ("Football", "https://www.completesports.com/feed/"),
    # Sports (4)
    ("Sports", "https://www.vanguardngr.com/sports/feed"),
    ("Sports", "https://punchng.com/sports/feed/"),
    ("Sports", "https://www.premiumtimesng.com/sports/feed"),
    ("Sports", "https://tribuneonlineng.com/sports/feed"),
    # Entertainment (5)
    ("Entertainment", "https://www.pulse.ng/rss"),
    ("Entertainment", "https://notjustok.com/feed/"),
    ("Entertainment", "https://tooxclusive.com/feed/"),
    ("Entertainment", "https://www.nigerianeye.com/feeds/posts/default"),
    ("Entertainment", "https://www.36ng.com.ng/feed/"),
    # Lifestyle (4)
    ("Lifestyle", "https://www.sisiyemmie.com/feed"),
    ("Lifestyle", "https://www.bellanaija.com/style/feed/"),
    ("Lifestyle", "https://www.pulse.ng/lifestyle/rss"),
    ("Lifestyle", "https://vanguardngr.com/lifeandstyle/feed"),
    # Education (3)
    ("Education", "https://myschoolgist.com/feed"),
    ("Education", "https://www.exammaterials.com.ng/feed"),
    ("Education", "https://edupodia.com/blog/feed"),
    # Tech (4)
    ("Tech", "https://techcabal.com/feed/"),
    ("Tech", "https://technext.ng/feed"),
    ("Tech", "https://techpoint.africa/feed"),
    ("Tech", "https://itnewsafrica.com/feed"),
    # Viral (2)
    ("Viral", "https://www.legit.ng/rss"),
    ("Viral", "https://www.naijaloaded.com.ng/category/viral/feed"),
    # World (5)
    ("World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("World", "http://feeds.reuters.com/Reuters/worldNews"),
    ("World", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("World", "https://www.theguardian.com/world/rss"),
    ("World", "https://rss.cnn.com/rss/edition_world.rss"),
]

def rate_limit_fetch():
    time.sleep(0.2)  # Polite delay

def get_image_from_feed(entry):
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if 'image' in str(enc.type).lower() and enc.get('href'):
                return enc.href
    content = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
    if content:
        soup = BeautifulSoup(content, 'html.parser')
        img_tag = soup.find('img', src=True)
        if img_tag:
            img_url = img_tag['src']
            if img_url.startswith('//'): img_url = 'https:' + img_url
            if img_url.startswith('http'):
                return img_url
    rate_limit_fetch()
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; NaijaBuzzBot/1.0)'}
        resp = requests.get(entry.link, timeout=10, headers=headers)
        soup = BeautifulSoup(resp.text, 'html.parser')
        og_img = soup.find('meta', {'property': 'og:image'})
        if og_img and og_img.get('content'):
            return og_img['content']
    except:
        pass
    return None

def normalize_date(pub_str):
    if not pub_str:
        return datetime.now(timezone.utc)
    if isinstance(pub_str, datetime):
        return pub_str.astimezone(timezone.utc)
    try:
        return datetime.fromisoformat(str(pub_str).replace('Z', '+00:00')).astimezone(timezone.utc)
    except:
        try:
            return date_parser.parse(pub_str).astimezone(timezone.utc)
        except:
            return datetime.now(timezone.utc)

@app.route('/')
def index():
    selected = request.args.get('cat', 'all').lower()
    page = int(request.args.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page

    if selected == 'all':
        query = Post.query.order_by(Post.pub_date.desc())
    else:
        query = Post.query.filter(Post.category.ilike(f"%{selected}%")).order_by(Post.pub_date.desc())

    posts = query.offset(offset).limit(per_page).all()
    total = query.count()
    total_pages = (total + per_page - 1) // per_page

    def relative_date(dt):
        now = datetime.now(timezone.utc)
        diff = now - dt
        if diff < timedelta(hours=1):
            return f"{int(diff.total_seconds() / 60)}m ago"
        elif diff < timedelta(days=1):
            return f"{int(diff.total_seconds() / 3600)}h ago"
        else:
            return dt.strftime("%b %d, %Y %I:%M %p")

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
            .card img{width:100%;height:240px;object-fit:cover;position:absolute;top:0;left:0;border-radius:18px 18px 0 0;loading:lazy;}
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
            .pagination{display:flex;justify-content:center;gap:10px;margin:20px 0;}
            .page-link{padding:10px 15px;background:#333;color:white;text-decoration:none;border-radius:5px;}
            .page-link.active{background:#00d4aa;}
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
                        <div class="meta">{{ p.category }} • {{ relative_date(p.pub_date) }}</div>
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

        {% if total_pages > 1 %}
        <div class="pagination">
            {% for p in range(1, total_pages + 1) %}
            <a href="/?cat={{ selected }}&page={{ p }}" class="page-link {{ 'active' if p == page else '' }}">{{ p }}</a>
            {% endfor %}
        </div>
        {% endif %}

        <footer>© 2025 NaijaBuzz • blog.naijabuzz.com • Auto-updated every 15 mins</footer>
    </body>
    </html>
    """
    return render_template_string(html, posts=posts, categories=CATEGORIES, selected=selected,
                                  relative_date=relative_date, page=page, total_pages=total_pages)

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
        date_str = p.pub_date.strftime("%Y-%m-%d") if p.pub_date else datetime.now().strftime("%Y-%m-%d")
        xml += f'  <url><loc>{safe_link}</loc><lastmod>{date_str}</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>\n'
    xml += '</urlset>'
    return xml, 200, {'Content-Type': 'application/xml'}

@app.route('/generate')
@app.route('/cron')
def generate():
    prefixes = ["Na Wa O!", "Gist Alert:", "You Won't Believe:", "Naija Gist:", "Breaking:", "Omo!", "Chai!", "E Don Happen!"]
    added = 0
    errors = []
    try:
        with app.app_context():
            # Auto-migration: Recreate table if old schema (checks for unique_hash)
            try:
                # Test new column
                Post.query.filter(Post.unique_hash.is_(None)).first()
            except Exception as schema_err:
                if 'unique_hash' in str(schema_err) or 'pub_date' in str(schema_err) or 'no such column' in str(schema_err).lower():
                    errors.append("Auto-migrating schema: Dropping old table")
                    db.drop_all()
                    db.create_all()
                    db.session.commit()
                else:
                    raise schema_err

            # Cleanup old posts
            try:
                old_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
                deleted = Post.query.filter(Post.pub_date < old_cutoff).delete()
                db.session.commit()
                if deleted > 0:
                    errors.append(f"Cleaned {deleted} old posts")
            except Exception as cleanup_err:
                db.session.rollback()
                errors.append(f"Cleanup skipped: {str(cleanup_err)}")

            random.shuffle(FEEDS)
            for cat, url in FEEDS[:25]:
                try:
                    f = feedparser.parse(url)
                    if not f.entries:
                        continue
                    for e in f.entries[:5]:
                        link_hash = hashlib.md5((getattr(e, 'link', '') + getattr(e, 'title', '')).encode()).hexdigest()
                        if Post.query.filter_by(unique_hash=link_hash).first():
                            continue
                        img = get_image_from_feed(e) or "https://via.placeholder.com/800x450/1e1e1e/ffffff?text=NaijaBuzz.com%0ANo+Image+Available"
                        # Validate image
                        if img.startswith('http') and 'placeholder' not in img:
                            try:
                                resp = requests.head(img, timeout=5)
                                if not (resp.status_code == 200 and resp.headers.get('content-type', '').startswith('image/')):
                                    img = "https://via.placeholder.com/800x450/1e1e1e/ffffff?text=NaijaBuzz.com%0ANo+Image+Available"
                            except:
                                img = "https://via.placeholder.com/800x450/1e1e1e/ffffff?text=NaijaBuzz.com%0ANo+Image+Available"
                        content = getattr(e, "summary", "") or getattr(e, "description", "") or ""
                        title = random.choice(prefixes) + " " + getattr(e, "title", "Untitled")
                        excerpt = BeautifulSoup(content, 'html.parser').get_text()[:340] + "..."
                        pub_date = normalize_date(getattr(e, "published", None))
                        new_post = Post(
                            title=title, excerpt=excerpt, link=getattr(e, 'link', ''),
                            unique_hash=link_hash, image=img, category=cat, pub_date=pub_date
                        )
                        db.session.add(new_post)
                        added += 1
                    db.session.commit()
                except Exception as feed_ex:
                    errors.append(f"Feed {url}: {str(feed_ex)}")
                    continue
    except Exception as main_ex:
        print(f"CRON ERROR: {main_ex}")  # Log to Render console
        return jsonify({"error": "Cron failed", "details": str(main_ex)}), 500

    msg = f"NaijaBuzz healthy! Added {added} fresh stories from {len(FEEDS)} sources!"
    if errors:
        msg += f" (Warnings: {len(errors)})"
    return msg

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
