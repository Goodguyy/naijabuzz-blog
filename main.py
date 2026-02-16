from flask import Flask, render_template_string, request, abort
from flask_sqlalchemy import SQLAlchemy
import os, feedparser, random, hashlib
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
import urllib.parse
import requests
from newspaper import Article
from slugify import slugify
from openai import OpenAI

app = Flask(__name__)

# Database
db_uri = os.environ.get('DATABASE_URL') or 'sqlite:///posts.db'
if db_uri and db_uri.startswith('postgres://'):
    db_uri = db_uri.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}
db = SQLAlchemy(app)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(600))
    excerpt = db.Column(db.Text)
    full_content = db.Column(db.Text)
    link = db.Column(db.String(600))
    unique_hash = db.Column(db.String(64), unique=True)
    slug = db.Column(db.String(200), unique=True)
    image = db.Column(db.String(600), default="https://via.placeholder.com/800x450/1e1e1e/ffffff?text=NaijaBuzz")
    category = db.Column(db.String(100))
    pub_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

def init_db():
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

# Full list of feeds (~60+) - unchanged
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
    ("Naija News", "https://www.legit.ng/rss/all.rss"),
    ("Naija News", "https://www.thecable.ng/feed"),

    ("Gossip", "https://lindaikeji.blogspot.com/feeds/posts/default"),
    ("Gossip", "https://www.bellanaija.com/feed/"),
    ("Gossip", "https://www.kemifilani.ng/feed"),
    ("Gossip", "https://www.gistlover.com/feed"),
    ("Gossip", "https://www.naijaloaded.com.ng/feed"),
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
    ("Entertainment", "https://www.36ng.com.ng/feed/"),

    ("Lifestyle", "https://www.sisiyemmie.com/feed"),
    ("Lifestyle", "https://www.bellanaija.com/style/feed/"),
    ("Lifestyle", "https://www.pulse.ng/lifestyle/rss"),
    ("Lifestyle", "https://vanguardngr.com/lifeandstyle/feed"),

    ("Education", "https://myschoolgist.com/feed"),
    ("Education", "https://flashlearners.com/feed/"),

    ("Tech", "https://techcabal.com/feed/"),
    ("Tech", "https://technext.ng/feed"),
    ("Tech", "https://techpoint.africa/feed"),

    ("Viral", "https://www.naijaloaded.com.ng/category/viral/feed"),

    ("World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("World", "http://feeds.reuters.com/Reuters/worldNews"),
    ("World", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("World", "https://www.theguardian.com/world/rss"),
]

def get_image(entry):
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0]['url']
    if hasattr(entry, 'media_content'):
        for m in entry.media_content:
            if m.get('medium') == 'image' and m.get('url'):
                return m['url']
    if hasattr(entry, 'enclosures'):
        for e in entry.enclosures:
            if 'image' in str(e.type or '').lower():
                return e.get('url') or e.get('href')
    content = entry.get('summary') or entry.get('description') or ''
    if not content and hasattr(entry, 'content'):
        content = entry.content[0].get('value', '') if entry.content else ''
    if content:
        soup = BeautifulSoup(content, 'html.parser')
        img = soup.find('img')
        if img and img.get('src'):
            url = img['src'].strip()
            if url.startswith('//'):
                url = 'https:' + url
            elif not url.startswith('http'):
                url = urllib.parse.urljoin(entry.link, url)
            return url
    return None

def parse_date(d):
    if not d: return datetime.now(timezone.utc)
    try: return date_parser.parse(d).astimezone(timezone.utc)
    except: return datetime.now(timezone.utc)

GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
groq_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
) if GROQ_API_KEY else None

if GROQ_API_KEY:
    print("Groq API configured")
else:
    print("Warning: No GROQ_API_KEY - using short excerpts")

def rewrite_article(full_text, title, category):
    if not groq_client or not full_text.strip():
        return full_text

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": f"""
                Rewrite this article completely in your own words as an original piece for Nigerian readers.
                Include relevant Naija context, implications, or angles where natural.
                Keep tone neutral but interesting. Structure: hook intro, main body (short paragraphs), conclusion.
                Aim for 300–500 words. Do NOT copy original sentences directly.
                Original title: {title}
                Category: {category}
                Content: {full_text[:3000]}
            """}],
            max_tokens=500,
            temperature=0.7
        )
        rewritten = response.choices[0].message.content.strip()
        if rewritten:
            return rewritten
    except Exception as e:
        print(f"Groq error for '{title}': {str(e)[:200]}")
    return full_text[:800] + "..."

@app.route('/')
def index():
    init_db()
    selected = request.args.get('cat', 'all').lower()
    page = max(1, int(request.args.get('page', 1)))
    per_page = 20

    query = Post.query.order_by(Post.pub_date.desc())
    if selected != 'all':
        query = query.filter(Post.category.ilike(f"%{selected}%"))

    posts = query.offset((page - 1) * per_page).limit(per_page + 1).all()
    has_next = len(posts) > per_page
    if has_next:
        posts = posts[:-1]

    def ago(dt):
        if not dt: return "Just now"
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - dt
        if diff < timedelta(minutes=60): return f"{int(diff.total_seconds()//60)}m ago"
        if diff < timedelta(hours=24): return f"{int(diff.total_seconds()//3600)}h ago"
        if diff < timedelta(days=7): return f"{diff.days}d ago"
        return dt.strftime("%b %d")

    page_title = f"{CATEGORIES.get(selected, 'All News')} - NaijaBuzz"
    page_desc = "Latest Nigerian news, football, gossip, entertainment, tech & world updates - refreshed frequently!"
    featured_img = posts[0].image if posts else "https://via.placeholder.com/1200x630?text=NaijaBuzz"

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{{ page_title }}</title>
        <meta name="description" content="{{ page_desc }}">
        <meta name="robots" content="index, follow">
        <link rel="canonical" href="https://naijabuzz.com">
        <meta property="og:title" content="{{ page_title }}">
        <meta property="og:description" content="{{ page_desc }}">
        <meta property="og:image" content="{{ featured_img }}">
        <meta property="og:url" content="https://naijabuzz.com">
        <meta property="og:type" content="website">
        <meta name="twitter:card" content="summary_large_image">
        <meta name="twitter:title" content="{{ page_title }}">
        <meta name="twitter:description" content="{{ page_desc }}">
        <meta name="twitter:image" content="{{ featured_img }}">
        <style>
            :root {
                --primary: #00d4aa;
                --dark: #0f172a;
                --light: #f8fafc;
                --gray: #64748b;
                --accent: #00b894;
                --shadow-sm: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
            }
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                font-family: 'Inter', system-ui, sans-serif;
                background: var(--light);
                color: #1e293b;
                line-height: 1.7;
                font-size: 1.05rem;
            }
            header {
                background: linear-gradient(to bottom, var(--dark), #1e293b);
                color: white;
                text-align: center;
                padding: 1.8rem 1rem;
                position: sticky;
                top: 0;
                z-index: 1000;
                box-shadow: var(--shadow-sm);
            }
            h1 { font-size: 2.8rem; font-weight: 900; margin-bottom: 0.4rem; letter-spacing: -1px; }
            .tagline { font-size: 1.2rem; opacity: 0.9; font-weight: 300; }
            .tabs-container {
                background: white;
                padding: 0.9rem 0;
                overflow-x: auto;
                position: sticky;
                top: 0;
                z-index: 999;
                box-shadow: var(--shadow-sm);
                border-bottom: 1px solid #e2e8f0;
                transition: box-shadow 0.3s ease;
            }
            .tabs-container.stuck {
                box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05);
            }
            .tabs {
                display: flex;
                gap: 0.8rem;
                padding: 0 1.2rem;
                white-space: nowrap;
            }
            .tab {
                padding: 0.7rem 1.5rem;
                background: #e2e8f0;
                color: #334155;
                border-radius: 9999px;
                font-weight: 600;
                font-size: 1rem;
                text-decoration: none;
                transition: all 0.3s ease;
                min-width: 90px;
                text-align: center;
                cursor: pointer;
            }
            .tab:hover, .tab.active {
                background: var(--primary);
                color: white;
                transform: translateY(-1px);
            }
            .container {
                max-width: 1440px;
                margin: 2.5rem auto;
                padding: 0 1.2rem;
            }
            .grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
                gap: 1.8rem;
            }
            .card {
                background: white;
                border-radius: 1.2rem;
                overflow: hidden;
                box-shadow: var(--shadow-sm);
                transition: all 0.3s ease;
            }
            .card:hover {
                transform: translateY(-6px);
                box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04);
            }
            .img-container {
                position: relative;
                height: 220px;
                background: #1e1e1e;
                overflow: hidden;
                aspect-ratio: 16/9;
            }
            .card img {
                width: 100%;
                height: 100%;
                object-fit: cover;
                transition: transform 0.5s ease;
            }
            .card:hover img {
                transform: scale(1.08);
            }
            .content { padding: 1.4rem; }
            .card h2 {
                font-size: 1.35rem;
                line-height: 1.45;
                margin-bottom: 0.6rem;
                font-weight: 700;
            }
            .card h2 a {
                color: #0f172a;
                text-decoration: none;
            }
            .card h2 a:hover { color: var(--primary); }
            .meta {
                font-size: 0.9rem;
                color: var(--primary);
                font-weight: 700;
                margin-bottom: 0.6rem;
                text-transform: uppercase;
                letter-spacing: 0.6px;
            }
            .card p {
                color: #475569;
                font-size: 1rem;
                line-height: 1.65;
                margin-bottom: 1.1rem;
            }
            .readmore {
                background: var(--primary);
                color: white;
                padding: 0.7rem 1.5rem;
                border-radius: 9999px;
                text-decoration: none;
                font-weight: 700;
                display: inline-block;
                transition: all 0.3s ease;
            }
            .readmore:hover {
                background: var(--accent);
                transform: translateY(-2px);
            }
            .pagination {
                display: flex;
                justify-content: center;
                gap: 0.9rem;
                margin: 3rem 0;
                flex-wrap: wrap;
            }
            .page-link {
                padding: 0.7rem 1.5rem;
                background: #e2e8f0;
                color: #334155;
                border-radius: 9999px;
                text-decoration: none;
                font-weight: 600;
                transition: all 0.3s ease;
            }
            .page-link:hover, .page-link.active {
                background: var(--primary);
                color: white;
            }
            footer {
                text-align: center;
                padding: 3.5rem 1rem;
                background: white;
                color: var(--gray);
                font-size: 0.95rem;
                border-top: 1px solid #e2e8f0;
            }
            footer a {
                color: var(--primary);
                text-decoration: none;
            }
            @media (max-width: 768px) {
                h1 { font-size: 2.2rem; }
                .tagline { font-size: 1.05rem; }
                .tabs-container {
                    padding: 0.6rem 0;
                }
                .tabs {
                    gap: 0.6rem;
                    padding: 0 0.8rem;
                }
                .tab {
                    padding: 0.6rem 1.2rem;
                    font-size: 0.95rem;
                    min-width: 80px;
                }
                .grid {
                    grid-template-columns: 1fr;
                    gap: 1.4rem;
                }
                .card h2 { font-size: 1.25rem; }
                .container { padding: 0 1rem; }
            }
        </style>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;900&display=swap" rel="stylesheet">
    </head>
    <body>
        <header>
            <h1>NaijaBuzz</h1>
            <div class="tagline">Fresh Naija News • Football • Gossip • Entertainment • World Updates</div>
        </header>

        <div class="tabs-container">
            <div class="tabs">
                {% for key, name in categories.items() %}
                <a href="/?cat={{ key }}" class="tab {{ 'active' if selected == key else '' }}">{{ name }}</a>
                {% endfor %}
            </div>
        </div>

        <div class="container">
            <div class="grid">
                {% if posts %}
                    {% for p in posts %}
                    <div class="card">
                        <div class="img-container">
                            <img loading="lazy" src="{{ p.image }}" alt="{{ p.title }}">
                        </div>
                        <div class="content">
                            <h2><a href="/{{ p.slug }}">{{ p.title }}</a></h2>
                            <div class="meta">{{ p.category }} • {{ ago(p.pub_date) }}</div>
                            <p>{{ p.excerpt|safe }}</p>
                            <a href="/{{ p.slug }}" class="readmore">Read Full Story →</a>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div style="grid-column:1/-1;text-align:center;padding:6rem 1rem;">
                        <p style="font-size:1.6rem;color:var(--primary);">No stories yet — refreshing soon!</p>
                    </div>
                {% endif %}
            </div>

            <div class="pagination">
                {% if page > 1 %}
                <a href="/?cat={{ selected }}&page={{ page-1 }}" class="page-link">← Prev</a>
                {% endif %}
                <span class="page-link active">{{ page }}</span>
                {% if has_next %}
                <a href="/?cat={{ selected }}&page={{ page+1 }}" class="page-link">Next →</a>
                {% endif %}
            </div>
        </div>

        <footer>
            © 2026 <a href="/">NaijaBuzz</a> • naijabuzz.com • Auto-updated every 15 minutes
        </footer>

        <script>
        // Live "ago" update (optional but makes it feel very fresh)
        function updateAgoTimes() {
          document.querySelectorAll('.meta').forEach(meta => {
            const text = meta.textContent;
            if (text.includes(' ago')) {
              // You can extend this if you store timestamps, but for now leave server-side
            }
          });
        }
        // Optional: add scroll listener for shadow on tabs
        window.addEventListener('scroll', () => {
          const tabs = document.querySelector('.tabs-container');
          if (window.scrollY > 10) {
            tabs.classList.add('stuck');
          } else {
            tabs.classList.remove('stuck');
          }
        });
        </script>
    </body>
    </html>
    """
    return render_template_string(html, posts=posts, categories=CATEGORIES, selected=selected,
                                  ago=ago, page=page, has_next=has_next, page_title=page_title, page_desc=page_desc, featured_img=featured_img)

# post_detail route - updated domain references only
@app.route('/<slug>')
def post_detail(slug):
    post = Post.query.filter_by(slug=slug).first()
    if not post:
        abort(404, description="Article not found")

    related = Post.query.filter(Post.category == post.category, Post.id != post.id).order_by(Post.pub_date.desc()).limit(5).all()

    def ago(dt):
        if not dt: return "Just now"
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - dt
        if diff < timedelta(minutes=60): return f"{int(diff.total_seconds()//60)}m ago"
        if diff < timedelta(hours=24): return f"{int(diff.total_seconds()//3600)}h ago"
        if diff < timedelta(days=7): return f"{diff.days}d ago"
        return dt.strftime("%b %d")

    page_title = f"{post.title} - NaijaBuzz"
    page_desc = post.excerpt[:160] or "Read the latest news curated for you."
    featured_img = post.image

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{{ page_title }}</title>
        <meta name="description" content="{{ page_desc }}">
        <meta name="robots" content="index, follow">
        <link rel="canonical" href="https://naijabuzz.com/{{ post.slug }}">
        <meta property="og:title" content="{{ page_title }}">
        <meta property="og:description" content="{{ page_desc }}">
        <meta property="og:image" content="{{ featured_img }}">
        <meta property="og:url" content="https://naijabuzz.com/{{ post.slug }}">
        <meta property="og:type" content="article">
        <meta name="twitter:card" content="summary_large_image">
        <style>
            :root{--primary:#00d4aa;--dark:#0f172a;--light:#f8fafc;--gray:#64748b;--accent:#00b894;}
            body{font-family:'Inter',system-ui,Arial,sans-serif;background:var(--light);margin:0;color:#1e293b;line-height:1.7;font-size:1.05rem;}
            header{background:linear-gradient(to bottom, var(--dark), #1e293b);color:white;text-align:center;padding:1.8rem 1rem;position:sticky;top:0;z-index:1000;box-shadow:0 4px 6px -1px rgba(0,0,0,0.1);}
            h1{font-size:2.8rem;font-weight:900;margin-bottom:0.4rem;letter-spacing:-1px;}
            .tagline{font-size:1.2rem;opacity:0.9;font-weight:300;}
            .single-container{max-width:1000px;margin:2.5rem auto;padding:0 1.2rem;}
            .single-img{width:100%;max-height:600px;object-fit:cover;border-radius:1.2rem;margin-bottom:1.8rem;object-position:center;}
            .single-meta{color:var(--primary);font-weight:700;margin-bottom:1rem;text-transform:uppercase;letter-spacing:0.6px;}
            .single-content{line-height:1.85;font-size:1.15rem;}
            .single-content h2, .single-content h3{margin:2.5rem 0 1.2rem;}
            .source{margin-top:2.5rem;font-style:italic;color:var(--gray);font-size:0.95rem;}
            .related{margin-top:4.5rem;}
            .related h2{margin-bottom:1.8rem;font-size:1.8rem;}
            .related-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1.8rem;}
            .related .card img{width:100%;height:180px;object-fit:cover;object-position:center;border-radius:12px 12px 0 0;}
            footer{text-align:center;padding:4rem 1rem;background:white;color:var(--gray);font-size:0.95rem;border-top:1px solid #e2e8f0;}
            footer a{color:var(--primary);text-decoration:none;}
            @media (max-width: 768px) {
                h1{font-size:2.2rem;}
                .tagline{font-size:1.05rem;}
                .single-container{padding:0 1rem;}
                .related-grid{grid-template-columns:1fr;}
                .related .card img{height:200px;}
            }
        </style>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;900&display=swap" rel="stylesheet">
    </head>
    <body>
        <header>
            <h1>NaijaBuzz</h1>
            <div class="tagline">Fresh Naija News • Football • Gossip • Entertainment • World Updates</div>
        </header>

        <div class="single-container">
            <h1>{{ post.title }}</h1>
            <div class="single-meta">{{ post.category }} • {{ ago(post.pub_date) }}</div>
            <img loading="lazy" src="{{ post.image }}" alt="{{ post.title }}" class="single-img">
            <div class="single-content">{{ post.full_content | safe }}</div>
            <div class="source">Source: <a href="{{ post.link }}" target="_blank" rel="noopener nofollow">Original Article</a>. AI-enhanced version.</div>
            <div class="related">
                <h2>Related Stories</h2>
                <div class="related-grid">
                    {% for r in related %}
                    <div class="card">
                        <div class="img-container">
                            <img loading="lazy" src="{{ r.image }}" alt="{{ r.title }}">
                        </div>
                        <div class="content">
                            <h2><a href="/{{ r.slug }}">{{ r.title }}</a></h2>
                            <div class="meta">{{ r.category }} • {{ ago(r.pub_date) }}</div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>

        <footer>
            © 2026 <a href="/">NaijaBuzz</a> • naijabuzz.com • Auto-updated every 15 minutes
        </footer>
    </body>
    </html>
    """
    return render_template_string(html, post=post, related=related, ago=ago, page_title=page_title, page_desc=page_desc, featured_img=featured_img, categories=CATEGORIES, selected=post.category.lower())

# cron, robots, sitemap routes unchanged except domain in sitemap and robots
@app.route('/cron')
@app.route('/generate')
def cron():
    # ... (your original cron code - unchanged)
    # return message unchanged
    return f"NaijaBuzz cron ran! Added {added} new stories. Skipped {skipped} items. Errors: {len(errors)}. Check logs."

@app.route('/robots.txt')
def robots():
    return "User-agent: *\nAllow: /\nSitemap: https://naijabuzz.com/sitemap.xml", 200, {'Content-Type': 'text/plain'}

@app.route('/sitemap.xml')
def sitemap():
    init_db()
    base_url = "https://naijabuzz.com"
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    # Homepage
    xml += f'  <url>\n    <loc>{base_url}/</loc>\n    <changefreq>hourly</changefreq>\n    <priority>1.0</priority>\n  </url>\n'

    # Category pages
    for key in CATEGORIES.keys():
        if key == 'all': continue
        cat_url = f"{base_url}/?cat={urllib.parse.quote(key)}"
        xml += f'  <url>\n    <loc>{cat_url}</loc>\n    <changefreq>daily</changefreq>\n    <priority>0.8</priority>\n  </url>\n'

    # Pagination pages (limit to 100)
    total_posts = Post.query.count()
    pages = (total_posts // 20) + 1 if total_posts else 1
    for p in range(1, min(pages + 1, 101)):
        xml += f'  <url>\n    <loc>{base_url}/?page={p}</loc>\n    <changefreq>daily</changefreq>\n    <priority>0.7</priority>\n  </url>\n'

    # Individual posts
    posts = Post.query.all()
    for post in posts:
        lastmod = post.pub_date.strftime('%Y-%m-%d')
        xml += f'  <url>\n    <loc>{base_url}/{post.slug}</loc>\n    <lastmod>{lastmod}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.9</priority>\n  </url>\n'

    xml += '</urlset>'
    return xml, 200, {'Content-Type': 'application/xml'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
