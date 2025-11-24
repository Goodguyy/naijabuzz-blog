from flask import Flask, render_template_string, request
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)

# Safe DB setup
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

@app.route('/')
@app.route('/blog')
def blog():
    posts = Post.query.order_by(Post.pub_date.desc()).limit(50).all()  # Show up to 50
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>NaijaBuzz - Latest Naija News & Celebrity Gist</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta name="description" content="Fresh Naija news, BBNaija gist, celebrity updates from Linda Ikeji, Punch, BellaNaija — updated every few minutes!">
        <meta property="og:title" content="NaijaBuzz - Latest Naija Gist">
        <meta property="og:description" content="Your #1 spot for fresh Nigerian news & celebrity gossip">
        <meta property="og:url" content="https://naijabuzz-live.onrender.com">
        <meta property="og:image" content="https://i.ibb.co.com/9bYdR1v/naijabuzz-og.jpg">
        <style>
            body{font-family:Arial;background:#f4f4f4;padding:20px;max-width:800px;margin:auto;}
            .post{background:white;margin:15px 0;padding:20px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);}
            h1{color:#00d4aa;text-align:center;}
            a{color:#00d4aa;text-decoration:none;font-weight:bold;}
        </style>
    </head>
    <body>
        <h1>NaijaBuzz - Fresh Gist & News</h1>
        {% if posts %}
            {% for p in posts %}
            <div class="post">
                <h2><a href="{{ p.link }}" target="_blank">{{ p.title }}</a></h2>
                <p><small>{{ p.category }} • {{ p.pub_date[:16] }}</small></p>
                <p>{{ p.excerpt }} <a href="{{ p.link }}">Read more →</a></p>
            </div>
            {% endfor %}
        {% else %}
            <p style="text-align:center;padding:50px;font-size:18px;">
                Loading fresh Naija gist... Check back in a minute! 🔥
            </p>
        {% endif %}
        <center><small>© 2025 NaijaBuzz • Auto-updated every few minutes</small></center>
    </body>
    </html>
    """
    return render_template_string(html, posts=posts)

# This route pulls new stories (UptimeRobot hits this)
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
            for e in f.entries[:10]:
                if Post.query.filter_by(link=e.link).first():
                    continue
                title = random.choice(prefixes) + " " + e.title
                excerpt = (e.summary[:250] + "...") if hasattr(e, "summary") else "Click to read full gist..."
                pub_date = e.published if hasattr(e, "published") else datetime.now().isoformat()
                db.session.add(Post(title=title, excerpt=excerpt, link=e.link, category=cat, pub_date=pub_date))
                added += 1
        db.session.commit()
    return f"NaijaBuzz is healthy! Added {added} new stories. Old ones stay forever."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
