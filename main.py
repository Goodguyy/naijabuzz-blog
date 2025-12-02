# main.py - NaijaBuzz 2025 FINAL (Website Only)
from flask import Flask, render_template_string, request
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime
from dateutil import parser as date_parser

app = Flask(__name__)

db_uri = os.environ.get('DATABASE_URL') or 'sqlite:///posts.db'
if db_uri.startswith('postgres://'):
    db_uri = db_uri.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(600))
    excerpt = db.Column(db.Text)
    link = db.Column(db.String(600), unique=True)
    image = db.Column(db.String(800), default="https://via.placeholder.com/800x500/0f172a/f8fafc?text=NaijaBuzz")
    category = db.Column(db.String(100))
    pub_date = db.Column(db.String(100))

# CREATE TABLE ON STARTUP
with app.app_context():
    db.create_all()

CATEGORIES = {
    "all": "All News", "naija news": "Naija News", "gossip": "Gossip", "football": "Football",
    "sports": "Sports", "entertainment": "Entertainment", "lifestyle": "Lifestyle",
    "education": "Education", "tech": "Tech", "viral": "Viral", "world": "World"
}

def time_ago(date_str):
    if not date_str: return "Just now"
    try:
        dt = date_parser.parse(date_str)
        now = datetime.now()
        diff = now - dt
        if diff.days >= 30: return dt.strftime("%b %d")
        elif diff.days >= 1: return f"{diff.days}d ago"
        elif diff.seconds >= 7200: return f"{diff.seconds//3600}h ago"
        elif diff.seconds >= 3600: return "1h ago"
        elif diff.seconds >= 120: return f"{diff.seconds//60}m ago"
        else: return "Just now"
    except:
        return "Recently"

app.jinja_env.filters['time_ago'] = time_ago

@app.route('/')
def index():
    selected = request.args.get('cat', 'all').lower()
    if selected == 'all':
        posts = Post.query.order_by(Post.pub_date.desc()).limit(90).all()
    else:
        posts = Post.query.filter(Post.category.ilike(selected)).order_by(Post.pub_date.desc()).limit(90).all()
    return render_template_string(HTML, posts=posts, categories=CATEGORIES, selected=selected)

HTML = '''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NaijaBuzz - Nigeria Youth News, BBNaija, Football, Music & Gist</title>
<meta name="description" content="Latest Naija youth news, BBNaija, Afrobeats, Premier League, Yahoo gist, Crypto, Fashion, Campus — updated every 5 mins!">
<link rel="canonical" href="https://blog.naijabuzz.com">
<style>
    :root{--bg:#0a0a0a;--card:#111;--text:#e0e0e0;--accent:#00ff9d;--accent2:#00d4aa;}
    *{margin:0;padding:0;box-sizing:border-box;}
    body{font-family:'Segoe UI',sans-serif;background:var(--bg);color:var(--text);line-height:1.6;}
    header{background:var(--card);padding:1.5rem;text-align:center;box-shadow:0 4px 20px rgba(0,255,157,0.1);}
    h1{font-size:2.6rem;background:linear-gradient(90deg,#00ff9d,#00d4aa);-webkit-background-clip:text;color:transparent;font-weight:900;}
    .tagline{font-size:1.1rem;color:#00ff9d;font-weight:600;}
    .nav{position:sticky;top:0;z-index:100;background:var(--card);padding:1rem 0;overflow-x:auto;box-shadow:0 4px 20px rgba(0,255,157,0.2);}
    .nav-inner{max-width:1400px;margin:0 auto;display:flex;gap:12px;padding:0 1rem;flex-wrap:nowrap;}
    .nav a{padding:12px 24px;background:var(--bg);color:var(--text);border-radius:50px;font-weight:700;text-decoration:none;transition:0.3s;white-space:nowrap;}
    .nav a:hover,.nav a.active{background:var(--accent);color:#000;}
    .container{max-width:1400px;margin:2rem auto;padding:0 1rem;}
    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:1.8rem;}
    .card{background:var(--card);border-radius:16px;overflow:hidden;box-shadow:0 10px 30px rgba(0,255,157,0.1);transition:0.4s;}
    .card:hover{transform:translateY(-12px);box-shadow:0 20px 40px rgba(0,255,157,0.2);}
    .card img{width:100%;height:220px;object-fit:cover;}
    .card-content{padding:1.5rem;}
    .card h2{font-size:1.35rem;line-height:1.3;margin:0.8rem 0;}
    .card h2 a{color:var(--text);text-decoration:none;font-weight:700;}
    .card h2 a:hover{color:var(--accent);}
    .meta{font-size:0.85rem;color:var(--accent);font-weight:700;text-transform:uppercase;margin-bottom:0.5rem;}
    .time{font-size:0.8rem;color:#888;margin-bottom:0.8rem;}
    .readmore{display:inline-block;margin-top:1rem;padding:10px 22px;background:var(--accent);color:#000;font-weight:bold;border-radius:50px;transition:0.3s;}
    .readmore:hover{background:var(--accent2);transform:scale(1.05);}
    .placeholder{height:220px;background:linear-gradient(45deg,#111,#222);display:flex;align-items:center;justify-content:center;color:#555;}
    footer{text-align:center;padding:3rem;color:#666;background:var(--card);}
</style></head><body>
<header><h1>NaijaBuzz</h1><div class="tagline">No.1 Naija Youth Gist • BBN • Football • Music • Crypto • Fashion</div></header>
<div class="nav"><div class="nav-inner">
{% for k, v in categories.items() %}
<a href="?cat={{k}}" class="{{'active' if selected==k else ''}}">{{v}}</a>
{% endfor %}
</div></div>
<div class="container"><div class="grid">
{% for p in posts %}
<div class="card">
<a href="{{p.link}}" target="_blank">
{% if 'placeholder.com' in p.image %}
<div class="placeholder"><div>NaijaBuzz</div></div>
{% else %}
<img src="{{p.image}}" alt="{{p.title}}" loading="lazy">
{% endif %}
</a>
<div class="card-content">
<div class="meta">{{p.category.upper()}}</div>
<h2><a href="{{p.link}}" target="_blank">{{p.title}}</a></h2>
<div class="time">{{p.pub_date|time_ago}}</div>
<p>{{p.excerpt}}</p>
<a href="{{p.link}}" target="_blank" class="readmore">Read Full Gist →</a>
</div>
</div>
{% endfor %}
</div></div>
<footer>© 2025 NaijaBuzz • Made for the Youths • Updated LIVE</footer>
</body></html>'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
