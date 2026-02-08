from flask import Flask, render_template_string, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_caching import Cache
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

# Caching (SimpleCache = in-memory; easy & fast for starters; switch to 'RedisCache' later if scaling)
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 300})

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
    # unchanged
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

# Groq primary - unchanged
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
    # unchanged
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
@cache.cached(timeout=300, query_string=True)
def index():
    init_db()
    selected = request.args.get('cat', 'all').lower()
    page = max(1, int(request.args.get('page', 1)))
    per_page = 20

    query = Post.query.order_by(Post.pub_date.desc())
    if selected != 'all':
        query = query.filter(Post.category.ilike(f"%{selected}%"))

    pag_obj = query.paginate(page=page, per_page=per_page, error_out=False)
    posts = pag_obj.items
    has_next = pag_obj.has_next

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
        <link rel="canonical" href="https://blog.naijabuzz.com">
        <meta property="og:title" content="{{ page_title }}">
        <meta property="og:description" content="{{ page_desc }}">
        <meta property="og:image" content="{{ featured_img }}">
        <meta property="og:url" content="https://blog.naijabuzz.com">
        <meta property="og:type" content="website">
        <meta name="twitter:card" content="summary_large_image">
        <meta name="twitter:title" content="{{ page_title }}">
        <meta name="twitter:description" content="{{ page_desc }}">
        <meta name="twitter:image" content="{{ featured_img }}">
        <meta name="keywords" content="naija news, nigerian gossip, football updates, entertainment news, tech news nigeria">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #00d4aa;
                --dark: #0f172a;
                --light: #f8fafc;
                --gray: #64748b;
                --accent: #00b894;
            }
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                font-family: 'Inter', system-ui, sans-serif;
                background: var(--light);
                color: #1e293b;
                line-height: 1.6;
                font-size: 16px;
            }
            header {
                background: linear-gradient(to bottom, var(--dark), #1e293b);
                color: white;
                text-align: center;
                padding: 1.5rem 1rem;
                position: sticky;
                top: 0;
                z-index: 1000;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            }
            h1 { font-size: 2.5rem; font-weight: 900; margin-bottom: 0.5rem; letter-spacing: -0.5px; }
            .tagline { font-size: 1.1rem; opacity: 0.9; font-weight: 300; }
            .tabs-container {
                background: white;
                padding: 0.75rem 0;
                overflow-x: auto;
                position: sticky;
                top: 4.5rem;
                z-index: 999;
                box-shadow: 0 2px 10px rgba(0,0,0,0.08);
                border-bottom: 1px solid #e2e8f0;
            }
            .tabs {
                display: flex;
                gap: 0.75rem;
                padding: 0 1rem;
                white-space: nowrap;
            }
            .tab {
                padding: 0.7rem 1.4rem;
                background: #e2e8f0;
                color: #334155;
                border-radius: 9999px;
                font-weight: 600;
                font-size: 0.95rem;
                text-decoration: none;
                transition: all 0.3s ease;
                min-width: 90px;
                text-align: center;
                min-height: 44px;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .tab:hover, .tab.active {
                background: var(--primary);
                color: white;
            }
            .container {
                max-width: 1400px;
                margin: 2.5rem auto;
                padding: 0 1rem;
            }
            .grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
                gap: 1.5rem;
            }
            .card {
                background: white;
                border-radius: 1rem;
                overflow: hidden;
                box-shadow: 0 4px 20px rgba(0,0,0,0.08);
                transition: transform 0.3s ease, box-shadow 0.3s ease;
            }
            .card:hover {
                transform: translateY(-8px);
                box-shadow: 0 20px 40px rgba(0,0,0,0.15);
            }
            .img-container {
                position: relative;
                height: 200px;
                background: #1e1e1e;
                overflow: hidden;
                aspect-ratio: 16/9;
            }
            .card img, .related-grid img {
                width: 100%;
                height: 100%;
                object-fit: cover;
                object-position: center;
                transition: transform 0.6s ease;
            }
            .card:hover img, .related-grid .card:hover img {
                transform: scale(1.05);
            }
            .content { padding: 1.25rem; }
            .card h2 {
                font-size: 1.25rem;
                line-height: 1.4;
                margin-bottom: 0.5rem;
                font-weight: 700;
            }
            .card h2 a {
                color: #0f172a;
                text-decoration: none;
            }
            .card h2 a:hover { color: var(--primary); }
            .meta {
                font-size: 0.85rem;
                color: var(--primary);
                font-weight: 700;
                margin-bottom: 0.5rem;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            .card p {
                color: #475569;
                font-size: 0.95rem;
                line-height: 1.6;
                margin-bottom: 1rem;
            }
            .readmore {
                background: var(--primary);
                color: white;
                padding: 0.7rem 1.4rem;
                border-radius: 9999px;
                text-decoration: none;
                font-weight: 700;
                display: inline-flex;
                align-items: center;
                min-height: 44px;
                transition: all 0.3s ease;
            }
            .readmore:hover {
                background: var(--accent);
                transform: translateY(-2px);
            }
            .pagination {
                display: flex;
                justify-content: center;
                gap: 0.75rem;
                margin: 2.5rem 0;
                flex-wrap: wrap;
            }
            .page-link {
                padding: 0.7rem 1.4rem;
                background: #e2e8f0;
                color: #334155;
                border-radius: 9999px;
                text-decoration: none;
                font-weight: 600;
                min-height: 44px;
                display: flex;
                align-items: center;
                transition: all 0.3s ease;
            }
            .page-link:hover, .page-link.active {
                background: var(--primary);
                color: white;
            }
            footer {
                text-align: center;
                padding: 3rem 1rem;
                background: white;
                color: var(--gray);
                font-size: 0.9rem;
                border-top: 1px solid #e2e8f0;
            }
            @media (max-width: 768px) {
                h1 { font-size: 2.2rem; }
                .tagline { font-size: 1rem; }
                .tabs-container { top: 4rem; padding: 0.5rem 0; }
                .tabs { gap: 0.5rem; padding: 0 0.5rem; }
                .tab { font-size: 0.9rem; padding: 0.6rem 1.2rem; min-width: auto; }
                .grid { grid-template-columns: 1fr; }
                .img-container { height: 220px; }
                .card h2 { font-size: 1.3rem; line-height: 1.45; }
                .single-container { padding: 0 0.75rem; }
            }
        </style>
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
                            <img loading="lazy" src="{{ p.image }}" alt="{{ p.title | e }}" width="400" height="225" style="aspect-ratio:16/9;">
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
                    <div style="grid-column:1/-1;text-align:center;padding:5rem 1rem;">
                        <p style="font-size:1.5rem;color:var(--primary);">No stories yet — refreshing soon!</p>
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

        <footer>© 2026 NaijaBuzz • blog.naijabuzz.com • Auto-updated every 15 minutes</footer>
    </body>
    </html>
    """
    return render_template_string(html, posts=posts, categories=CATEGORIES, selected=selected,
                                  ago=ago, page=page, has_next=has_next, page_title=page_title, page_desc=page_desc, featured_img=featured_img)

@app.route('/<slug>')
@cache.cached(timeout=1800, key_prefix=lambda: f"post_{request.view_args.get('slug')}")
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
        <link rel="canonical" href="https://blog.naijabuzz.com/{{ post.slug }}">
        <meta property="og:title" content="{{ page_title }}">
        <meta property="og:description" content="{{ page_desc }}">
        <meta property="og:image" content="{{ featured_img }}">
        <meta property="og:url" content="https://blog.naijabuzz.com/{{ post.slug }}">
        <meta property="og:type" content="article">
        <meta name="twitter:card" content="summary_large_image">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap" rel="stylesheet">
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "NewsArticle",
          "headline": "{{ post.title | e }}",
          "image": "{{ featured_img }}",
          "datePublished": "{{ post.pub_date.isoformat() }}",
          "dateModified": "{{ post.pub_date.isoformat() }}",
          "author": {"@type": "Organization", "name": "NaijaBuzz"},
          "publisher": {"@type": "Organization", "name": "NaijaBuzz"},
          "description": "{{ post.excerpt | striptags | e | safe }}"
        }
        </script>
        <style>
            :root{--primary:#00d4aa;--dark:#0f172a;--light:#f8fafc;--gray:#64748b;}
            body{font-family:'Inter',system-ui,Arial,sans-serif;background:var(--light);margin:0;color:#1e293b;line-height:1.6;font-size:16px;}
            header{background:linear-gradient(to bottom, var(--dark), #1e293b);color:white;text-align:center;padding:1.5rem 1rem;position:sticky;top:0;z-index:1000;box-shadow:0 4px 20px rgba(0,0,0,0.1);}
            h1{font-size:2.5rem;font-weight:900;margin-bottom:0.5rem;letter-spacing:-0.5px;}
            .tagline{font-size:1.1rem;opacity:0.9;font-weight:300;}
            .tabs-container{background:white;padding:0.75rem 0;overflow-x:auto;position:sticky;top:4.5rem;z-index:999;box-shadow:0 2px 10px rgba(0,0,0,0.08);}
            .tabs{display:flex;gap:0.75rem;padding:0 1rem;white-space:nowrap;}
            .tab{padding:0.7rem 1.4rem;background:#e2e8f0;color:#334155;border-radius:9999px;font-weight:600;font-size:0.95rem;text-decoration:none;transition:all 0.3s;min-height:44px;display:flex;align-items:center;justify-content:center;}
            .tab:hover,.tab.active{background:var(--primary);color:white;}
            .single-container{max-width:900px;margin:2.5rem auto;padding:0 1rem;}
            .single-img{width:100%;max-height:500px;object-fit:cover;border-radius:1rem;margin-bottom:1.5rem;object-position:center;}
            .single-meta{color:var(--primary);font-weight:700;margin-bottom:1rem;text-transform:uppercase;letter-spacing:0.5px;}
            .single-content{line-height:1.8;font-size:1.1rem;}
            .single-content h2, .single-content h3{margin:2rem 0 1rem;}
            .source{margin-top:2rem;font-style:italic;color:var(--gray);}
            .related{margin-top:4rem;}
            .related h2{margin-bottom:1.5rem;}
            .related-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1.5rem;}
            .related .card img{width:100%;height:150px;object-fit:cover;object-position:center;border-radius:12px 12px 0 0;}
            footer{text-align:center;padding:3rem 1rem;background:white;color:var(--gray);font-size:0.9rem;border-top:1px solid #e2e8f0;}
            @media (max-width: 768px) {
                h1{font-size:2.2rem;}
                .tagline{font-size:1rem;}
                .tabs-container{top:4rem;}
                .tabs{flex-wrap:nowrap;justify-content:flex-start;gap:0.5rem;padding:0 0.5rem;}
                .tab{font-size:0.9rem;padding:0.6rem 1.2rem;}
                .related-grid{grid-template-columns:1fr;}
                .related .card img{height:180px;}
            }
        </style>
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

        <div class="single-container">
            <h1>{{ post.title }}</h1>
            <div class="single-meta">{{ post.category }} • {{ ago(post.pub_date) }}</div>
            <img loading="lazy" src="{{ post.image }}" alt="{{ post.title | e }}" width="800" height="450" style="aspect-ratio:16/9;" class="single-img">
            <div class="single-content">{{ post.full_content | safe }}</div>
            <div class="source">Source: <a href="{{ post.link }}" target="_blank" rel="noopener nofollow">Original Article</a>. AI-enhanced version.</div>
            <div class="related">
                <h2>Related Stories</h2>
                <div class="related-grid">
                    {% for r in related %}
                    <div class="card">
                        <div class="img-container">
                            <img loading="lazy" src="{{ r.image }}" alt="{{ r.title | e }}" width="300" height="169" style="aspect-ratio:16/9;">
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

        <footer>© 2026 NaijaBuzz • blog.naijabuzz.com • Auto-updated every 15 minutes</footer>
    </body>
    </html>
    """
    return render_template_string(html, post=post, related=related, ago=ago, page_title=page_title, page_desc=page_desc, featured_img=featured_img, categories=CATEGORIES, selected=post.category.lower())

@app.route('/cron')
@app.route('/generate')
def cron():
    # unchanged
    init_db()
    added = 0
    skipped = 0
    errors = []
    try:
        with app.app_context():
            try: Post.query.first()
            except: db.drop_all(); db.create_all()
            random.shuffle(FEEDS)
            print(f"Processing batch of 10 feeds...")
            batch_size = 10
            for cat, url in FEEDS[:batch_size]:
                try:
                    f = feedparser.parse(url)
                    if not f.entries:
                        print(f"No entries from {url}")
                        continue
                    for e in f.entries[:3]:
                        try:
                            h = hashlib.md5((e.link + e.title).encode()).hexdigest()
                            if Post.query.filter_by(unique_hash=h).first():
                                continue
                            img = get_image(e)
                            summary = e.get('summary') or e.get('description') or ''
                            excerpt = BeautifulSoup(summary, 'html.parser').get_text(separator=' ')[:360] + "..." if summary else ""
                            title = e.title or "Untitled"
                            full_text = excerpt
                            try:
                                article = Article(e.link, fetch_images=False, request_timeout=10)
                                article.download()
                                article.parse()
                                full_text = article.text or excerpt
                                if not img and article.top_image:
                                    img = article.top_image
                                    if img.startswith('//'):
                                        img = 'https:' + img
                                    elif not img.startswith('http'):
                                        img = urllib.parse.urljoin(e.link, img)
                            except Exception as ex:
                                print(f"Article fetch skipped for '{title}': {ex}")
                                full_text = excerpt
                            if not img:
                                img = "https://via.placeholder.com/800x450/1e1e1e/ffffff?text=NaijaBuzz"
                            full_content = rewrite_article(full_text, title, cat)
                            del full_text
                            base_slug = slugify(title)[:180]
                            slug = base_slug
                            count = 1
                            while Post.query.filter_by(slug=slug).first():
                                slug = f"{base_slug}-{count}"
                                count += 1
                                if count > 5: break
                            post = Post(
                                title=title,
                                excerpt=excerpt,
                                full_content=full_content,
                                link=e.link,
                                unique_hash=h,
                                slug=slug,
                                image=img,
                                category=cat,
                                pub_date=parse_date(getattr(e, 'published', None))
                            )
                            db.session.add(post)
                            added += 1
                        except Exception as item_ex:
                            skipped += 1
                            errors.append(f"Item skipped in {cat} ({url}): {str(item_ex)[:150]}")
                            continue
                    db.session.commit()
                except Exception as feed_ex:
                    skipped += 1
                    errors.append(f"Feed skipped {url}: {str(feed_ex)[:150]}")
                    continue
    except Exception as main_ex:
        errors.append(f"Main cron error: {str(main_ex)}")
        print(f"Main cron error: {str(main_ex)}")
    finally:
        if errors:
            print("Cron partial errors:")
            for err in errors[:5]:
                print(err)
            if len(errors) > 5:
                print(f"... and {len(errors)-5} more")
    return f"NaijaBuzz cron ran! Added {added} new stories. Skipped {skipped} items. Errors: {len(errors)}. Check logs."

@app.route('/robots.txt')
def robots():
    return "User-agent: *\nAllow: /\nSitemap: https://blog.naijabuzz.com/sitemap.xml", 200, {'Content-Type': 'text/plain'}

@app.route('/sitemap.xml')
def sitemap():
    init_db()
    base_url = "https://blog.naijabuzz.com"
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    # Homepage
    xml += f'  <url>\n    <loc>{base_url}/</loc>\n    <lastmod>{datetime.now(timezone.utc).strftime("%Y-%m-%d")}</lastmod>\n    <changefreq>hourly</changefreq>\n    <priority>1.0</priority>\n  </url>\n'

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
