from flask import Flask, render_template_string, request
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)

# Safe DB setup (works on Render free tier)
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
    title = db.Column(db.String(500))
    excerpt = db.Column(db.Text)
    link = db.Column(db.String(500), unique=True)
    category = db.Column(db.String(50))
    pub_date = db.Column(db.String(100))

with app.app_context():
    db.create_all()

# Homepage + SEO tags
@app.route('/')
@app.route('/blog')
def blog():
    posts = Post.query.order_by(Post.pub_date.desc()).limit(30).all()
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>NaijaBuzz - Latest Naija News & Celebrity Gist 2025</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta name="description" content="Fresh Naija news, celebrity gossip, BBNaija updates & trending gist from Linda Ikeji, Punch, Vanguard – updated every 4 hours!">
        <meta name="keywords" content="Naija news, Nigeria gossip, celebrity gist, BBNaija 2025, Linda Ikeji blog, latest Nigeria news">
        <meta name="robots" content="index, follow">
        <link rel="canonical" href="https://naijabuzz-live.onrender.com">
        
        <!-- Open Graph / Social Share -->
        <meta property="og:title" content="NaijaBuzz - Latest Naija News & Celebrity Gist">
        <meta property="og:description" content="Fresh Naija gist updated every 4 hours!">
        <meta property="og:url" content="https://naijabuzz-live.onrender.com">
        <meta property="og:type" content="website">
        <meta property="og:image" content="https://i.ibb.co.com/9bYdR1v/naijabuzz-og.jpg">
        
        <!-- Twitter Card -->
        <meta name="twitter:card" content="summary_large_image">
        <meta name="twitter:title" content="NaijaBuzz - Latest Naija News & Gist">
        <meta name="twitter:description" content="Fresh Naija gist every 4 hours!">
        <meta name="twitter:image" content="https://i.ibb.co.com/9bYdR1v/naijabuzz-og.jpg">

        <!-- Schema.org Blog Markup -->
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Blog",
          "name": "NaijaBuzz",
          "url": "https://naijabuzz-live.onrender.com",
          "description": "Latest Naija news and celebrity gossip updated every 4 hours"
        }
        </script>

        <style>
            body{font-family:Arial;background:#f4f4f4;padding:20px;max-width:800px;margin:auto;}
            .post{background:white;margin:15px 0;padding:20px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);}
            h1{color:#00d4aa;text-align:center;}
            a{color:#00d4aa;text-decoration:none;font-weight:bold;}
        </style>
    </head>
    <body>
        <h1>NaijaBuzz - Fresh Gist & News Every 4 Hours</h1>
        {% for p in posts %}
        <div class="post">
            <h2><a href="{{ p.link }}" target="_blank">{{ p.title }}</a></h2>
            <p><small>{{ p.category }} • {{ p.pub_date[:16] }}</small></p>
            <p>{{ p.excerpt }} <a href="{{ p.link }}">Read more</a></p>
        </div>
        {% endfor %}
        {% if not posts %}<p>No gist yet — refreshing in a minute!</p>{% endif %}
        <center><small>© 2025 NaijaBuzz • Auto-updated every 4 hours</small></center>
    </body>
    </html>
    """
    return render_template_string(html, posts=posts)

# Sitemap.xml
@app.route('/sitemap.xml')
def sitemap():
    posts = Post.query.all()
    xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    xml += '<url><loc>https://naijabuzz-live.onrender.com</loc><changefreq>hourly</changefreq></url>'
    for p in posts:
        xml += f'<url><loc>{p.link}</loc><lastmod>{p.pub_date[:10]}</lastmod></url>'
    xml += '</urlset>'
    return xml, 200, {'Content-Type': 'application/xml'}

# Robots.txt
@app.route('/robots.txt')
def robots():
    return "User-agent: *\nAllow: /\nSitemap: https://naijabuzz-live.onrender.com/sitemap.xml"

# Generator route (for UptimeRobot)
@app.route('/generate')
def generate():
    import feedparser, random
    from datetime import datetime
    feeds = [
        ("News", "https://punchng.com/feed/"),
        ("News", "https://vanguardngr.com/feed"),
        ("News", "https://premiumtimesng.com/feed"),
        ("Gossip", "https://lindaikeji.blogspot.com/feeds/posts/default"),
        ("Gossip", "https://bellanaija.com/feed/"),
    ]
    prefixes = ["Na Wa O!", "Gist Alert:", "You Won’t Believe:", "Naija Gist:", "Breaking:", "Omo!", "Chai!"]
    added = 0
    with app.app_context():
        for cat, url in feeds:
            f = feedparser.parse(url)
            for e in f.entries[:8]:
                if Post.query.filter_by(link=e.link).first():
                    continue
                title = random.choice(prefixes) + " " + e.title
                excerpt = (e.summary[:250] + "...") if hasattr(e, "summary") else "Click to read..."
                pub_date = e.published if hasattr(e, "published") else datetime.now().isoformat()
                db.session.add(Post(title=title, excerpt=excerpt, link=e.link, category=cat, pub_date=pub_date))
                added += 1
        db.session.commit()
    return f"Added {added} fresh Naija stories! Blog updated."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
