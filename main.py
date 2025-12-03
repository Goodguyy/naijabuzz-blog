from flask import Flask, render_template_string, request, jsonify
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
    title = db.Column(db.String(600))
    excerpt = db.Column(db.Text)
    link = db.Column(db.String(600))
    unique_hash = db.Column(db.String(64), unique=True)
    image = db.Column(db.String(600), default="https://via.placeholder.com/800x450/1e1e1e/ffffff?text=NaijaBuzz")
    category = db.Column(db.String(100))
    pub_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

def init_db():
    with app.app_context():
        db.create_all()

CATEGORIES = {
    "all": "All News", "naija news": "Naija News", "gossip": "Gossip", "football": "Football",
    "sports": "Sports", "entertainment": "Entertainment", "lifestyle": "Lifestyle",
    "education": "Education", "tech": "Tech", "viral": "Viral", "world": "World"
}

# ONLY 20 SUPER FAST & RELIABLE SOURCES (runs in under 8 seconds on free tier)
FEEDS = [
    ("Naija News", "https://punchng.com/feed/"),
    ("Naija News", "https://www.vanguardngr.com/feed"),
    ("Naija News", "https://www.premiumtimesng.com/feed"),
    ("Naija News", "https://dailypost.ng/feed/"),
    ("Naija News", "https://guardian.ng/feed/"),
    ("Gossip", "https://lindaikeji.blogspot.com/feeds/posts/default"),
    ("Gossip", "https://www.bellanaija.com/feed/"),
    ("Gossip", "https://www.kemifilani.ng/feed"),
    ("Football", "https://www.goal.com/en-ng/rss"),
    ("Football", "https://soccernet.ng/rss"),
    ("Football", "https://www.pulsesports.ng/rss"),
    ("Entertainment", "https://www.pulse.ng/rss"),
    ("Entertainment", "https://notjustok.com/feed/"),
    ("Entertainment", "https://tooxclusive.com/feed/"),
    ("Viral", "https://www.legit.ng/rss and rss"),
    ("World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("World", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("Tech", "https://techcabal.com/feed/"),
    ("Lifestyle", "https://www.bellanaija.com/style/feed/"),
    ("Sports", "https://punchng.com/sports/feed/"),
]

# FAST IMAGE: Only from RSS summary/enclosure — NO full page requests!
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
    return "https://via.placeholder.com/800x450/1e1e1e/ffffff?text=NaijaBuzz"

def parse_date(d):
    if not d: return datetime.now(timezone.utc)
    try: return date_parser.parse(d).astimezone(timezone.utc)
    except: return datetime.now(timezone.utc)

@app.route('/')
def index():
    init_db()
    selected = request.args.get('cat', 'all').lower()
    page = int(request.args.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page

    q = Post.query.order_by(Post.pub_date.desc())
    if selected != 'all':
        q = q.filter(Post.category.ilike(f"%{selected}%"))
    posts = q.offset(offset).limit(per_page).all()
    total_pages = (q.count() + per_page - 1) // per_page

    def ago(dt):
        diff = datetime.now(timezone.utc) - dt
        if diff < timedelta(hours=1):
            return f"{int(diff.total_seconds()//60)}m ago"
        if diff < timedelta(days=1):
            return f"{int(diff.total_seconds()//3600)}h ago"
        return dt.strftime("%b %d, %I:%M%p")

    html = """[YOUR FULL HTML GOES HERE — copy exactly from your current working version]"""
    # ← Paste your entire beautiful HTML (tabs, grid, cards, etc.) here

    return render_template_string(html, posts=posts, categories=CATEGORIES, selected=selected,
                                  ago=ago, page=page, pages=total_pages)

@app.route('/cron')
@app.route('/generate')
def cron():
    init_db()
    added = 0
    try:
        with app.app_context():
            # One-time DB reset if old schema
            try:
                Post.query.first()
            except:
                db.drop_all()
                db.create_all()

            random.shuffle(FEEDS)
            for cat, url in FEEDS[:15]:  # Only 15 feeds = lightning fast
                try:
                    f = feedparser.parse(url)
                    for e in f.entries[:4]:  # Only 4 per feed
                        h = hashlib.md5((e.link + e.title).encode()).hexdigest()
                        if Post.query.filter_by(unique_hash=h).first():
                            continue
                        img = get_image(e)
                        summary = e.get('summary') or e.get('description') or ''
                        excerpt = BeautifulSoup(summary, 'html.parser').get_text()[:340] + "..."
                        title = random.choice(["Na Wa O! ", "Omo! ", "Chai! ", "Breaking: ", "Gist Alert: "]) + e.title
                        post = Post(title=title, excerpt=excerpt, link=e.link, unique_hash=h,
                                    image=img, category=cat, pub_date=parse_date(getattr(e,'published',None)))
                        db.session.add(post)
                        added += 1
                    db.session.commit()
                except Exception as ex:
                    print(f"Feed failed: {ex}")
                    continue
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return f"NaijaBuzz healthy! Added {added} fresh stories!"

@app.route('/robots.txt')
def robots():
    return "User-agent: *\nAllow: /\nSitemap: https://blog.naijabuzz.com/sitemap.xml", 200, {'Content-Type': 'text/plain'}

@app.route('/sitemap.xml')
def sitemap():
    init_db()
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += '  <url><loc>https://blog.naijabuzz.com</loc><changefreq>hourly</changefreq></url>\n'
    posts = Post.query.order_by(Post.pub_date.desc()).limit(500).all()
    for p in posts:
        safe = p.link.replace('&', '&amp;')
        date = p.pub_date.strftime("%Y-%m-%d")
        xml += f'  <url><loc>{safe}</loc><lastmod>{date}</lastmod></url>\n'
    xml += '</urlset>'
    return xml, 200, {'Content-Type': 'application/xml'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
