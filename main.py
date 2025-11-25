from flask import Flask, render_template_string
from flask_sqlalchemy import SQLAlchemy
import os, feedparser, random
from datetime import datetime
from bs4 import BeautifulSoup
from openai import OpenAI

app = Flask(__name__)

# OpenAI — NEW VERSION (no crash)
openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY')) if os.environ.get('OPENAI_API_KEY') else None

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
    image = db.Column(db.String(600), default="https://via.placeholder.com/800x450/00d4aa/ffffff?text=NaijaBuzz+Image")
    category = db.Column(db.String(100))
    pub_date = db.Column(db.String(100))

with app.app_context():
    db.create_all()

def generate_ai_image(topic):
    if not openai_client:
        return "https://via.placeholder.com/800x450/00d4aa/ffffff?text=NaijaBuzz+Image"
    try:
        response = openai_client.images.generate(
            model="dall-e-3",
            prompt=f"Realistic Nigerian news illustration: {topic}, dramatic, high quality, no text, 16:9",
            size="1024x576",
            n=1
        )
        return response.data[0].url
    except:
        return "https://via.placeholder.com/800x450/00d4aa/ffffff?text=NaijaBuzz+Image"

@app.route('/')
def index():
    posts = Post.query.order_by(Post.pub_date.desc()).limit(90).all()
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>NaijaBuzz - Nigeria News, Football, Gossip & World Updates</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body{font-family:'Segoe UI',Arial,sans-serif;background:#f0f2f5;margin:0;padding:10px;}
            header{background:#00d4aa;color:white;text-align:center;padding:25px;border-radius:15px;margin:15px auto;max-width:1400px;}
            h1{margin:0;font-size:32px;font-weight:bold;}
            .subtitle{color:#e8fff9;font-size:18px;}
            .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:28 воpx;max-width:1400px;margin:30px auto;padding:0 15px;}
            .card{background:white;border-radius:18px;overflow:hidden;box-shadow:0 8px 25px rgba(0,0,0,0.12);transition:0.3s;}
            .: hover{transform:translateY(-10px);box-shadow:0 20px 40px rgba(0,0,0,0.18);}
            .card img{width:100%;height:240px;object-fit:cover;border-radius:18px 18px 0 0;}
            .content{padding:20px;}
            .card h2{font-size:20px;line-height:1.3;margin:0 0 12px 0;}
            .card h2 a{color:#1a1a1a;text-decoration:none;font-weight:bold;}
            .card h2 a:hover{color:#00d4aa;}
            .meta{font-size:14px;color:#00d4aa;font-weight:bold;margin-bottom:10px;}
            .card p{color:#444;font-size:16px;line-height:1.5;margin:0 0 15px 0;}
            .readmore{background:#00d4aa;color:white;padding:12px 20px;border-radius:12px;text-decoration:none;font-weight:bold;display:inline-block;}
            footer{text-align:center;padding:50px;color:#666;font-size:15px;}
            @media(max-width:1024px){.grid{grid-template-columns:repeat(2,1fr);}}
            @media(max-width:600px){.grid{grid-template-columns:repeat(2,1fr);gap:20px;}}
            @media(max-width:480px){.grid{grid-template-columns:1fr;}}
        </style>
    </head>
    <body>
        <header>
            <h1>NaijaBuzz</h1>
            <div class="subtitle">Fresh Naija News • Football • Gossip • World Updates</div>
        </header>
        <div class="grid">
            {% if posts %}
                {% for p in posts %}
                <div class="card">
                    <img src="{{ p.image }}" alt="{{ p.title }}" onerror="this.src='https://via.placeholder.com/800x450/00d4aa/ffffff?text=NaijaBuzz+Image'">
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
                    Loading the hottest Naija gist... Refresh in a minute!
                </p></div>
            {% endif %}
        </div>
        <footer>© 2025 NaijaBuzz • www.naijabuzz.com • Auto-updated every few minutes</footer>
    </body>
    </html>
    """
    return render_template_string(html, posts=posts)

@app.route('/generate')
def generate():
    feeds = [
        ("Naija News", "https://punchng.com/feed/"),
        ("Naija News", "https://vanguardngr.com/feed"),
        ("Naija News", "https://premiumtimesng.com/feed"),
        ("Gossip", "https://lindaikeji.blogspot.com/feeds/posts/default"),
        ("Gossip", "https://bellanaija.com/feed/"),
        ("Football", "https://www.goal.com/en-ng/feeds/news"),
        ("Sports", "https://www.completesports.com/feed/"),
        ("World", "https://bbc.com/news/world/rss.xml"),
        ("Tech", "https://techcabal.com/feed/"),
        ("Viral", "https://legit.ng/rss"),
        ("Entertainment", "https://pulse.ng/rss"),
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
                    img = "https://via.placeholder.com/800x450/00d4aa/ffffff?text=NaijaBuzz+Image"
                    content = getattr(e, "summary", "") or getattr(e, "description", "") or ""
                    if content:
                        soup = BeautifulSoup(content, 'html.parser')
                        img_tag = soup.find('img')
                        if img_tag and img_tag.get('src'):
                            img = img_tag['src']
                            if img.startswith('//'): img = 'https:' + img
                    if "placeholder.com" in img and openai_client:
                        ai_img = generate_ai_image(e.title)
                        if ai_img: img = ai_img
                    title = random.choice(prefixes) + " " + e.title
                    excerpt = BeautifulSoup(content, 'html.parser').get_text()[:340] + "..."
                    pub_date = getattr(e, "published", datetime.now().isoformat())
                    db.session.add(Post(title=title, excerpt=excerpt, link=e.link, image=img, category=cat, pub_date=pub_date))
                    added += 1
            except: continue
        db.session.commit()
    return f"NaijaBuzz healthy! Added {added} stories with real + AI images!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
