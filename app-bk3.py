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
with app.app_context():
    init_db()

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
    links = Link.get_all()
    stats_data = []
    for link in links:
        click_count = Click.count_for_link(link.id)
        # Generate the full short URL for display
        short_url = url_for('redirect_to_original', short_code=link.short_code, _external=True)


        # --- Start QR Code Generation ---
        qr = qrcode.QRCode(
            version=1, # Keep it simple, controls the size/complexity
            error_correction=qrcode.constants.ERROR_CORRECT_L, # Low error correction
            box_size=4, # Size of each box in the QR code grid (pixels)
            border=1,  # Thickness of the border (number of boxes)
        )
        qr.add_data(short_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Convert image to Base64 Data URI
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        qr_code_data_uri = f"data:image/png;base64,{img_str}"
        # --- End QR Code Generation ---


        stats_data.append({
            'link': link,  
            'short_url': short_url,
            'click_count': click_count,
            'qr_code_data_uri': qr_code_data_uri
        })
    return render_template('stats.html', stats_data=stats_data)




@app.route('/delete/<int:link_id>', methods=['POST'])
def delete_link(link_id):
    # First, delete associated clicks
    Click.delete_for_link(link_id)
    # Then, delete the link itself
    Link.delete(link_id)
    flash('Link deleted successfully!', 'success') # Send a success message
    return redirect(url_for('show_stats')) # Redirect back to the stats page

if __name__ == "__main__":
    app.run(debug=True)