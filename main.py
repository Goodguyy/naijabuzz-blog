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
    image = db.Column(db.String(600), default="https://via.placeholder.com/800x450/1e1e1e/ffffff?text=No+Image+-+NaijaBuzz")
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

# Your expanded feeds (unchanged)
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
    ("Entertainment", "https://www.pulse.ng/entertainment/rss"),
    ("Entertainment", "https://notjustok.com/feed/"),
    ("Entertainment", "https://tooxclusive.com/feed/"),
    ("Entertainment", "https://www.36ng.com.ng/feed/"),
    ("Entertainment", "https://www.legit.ng/rss/entertainment.rss"),

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
    ("Sports", "https://www.legit.ng/rss/sports.rss"),

    ("Lifestyle", "https://www.sisiyemmie.com/feed"),
    ("Lifestyle", "https://www.bellanaija.com/feed/"),
    ("Lifestyle", "https://www.bellanaija.com/style/feed/"),
    ("Lifestyle", "https://www.pulse.ng/lifestyle/rss"),
    ("Lifestyle", "https://vanguardngr.com/lifeandstyle/feed"),

    ("Education", "https://myschoolgist.com/feed"),
    ("Education", "https://flashlearners.com/feed/"),
    ("Education", "https://www.legit.ng/rss/education.rss"),

    ("Tech", "https://techcabal.com/feed/"),
    ("Tech", "https://technext.ng/feed"),
    ("Tech", "https://techpoint.africa/feed"),
    ("Tech", "https://www.legit.ng/rss/technology.rss"),

    ("Viral", "https://www.naijaloaded.com.ng/category/viral/feed"),
    ("Viral", "https://www.legit.ng/rss/viral.rss"),

    ("World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("World", "http://feeds.reuters.com/Reuters/worldNews"),
    ("World", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("World", "https://www.theguardian.com/world/rss"),
    ("World", "https://www.bbc.com/news/world/rss.xml"),
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
    return "https://via.placeholder.com/800x450/1e1e1e/ffffff?text=No+Image+-+NaijaBuzz"

def parse_date(d):
    if not d: return datetime.now(timezone.utc)
    try: return date_parser.parse(d).astimezone(timezone.utc)
    except: return datetime.now(timezone.utc)

# Groq API setup (OpenAI-compatible, fast & free tier)
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
groq_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
) if GROQ_API_KEY else None

if GROQ_API_KEY:
    print("Groq API configured successfully")
else:
    print("Warning: No GROQ_API_KEY set - using fallback short excerpts")

def rewrite_article(full_text, title, category):
    if not groq_client or not full_text.strip():
        return full_text

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Strong Groq model for rewriting
            messages=[{"role": "user", "content": f"""
                Rewrite this article completely in your own words as an original, engaging piece for Nigerian readers.
                Include relevant Naija context, implications, or angles where natural.
                Keep tone neutral but interesting. Structure: hook intro, main body (short paragraphs, headings if useful), conclusion.
                Aim for 500–800 words. Do NOT copy original sentences directly.
                Original title: {title}
                Category: {category}
                Content: {full_text[:8000]}
            """}],
            max_tokens=1200,
            temperature=0.7
        )
        rewritten = response.choices[0].message.content.strip()
        if not rewritten:
            return full_text
        return rewritten
    except Exception as e:
        print(f"Groq rewrite error: {str(e)[:200]}")
        return full_text  # fallback

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
    page_desc = "Latest Nigerian news, football, gossip & updates - AI-curated for you."
    featured_img = posts[0].image if posts else "https://via.placeholder.com/800x450?text=NaijaBuzz"

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>{{ page_title }}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
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
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [{% for p in posts %}{"@type": "ListItem", "position": {{ loop.index }}, "item": {"@type": "NewsArticle", "headline": "{{ p.title | e }}", "url": "https://blog.naijabuzz.com/{{ p.slug }}", "image": "{{ p.image }}", "datePublished": "{{ p.pub_date.isoformat() }}", "publisher": {"@type": "Organization", "name": "NaijaBuzz"}} }{% if not loop.last %},{% endif %}{% endfor %}]}
        </script>
        <style>
            :root{--primary:#00d4aa;--dark:#0f172a;--light:#f8fafc;--gray:#64748b;}
            body{font-family:'Inter',system-ui,Arial,sans-serif;background:var(--light);margin:0;color:#1e293b;}
            header{background:var(--dark);color:white;text-align:center;padding:20px 16px;position:sticky;top:0;z-index:1000;box-shadow:0 4px 20px rgba(0,0,0,0.1);}
            h1{margin:0;font-size:32px;font-weight:900;}
            .tagline{font-size:16px;margin-top:8px;opacity:0.9;}
            .tabs-container{background:white;padding:12px 0;overflow-x:auto;position:sticky;top:80px;z-index:999;box-shadow:0 2px 10px rgba(0,0,0,0.08);}
            .tabs{display:flex;gap:10px;padding:0 16px;}
            .tab{padding:10px 20px;background:#e2e8f0;color:#334155;border-radius:30px;font-weight:600;font-size:14px;text-decoration:none;transition:0.3s;}
            .tab:hover,.tab.active{background:var(--primary);color:white;}
            .container{max-width:1400px;margin:40px auto;padding:0 16px;}
            .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:24px;}
            @media(min-width:640px){.grid{grid-template-columns:repeat(2,1fr);}}
            @media(min-width:1024px){.grid{grid-template-columns:repeat(3,1fr);}}
            @media(min-width:1400px){.grid{grid-template-columns:repeat(4,1fr);}}
            .card{background:white;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08);transition:0.4s;}
            .card:hover{transform:translateY(-8px);box-shadow:0 20px 40px rgba(0,0,0,0.15);}
            .img-container{position:relative;height:200px;background:#1e293b;overflow:hidden;aspect-ratio:16/9;border-radius:12px 12px 0 0;}
            .card img{width:100%;height:100%;object-fit:cover;object-position:center;transition:transform 0.6s;}
            .card:hover img{transform:scale(1.1);}
            .placeholder{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:white;font-size:18px;font-weight:bold;background:rgba(30,41,59,0.8);}
            .content{padding:20px;}
            .card h2{font-size:19px;line-height:1.4;margin:0 0 8px;font-weight:700;}
            .card h2 a{color:#0f172a;text-decoration:none;}
            .card h2 a:hover{color:var(--primary);}
            .meta{font-size:13px;color:var(--primary);font-weight:700;margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px;}
            .card p{color:#475569;font-size:15px;line-height:1.6;margin:0 0 16px;}
            .readmore{background:var(--primary);color:white;padding:10px 20px;border-radius:30px;text-decoration:none;font-weight:700;display:inline-block;transition:0.3s;}
            .readmore:hover{background:#00b894;transform:translateY(-2px);}
            .pagination{display:flex;justify-content:center;gap:10px;margin:40px 0;flex-wrap:wrap;}
            .page-link{padding:10px 18px;background:#e2e8f0;color:#334155;border-radius:30px;text-decoration:none;font-weight:600;transition:0.3s;}
            .page-link:hover,.page-link.active{background:var(--primary);color:white;}
            footer{text-align:center;padding:40px 20px;background:white;color:var(--gray);font-size:14px;border-top:1px solid #e2e8f0;}
        </style>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap" rel="stylesheet">
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
                            <img loading="lazy" src="{{ p.image }}" alt="{{ p.title }}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                            <div class="placeholder" style="display:none;">No Image Available</div>
                        </div>
                        <div class="content">
                            <h2><a href="/{{ p.slug }}" rel="noopener">{{ p.title }}</a></h2>
                            <div class="meta">{{ p.category }} • {{ ago(p.pub_date) }}</div>
                            <p>{{ p.excerpt|safe }}</p>
                            <a href="/{{ p.slug }}" rel="noopener" class="readmore">Read Full Story →</a>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="card" style="grid-column:1/-1;text-align:center;padding:80px;">
                        <p style="font-size:24px;color:var(--primary);">No stories yet in this category — more coming soon!</p>
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
def post_detail(slug):
    post = Post.query.filter_by(slug=slug).first_or_404()
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
    page_desc = post.excerpt[:160]
    featured_img = post.image

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>{{ page_title }}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta name="description" content="{{ page_desc }}">
        <meta name="robots" content="index, follow">
        <link rel="canonical" href="https://blog.naijabuzz.com/{{ post.slug }}">
        <meta property="og:title" content="{{ page_title }}">
        <meta property="og:description" content="{{ page_desc }}">
        <meta property="og:image" content="{{ featured_img }}">
        <meta property="og:url" content="https://blog.naijabuzz.com/{{ post.slug }}">
        <meta property="og:type" content="article">
        <meta name="twitter:card" content="summary_large_image">
        <meta name="twitter:title" content="{{ page_title }}">
        <meta name="twitter:description" content="{{ page_desc }}">
        <meta name="twitter:image" content="{{ featured_img }}">
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "NewsArticle", "headline": "{{ post.title | e }}", "image": "{{ featured_img }}", "datePublished": "{{ post.pub_date.isoformat() }}", "publisher": {"@type": "Organization", "name": "NaijaBuzz"}}
        </script>
        <style>
            :root{--primary:#00d4aa;--dark:#0f172a;--light:#f8fafc;--gray:#64748b;}
            body{font-family:'Inter',system-ui,Arial,sans-serif;background:var(--light);margin:0;color:#1e293b;}
            header{background:var(--dark);color:white;text-align:center;padding:20px 16px;position:sticky;top:0;z-index:1000;box-shadow:0 4px 20px rgba(0,0,0,0.1);}
            h1{margin:0;font-size:32px;font-weight:900;}
            .tagline{font-size:16px;margin-top:8px;opacity:0.9;}
            .tabs-container{background:white;padding:12px 0;overflow-x:auto;position:sticky;top:80px;z-index:999;box-shadow:0 2px 10px rgba(0,0,0,0.08);}
            .tabs{display:flex;gap:10px;padding:0 16px;}
            .tab{padding:10px 20px;background:#e2e8f0;color:#334155;border-radius:30px;font-weight:600;font-size:14px;text-decoration:none;transition:0.3s;}
            .tab:hover,.tab.active{background:var(--primary);color:white;}
            .single-container{max-width:800px;margin:40px auto;padding:0 16px;}
            .single-img{width:100%;max-height:500px;object-fit:contain;border-radius:16px;margin-bottom:24px;}
            .single-meta{color:var(--primary);font-weight:700;margin-bottom:16px;}
            .single-content{line-height:1.7;color:#334155;}
            .source{margin-top:32px;color:var(--gray);font-style:italic;}
            .related{margin-top:64px;}
            .related h2{margin-bottom:24px;}
            .related-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:24px;}
            .related .card img{width:100%;height:150px;object-fit:cover;object-position:center;border-radius:12px 12px 0 0;}
            footer{text-align:center;padding:40px 20px;background:white;color:var(--gray);font-size:14px;border-top:1px solid #e2e8f0;}
        </style>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap" rel="stylesheet">
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
            <img loading="lazy" src="{{ post.image }}" alt="{{ post.title }}" class="single-img">
            <div class="single-content">{{ post.full_content | safe }}</div>
            <div class="source">Based on original from <a href="{{ post.link }}" target="_blank" rel="noopener nofollow">source</a>. AI-curated version.</div>
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
        <footer>© 2026 NaijaBuzz • blog.naijabuzz.com • Auto-updated every 15 minutes</footer>
    </body>
    </html>
    """
    return render_template_string(html, post=post, related=related, ago=ago, page_title=page_title, page_desc=page_desc, featured_img=featured_img, categories=CATEGORIES, selected=post.category.lower())

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
            print(f"Processing all {len(FEEDS)} feeds...")
            for cat, url in FEEDS:
                try:
                    f = feedparser.parse(url)
                    if not f.entries:
                        print(f"No entries from {url}")
                        continue
                    for e in f.entries[:6]:
                        h = hashlib.md5((e.link + e.title).encode()).hexdigest()
                        if Post.query.filter_by(unique_hash=h).first(): continue
                        img = get_image(e)
                        summary = e.get('summary') or e.get('description') or ''
                        excerpt = BeautifulSoup(summary, 'html.parser').get_text(separator=' ')[:360] + "..."
                        title = e.title
                        try:
                            article = Article(e.link)
                            article.download()
                            article.parse()
                            full_text = article.text
                        except Exception as ex:
                            print(f"Article fetch error: {ex}")
                            full_text = excerpt
                        full_content = rewrite_article(full_text, title, cat)
                        base_slug = slugify(title)
                        slug = base_slug
                        count = 1
                        while Post.query.filter_by(slug=slug).first():
                            slug = f"{base_slug}-{count}"
                            count += 1
                        post = Post(title=title, excerpt=excerpt, full_content=full_content, link=e.link, unique_hash=h,
                                    slug=slug, image=img, category=cat, pub_date=parse_date(getattr(e, 'published', None)))
                        db.session.add(post)
                        added += 1
                    db.session.commit()
                except Exception as ex:
                    print(f"Feed error {url}: {ex}")
    except Exception as ex:
        print(f"Cron error: {ex}")
    return f"NaijaBuzz updated! Added {added} new stories."

@app.route('/robots.txt')
def robots():
    return "User-agent: *\nAllow: /\nSitemap: https://blog.naijabuzz.com/sitemap.xml", 200, {'Content-Type': 'text/plain'}

@app.route('/sitemap.xml')
def sitemap():
    init_db()
    base_url = "https://blog.naijabuzz.com"
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += f'  <url>\n    <loc>{base_url}/</loc>\n    <changefreq>hourly</changefreq>\n    <priority>1.0</priority>\n  </url>\n'
    for key in CATEGORIES.keys():
        if key == 'all': continue
        cat_url = f"{base_url}/?cat={urllib.parse.quote(key)}"
        xml += f'  <url>\n    <loc>{cat_url}</loc>\n    <changefreq>daily</changefreq>\n    <priority>0.8</priority>\n  </url>\n'
    total_posts = Post.query.count()
    pages = (total_posts // 20) + 1 if total_posts else 1
    for p in range(1, pages + 1):
        xml += f'  <url>\n    <loc>{base_url}/?page={p}</loc>\n    <changefreq>daily</changefreq>\n    <priority>0.7</priority>\n  </url>\n'
    posts = Post.query.all()
    for post in posts:
        xml += f'  <url>\n    <loc>{base_url}/{post.slug}</loc>\n    <lastmod>{post.pub_date.isoformat()}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.9</priority>\n  </url>\n'
    xml += '</urlset>'
    return xml, 200, {'Content-Type': 'application/xml'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
