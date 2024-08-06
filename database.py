import sqlite3

def init_db():
    conn = sqlite3.connect('website_data.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS page_text (
        id INTEGER PRIMARY KEY,
        url TEXT NOT NULL UNIQUE,
        text TEXT NOT NULL,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.commit()
    conn.close()

def save_page_text(url, text):
    conn = sqlite3.connect('website_data.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR REPLACE INTO page_text (url, text, last_updated) 
    VALUES (?, ?, CURRENT_TIMESTAMP)
    ''', (url, text))
    conn.commit()
    conn.close()

def get_page_text(url):
    conn = sqlite3.connect('website_data.db')
    cursor = conn.cursor()
    cursor.execute('''
    SELECT text FROM page_text WHERE url = ?
    ''', (url,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None