from flask import g
import sqlite3
import sqlite3
from datetime import datetime
import secrets
import string
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = 'utm_links.db'

def get_db():
    # 4 spaces indent start
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, timeout=10)
        db.row_factory = sqlite3.Row
        print("--- New DB Connection Created ---") # Optional debug
    return db

def init_db():
    db = get_db()
    try:
        with open('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()
        print("Database initialized successfully from schema.sql") # Added simple confirmation
    except Exception as e:
        print(f"ERROR initializing database: {e}")
    finally:
        if db:
            db.close()

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
    def create(original_url, utm_source, utm_medium, utm_campaign, utm_term=None, utm_content=None, user_id=None):
        if user_id is None:
            print("ERROR: user_id is required to create a link.")
            return None

        db = get_db()
        cursor = db.cursor()
        short_code = None # Initialize short_code

        # Generate a unique short code
        while True:
            short_code = generate_short_code()
            cursor.execute("SELECT id FROM links WHERE short_code = ?", (short_code,))
            if not cursor.fetchone():
                break

        try:
            cursor.execute(
                "INSERT INTO links (original_url, utm_source, utm_medium, utm_campaign, utm_term, utm_content, short_code, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (original_url, utm_source, utm_medium, utm_campaign, utm_term, utm_content, short_code, user_id)
            )
            # --- Add this line! ---
            db.commit()
            # ----------------------
            link_id = cursor.lastrowid
            print(f"Link created successfully with ID: {link_id}") # Optional debug
            return link_id
        except sqlite3.IntegrityError as e:
             # Handle potential errors like duplicate short_code if the while loop fails somehow
             print(f"Database Integrity Error during Link.create INSERT: {e}")
             db.rollback() # Rollback the transaction on error
             return None
        except sqlite3.Error as e:
             # Handle other potential SQLite errors
             print(f"Database Error during Link.create INSERT: {e}")
             db.rollback()
             return None

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

# Inside class Link:

    @staticmethod
    def get_filtered(campaign_filter=None, sort_by='created_at', sort_order='desc', user_id=None):
        # --- Start of function body (4 spaces indent) ---
        db = get_db()
        cursor = db.cursor()

        # Base query with LEFT JOIN to count clicks
        sql = """
            SELECT
                links.id, links.original_url, links.utm_source, links.utm_medium,
                links.utm_campaign, links.utm_term, links.utm_content,
                links.short_code, links.created_at, links.user_id,
                COUNT(clicks.id) as click_count
            FROM links
            LEFT JOIN clicks ON links.id = clicks.link_id
        """
        params = []
        where_clauses = []

        # Add user_id filter FIRST if provided
        if user_id is not None:
            where_clauses.append("links.user_id = ?")
            params.append(user_id)

        # Add campaign filter if provided
        if campaign_filter:
            where_clauses.append("links.utm_campaign LIKE ?")
            params.append(f'%{campaign_filter}%')

        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        # GROUP BY clause
        sql += """
            GROUP BY links.id, links.original_url, links.utm_source, links.utm_medium,
                     links.utm_campaign, links.utm_term, links.utm_content,
                     links.short_code, links.created_at, links.user_id
        """

        # --- Sorting Logic ---
        allowed_sort_columns = ['id', 'original_url', 'utm_source', 'utm_medium', 'utm_campaign', 'created_at', 'short_code', 'click_count']
        if sort_by not in allowed_sort_columns:
            sort_by = 'created_at'

        order_by_column = 'click_count' if sort_by == 'click_count' else f'links.{sort_by}'

        # Validate sort_order parameter
        if sort_order is None or sort_order.lower() not in ['asc', 'desc']:
             validated_sort_order = 'DESC' # Default to DESC
        else:
             validated_sort_order = 'ASC' if sort_order.lower() == 'asc' else 'DESC'


        # Add ORDER BY clause dynamically (using validated values)
        sql += f" ORDER BY {order_by_column} {validated_sort_order}"
        # --- End Sorting Logic ---

        cursor.execute(sql, params)
        rows = cursor.fetchall() # Return rows directly
        return rows
        # --- End of function body ---
    
    

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
    
class User(UserMixin):
    def __init__(self, id, username, email, password_hash):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash

    # Methods required by Flask-Login are provided by UserMixin
    # (is_authenticated, is_active, is_anonymous, get_id)

    def set_password(self, password):
        """Creates hashed password."""
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        """Checks submitted password against stored hash."""
        return check_password_hash(self.password_hash, password)

    # --- Static methods to interact with the database ---
    @staticmethod
    def create(username, email, password):
        db = get_db()
        cursor = db.cursor()
        # Check if username or email already exists (optional but recommended)
        cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
        if cursor.fetchone():
            # Handle case where user already exists (e.g., raise an error or return None)
            print(f"Warning: Username '{username}' or Email '{email}' already exists.")
            return None # Or raise a custom exception

        # Create user if not exists
        password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        try:
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, password_hash)
            )
            db.commit()
            user_id = cursor.lastrowid
            print(f"User created with ID: {user_id}") # Debug print
            return User.get_by_id(user_id)
        except sqlite3.IntegrityError as e:
             print(f"Database integrity error (maybe unique constraint?): {e}")
             return None # Or handle differently
        except Exception as e:
             print(f"Error creating user: {e}")
             return None


    @staticmethod
    def get_by_username(username):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if row:
            return User(row['id'], row['username'], row['email'], row['password_hash'])
        return None

    @staticmethod
    def get_by_email(email): # Good for checking duplicates or password resets
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        if row:
            return User(row['id'], row['username'], row['email'], row['password_hash'])
        return None

    @staticmethod
    def get_by_id(user_id):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return User(row['id'], row['username'], row['email'], row['password_hash'])
        return None

def generate_short_code(length=6):
    """Generates a random short code."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))



