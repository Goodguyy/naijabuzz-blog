from flask import Flask, render_template_string
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
# Fix for Render Postgres URL
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300))
    excerpt = db.Column(db.Text)
    link = db.Column(db.String(500))
    category = db.Column(db.String(50))
    pub_date = db.Column(db.String(100))

# Create tables on first run
with app.app_context():
    db.create_all()

@app.route('/')
@app.route('/blog')
def blog():
    posts = Post.query.order_by(Post.pub_date.desc()).limit(30).all()
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>NaijaBuzz - Latest News & Gist</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body{font-family:Arial;background:#f4f4f4;padding:20px;max-width:800px;margin:auto;}
            .post{background:white;margin:15px 0;padding:20px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);}
            h1{color:#00d4aa;text-align:center;}
            a{color:#00d4aa;text-decoration:none;font-weight:bold;}
            small{color:#666;}
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
        <center><small>Powered by NaijaBuzz • Auto-updated every 4 hours</small></center>
    </body>
    </html>
    """
    return render_template_string(html, posts=posts)

if __name__ == '__main__':
    app.run(debug=True)
