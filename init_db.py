# init_db.py - RUN THIS ONCE TO CREATE THE DATABASE TABLE
from main import app, db
import os

if __name__ == "__main__":
    with app.app_context():
        print("Creating database table...")
        db.create_all()
        print("Database table 'post' created successfully!")
        print("You can now delete this file if you want.")
