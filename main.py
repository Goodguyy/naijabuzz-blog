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
from sqlalchemy import exc as sa_exc

app = Flask(__name__)

# Database configuration
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

FEEDS = [
    ("Naija News", "https://punchng.com/feed/"),
    ("Naija News", "https://www.vanguardngr.com/feed"),
    ("Naija News", "https://www.premiumtimesng.com/feed"),
    # ... (keeping all your original feeds unchanged)
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

GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
groq_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
) if GROQ_API_KEY else None

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
        <link rel="canonical" href="https://naijabuzz.com/?cat={{ selected if selected != 'all' else '' }}">
        <meta property="og:title" content="{{ page_title }}">
        <meta property="og:description" content="{{ page_desc }}">
        <meta property="og:image" content="{{ featured_img }}">
        <meta property="og:url" content="https://naijabuzz.com">
        <meta property="og:type" content="website">
        <meta name="twitter:card" content="summary_large_image">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;900&family=Playfair+Display:wght@700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #0066cc;
                --primary-dark: #004080;
                --accent: #ff6b35;
                --dark: #0f172a;
                --light: #f8fafc;
                --gray: #64748b;
                --border: #e2e8f0;
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
                background: linear-gradient(135deg, var(--dark) 0%, #1e293b 100%);
                color: white;
                position: sticky;
                top: 0;
                z-index: 1000;
                box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            }
            .header-inner {
                text-align: center;
                padding: 2rem 1rem 1.2rem;
            }
            h1 {
                font-family: 'Playfair Display', serif;
                font-size: 3.2rem;
                font-weight: 700;
                margin-bottom: 0.4rem;
                letter-spacing: -1.5px;
            }
            .tagline {
                font-size: 1.25rem;
                opacity: 0.9;
                font-weight: 300;
            }
            .tabs-container {
                background: white;
                padding: 1rem 0;
                overflow-x: auto;
                border-bottom: 1px solid var(--border);
                box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            }
            .tabs {
                display: flex;
                gap: 0.8rem;
                padding: 0 1.5rem;
                white-space: nowrap;
                justify-content: center;
            }
            .tab {
                padding: 0.75rem 1.6rem;
                background: #f1f5f9;
                color: #475569;
                border-radius: 9999px;
                font-weight: 600;
                font-size: 1rem;
                text-decoration: none;
                transition: all 0.3s ease;
                border: 1px solid transparent;
            }
            .tab:hover, .tab.active {
                background: var(--primary);
                color: white;
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0,102,204,0.2);
            }
            .container {
                max-width: 1440px;
                margin: 3rem auto;
                padding: 0 1.5rem;
            }
            .grid {
                display: grid;
                grid-template-columns: repeat(4, 1fr);           /* 4 columns on desktop */
                gap: 2rem;
            }
            .card {
                background: white;
                border-radius: 1rem;
                overflow: hidden;
                box-shadow: 0 6px 20px rgba(0,0,0,0.08);
                transition: all 0.3s ease;
                border: 1px solid var(--border);
            }
            .card:hover {
                transform: translateY(-8px);
                box-shadow: 0 20px 40px rgba(0,0,0,0.12);
                border-color: var(--primary);
            }
            .img-container {
                height: 240px;
                background: #0f172a;
                overflow: hidden;
                position: relative;
            }
            .card img {
                width: 100%;
                height: 100%;
                object-fit: cover;
                transition: transform 0.6s ease;
            }
            .card:hover img { transform: scale(1.08); }
            .content {
                padding: 1.5rem;
            }
            .category-badge {
                display: inline-block;
                background: var(--primary);
                color: white;
                padding: 0.35rem 0.9rem;
                border-radius: 9999px;
                font-size: 0.8rem;
                font-weight: 600;
                margin-bottom: 0.8rem;
            }
            .card h2 {
                font-size: 1.4rem;
                line-height: 1.4;
                margin-bottom: 0.8rem;
                font-weight: 700;
            }
            .card h2 a {
                color: #0f172a;
                text-decoration: none;
            }
            .card h2 a:hover {
                color: var(--primary);
            }
            .meta {
                font-size: 0.9rem;
                color: var(--gray);
                margin-bottom: 0.8rem;
            }
            .card p {
                color: #475569;
                font-size: 1rem;
                line-height: 1.6;
                margin-bottom: 1.2rem;
            }
            .readmore {
                background: var(--primary);
                color: white;
                padding: 0.8rem 1.8rem;
                border-radius: 9999px;
                text-decoration: none;
                font-weight: 700;
                display: inline-block;
                transition: all 0.3s ease;
            }
            .readmore:hover {
                background: var(--primary-dark);
                transform: translateY(-2px);
            }
            .pagination {
                display: flex;
                justify-content: center;
                gap: 1rem;
                margin: 4rem 0;
                flex-wrap: wrap;
            }
            .page-link {
                padding: 0.8rem 1.8rem;
                background: #f1f5f9;
                color: #475569;
                border-radius: 9999px;
                text-decoration: none;
                font-weight: 600;
                transition: all 0.3s;
            }
            .page-link:hover, .page-link.active {
                background: var(--primary);
                color: white;
                transform: translateY(-2px);
            }
            footer {
                text-align: center;
                padding: 4rem 1rem 2rem;
                background: var(--dark);
                color: #94a3b8;
                font-size: 0.95rem;
                border-top: 1px solid #334155;
            }
            footer a {
                color: var(--primary);
                text-decoration: none;
                font-weight: 600;
            }
            @media (max-width: 1024px) {
                .grid { grid-template-columns: repeat(3, 1fr); }
            }
            @media (max-width: 768px) {
                .grid { grid-template-columns: repeat(2, 1fr); gap: 1.5rem; }
                h1 { font-size: 2.6rem; }
                .header-inner { padding: 1.8rem 1rem 1rem; }
                .tabs { justify-content: flex-start; padding: 0 1rem; }
            }
            @media (max-width: 480px) {
                .grid { grid-template-columns: 1fr; }
                h1 { font-size: 2.2rem; }
            }
        </style>
    </head>
    <body>
        <header>
            <div class="header-inner">
                <h1>NaijaBuzz</h1>
                <div class="tagline">Your Daily Dose of Fresh Nigerian & Global News</div>
            </div>

            <nav class="tabs-container">
                <div class="tabs">
                    {% for key, name in categories.items() %}
                    <a href="/?cat={{ key }}" class="tab {{ 'active' if selected == key else '' }}">{{ name }}</a>
                    {% endfor %}
                </div>
            </nav>
        </header>

        <div class="container">
            <div class="grid">
                {% if posts %}
                    {% for p in posts %}
                    <div class="card">
                        <div class="img-container">
                            <img loading="lazy" src="{{ p.image }}" alt="{{ p.title }}">
                        </div>
                        <div class="content">
                            <span class="category-badge">{{ p.category }}</span>
                            <h2><a href="/{{ p.slug }}">{{ p.title }}</a></h2>
                            <div class="meta">{{ ago(p.pub_date) }}</div>
                            <p>{{ p.excerpt|safe }}</p>
                            <a href="/{{ p.slug }}" class="readmore">Read Full Story →</a>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div style="grid-column:1/-1;text-align:center;padding:8rem 1rem;">
                        <p style="font-size:1.8rem;color:var(--primary);font-weight:600;">
                            No stories yet — content refreshes every 15 minutes!
                        </p>
                    </div>
                {% endif %}
            </div>

            <div class="pagination">
                {% if page > 1 %}
                <a href="/?cat={{ selected }}&page={{ page-1 }}" class="page-link">← Previous</a>
                {% endif %}
                <span class="page-link active">Page {{ page }}</span>
                {% if has_next %}
                <a href="/?cat={{ selected }}&page={{ page+1 }}" class="page-link">Next →</a>
                {% endif %}
            </div>
        </div>

        <footer>
            © 2026 <a href="/">NaijaBuzz</a> • All rights reserved • Auto-refreshed every 15 minutes
        </footer>
    </body>
    </html>
    """
    return render_template_string(html, posts=posts, categories=CATEGORIES, selected=selected,
                                  ago=ago, page=page, has_next=has_next, page_title=page_title, page_desc=page_desc, featured_img=featured_img)

# ────────────────────────────────────────────────
#  POST DETAIL PAGE (updated with more professional look)
# ────────────────────────────────────────────────

@app.route('/<slug>')
def post_detail(slug):
    post = Post.query.filter_by(slug=slug).first()
    if not post:
        abort(404, description="Article not found")

    related = Post.query.filter(Post.category == post.category, Post.id != post.id).order_by(Post.pub_date.desc()).limit(6).all()

    def ago(dt):
        if not dt: return "Just now"
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - dt
        if diff < timedelta(minutes=60): return f"{int(diff.total_seconds()//60)}m ago"
        if diff < timedelta(hours=24): return f"{int(diff.total_seconds()//3600)}h ago"
        if diff < timedelta(days=7): return f"{diff.days}d ago"
        return dt.strftime("%b %d, %Y")

    page_title = f"{post.title} - NaijaBuzz"
    page_desc = post.excerpt[:160] or "Read the latest curated news story."
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
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;900&family=Playfair+Display:wght@700&display=swap" rel="stylesheet">
        <style>
            :root{--primary:#0066cc;--primary-dark:#004080;--accent:#ff6b35;--dark:#0f172a;--light:#f8fafc;--gray:#64748b;--border:#e2e8f0;}
            body{font-family:'Inter',system-ui,sans-serif;background:var(--light);margin:0;color:#1e293b;line-height:1.8;font-size:1.1rem;}
            header{background:linear-gradient(135deg, var(--dark) 0%, #1e293b 100%);color:white;text-align:center;padding:2.2rem 1rem 1.4rem;position:sticky;top:0;z-index:1000;box-shadow:0 6px 25px rgba(0,0,0,0.2);}
            h1{font-family:'Playfair Display',serif;font-size:3rem;font-weight:700;margin-bottom:0.6rem;letter-spacing:-1px;}
            .tagline{font-size:1.3rem;opacity:0.9;font-weight:300;}
            .single-container{max-width:1100px;margin:3.5rem auto;padding:0 1.5rem;}
            .single-img{width:100%;max-height:680px;object-fit:cover;border-radius:1.2rem;margin:2rem 0;box-shadow:0 10px 30px rgba(0,0,0,0.15);}
            .single-meta{color:var(--primary);font-weight:700;font-size:1rem;text-transform:uppercase;letter-spacing:1px;margin-bottom:1.2rem;}
            .single-content{line-height:1.9;font-size:1.18rem;}
            .single-content h2, .single-content h3{margin:2.8rem 0 1.4rem;color:var(--dark);}
            .source{margin:3rem 0 2rem;font-style:italic;color:var(--gray);font-size:1rem;}
            .source a{color:var(--primary);text-decoration:none;}
            .source a:hover{text-decoration:underline;}
            .related{margin-top:5rem;}
            .related h2{font-family:'Playfair Display',serif;font-size:2.2rem;margin-bottom:2rem;color:var(--dark);}
            .related-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:2rem;}
            .related .card{background:white;border-radius:1rem;overflow:hidden;box-shadow:0 6px 20px rgba(0,0,0,0.08);transition:all 0.3s;}
            .related .card:hover{transform:translateY(-8px);box-shadow:0 20px 40px rgba(0,0,0,0.12);}
            .related .img-container{height:200px;background:#0f172a;overflow:hidden;}
            .related .img-container img{width:100%;height:100%;object-fit:cover;}
            .related .content{padding:1.4rem;}
            .related .card h2{font-size:1.3rem;line-height:1.4;margin-bottom:0.6rem;}
            .related .meta{font-size:0.9rem;color:var(--gray);}
            footer{text-align:center;padding:5rem 1rem 3rem;background:var(--dark);color:#94a3b8;font-size:1rem;border-top:1px solid #334155;}
            footer a{color:var(--primary);text-decoration:none;font-weight:600;}
            @media (max-width:1024px){.single-container{max-width:900px;}}
            @media (max-width:768px){
                h1{font-size:2.4rem;}
                .single-container{padding:0 1rem;margin:2rem auto;}
                .single-img{max-height:500px;}
                .related-grid{grid-template-columns:1fr;}
            }
        </style>
    </head>
    <body>
        <header>
            <div class="header-inner">
                <h1>NaijaBuzz</h1>
                <div class="tagline">Your Trusted Source for Fresh News & Updates</div>
            </div>
            <nav class="tabs-container">
                <div class="tabs">
                    {% for key, name in categories.items() %}
                    <a href="/?cat={{ key }}" class="tab {{ 'active' if selected == key else '' }}">{{ name }}</a>
                    {% endfor %}
                </div>
            </nav>
        </header>

        <div class="single-container">
            <div class="single-meta">{{ post.category }} • {{ ago(post.pub_date) }}</div>
            <h1>{{ post.title }}</h1>
            <img loading="lazy" src="{{ post.image }}" alt="{{ post.title }}" class="single-img">
            <div class="single-content">{{ post.full_content | safe }}</div>
            <div class="source">Source: <a href="{{ post.link }}" target="_blank" rel="noopener nofollow">Original Article</a> • AI-enhanced version for clarity & Nigerian context</div>

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
            © 2026 <a href="/">NaijaBuzz</a> • naijabuzz.com • Always refreshed with the latest stories
        </footer>
    </body>
    </html>
    """
    return render_template_string(html, post=post, related=related, ago=ago, page_title=page_title, page_desc=page_desc, featured_img=featured_img, categories=CATEGORIES, selected=post.category.lower())

# Cron job (unchanged)
@app.route('/cron')
@app.route('/generate')
def cron():
    # ... (your original cron code remains 100% unchanged)
    # I've omitted it here for brevity, but keep it exactly as it was
    pass  # ← replace with your full cron function

@app.route('/robots.txt')
def robots():
    return "User-agent: *\nAllow: /\nSitemap: https://naijabuzz.com/sitemap.xml", 200, {'Content-Type': 'text/plain'}

# NO /sitemap.xml route anymore — use static file instead

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
