# generate.py - THE ONLY SCRIPT THAT ADDS NEWS (RUN THIS EVERY 5 MINS)
import feedparser, random, os, sys
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import app, db, Post
from dateutil import parser as date_parser
from bs4 import BeautifulSoup

# 35+ UNBLOCKABLE SOURCES — GOOGLE NEWS RSS (NEVER BLOCKED!)
FEEDS = [
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:punchng.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:vanguardngr.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:premiumtimesng.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:thenationonlineng.net&hl=en-NG&gl=NG&ceid=NG:en"),
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:dailypost.ng&hl=en-NG&gl=NG&ceid=NG:en"),
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:saharareporters.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:thecable.ng&hl=en-NG&gl=NG&ceid=NG:en"),
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:thisdaylive.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("gossip", "https://news.google.com/rss/search?q=when:24h+site:lindaikejisblog.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("gossip", "https://news.google.com/rss/search?q=when:24h+site:bellanaija.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("gossip", "https://news.google.com/rss/search?q=when:24h+site:gistlover.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("football", "https://news.google.com/rss/search?q=when:24h+super+eagles+OR+premier+league+nigeria&hl=en-NG&gl=NG&ceid=NG:en"),
    ("football", "https://news.google.com/rss/search?q=when:24h+site:goal.com+nigeria&hl=en-NG&gl=NG&ceid=NG:en"),
    ("sports", "https://news.google.com/rss/search?q=when:24h+afcon+OR+nigeria+sports&hl=en-NG&gl=NG&ceid=NG:en"),
    ("sports", "https://news.google.com/rss/search?q=when:24h+site:completesports.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("entertainment", "https://news.google.com/rss/search?q=when:24h+bbnaija+OR+nollywood&hl=en-NG&gl=NG&ceid=NG:en"),
    ("entertainment", "https://news.google.com/rss/search?q=when:24h+site:pulse.ng&hl=en-NG&gl=NG&ceid=NG:en"),
    ("viral", "https://news.google.com/rss/search?q=when:24h+site:legit.ng&hl=en-NG&gl=NG&ceid=NG:en"),
    ("tech", "https://news.google.com/rss/search?q=when:24h+site:techcabal.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("world", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"),
    ("lifestyle", "https://news.google.com/rss/search?q=when:24h+fashion+OR+wedding+nigeria&hl=en-NG&gl=NG&ceid=NG:en"),
    ("education", "https://news.google.com/rss/search?q=when:24h+jamb+OR+waec+OR+university+nigeria&hl=en-NG&gl=NG&ceid=NG:en"),
    # 13 more top sources
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:guardian.ng&hl=en-NG&gl=NG&ceid=NG:en"),
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:tribuneonlineng.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("entertainment", "https://news.google.com/rss/search?q=when:24h+site:notjustok.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("sports", "https://news.google.com/rss/search?q=when:24h+site:allnigeriasoccer.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:leadership.ng&hl=en-NG&gl=NG&ceid=NG:en"),
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:pmnewsnigeria.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:independent.ng&hl=en-NG&gl=NG&ceid=NG:en"),
    ("naija news", "https://news.google.com/rss/search?q=when:24h+site:naijanews.com&hl=en-NG&gl=NG&ceid=NG:en"),
    ("entertainment", "https://news.google.com/rss/search?q=when:24h+site:thenet.ng&hl=en-NG&gl=NG&ceid=NG:en"),
    ("lifestyle", "https://news.google.com/rss/search?q=when:24h+site:sisiyemmie.com&hl=en-NG&gl=NG&ceid=NG:en"),
]

def extract_image(entry):
    if hasattr(entry, 'media_content'):
        for m in entry.media_content:
            url = m.get('url')
            if url and url.startswith('http'):
                return url
    if hasattr(entry, 'enclosures'):
        for e in entry.enclosures:
            if e.url and e.url.startswith('http'):
                return e.url
    return "https://via.placeholder.com/800x500/0f172a/f8fafc?text=NaijaBuzz"

def run():
    prefixes = ["Na Wa O!", "Gist Alert:", "You Won't Believe:", "Naija Gist:", "Breaking:", "Omo!", "Chai!", "E Don Happen!"]
    added = 0
    with app.app_context():
        random.shuffle(FEEDS)
        for cat, url in FEEDS:
            try:
                f = feedparser.parse(url)
                for e in f.entries[:15]:
                    if not e.link or Post.query.filter_by(link=e.link).first():
                        continue
                    image = extract_image(e)
                    title = random.choice(prefixes) + " " + BeautifulSoup(e.title, 'html.parser').get_text()
                    excerpt = BeautifulSoup(e.summary or "", 'html.parser').get_text()[:340] + "..."
                    pub_date = e.published if 'published' in e else datetime.now().isoformat()
                    db.session.add(Post(title=title, excerpt=excerpt, link=e.link,
                                      image=image, category=cat, pub_date=pub_date))
                    added += 1
            except Exception as e:
                continue
        if added:
            db.session.commit()
        print(f"NaijaBuzz UPDATED! Added {added} fresh stories!")

if __name__ == "__main__":
    run()
