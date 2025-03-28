import sqlite3
from datetime import datetime
import secrets
import string

DATABASE = 'utm_links.db'

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row  # This enables column access by name: row['column_name']
    return db

def init_db():
    db = get_db()
    try:
        with open('schema.sql', mode='r') as f:
            sql_script = f.read()
    except FileNotFoundError:
        print("Error: schema.sql not found!")
        return

    # Use a transaction to ensure atomicity
    with db:
        try:
            cursor = db.cursor()

            # Function to check if a table exists
            def table_exists(table_name):
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
                return cursor.fetchone() is not None

            # Function to get CREATE TABLE statement from schema
            def get_create_statement(table_name, script):
                statement = ""
                in_statement = False
                for line in script.splitlines():
                    stripped_line = line.strip().upper()
                    if stripped_line.startswith(f"CREATE TABLE {table_name.upper()}"):
                        in_statement = True
                    if in_statement:
                        statement += line + "\n" # Keep original line endings if needed
                        if line.strip().endswith(";"):
                            break # End of statement
                return statement.strip() if statement else None

            # Create 'links' table if it doesn't exist
            if not table_exists('links'):
                create_links_sql = get_create_statement('links', sql_script)
                if create_links_sql:
                    print("Creating table: links")
                    cursor.executescript(create_links_sql)
                else:
                    print("Warning: CREATE TABLE links statement not found in schema.sql")


            # Create 'clicks' table if it doesn't exist
            if not table_exists('clicks'):
                create_clicks_sql = get_create_statement('clicks', sql_script)
                if create_clicks_sql:
                    print("Creating table: clicks")
                    cursor.executescript(create_clicks_sql)
                else:
                    print("Warning: CREATE TABLE clicks statement not found in schema.sql")

            # You can add checks for other tables here if needed

            # No explicit commit needed here because 'with db:' handles it.
            # db.commit() # Removed - handled by 'with db:' context manager

        except sqlite3.Error as e:
            print(f"An error occurred during DB initialization: {e}")
            # Rollback is handled automatically by 'with db:' on error

class Link:
    def __init__(self, id, original_url, utm_source, utm_medium, utm_campaign, utm_term=None, utm_content=None, short_code=None, created_at=None):
        self.id = id
        self.original_url = original_url
        self.utm_source = utm_source
        self.utm_medium = utm_medium
        self.utm_campaign = utm_campaign
        self.utm_term = utm_term
        self.utm_content = utm_content
        self.short_code = short_code
        self.created_at = created_at

    @staticmethod
    def create(original_url, utm_source, utm_medium, utm_campaign, utm_term=None, utm_content=None):
        db = get_db()
        cursor = db.cursor()

        # Generate a unique short code
        while True:
            short_code = generate_short_code()
            cursor.execute("SELECT id FROM links WHERE short_code = ?", (short_code,))
            if not cursor.fetchone():
                break  # Short code is unique

        cursor.execute(
            "INSERT INTO links (original_url, utm_source, utm_medium, utm_campaign, utm_term, utm_content, short_code) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (original_url, utm_source, utm_medium, utm_campaign, utm_term, utm_content, short_code)
        )
        db.commit()
        link_id = cursor.lastrowid
        return Link.get(link_id)

    @staticmethod
    def get(link_id):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM links WHERE id = ?", (link_id,))
        row = cursor.fetchone()
        if row:
            return Link(row['id'], row['original_url'], row['utm_source'], row['utm_medium'], row['utm_campaign'], row['utm_term'], row['utm_content'], row['short_code'], row['created_at'])
        return None
    
    @staticmethod
    def get_by_short_code(short_code):
      db = get_db()
      cursor = db.cursor()
      cursor.execute("SELECT * FROM links WHERE short_code = ?", (short_code,))
      row = cursor.fetchone()
      if row:
          return Link(row['id'], row['original_url'], row['utm_source'], row['utm_medium'], row['utm_campaign'], row['utm_term'], row['utm_content'], row['short_code'], row['created_at'])
      return None

    @staticmethod
    def get_all():
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM links ORDER BY created_at DESC") # Order by newest first
        rows = cursor.fetchall()
        links = []
        for row in rows:
            links.append(Link(row['id'], row['original_url'], row['utm_source'], row['utm_medium'], row['utm_campaign'], row['utm_term'], row['utm_content'], row['short_code'], row['created_at']))
        return links
    
    @staticmethod
    def delete(link_id):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM links WHERE id = ?", (link_id,))
        db.commit()

    @staticmethod
    def update(link_id, data):
        # data is expected to be a dictionary-like object (e.g., request.form)
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """UPDATE links SET
                original_url = ?,
                utm_source = ?,
                utm_medium = ?,
                utm_campaign = ?,
                utm_term = ?,
                utm_content = ?
            WHERE id = ?""",
            (
                data.get('original_url', ''), # Use .get for safety
                data.get('utm_source', ''),
                data.get('utm_medium', ''),
                data.get('utm_campaign', ''),
                data.get('utm_term', None), # Allow None for optional fields
                data.get('utm_content', None),
                link_id
            )
        )
        db.commit()

    @staticmethod
    def get_filtered(campaign_filter=None, sort_by='created_at', sort_order='desc'):
        db = get_db()
        cursor = db.cursor()

        sql = "SELECT * FROM links" # <-- Select all columns directly from links
        params = []
        where_clauses = []

        if campaign_filter:
            where_clauses.append("utm_campaign LIKE ?")
            params.append(f'%{campaign_filter}%')

        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        # --- Sorting Logic (Simpler: No 'clicks' allowed for now) ---
        allowed_sort_columns = ['id', 'original_url', 'utm_source', 'utm_medium', 'utm_campaign', 'created_at', 'short_code']
        if sort_by not in allowed_sort_columns:
            sort_by = 'created_at'

        if sort_order is None or sort_order.lower() not in ['asc', 'desc']:
             validated_sort_order = 'DESC'
        else:
             validated_sort_order = 'ASC' if sort_order.lower() == 'asc' else 'DESC'

        sql += f" ORDER BY {sort_by} {validated_sort_order}"
        # --- End Sorting Logic ---

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # Convert rows back to Link objects here
        links = []
        for row in rows:
             links.append(Link(row['id'], row['original_url'], row['utm_source'], row['utm_medium'], row['utm_campaign'], row['utm_term'], row['utm_content'], row['short_code'], row['created_at']))
        return links # <-- Return list of Link objects again
    
    

    def to_dict(self):
        return {
            'id': self.id,
            'original_url': self.original_url,
            'utm_source': self.utm_source,
            'utm_medium': self.utm_medium,
            'utm_campaign': self.utm_campaign,
            'utm_term': self.utm_term,
            'utm_content': self.utm_content,
            'short_code' : self.short_code,
            'created_at': self.created_at
        }
    

class Click:
    def __init__(self, id, link_id, clicked_at):
        self.id = id
        self.link_id = link_id
        self.clicked_at = clicked_at

    @staticmethod
    def create(link_id):
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO clicks (link_id) VALUES (?)",
            (link_id,)
        )
        db.commit()
        click_id = cursor.lastrowid
        return Click.get(click_id)

    @staticmethod
    def get(click_id):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM clicks WHERE id = ?", (click_id,))
        row = cursor.fetchone()
        if row:
            return Click(row['id'], row['link_id'], row['clicked_at'])
        return None
    
    @staticmethod
    def count_for_link(link_id):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(id) FROM clicks WHERE link_id = ?", (link_id,))
        # fetchone()[0] gets the first column of the first row (the count)
        count = cursor.fetchone()[0]
        return count
    
    @staticmethod
    def delete_for_link(link_id):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM clicks WHERE link_id = ?", (link_id,))
        db.commit()

    def to_dict(self):
      return {
            'id': self.id,
            'link_id': self.link_id,
            'clicked_at': self.clicked_at
        }

def generate_short_code(length=6):
    """Generates a random short code."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))