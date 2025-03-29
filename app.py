
from flask import Flask, render_template, request, redirect, url_for, flash, g
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from forms import RegistrationForm, LoginForm
from models import Link, Click, User, init_db, get_db
import urllib.parse
import qrcode
from io import BytesIO
import base64


app = Flask(__name__)

# --- Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Name of the function for our login route (we'll create it later)
login_manager.login_message = "Please log in to access this page." # Optional message
login_manager.login_message_category = "info" # Optional: category for flash message styling
# -------------------------

app.config['SECRET_KEY'] = 'c>CJ`Ni$/lpx4"r'  # Replace with a strong secret key!

# Initialize the database (create tables if they don't exist)
#with app.app_context():
#init_db()


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login callback to load a user from the database."""
    try:
        # user_id stored in the session is a string, convert to int
        return User.get_by_id(int(user_id))
    except ValueError:
        # Handle cases where user_id is not a valid integer
        return None
    except Exception as e:
        # Handle other potential errors during user loading
        print(f"Error loading user {user_id}: {e}")
        return None


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    utm_link = None
    short_link = None # added
    # Inside the index() function
    if request.method == "POST":
        website_url = request.form["website_url"]
        utm_source = request.form["utm_source"]
        utm_medium = request.form["utm_medium"]
        utm_campaign = request.form["utm_campaign"]
        utm_term = request.form.get("utm_term")
        utm_content = request.form.get("utm_content")

        utm_params = {}
        # ... (code to build utm_params - keep as is) ...
        if utm_source: utm_params["utm_source"] = utm_source
        if utm_medium: utm_params["utm_medium"] = utm_medium
        if utm_campaign: utm_params["utm_campaign"] = utm_campaign
        if utm_term: utm_params["utm_term"] = utm_term
        if utm_content: utm_params["utm_content"] = utm_content

        utm_link = None # Initialize here
        if utm_params:
            # ... (code to build the full utm_link string - keep as is) ...
            try:
                url_parts = list(urllib.parse.urlparse(website_url))
                query = dict(urllib.parse.parse_qsl(url_parts[4]))
                query.update(utm_params)
                url_parts[4] = urllib.parse.urlencode(query)
                utm_link = urllib.parse.urlunparse(url_parts)
            except Exception as e:
                print(f"Error building UTM link string: {e}")
                # Decide how to handle this - maybe flash a warning?
                # For now, utm_link will remain None if building fails

        # --- Database interaction ---
        link_id = Link.create(
            original_url=website_url,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            utm_term=utm_term,
            utm_content=utm_content,
            user_id=current_user.id
        )

        short_link = None # Initialize short_link to None

        if link_id:
             link = Link.get(link_id)
             if link:
                 # --- Move this line INSIDE the 'if link:' block ---
                 short_link = url_for('redirect_to_original', short_code=link.short_code, _external=True)
                 # Optionally flash success message here if desired
                 # flash('Link created successfully!', 'success')
             else:
                  flash('Error: Could not retrieve link details after creation.', 'danger')
                  # link is None, short_link remains None
        else:
             flash('Error: Failed to create link in database.', 'danger')
             # link_id is None, short_link remains None

        # Render the template, passing potentially None values if creation/retrieval failed
        return render_template("form.html", utm_link=utm_link, short_link=short_link)

    # --- End of POST request handling ---

    # If GET request:
    return render_template("form.html", utm_link=None, short_link=None)




@app.route('/s/<short_code>')
def redirect_to_original(short_code):
    link = Link.get_by_short_code(short_code)
    if link:
        # Log the click
        Click.create(link.id)  # Create a new click record

        return redirect(link.original_url)
    else:
        return "Short link not found", 404
    

# app.py

@app.route('/stats')
@login_required # Ensures only logged-in users access this
def show_stats():
    # Get filter and sort parameters from URL
    campaign_filter = request.args.get('campaign_filter', '')
    sort_by = request.args.get('sort_by', 'created_at')
    sort_order = request.args.get('sort_order', 'desc')

    # --- Get filtered AND user-specific link data ---
    # Call get_filtered ONCE, passing the user_id
    # It returns database ROWS including 'click_count'
    links_rows = Link.get_filtered(
        campaign_filter=campaign_filter,
        sort_by=sort_by,
        sort_order=sort_order,
        user_id=current_user.id # Filter by logged-in user
    )

    stats_data = []
    # Loop through the database ROWS returned
    for row in links_rows:
        # --- Create Link object from row data ---
        # Assuming your Link.__init__ takes these arguments
        link = Link(
            id=row['id'],
            original_url=row['original_url'],
            utm_source=row['utm_source'],
            utm_medium=row['utm_medium'],
            utm_campaign=row['utm_campaign'],
            utm_term=row['utm_term'],
            utm_content=row['utm_content'],
            short_code=row['short_code'],
            created_at=row['created_at']
            # user_id=row['user_id'] # Optional: if needed in the Link object itself
        )
        # --- Get click count directly from the query result ---
        click_count = row['click_count']

        # --- Generate short_url ---
        short_url = url_for('redirect_to_original', short_code=link.short_code, _external=True)

        # --- Generate QR Code ---
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=4, border=1)
        qr.add_data(short_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        qr_code_data_uri = f"data:image/png;base64,{img_str}"
        # --- End QR Code ---

        # Append dictionary with Link object and other data
        stats_data.append({
            'link': link,
            'short_url': short_url,
            'click_count': click_count,
            'qr_code_data_uri': qr_code_data_uri
        })

    # --- Determine next sort order ---
    next_sort_order = 'asc' if sort_order == 'desc' else 'desc'

    # --- Render the template ONCE at the end ---
    return render_template(
        'stats.html',
        stats_data=stats_data,
        current_filter=campaign_filter,
        current_sort_by=sort_by,
        current_sort_order=sort_order,
        next_sort_order=next_sort_order
    )




@app.route('/delete/<int:link_id>', methods=['POST'])
@login_required
def delete_link(link_id):
    # First, delete associated clicks
    Click.delete_for_link(link_id)
    # Then, delete the link itself
    Link.delete(link_id)
    flash('Link deleted successfully!', 'success') # Send a success message
    return redirect(url_for('show_stats')) # Redirect back to the stats page

@app.route('/edit/<int:link_id>', methods=['GET', 'POST'])
@login_required
def edit_link(link_id):
    link = Link.get(link_id) # Get the link by its ID

    if not link:
        flash('Link not found!', 'error')
        return redirect(url_for('show_stats'))

    if request.method == 'POST':
        # Get updated data from the form
        updated_data = request.form
        # Call the update method in the model
        Link.update(link_id, updated_data)
        flash('Link updated successfully!', 'success')
        return redirect(url_for('show_stats'))

    # If GET request, show the pre-filled form
    return render_template('edit_link.html', link=link)








@app.route("/register", methods=['GET', 'POST'])
def register():
    # If user is already logged in, redirect them
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit(): # Checks if POST request and form is valid
        # Check if User model was imported correctly in forms.py
        if User is None:
             flash('User model not available. Registration failed.', 'danger')
             return render_template('register.html', title='Register', form=form)

        # Attempt to create user
        user = User.create(username=form.username.data,
                           email=form.email.data,
                           password=form.password.data)
        if user: # If user was created successfully
            flash(f'Account created for {form.username.data}! You can now log in.', 'success')
            return redirect(url_for('login'))
        else:
            # User creation failed (likely username/email exists - handled by form validators now)
            # Or another error occurred during creation
             flash('Registration failed. Please check your input or try a different username/email.', 'warning')
    # If GET request or validation failed, show the form
    return render_template('register.html', title='Register', form=form)






@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        # Check if User model was imported
        if User is None:
             flash('User model not available. Login failed.', 'danger')
             return render_template('login.html', title='Login', form=form)

        user = User.get_by_username(form.username.data)
        # Check if user exists and password is correct
        if user and user.check_password(form.password.data):
            # Log the user in using Flask-Login
            login_user(user, remember=form.remember.data)
            # Redirect to the page user wanted to access, or index
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Login Unsuccessful. Please check username and password.', 'danger')
    return render_template('login.html', title='Login', form=form)





@app.route("/logout")
def logout():
    logout_user() # Logs the user out (clears session)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))







@app.teardown_appcontext
def teardown_db(exception=None):
    """Closes the database again at the end of the request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
        print("--- DB Connection Closed ---") # Optional debug



if __name__ == "__main__":
    app.run(debug=True)