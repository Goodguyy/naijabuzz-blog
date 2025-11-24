from flask import Flask, render_template_string
from flask_sqlalchemy import SQLAlchemy
import os, feedparser, random
from datetime import datetime
from bs4 import BeautifulSoup

app = Flask(__name__)

# DB setup
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
    image = db.Column(db.String(500), default="https://i.ibb.co.com/0jR9Y3v/naijabuzz-logo.png")
    category = db.Column(db.String(50))
    pub_date = db.Column(db.String(100))

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    posts = Post.query.order_by(Post.pub_date.desc()).limit(40).all()
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>NaijaBuzz - Latest Naija News & Celebrity Gist</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta name="description" content="Fresh Naija news, BBNaija gist, celebrity updates from Linda Ikeji, Punch, BellaNaija — updated every few minutes!">
        <meta property="og:title" content="NaijaBuzz - Hottest Naija Gist">
        <meta property="og:description" content="Your #1 spot for fresh Nigerian news & celebrity gossip">
        <meta property="og:url" content="https://www.naijabuzz.com">
        <meta property="og:image" content="https://i.ibb.co.com/0jR9Y3v/naijabuzz-logo.png">
        <style>
            body{font-family:Arial;background:#f4f4f4;padding:15px;margin:0;}
            .container{max-width:800px;margin:auto;background:#fff;border-radius:15px;overflow:hidden;box-shadow:0 5px 20px rgba(0,0,0,0.1);}
            header{background:#00d4aa;color:white;text-align:center;padding:20px;}
            h1{margin:0;font-size:24px;}
            .post{margin:15px;padding:15px;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 3px 15px rgba(0,0,0,0.08);}
            .post img{width:100%;height:220px;object-fit:cover;border-radius:10px;}
            .post h2{font-size:19px;margin:12px 0;line-height:1.3;}
            .post h2 a{color:#333;text-decoration:none;font-weight:bold;}
            .post p{color:#555;font-size:15px;line-height:1.5;}
            .readmore{background:#00d4aa;color:white;padding:10px 18px;border:none;border-radius:8px;font-weight:bold;text-decoration:none;display:inline-block;margin-top:10px;}
            footer{text-align:center;padding:20px;color:#777;font-size:13px;}
        </style>
    </head>
    <body>
        <div class="container">
            <header><h1>NaijaBuzz - Fresh Gist & News</h1></header>
            {% if posts %}
                {% for p in posts %}
                <div class="post">
                    <img src="{{ p.image }}" alt="{{ p.title }}" onerror="this.src='https://i.ibb.co.com/0jR9Y3v/naijabuzz-logo.png'">
                    <h2><a href="{{ p.link }}" target="_blank">{{ p.title }}</a></h2>
                    <p><small><strong>{{ p.category }}</strong> • {{ p.pub_date[:16] }}</small></p>
                    <p>{{ p.excerpt }}</p>
                    <a href="{{ p.link }}" target="_blank" class="readmore">Read Full Story →</a>
                </div>
                {% endfor %}
            {% else %}
                <div class="post"><p style="text-align:center;padding:60px;font-size:19px;">
                    Loading the hottest Naija gist... Refresh in a minute! 
                </p></div>
            {% endif %}
            <footer>© 2025 NaijaBuzz • www.naijabuzz.com • Auto-updated every few minutes</footer>
        </div>
    </body>
    </html>
    """
    return render_template_string(html, posts=posts)

@app.route('/generate')
def generate():
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
            for e in f.entries[:12]:
                if Post.query.filter_by(link=e.link).first():
                    continue
                # Extract real image from HTML summary
                img = "https://i.ibb.co.com/0jR9Y3v/naijabuzz-logo.png"
                content = getattr(e, "summary", "") or getattr(e, "description", "")
                if content:
                    soup = BeautifulSoup(content, 'html.parser')
                    img_tag = soup.find('img')
                    if img_tag and img_tag.get('src'):
                        img = img_tag['src']
                        if img.startswith('//'): img = 'https:' + img
                title = random.choice(prefixes) + " " + e.title
                excerpt = (getattr(e, "summary", "")[:300] + "...").replace('<[^<]+?>', '') if hasattr(e, "summary") else "Click to read full gist..."
                pub_date = getattr(e, "published", datetime.now().isoformat())
                db.session.add(Post(title=title, excerpt=excerpt, link=e.link, image=img, category=cat, pub_date=pub_date))
                added += 1
        db.session.commit()
    return f"NaijaBuzz healthy! Added {added} fresh stories with real images."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
