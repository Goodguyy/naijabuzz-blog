from flask import Flask, render_template_string, request, abort, send_from_directory
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
import google.generativeai as genai
from functools import lru_cache
from sqlalchemy import text  # for clean DB ping

app = Flask(__name__)

# Load environment variables from .env file (if present)
from dotenv import load_dotenv
load_dotenv()

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

# API Clients
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
groq_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
) if GROQ_API_KEY else None

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

HF_API_KEY = os.environ.get('HUGGINGFACE_API_KEY')

# Cache rewrites (max 500 unique in memory)
@lru_cache(maxsize=500)
def cached_rewrite(key):
    return None  # placeholder

def rewrite_article(full_text, title, category):
    cache_key = hashlib.sha256((title + full_text[:1000]).encode()).hexdigest()
    cached = cached_rewrite(cache_key)
    if cached:
        print(f"[CACHE HIT] {title}")
        return cached

    original_text = full_text.strip()
    print(f"[REWRITE] {title} ({len(original_text)} chars)")

    # 1. Gemini
    if GEMINI_API_KEY:
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            prompt = f"""
                Rewrite this article completely in your own words as an original piece for Nigerian readers.
                Include relevant Naija context, implications, or angles where natural.
                Keep tone neutral but interesting. Structure: hook intro, main body (short paragraphs), conclusion.
                Aim for 300–500 words. Do NOT copy original sentences directly.
                Original title: {title}
                Category: {category}
                Content: {original_text[:4000]}
            """
            print("[Gemini] Trying...")
            response = model.generate_content(prompt, request_options={"timeout": 45})
            rewritten = response.text.strip()
            if rewritten and len(rewritten) > 200:
                print(f"[Gemini SUCCESS] {len(rewritten)} chars")
                cached_rewrite(cache_key)
                return rewritten
        except Exception as e:
            print(f"[Gemini FAILED] {str(e)}")

    # 2. Hugging Face
    if HF_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {HF_API_KEY}"}
            payload = {
                "inputs": f"""
                    Rewrite this article completely in your own words as an original piece for Nigerian readers.
                    Include relevant Naija context, implications, or angles where natural.
                    Keep tone neutral but interesting. Structure: hook intro, main body (short paragraphs), conclusion.
                    Aim for 300–500 words. Do NOT copy original sentences directly.
                    Original title: {title}
                    Category: {category}
                    Content: {original_text[:3000]}
                """,
                "parameters": {"max_new_tokens": 700, "temperature": 0.7, "do_sample": True}
            }
            print("[HF] Trying...")
            resp = requests.post(
                "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3",
                headers=headers,
                json=payload,
                timeout=45
            )
            resp.raise_for_status()
            result = resp.json()
            rewritten = result[0]['generated_text'].strip()
            if rewritten and len(rewritten) > 200:
                print(f"[HF SUCCESS] {len(rewritten)} chars")
                cached_rewrite(cache_key)
                return rewritten
        except Exception as e:
            print(f"[HF FAILED] {str(e)}")

    # 3. Groq
    if groq_client:
        try:
            print("[Groq] Trying...")
            resp = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": f"""
                    Rewrite this article in your own words for Nigerian readers. Add Naija context if relevant.
                    Tone neutral, interesting. 300–500 words. Title: {title}. Category: {category}.
                    Content: {original_text[:2000]}
                """}],
                max_tokens=600,
                temperature=0.7,
                timeout=45
            )
            rewritten = resp.choices[0].message.content.strip()
            if rewritten and len(rewritten) > 200:
                print(f"[Groq SUCCESS] {len(rewritten)} chars")
                cached_rewrite(cache_key)
                return rewritten
        except Exception as e:
            print(f"[Groq FAILED] {str(e)}")

    print("[FALLBACK] Using original text")
    return original_text

# Serve static files
@app.route('/sitemap.xml')
def serve_sitemap():
    return send_from_directory('.', 'sitemap.xml')

@app.route('/robots.txt')
def serve_robots():
    return send_from_directory('.', 'robots.txt')

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
                box-shadow: 0 2px 10px rgba(0,0,0,0.15);
                padding: 1.2rem 0;
                transition: padding 0.3s ease;
            }
            .header-inner {
                text-align: center;
                padding: 0 1rem;
            }
            h1 {
                font-family: 'Playfair Display', serif;
                font-size: 2.6rem;
                font-weight: 700;
                margin: 0;
                letter-spacing: -1px;
            }
            .tagline {
                font-size: 1.1rem;
                opacity: 0.9;
                margin-top: 0.3rem;
            }
            .tabs-container {
                background: white;
                padding: 0.8rem 0;
                overflow-x: auto;
                border-bottom: 1px solid var(--border);
            }
            .tabs {
                display: flex;
                gap: 0.7rem;
                padding: 0 1rem;
                white-space: nowrap;
                justify-content: center;
            }
            .tab {
                padding: 0.6rem 1.3rem;
                background: #f1f5f9;
                color: #475569;
                border-radius: 9999px;
                font-weight: 600;
                font-size: 0.95rem;
                text-decoration: none;
                transition: all 0.3s ease;
            }
            .tab:hover, .tab.active {
                background: var(--primary);
                color: white;
            }
            .container {
                max-width: 1440px;
                margin: 2rem auto;
                padding: 0 1rem;
            }
            .grid {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 1.8rem;
            }
            .card {
                background: white;
                border-radius: 1rem;
                overflow: hidden;
                box-shadow: 0 4px 16px rgba(0,0,0,0.08);
                transition: all 0.3s ease;
                border: 1px solid var(--border);
            }
            .card:hover {
                transform: translateY(-6px);
                box-shadow: 0 16px 32px rgba(0,0,0,0.12);
            }
            .img-container {
                height: 220px;
                background: #0f172a;
                overflow: hidden;
            }
            .card img {
                width: 100%;
                height: 100%;
                object-fit: cover;
                transition: transform 0.5s ease;
            }
            .card:hover img { transform: scale(1.06); }
            .content { padding: 1.3rem; }
            .category-badge {
                display: inline-block;
                background: var(--primary);
                color: white;
                padding: 0.3rem 0.8rem;
                border-radius: 9999px;
                font-size: 0.75rem;
                font-weight: 600;
                margin-bottom: 0.6rem;
            }
            .card h2 { font-size: 1.3rem; line-height: 1.4; margin-bottom: 0.6rem; font-weight: 700; }
            .card h2 a { color: #0f172a; text-decoration: none; }
            .card h2 a:hover { color: var(--primary); }
            .meta { font-size: 0.85rem; color: var(--gray); margin-bottom: 0.7rem; }
            .card p { color: #475569; font-size: 0.98rem; line-height: 1.6; margin-bottom: 1rem; }
            .readmore {
                background: var(--primary);
                color: white;
                padding: 0.7rem 1.5rem;
                border-radius: 9999px;
                text-decoration: none;
                font-weight: 700;
                font-size: 0.95rem;
                display: inline-block;
                transition: all 0.3s;
            }
            .readmore:hover { background: var(--primary-dark); }
            .pagination { display: flex; justify-content: center; gap: 0.8rem; margin: 3rem 0; flex-wrap: wrap; }
            .page-link { padding: 0.7rem 1.4rem; background: #f1f5f9; color: #475569; border-radius: 9999px; text-decoration: none; font-weight: 600; transition: all 0.3s; }
            .page-link:hover, .page-link.active { background: var(--primary); color: white; }
            footer { text-align: center; padding: 3rem 1rem; background: var(--dark); color: #94a3b8; font-size: 0.9rem; }
            footer a { color: var(--primary); text-decoration: none; }
            @media (max-width: 1024px) { .grid { grid-template-columns: repeat(3, 1fr); } }
            @media (max-width: 768px) {
                header { padding: 0.8rem 0; }
                h1 { font-size: 2rem; margin: 0; }
                .tagline { font-size: 0.95rem; }
                .tabs { padding: 0 0.5rem; gap: 0.5rem; }
                .tab { padding: 0.5rem 1rem; font-size: 0.9rem; }
                .grid { grid-template-columns: repeat(2, 1fr); gap: 1.2rem; }
                .container { margin: 1.5rem auto; padding: 0 0.8rem; }
                .img-container { height: 180px; }
            }
            @media (max-width: 480px) {
                .grid { grid-template-columns: 1fr; }
                h1 { font-size: 1.8rem; }
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
                    <div style="grid-column:1/-1;text-align:center;padding:6rem 1rem;">
                        <p style="font-size:1.6rem;color:var(--primary);font-weight:600;">
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
                line-height: 1.8;
                font-size: 1.1rem;
            }
            header {
                background: linear-gradient(135deg, var(--dark) 0%, #1e293b 100%);
                color: white;
                position: sticky;
                top: 0;
                z-index: 1000;
                box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                padding: 0.8rem 0;
                transition: padding 0.3s ease;
            }
            .header-inner {
                text-align: center;
                padding: 0 1rem;
            }
            h1 {
                font-family: 'Playfair Display', serif;
                font-size: 2.2rem;
                font-weight: 700;
                margin: 0.4rem 0 0.2rem;
                letter-spacing: -1px;
            }
            .tagline {
                font-size: 1rem;
                opacity: 0.9;
                margin: 0;
            }
            .tabs-container {
                background: white;
                padding: 0.6rem 0;
                overflow-x: auto;
                border-bottom: 1px solid var(--border);
            }
            .tabs {
                display: flex;
                gap: 0.6rem;
                padding: 0 0.8rem;
                white-space: nowrap;
                justify-content: center;
            }
            .tab {
                padding: 0.5rem 1.1rem;
                background: #f1f5f9;
                color: #475569;
                border-radius: 9999px;
                font-weight: 600;
                font-size: 0.9rem;
                text-decoration: none;
                transition: all 0.3s ease;
            }
            .tab:hover, .tab.active {
                background: var(--primary);
                color: white;
            }
            .single-container {
                max-width: 1000px;
                margin: 1.5rem auto;
                padding: 0 1rem;
            }
            .single-img {
                width: 100%;
                max-height: 500px;
                object-fit: cover;
                border-radius: 1rem;
                margin: 1rem 0 1.5rem;
                box-shadow: 0 8px 24px rgba(0,0,0,0.12);
            }
            .single-meta {
                color: var(--primary);
                font-weight: 700;
                font-size: 0.95rem;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-bottom: 0.8rem;
            }
            h1 {
                font-size: 2.4rem;
                line-height: 1.2;
                margin-bottom: 1rem;
                color: var(--dark);
            }
            .single-content {
                line-height: 1.9;
                font-size: 1.15rem;
                color: #1e293b;
            }
            .single-content h2, .single-content h3 {
                margin: 2rem 0 1rem;
                color: var(--dark);
            }
            .source {
                margin: 2.5rem 0 3rem;
                font-style: italic;
                color: var(--gray);
                font-size: 0.95rem;
            }
            .source a {
                color: var(--primary);
                text-decoration: none;
            }
            .related {
                margin-top: 4rem;
            }
            .related h2 {
                font-family: 'Playfair Display', serif;
                font-size: 2rem;
                margin-bottom: 1.5rem;
                color: var(--dark);
            }
            .related-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 1.8rem;
            }
            .related .card {
                background: white;
                border-radius: 1rem;
                overflow: hidden;
                box-shadow: 0 4px 16px rgba(0,0,0,0.08);
                transition: all 0.3s;
            }
            .related .card:hover {
                transform: translateY(-6px);
                box-shadow: 0 16px 32px rgba(0,0,0,0.12);
            }
            .related .img-container {
                height: 180px;
                background: #0f172a;
                overflow: hidden;
            }
            .related .img-container img {
                width: 100%;
                height: 100%;
                object-fit: cover;
            }
            .related .content {
                padding: 1.2rem;
            }
            .related .card h2 {
                font-size: 1.25rem;
                margin-bottom: 0.5rem;
            }
            .related .meta {
                font-size: 0.85rem;
                color: var(--gray);
            }
            footer {
                text-align: center;
                padding: 4rem 1rem 2rem;
                background: var(--dark);
                color: #94a3b8;
                font-size: 0.95rem;
            }
            footer a {
                color: var(--primary);
                text-decoration: none;
            }
            @media (max-width: 768px) {
                header { padding: 0.6rem 0; }
                h1 { font-size: 1.8rem; margin: 0.3rem 0; }
                .tagline { font-size: 0.9rem; }
                .single-container { margin: 1rem auto; padding: 0 0.8rem; }
                .single-img { max-height: 400px; margin: 0.8rem 0 1.2rem; }
                .single-meta { font-size: 0.85rem; margin-bottom: 0.6rem; }
                .single-content { font-size: 1.05rem; }
                .related-grid { grid-template-columns: 1fr; }
            }
            @media (max-width: 480px) {
                h1 { font-size: 1.6rem; }
                .single-img { max-height: 300px; }
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

@app.route('/cron')
@app.route('/generate')
def cron():
    added = 0
    skipped = 0
    errors = []

    try:
        init_db()

        # DB health check (fixed with text())
        try:
            db.session.execute(text("SELECT 1"))
        except Exception as db_err:
            errors.append(f"DB ping failed: {str(db_err)}")
            db.session.rollback()

        with app.app_context():
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
                            errors.append(str(item_ex)[:150])
                            continue
                    db.session.commit()
                except Exception as feed_ex:
                    skipped += 1
                    errors.append(str(feed_ex)[:150])
                    continue
    except Exception as main_ex:
        errors.append(str(main_ex))
        print(f"Main cron error: {str(main_ex)}")

    finally:
        msg = f"NaijaBuzz cron ran! Added {added} new stories. Skipped {skipped} items. Errors: {len(errors)}."
        if errors:
            msg += " Last error: " + errors[-1]
            print("Cron errors:", errors)
        return msg

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
