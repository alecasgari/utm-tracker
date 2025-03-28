from flask import Flask, render_template, request, redirect, url_for
import urllib.parse
from models import Link, init_db, get_db  # Import the Link class and database functions
from models import Link, Click, init_db, get_db # Added Click here
from flask import Flask, render_template, request, redirect, url_for, flash # Added flash
import qrcode
from io import BytesIO
import base64


app = Flask(__name__)
app.config['SECRET_KEY'] = 'c>CJ`Ni$/lpx4"r'  # Replace with a strong secret key!

# Initialize the database (create tables if they don't exist)
#with app.app_context():
#init_db()

@app.route("/", methods=["GET", "POST"])
def index():
    utm_link = None
    short_link = None # added
    if request.method == "POST":
        website_url = request.form["website_url"]
        utm_source = request.form["utm_source"]
        utm_medium = request.form["utm_medium"]
        utm_campaign = request.form["utm_campaign"]
        utm_term = request.form.get("utm_term")
        utm_content = request.form.get("utm_content")

        utm_params = {}
        if utm_source:
            utm_params["utm_source"] = utm_source
        if utm_medium:
            utm_params["utm_medium"] = utm_medium
        if utm_campaign:
            utm_params["utm_campaign"] = utm_campaign
        if utm_term:
            utm_params["utm_term"] = utm_term
        if utm_content:
            utm_params["utm_content"] = utm_content


        if utm_params:
            url_parts = list(urllib.parse.urlparse(website_url))
            query = dict(urllib.parse.parse_qsl(url_parts[4]))
            query.update(utm_params)
            url_parts[4] = urllib.parse.urlencode(query)
            utm_link = urllib.parse.urlunparse(url_parts)

        # --- Database interaction ---
        link = Link.create(
        original_url=website_url,
        utm_source=utm_source,
        utm_medium=utm_medium,
        utm_campaign=utm_campaign,
        utm_term=utm_term,
        utm_content=utm_content
    )

    
        short_link = url_for('redirect_to_original', short_code=link.short_code, _external=True)
        return render_template("form.html", utm_link=utm_link, short_link=short_link)

    return render_template("form.html", utm_link=utm_link, short_link=short_link)

@app.route('/s/<short_code>')
def redirect_to_original(short_code):
    link = Link.get_by_short_code(short_code)
    if link:
        # Log the click
        Click.create(link.id)  # Create a new click record

        return redirect(link.original_url)
    else:
        return "Short link not found", 404
    
@app.route('/stats')
def show_stats():
    campaign_filter = request.args.get('campaign_filter', '')
    sort_by = request.args.get('sort_by', 'created_at')
    sort_order = request.args.get('sort_order', 'desc')

    # Using the simplified get_filtered which returns Link objects
    links = Link.get_filtered(campaign_filter=campaign_filter, sort_by=sort_by, sort_order=sort_order)

    stats_data = []
    # Loop through Link objects
    for link in links:
        # Calculate click count separately
        click_count = Click.count_for_link(link.id)

        # Generate short_url
        short_url = url_for('redirect_to_original', short_code=link.short_code, _external=True)

        # --- Start QR Code Generation ---
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=4,
            border=1,
        )
        qr.add_data(short_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        qr_code_data_uri = f"data:image/png;base64,{img_str}"
        # --- End QR Code Generation ---

        # Append ONCE per link
        stats_data.append({
            'link': link,
            'short_url': short_url,
            'click_count': click_count,
            'qr_code_data_uri': qr_code_data_uri
        })
        # DO NOT ADD a second stats_data.append() here

    next_sort_order = 'asc' if sort_order == 'desc' else 'desc'

    return render_template(
        'stats.html',
        stats_data=stats_data,
        current_filter=campaign_filter,
        current_sort_by=sort_by,
        current_sort_order=sort_order,
        next_sort_order=next_sort_order
    )

    # --- Determine next sort order for template links ---
    next_sort_order = 'asc' if sort_order == 'desc' else 'desc'

    # Pass sorting info to the template
    return render_template(
        'stats.html',
        stats_data=stats_data,
        current_filter=campaign_filter,
        current_sort_by=sort_by,
        current_sort_order=sort_order,
        next_sort_order=next_sort_order # Pass the next order for link generation
    )




@app.route('/delete/<int:link_id>', methods=['POST'])
def delete_link(link_id):
    # First, delete associated clicks
    Click.delete_for_link(link_id)
    # Then, delete the link itself
    Link.delete(link_id)
    flash('Link deleted successfully!', 'success') # Send a success message
    return redirect(url_for('show_stats')) # Redirect back to the stats page

@app.route('/edit/<int:link_id>', methods=['GET', 'POST'])
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

if __name__ == "__main__":
    app.run(debug=True)