import os
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_from_directory
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------

app = Flask(__name__)
app.config['SECRET_KEY'] = 'changeme–use-a-strong-random-string'
base_dir = os.path.abspath(os.path.dirname(__file__))

# SQLite configuration (for now). Later you can replace with PostgreSQL.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Upload folder (for product images)
UPLOAD_FOLDER = os.path.join(base_dir, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Allowed extensions for images
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

def allowed_file(filename):
    """Check if the filename has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_images(files):
    """
    Given a list of FileStorage objects, save each one with a secure filename
    and return a list of filenames (relative to /static/uploads).
    """
    filenames = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{datetime.utcnow().timestamp()}_{file.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            # Store just the filename (not full path); templates can reference /static/uploads/<filename>
            filenames.append(filename)
    return filenames

def is_admin_logged_in():
    return session.get('admin_logged_in') is True

# ------------------------------------------------------------------------------
# Database models
# ------------------------------------------------------------------------------

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    # One-to-many relationship: a product can have multiple images
    images = db.relationship('ProductImage', back_populates='product', cascade='all, delete-orphan')
    # One-to-many: a product can have multiple reviews
    reviews = db.relationship('Review', back_populates='product', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Product {self.name}>"


class ProductImage(db.Model):
    __tablename__ = 'product_images'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(300), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)

    product = db.relationship('Product', back_populates='images')

    def __repr__(self):
        return f"<ProductImage {self.filename} for Product {self.product_id}>"


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    reviewer_name = db.Column(db.String(100), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # e.g. 1 to 5
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    product = db.relationship('Product', back_populates='reviews')

    def __repr__(self):
        return f"<Review {self.rating} by {self.reviewer_name}>"


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Customer info
    customer_name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.Text, nullable=False)
    phone_number = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    whatsapp_number = db.Column(db.String(50), nullable=True)
    payment_method = db.Column(db.String(50), nullable=False)  # 'COD' or 'Advanced'

    # One-to-many: an order has multiple OrderItem entries
    items = db.relationship('OrderItem', back_populates='order', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Order {self.id} by {self.customer_name}>"


class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    
    order = db.relationship('Order', back_populates='items')
    product = db.relationship('Product')

    def __repr__(self):
        return f"<OrderItem {self.quantity} x Product {self.product_id}>"


class ContactMessage(db.Model):
    __tablename__ = 'contact_messages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(300), nullable=True)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ContactMessage from {self.name}>"

# ------------------------------------------------------------------------------
# Create database tables
# ------------------------------------------------------------------------------
with app.app_context():
    db.create_all()

# ------------------------------------------------------------------------------
# Admin credentials (hardcoded for now)
# ------------------------------------------------------------------------------
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'password123'


# ------------------------------------------------------------------------------
# Public routes
# ------------------------------------------------------------------------------

@app.route('/')
def index():
    """
    Homepage: show a few featured products in a “slide” (e.g. top 5 most recent).
    """
    featured = Product.query.order_by(Product.id.desc()).limit(5).all()
    return render_template('index.html', featured=featured)


@app.route('/about')
def about():
    """About page."""
    return render_template('about.html')


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    """
    Contact page: GET shows the form; POST saves to ContactMessage.
    """
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()

        if not name or not email or not message:
            flash('Name, email, and message are required.', 'danger')
            return redirect(url_for('contact'))

        cm = ContactMessage(
            name=name,
            email=email,
            subject=subject,
            message=message
        )
        db.session.add(cm)
        db.session.commit()
        flash('Your message has been sent. We will get back to you shortly.', 'success')
        return redirect(url_for('contact'))

    return render_template('contact.html')


@app.route('/products')
def products():
    """
    Product listing page.
    If a ?q=search_term is provided, filter by product name like %q%.
    """
    q = request.args.get('q', '').strip()
    if q:
        all_products = Product.query.filter(Product.name.ilike(f'%{q}%')).all()
    else:
        all_products = Product.query.all()
    return render_template('products.html', products=all_products, q=q)


@app.route('/product/<int:product_id>', methods=['GET', 'POST'])
def product_detail(product_id):
    """
    Product detail page: shows multiple images, name, price, description, reviews.
    On this page you can also POST a new review.
    """
    product = Product.query.get_or_404(product_id)

    if request.method == 'POST':
        # Handle a new review submission
        reviewer_name = request.form.get('reviewer_name', '').strip()
        rating = request.form.get('rating')
        comment = request.form.get('comment', '').strip()

        if not reviewer_name or not rating:
            flash('Reviewer name and rating are required.', 'danger')
            return redirect(url_for('product_detail', product_id=product_id))

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                raise ValueError()
        except ValueError:
            flash('Rating must be an integer between 1 and 5.', 'danger')
            return redirect(url_for('product_detail', product_id=product_id))

        rv = Review(
            reviewer_name=reviewer_name,
            rating=rating,
            comment=comment,
            product=product
        )
        db.session.add(rv)
        db.session.commit()
        flash('Your review has been posted.', 'success')
        return redirect(url_for('product_detail', product_id=product_id))

    return render_template('product_detail.html', product=product)


# ----------------------------------------
# Shopping Cart (stored in session)
# ----------------------------------------

def _initialize_cart():
    """Ensure session['cart'] is a dict mapping product_id -> quantity."""
    if 'cart' not in session:
        session['cart'] = {}
    return session['cart']


@app.route('/cart')
def view_cart():
    """
    Show the current shopping cart.
    session['cart'] is a dict { product_id (str) : quantity (int) }.
    """
    cart = _initialize_cart()
    cart_items = []
    total = 0.0

    for pid_str, qty in cart.items():
        product = Product.query.get(int(pid_str))
        if not product:
            continue
        subtotal = product.price * qty
        total += subtotal
        cart_items.append({
            'product': product,
            'quantity': qty,
            'subtotal': subtotal
        })

    return render_template('cart.html', cart_items=cart_items, total=total)


@app.route('/cart/add/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    """
    Add one unit of product to cart (or increment if already present).
    Expects form data (e.g. quantity in future).
    """
    product = Product.query.get_or_404(product_id)
    cart = _initialize_cart()

    pid_str = str(product_id)
    current_qty = cart.get(pid_str, 0)
    cart[pid_str] = current_qty + 1

    session['cart'] = cart
    flash(f'Added "{product.name}" to cart.', 'success')
    return redirect(url_for('view_cart'))


@app.route('/cart/remove/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    """Remove the product entirely from the cart."""
    cart = _initialize_cart()
    pid_str = str(product_id)
    if pid_str in cart:
        cart.pop(pid_str)
        session['cart'] = cart
        flash('Product removed from cart.', 'info')
    return redirect(url_for('view_cart'))


@app.route('/cart/update/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    """
    Update the quantity of a given product in the cart.
    Expects form field 'quantity'.
    """
    cart = _initialize_cart()
    pid_str = str(product_id)
    if pid_str not in cart:
        flash('Product not in cart.', 'danger')
        return redirect(url_for('view_cart'))

    try:
        qty = int(request.form.get('quantity', '1'))
        if qty < 1:
            raise ValueError()
    except ValueError:
        flash('Quantity must be a positive integer.', 'danger')
        return redirect(url_for('view_cart'))

    cart[pid_str] = qty
    session['cart'] = cart
    flash('Cart updated.', 'success')
    return redirect(url_for('view_cart'))

def get_cart_items():
    cart_items = []
    if 'cart' in session:
        for product_id, quantity in session['cart'].items():
            product = Product.query.get(int(product_id))
            if product:
                subtotal = product.price * quantity
                cart_items.append({
                    'product': product,
                    'quantity': quantity,
                    'subtotal': subtotal
                })
    return cart_items
# ----------------------------------------
# Checkout (guest checkout; no user accounts)
# ----------------------------------------

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if request.method == 'POST':
        try:
            # Get order details from form
            customer_name = request.form.get('name')
            address = request.form.get('address')
            phone_number = request.form.get('phone')
            email = request.form.get('email')
            whatsapp_number = request.form.get('whatsapp')
            payment_method = request.form.get('payment_method')

            # Handle direct buy vs cart checkout
            product_id = request.form.get('product_id')
            buy_now = request.form.get('buy_now')

            if product_id and buy_now:
                # Direct buy flow
                product = Product.query.get_or_404(int(product_id))
                cart_items = [{'product': product, 'quantity': 1, 'subtotal': product.price}]
                total = product.price
            else:
                # Cart checkout flow
                cart_items = get_cart_items()
                if not cart_items:
                    flash('Your cart is empty', 'warning')
                    return redirect(url_for('products'))
                total = sum(item['subtotal'] for item in cart_items)

            # Only create order if we have customer details
            if customer_name and address and phone_number and email and payment_method:
                # Create new order
                order = Order(
                    customer_name=customer_name,
                    address=address,
                    phone_number=phone_number,
                    email=email,
                    whatsapp_number=whatsapp_number,
                    payment_method=payment_method
                )
                db.session.add(order)

                # Add order items
                for item in cart_items:
                    order_item = OrderItem(
                        order=order,
                        product=item['product'],
                        quantity=item['quantity'],
                        unit_price=item['product'].price
                    )
                    db.session.add(order_item)

                db.session.commit()

                # Clear cart after successful order (only for cart checkout)
                if not buy_now and 'cart' in session:
                    session.pop('cart')

                flash('Order placed successfully!', 'success')
                return redirect(url_for('index'))

            # If we don't have customer details, show checkout form
            return render_template('checkout.html', 
                                cart_items=cart_items, 
                                total=total,
                                product_id=product_id if buy_now else None)

        except Exception as e:
            db.session.rollback()
            flash('An error occurred while placing your order. Please try again.', 'error')
            return redirect(url_for('checkout'))

    # GET request - show checkout form
    cart_items = get_cart_items()
    if not cart_items:
        flash('Your cart is empty', 'warning')
        return redirect(url_for('products'))
    
    total = sum(item['subtotal'] for item in cart_items)
    return render_template('checkout.html', cart_items=cart_items, total=total)
# ------------------------------------------------------------------------------
# Admin routes
# ------------------------------------------------------------------------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """
    Simple admin login (no Flask-Login). Checks against ADMIN_USERNAME & ADMIN_PASSWORD.
    """
    if is_admin_logged_in():
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash('Logged in successfully.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials.', 'danger')
            return redirect(url_for('admin_login'))

    return render_template('admin/login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Logged out.', 'info')
    return redirect(url_for('admin_login'))


@app.route('/admin/dashboard')
def admin_dashboard():
    """Show basic stats: total products, total orders, total contacts."""
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))

    total_products = Product.query.count()
    total_orders = Order.query.count()
    total_contacts = ContactMessage.query.count()
    return render_template(
        'admin/dashboard.html',
        total_products=total_products,
        total_orders=total_orders,
        total_contacts=total_contacts
    )


# ------------------------------
# Admin: Products CRUD
# ------------------------------

@app.route('/admin/products')
def admin_list_products():
    """List all products with edit/delete links."""
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))

    products = Product.query.all()
    return render_template('admin/list_products.html', products=products)


@app.route('/admin/products/add', methods=['GET', 'POST'])
def admin_add_product():
    """
    Admin form to add a new product.
    Supports multiple image uploads.
    """
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        price = request.form.get('price', '').strip()
        description = request.form.get('description', '').strip()
        image_files = request.files.getlist('images')

        if not name or not price:
            flash('Name and price are required.', 'danger')
            return redirect(url_for('admin_add_product'))

        try:
            price = float(price)
        except ValueError:
            flash('Price must be a number.', 'danger')
            return redirect(url_for('admin_add_product'))

        product = Product(name=name, price=price, description=description)
        db.session.add(product)
        db.session.flush()  # so product.id is available

        # Save images
        saved_filenames = save_images(image_files)
        for fn in saved_filenames:
            pi = ProductImage(filename=fn, product_id=product.id)
            db.session.add(pi)

        db.session.commit()
        flash(f'Product "{name}" added successfully.', 'success')
        return redirect(url_for('admin_list_products'))

    return render_template('admin/add_product.html')


@app.route('/admin/products/edit/<int:product_id>', methods=['GET', 'POST'])
def admin_edit_product(product_id):
    """
    Admin form to edit an existing product.
    You can change name, price, description, and upload additional images.
    """
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))
    
    product = Product.query.get_or_404(product_id)
    
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            price = request.form.get('price', '').strip()
            description = request.form.get('description', '').strip()
            image_files = request.files.getlist('images')

            # Validation
            if not name or not price:
                flash('Name and price are required.', 'danger')
                return redirect(url_for('admin_edit_product', product_id=product_id))
            
            try:
                price = float(price)
            except ValueError:
                flash('Price must be a number.', 'danger')
                return redirect(url_for('admin_edit_product', product_id=product_id))

            # Update product
            product.name = name
            product.price = price
            product.description = description

            # Handle new images
            if image_files and image_files[0].filename:
                saved_filenames = save_images(image_files)
                for fn in saved_filenames:
                    pi = ProductImage(filename=fn, product_id=product.id)
                    db.session.add(pi)

            db.session.commit()
            flash(f'Product "{name}" updated successfully.', 'success')
            return redirect(url_for('admin_list_products'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating product: {str(e)}', 'danger')
            return redirect(url_for('admin_edit_product', product_id=product_id))

    return render_template('admin/edit_product.html', product=product)


@app.route('/admin/products/delete/<int:product_id>', methods=['POST'])
def admin_delete_product(product_id):
    """
    Delete a product and all its images/reviews.
    Also delete the image files from disk.
    """
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))

    product = Product.query.get_or_404(product_id)

    # First delete image files from disk
    for img in product.images:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], img.filename))
        except OSError:
            pass  # ignore if file not found

    db.session.delete(product)
    db.session.commit()
    flash(f'Product "{product.name}" deleted.', 'info')
    return redirect(url_for('admin_list_products'))


@app.route('/admin/product_images/delete/<int:image_id>', methods=['POST'])
def admin_delete_product_image(image_id):
    """
    Delete a single image from a product.
    Useful if admin wants to remove one image without deleting the product.
    """
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))

    img = ProductImage.query.get_or_404(image_id)
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], img.filename)
    try:
        os.remove(image_path)
    except OSError:
        pass
    db.session.delete(img)
    db.session.commit()
    flash('Image deleted.', 'info')
    return redirect(url_for('admin_edit_product', product_id=img.product_id))


# ------------------------------
# Admin: View Orders
# ------------------------------

@app.route('/admin/orders')
def admin_list_orders():
    """
    List all orders, with ability to click into details if you want.
    """
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))

    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin/list_orders.html', orders=orders)


@app.route('/admin/orders/<int:order_id>')
def admin_view_order(order_id):
    """
    View details for a single order (including items).
    """
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))

    order = Order.query.get_or_404(order_id)
    return render_template('admin/view_order.html', order=order)


# ------------------------------
# Admin: View Contact Messages
# ------------------------------

@app.route('/admin/contacts')
def admin_list_contacts():
    """
    List all messages sent via the Contact page.
    """
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))

    contacts = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
    return render_template('admin/list_contacts.html', contacts=contacts)

@app.route('/admin/orders/<int:order_id>/delete', methods=['POST'])
def admin_delete_order(order_id):
    """Delete an order."""
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))
        
    order = Order.query.get_or_404(order_id)
    try:
        db.session.delete(order)
        db.session.commit()
        flash(f'Order #{order_id} has been deleted.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting order: {str(e)}', 'danger')
        
    return redirect(url_for('admin_list_orders'))
# ------------------------------------------------------------------------------
# Static route for uploaded images (optional; Flask can serve /static automatically)
# ------------------------------------------------------------------------------

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ------------------------------------------------------------------------------
# Error handlers (optional)
# ------------------------------------------------------------------------------

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    return render_template('500.html'), 500


# ------------------------------------------------------------------------------
# Run
# ------------------------------------------------------------------------------

