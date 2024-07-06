import sqlite3

def init_db():
    conn = sqlite3.connect('website_data.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS website_text (
        id INTEGER PRIMARY KEY,
        url TEXT NOT NULL,
        text TEXT NOT NULL
    )
    ''')
    conn.commit()
    conn.close()

def save_website_text(url, text):
    conn = sqlite3.connect('website_data.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO website_text (url, text) VALUES (?, ?)
    ''', (url, text))
    conn.commit()
    conn.close()

def get_website_text(url):
    conn = sqlite3.connect('website_data.db')
    cursor = conn.cursor()
    cursor.execute('''
    SELECT text FROM website_text WHERE url = ?
    ''', (url,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None
