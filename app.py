from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import json
import secrets
import re
import time
from urllib.parse import urlparse
from sqlalchemy import or_, update
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
@app.template_filter('fromjson')
def fromjson_filter(value):
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return {}
# Never hard-code secrets in source control. Set SECRET_KEY in the deployment environment.
_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    if os.environ.get('FLASK_ENV', '').lower() == 'production':
        raise RuntimeError('SECRET_KEY must be set in production.')
    _secret_key = secrets.token_hex(32)

app.config.update(
    SECRET_KEY=_secret_key,
    SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'sqlite:///zer.db').replace('postgres://', 'postgresql://', 1),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=os.environ.get('SESSION_COOKIE_SECURE', '1' if os.environ.get('FLASK_ENV', '').lower() == 'production' else '0') != '0',
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)

db = SQLAlchemy(app)

# Small in-process login throttle; put a reverse proxy/WAF rate limit in front for multi-worker deployments.
_login_failures = {}
LOGIN_WINDOW = 10 * 60
LOGIN_LIMIT = 8

# ─── Models ───────────────────────────────────────────────────────────────────

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', backref='user', lazy=True)
    wishlist = db.relationship('Wishlist', backref='user', lazy=True)
    reviews = db.relationship('Review', backref='user', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    original_price = db.Column(db.Float)
    category = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(300))
    image_url_2 = db.Column(db.String(300))
    image_url_3 = db.Column(db.String(300))
    image_url_4 = db.Column(db.String(300))
    stock = db.Column(db.Integer, default=10)
    is_featured = db.Column(db.Boolean, default=False)
    is_trending = db.Column(db.Boolean, default=False)
    material = db.Column(db.String(100))
    weight = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviews = db.relationship('Review', backref='product', lazy=True)
    wishlist = db.relationship('Wishlist', backref='product', lazy=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(50), default='Pending')
    shipping_name = db.Column(db.String(100))
    shipping_address = db.Column(db.Text)
    shipping_phone = db.Column(db.String(20))
    payment_method = db.Column(db.String(50))
    items_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Wishlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Newsletter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    subject = db.Column(db.String(200))
    message = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _safe_int(value, default=1, minimum=1, maximum=99):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def get_cart():
    # Cart stores only product IDs and quantities. Never trust prices from the browser.
    raw = session.get('cart', {})
    if not isinstance(raw, dict):
        return {}
    clean = {}
    for pid, item in raw.items():
        try:
            product_id = int(pid)
            qty = _safe_int(item.get('qty', 1) if isinstance(item, dict) else 1)
            clean[str(product_id)] = {'qty': qty}
        except (TypeError, ValueError):
            continue
    return clean


def save_cart(cart):
    session['cart'] = {str(pid): {'qty': _safe_int(item.get('qty', 1))}
                       for pid, item in cart.items()}


def cart_count():
    return sum(item['qty'] for item in get_cart().values())


def cart_items():
    items = []
    for pid, item in get_cart().items():
        product = db.session.get(Product, int(pid))
        if product:
            qty = min(item['qty'], max(product.stock, 0))
            if qty > 0:
                items.append({'product': product, 'qty': qty,
                              'subtotal': product.price * qty})
    return items


def cart_total():
    return sum(item['subtotal'] for item in cart_items())


def get_wishlist_ids():
    uid = session.get('user_id')
    if uid:
        items = Wishlist.query.filter_by(user_id=uid).all()
        return [w.product_id for w in items]
    return []


def get_admin_counts():
    pending_orders = Order.query.filter_by(status='Confirmed').count()
    new_messages = ContactMessage.query.filter_by(is_read=False).count()
    return pending_orders, new_messages


def valid_email(value):
    return bool(re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', (value or '').strip()))


def safe_next_url(value):
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return None
    return value if value.startswith('/') else None


def login_throttled(key):
    now = time.monotonic()
    failures = [t for t in _login_failures.get(key, []) if now - t < LOGIN_WINDOW]
    _login_failures[key] = failures
    return len(failures) >= LOGIN_LIMIT


def record_login_failure(key):
    now = time.monotonic()
    failures = [t for t in _login_failures.get(key, []) if now - t < LOGIN_WINDOW]
    failures.append(now)
    _login_failures[key] = failures


@app.context_processor
def inject_globals():
    uid = session.get('user_id')
    current_user = db.session.get(User, uid) if uid else None
    return dict(
        cart_count=cart_count(),
        wishlist_ids=get_wishlist_ids(),
        current_user=current_user,
        csrf_token=csrf_token,
        categories=['Earrings','Necklaces','Rings','Bracelets','Anklets','Nose Pins']
    )


def csrf_token():
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf_token'] = token
    return token


@app.before_request
def protect_state_changing_requests():
    if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        expected = session.get('_csrf_token')
        supplied = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
        if not expected or not supplied or not secrets.compare_digest(expected, supplied):
            if request.path.startswith('/wishlist/'):
                return jsonify({'status': 'csrf_error'}), 400
            flash('Your session expired. Please try again.', 'error')
            return redirect(safe_next_url(request.referrer) or url_for('home'))


@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; "
        "form-action 'self'; img-src 'self' data: https://images.unsplash.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com data:; "
        "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; connect-src 'self'"
    )
    if request.is_secure:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    featured = Product.query.filter_by(is_featured=True).limit(8).all()
    trending = Product.query.filter_by(is_trending=True).limit(6).all()
    reviews = db.session.query(Review, User, Product).join(User, Review.user_id==User.id).join(Product, Review.product_id==Product.id).filter(Review.rating>=4).limit(6).all()
    return render_template('home.html', featured=featured, trending=trending, reviews=reviews)

@app.route('/shop')
def shop():
    category = request.args.get('category', '')
    search = request.args.get('search', '')[:100]
    sort = request.args.get('sort', 'newest')
    page = request.args.get('page', 1, type=int)

    query = Product.query
    if category:
        query = query.filter_by(category=category)
    if search:
        search_terms = search.strip().split()
        from sqlalchemy import or_
        conditions = []
        for term in search_terms:
            conditions.append(Product.name.ilike(f'%{term}%'))
            conditions.append(Product.description.ilike(f'%{term}%'))
            conditions.append(Product.category.ilike(f'%{term}%'))
            conditions.append(Product.material.ilike(f'%{term}%'))
        query = query.filter(or_(*conditions))
    if sort == 'price_asc':
        query = query.order_by(Product.price.asc())
    elif sort == 'price_desc':
        query = query.order_by(Product.price.desc())
    elif sort == 'newest':
        query = query.order_by(Product.created_at.desc())

    products = query.paginate(page=page, per_page=12, error_out=False)
    return render_template('shop.html', products=products, category=category, search=search, sort=sort)

@app.route('/product/<int:id>')
def product_detail(id):
    product = Product.query.get_or_404(id)
    reviews = db.session.query(Review, User).join(User, Review.user_id==User.id).filter(Review.product_id==id).all()
    avg_rating = db.session.query(db.func.avg(Review.rating)).filter_by(product_id=id).scalar() or 0
    related = Product.query.filter_by(category=product.category).filter(Product.id!=id).limit(4).all()
    return render_template('product.html', product=product, reviews=reviews, avg_rating=round(avg_rating,1), related=related)

@app.route('/cart')
def cart():
    items = cart_items()
    total = sum(item['subtotal'] for item in items)
    return render_template('cart.html', items=items, total=total)


@app.route('/add_to_cart/<int:id>', methods=['POST'])
def add_to_cart(id):
    product = Product.query.get_or_404(id)
    if product.stock <= 0:
        flash('This product is currently sold out.', 'error')
        return redirect(safe_next_url(request.referrer) or url_for('shop'))

    qty = _safe_int(request.form.get('qty', 1), maximum=99)
    cart = get_cart()
    pid = str(id)
    existing_qty = cart.get(pid, {}).get('qty', 0)
    new_qty = min(existing_qty + qty, product.stock, 99)
    cart[pid] = {'qty': new_qty}
    save_cart(cart)
    flash(f'"{product.name}" added to cart!', 'success')
    return redirect(safe_next_url(request.referrer) or url_for('shop'))


@app.route('/buy_now/<int:id>', methods=['POST'])
def buy_now(id):
    product = Product.query.get_or_404(id)
    if product.stock <= 0:
        flash('This product is currently sold out.', 'error')
        return redirect(url_for('product_detail', id=id))
    qty = min(_safe_int(request.form.get('qty', 1), maximum=99), product.stock)
    cart = get_cart()
    cart[str(id)] = {'qty': qty}
    save_cart(cart)
    return redirect(url_for('checkout'))


@app.route('/remove_from_cart/<int:id>', methods=['POST'])
def remove_from_cart(id):
    cart = get_cart()
    cart.pop(str(id), None)
    save_cart(cart)
    return redirect(url_for('cart'))


@app.route('/update_cart/<int:id>', methods=['POST'])
def update_cart(id):
    cart = get_cart()
    if str(id) not in cart:
        return redirect(url_for('cart'))
    product = Product.query.get_or_404(id)
    qty = _safe_int(request.form.get('qty', 1), maximum=99)
    if product.stock <= 0:
        cart.pop(str(id), None)
        flash(f'"{product.name}" is sold out and was removed from your cart.', 'error')
    else:
        cart[str(id)] = {'qty': min(qty, product.stock)}
    save_cart(cart)
    return redirect(url_for('cart'))


@app.route('/wishlist/toggle/<int:id>', methods=['POST'])
def toggle_wishlist(id):
    uid = session.get('user_id')
    if not uid:
        return jsonify({'status': 'login_required'})
    if not Product.query.get(id):
        return jsonify({'status': 'not_found'}), 404
    existing = Wishlist.query.filter_by(user_id=uid, product_id=id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'status': 'removed'})
    else:
        w = Wishlist(user_id=uid, product_id=id)
        db.session.add(w)
        db.session.commit()
        return jsonify({'status': 'added'})
@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session:
        flash('Please log in to checkout.', 'warning')
        return redirect(url_for('login'))

    items = cart_items()
    if not items:
        return redirect(url_for('cart'))

    subtotal = sum(item['subtotal'] for item in items)

    if request.method == 'POST':
        if subtotal < 500:
            flash('Minimum order amount is PKR 500 (excluding delivery). Please add more items.', 'error')
            return redirect(url_for('checkout'))

        name = request.form.get('name', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        postal = request.form.get('postal', '').strip()
        phone = request.form.get('phone', '').strip()
        payment = request.form.get('payment', '').strip()

        if not name or len(name) > 100 or not address or len(address) > 1000 or not city or len(city) > 100 or len(postal) > 20:
            flash('Please enter valid shipping details.', 'error')
            return redirect(url_for('checkout'))
        if not phone or len(phone) > 20:
            flash('Please enter a valid phone number.', 'error')
            return redirect(url_for('checkout'))
        if payment != 'Cash on Delivery':
            flash('Invalid payment method.', 'error')
            return redirect(url_for('checkout'))

        shipping_address = f"{address}, {city}" + (f", {postal}" if postal else '')

        # Re-read products and reserve stock atomically before creating the order.
        order_items = {}
        try:
            for item in items:
                product = db.session.get(Product, item['product'].id)
                qty = item['qty']
                if not product or product.stock < qty:
                    raise ValueError(f'Sorry, "{item["product"].name}" does not have enough stock.')

                result = db.session.execute(
                    update(Product)
                    .where(Product.id == product.id, Product.stock >= qty)
                    .values(stock=Product.stock - qty)
                )
                if result.rowcount != 1:
                    raise ValueError(f'Sorry, "{product.name}" just sold out. Please review your cart.')

                order_items[str(product.id)] = {
                    'name': product.name,
                    'price': product.price,
                    'qty': qty,
                    'image': product.image_url,
                }

            # Recalculate from authoritative DB prices, not session values.
            authoritative_total = sum(v['price'] * v['qty'] for v in order_items.values())
            order = Order(
                user_id=session['user_id'],
                total=authoritative_total + 200,
                shipping_name=name,
                shipping_address=shipping_address,
                shipping_phone=phone,
                payment_method=payment,
                items_json=json.dumps(order_items),
                status='Confirmed'
            )
            db.session.add(order)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            flash(str(exc) if isinstance(exc, ValueError) else 'We could not place your order. Please try again.', 'error')
            return redirect(url_for('cart'))

        session['cart'] = {}
        flash('Order placed successfully! Thank you for shopping with ZER.', 'success')
        return redirect(url_for('order_confirmed', id=order.id))

    return render_template('checkout.html', items=items, total=subtotal)


@app.route('/order-confirmed/<int:id>')
def order_confirmed(id):
    if 'user_id' not in session:
        flash('Please log in to view your order.', 'warning')
        return redirect(url_for('login'))

    order = Order.query.filter_by(
        id=id,
        user_id=session['user_id']
    ).first_or_404()

    return render_template(
        'order_confirmed.html',
        order=order
    )
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard' if session.get('is_admin') else 'home'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        email = email[:120]
        key = f"{request.remote_addr or 'unknown'}:{email}"
        if login_throttled(key):
            flash('Too many failed attempts. Please wait a few minutes and try again.', 'error')
            return render_template('login.html'), 429

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session.clear()
            session['user_id'] = user.id
            session['is_admin'] = bool(user.is_admin)
            session.permanent = True
            flash('Welcome back!', 'success')
            return redirect(url_for('admin_dashboard' if user.is_admin else 'home'))

        record_login_failure(key)
        flash('Invalid email or password.', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        phone = request.form.get('phone', '').strip()

        if not name or len(name) > 100:
            flash('Please enter a valid name.', 'error')
            return redirect(url_for('register'))

        if not valid_email(email) or len(email) > 120:
            flash('Please enter a valid email address.', 'error')
            return redirect(url_for('register'))

        if len(password) < 8 or len(password) > 128:
            flash('Password must be between 8 and 128 characters.', 'error')
            return redirect(url_for('register'))

        if len(phone) > 20:
            flash('Please enter a valid phone number.', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return redirect(url_for('register'))

        user = User(
            name=name,
            email=email,
            password=generate_password_hash(password),
            phone=phone
        )

        try:
            db.session.add(user)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print("REGISTER ERROR:", e)
            flash(str(e), "error")
            return redirect(url_for('register'))

        session.clear()
        session['user_id'] = user.id
        session['is_admin'] = False
        session.permanent = True

        flash('Account created successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('register.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    # Keep the old /signup URL working; use the same hardened registration flow.
    return register()


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))


@app.route('/dashboard')
def dashboard():
    uid = session.get('user_id')
    if not uid:
        return redirect(url_for('login'))
    user = User.query.get(uid)
    orders = Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).all()
    wishlist_items = db.session.query(Wishlist, Product).join(Product, Wishlist.product_id==Product.id).filter(Wishlist.user_id==user.id).all()
    return render_template('dashboard.html', user=user, orders=orders, wishlist_items=wishlist_items)

@app.route('/dashboard/update', methods=['POST'])
def update_profile():
    uid = session.get('user_id')
    if not uid:
        return redirect(url_for('login'))
    user = User.query.get(uid)
    name = request.form.get('name', user.name).strip()
    phone = request.form.get('phone', user.phone or '').strip()
    address = request.form.get('address', user.address or '').strip()
    if not name or len(name) > 100 or len(phone) > 20 or len(address) > 1000:
        flash('Please enter valid profile details.', 'error')
        return redirect(url_for('dashboard'))
    user.name = name
    user.phone = phone
    user.address = address
    db.session.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/review/<int:product_id>', methods=['POST'])
def add_review(product_id):
    uid = session.get('user_id')
    if not uid:
        flash('Please log in to leave a review.', 'warning')
        return redirect(url_for('login'))
    if not Product.query.get(product_id):
        return redirect(url_for('shop'))
    existing = Review.query.filter_by(user_id=uid, product_id=product_id).first()
    if existing:
        flash('You have already reviewed this product.', 'info')
        return redirect(url_for('product_detail', id=product_id))
    review = Review(
        user_id=uid,
        product_id=product_id,
        rating=max(1, min(5, _safe_int(request.form.get('rating', 5), default=5, maximum=5))),
        comment=request.form.get('comment', '').strip()[:2000]
    )
    db.session.add(review)
    db.session.commit()
    flash('Thank you for your review!', 'success')
    return redirect(url_for('product_detail', id=product_id))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET','POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        if not name or len(name) > 100 or not valid_email(email) or len(subject) > 200 or not message or len(message) > 5000:
            flash('Please enter valid contact details.', 'error')
            return redirect(url_for('contact'))
        msg = ContactMessage(name=name, email=email, subject=subject, message=message)
        db.session.add(msg)
        db.session.commit()
        flash('Your message has been sent. We will get back to you shortly.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/newsletter', methods=['POST'])
def newsletter():
    email = request.form.get('email', '').strip().lower()
    if email and valid_email(email) and len(email) <= 120:
        existing = Newsletter.query.filter_by(email=email).first()
        if not existing:
            n = Newsletter(email=email)
            db.session.add(n)
            db.session.commit()
            flash('Thank you for subscribing to ZÉR.', 'success')
        else:
            flash('You are already subscribed!', 'info')
    return redirect(request.referrer or url_for('home'))

# ─── Admin ────────────────────────────────────────────────────────────────────

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            flash('Admin access required.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/admin')
@admin_required
def admin_dashboard():
    users = User.query.count()
    products = Product.query.count()
    orders = Order.query.count()
    revenue = db.session.query(db.func.sum(Order.total)).filter(Order.status != 'Cancelled').scalar() or 0
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    pending_orders, new_messages = get_admin_counts()
    return render_template('admin/dashboard.html', users=users, products=products,
                           orders=orders, revenue=revenue, recent_orders=recent_orders,
                           pending_orders=pending_orders, new_messages=new_messages)

@app.route('/admin/products')
@admin_required
def admin_products():
    products = Product.query.order_by(Product.created_at.desc()).all()
    pending_orders, new_messages = get_admin_counts()
    return render_template('admin/products.html', products=products,
                           pending_orders=pending_orders, new_messages=new_messages)

@app.route('/admin/product/add', methods=['GET','POST'])
@admin_required
def admin_add_product():
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            price = float(request.form.get('price', '0'))
            original = float(request.form.get('original_price') or 0)
            stock = int(request.form.get('stock', '0'))
        except (TypeError, ValueError):
            flash('Invalid product number.', 'error')
            return redirect(url_for('admin_add_product'))

        if not name or len(name) > 200 or price <= 0 or original < 0 or stock < 0:
            flash('Please enter valid product details.', 'error')
            return redirect(url_for('admin_add_product'))

        p = Product(
            name=name,
            description=request.form.get('description', '').strip()[:10000],
            price=price,
            original_price=original or None,
            category=request.form.get('category', '').strip()[:50],
            image_url=request.form.get('image_url', '').strip()[:300],
            stock=min(stock, 100000),
            material=request.form.get('material', '').strip()[:100],
            weight=request.form.get('weight', '').strip()[:50],
            is_featured='is_featured' in request.form,
            is_trending='is_trending' in request.form,
            image_url_2=request.form.get('image_url_2', '').strip()[:300],
            image_url_3=request.form.get('image_url_3', '').strip()[:300],
            image_url_4=request.form.get('image_url_4', '').strip()[:300],
        )
        db.session.add(p)
        db.session.commit()
        flash('Product added!', 'success')
        return redirect(url_for('admin_products'))
    pending_orders, new_messages = get_admin_counts()
    return render_template('admin/add_product.html', pending_orders=pending_orders, new_messages=new_messages)


@app.route('/admin/product/edit/<int:id>', methods=['GET','POST'])
@admin_required
def admin_edit_product(id):
    p = Product.query.get_or_404(id)
    if request.method == 'POST':
        try:
            price = float(request.form.get('price', '0'))
            original = float(request.form.get('original_price') or 0)
            stock = int(request.form.get('stock', '0'))
        except (TypeError, ValueError):
            flash('Invalid product number.', 'error')
            return redirect(url_for('admin_edit_product', id=id))

        name = request.form.get('name', '').strip()
        if not name or len(name) > 200 or price <= 0 or original < 0 or stock < 0:
            flash('Please enter valid product details.', 'error')
            return redirect(url_for('admin_edit_product', id=id))

        p.name = name
        p.description = request.form.get('description', '').strip()[:10000]
        p.price = price
        p.original_price = original or None
        p.category = request.form.get('category', '').strip()[:50]
        p.image_url = request.form.get('image_url', '').strip()[:300]
        p.stock = min(stock, 100000)
        p.material = request.form.get('material', '').strip()[:100]
        p.weight = request.form.get('weight', '').strip()[:50]
        p.is_featured = 'is_featured' in request.form
        p.is_trending = 'is_trending' in request.form
        p.image_url_2 = request.form.get('image_url_2', '').strip()[:300]
        p.image_url_3 = request.form.get('image_url_3', '').strip()[:300]
        p.image_url_4 = request.form.get('image_url_4', '').strip()[:300]
        db.session.commit()
        flash('Product updated!', 'success')
        return redirect(url_for('admin_products'))
    pending_orders, new_messages = get_admin_counts()
    return render_template('admin/add_product.html', product=p,
                           pending_orders=pending_orders, new_messages=new_messages)


@app.route('/admin/product/delete/<int:id>', methods=['POST'])
@admin_required
def admin_delete_product(id):
    p = Product.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    flash('Product deleted.', 'info')
    return redirect(url_for('admin_products'))

@app.route('/admin/orders')
@admin_required
def admin_orders():
    orders = db.session.query(Order, User).join(User, Order.user_id==User.id).order_by(Order.created_at.desc()).all()
    pending_orders, new_messages = get_admin_counts()
    return render_template('admin/orders.html', orders=orders,
                           pending_orders=pending_orders, new_messages=new_messages)

@app.route('/admin/order/status/<int:id>', methods=['POST'])
@admin_required
def update_order_status(id):
    order = Order.query.get_or_404(id)
    order.status = request.form.get('status')
    db.session.commit()
    flash('Order status updated.', 'success')
    return redirect(url_for('admin_orders'))
@app.route('/admin/order/delete/<int:id>', methods=['POST'])
@admin_required
def admin_delete_order(id):
    order = Order.query.get_or_404(id)

    # Restore stock for every product in this order
    try:
        order_items = json.loads(order.items_json or '{}')

        for pid, item in order_items.items():
            product = Product.query.get(int(pid))

            if product:
                product.stock += int(item.get('qty', 0))

    except (json.JSONDecodeError, ValueError, TypeError):
        flash('Order could not be deleted because its item data is invalid.', 'error')
        return redirect(url_for('admin_orders'))

    # Delete the order after restoring stock
    db.session.delete(order)
    db.session.commit()

    flash('Order deleted and product stock restored.', 'success')
    return redirect(url_for('admin_orders'))
@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    pending_orders, new_messages = get_admin_counts()

    return render_template(
        'admin/users.html',
        users=users,
        pending_orders=pending_orders,
        new_messages=new_messages
    )
@app.route('/admin/messages')
@admin_required
def admin_messages():
    ContactMessage.query.filter_by(is_read=False).update({'is_read': True})
    db.session.commit()
    messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
    pending_orders, new_messages = get_admin_counts()
    return render_template('admin/messages.html', messages=messages,
                           pending_orders=pending_orders, new_messages=new_messages)

# ─── Seed Data ────────────────────────────────────────────────────────────────

def seed_data():
    if Product.query.count() > 0:
        return
    products = [
        {"name":"Aurora Gold Jhumkas","desc":"Handcrafted 22K gold jhumkas with intricate floral filigree. A timeless heirloom piece.","price":12500,"orig":15000,"cat":"Earrings","img":"https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?w=600&q=80","mat":"22K Gold","wt":"8g","feat":True,"trend":True},
        {"name":"Pearl Drop Elegance","desc":"Lustrous South Sea pearl drops suspended from delicate gold hooks. Pure sophistication.","price":8900,"orig":11000,"cat":"Earrings","img":"https://images.unsplash.com/photo-1573408301185-9519f94815b5?w=600&q=80","mat":"18K Gold, Pearl","wt":"5g","feat":True,"trend":False},
        {"name":"Diamond Stud Classics","desc":"Certified solitaire diamond studs. Brilliant cut. Timeless and understated.","price":45000,"orig":None,"cat":"Earrings","img":"https://images.unsplash.com/photo-1617038260897-41a1f14a8ca0?w=600&q=80","mat":"18K White Gold, Diamond","wt":"3g","feat":True,"trend":True},
        {"name":"Emerald Chandelier","desc":"Statement emerald and gold chandelier earrings for the modern empress.","price":18000,"orig":22000,"cat":"Earrings","img":"https://images.unsplash.com/photo-1626784215021-2e39ccf971cd?w=600&q=80","mat":"18K Gold, Emerald","wt":"10g","feat":False,"trend":True},
        {"name":"Golden Serpent Chain","desc":"A sleek 18K gold serpent chain, elegantly minimal. The foundation of every jewellery wardrobe.","price":22000,"orig":None,"cat":"Necklaces","img":"https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=600&q=80","mat":"18K Gold","wt":"12g","feat":True,"trend":True},
        {"name":"Kundan Bridal Set","desc":"Royal Kundan necklace with ruby accents. Crafted for the modern bride who values tradition.","price":65000,"orig":80000,"cat":"Necklaces","img":"https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=600&q=80","mat":"22K Gold, Kundan, Ruby","wt":"45g","feat":True,"trend":False},
        {"name":"Layered Pearl Strand","desc":"Three-layered freshwater pearl strand with gold clasp. Effortlessly chic.","price":9800,"orig":12000,"cat":"Necklaces","img":"https://images.unsplash.com/photo-1611085583191-a3b181a88401?w=600&q=80","mat":"Freshwater Pearl, Gold","wt":"20g","feat":False,"trend":True},
        {"name":"Solitaire Promise Ring","desc":"A single brilliant diamond set in 18K rose gold. For moments that last forever.","price":35000,"orig":None,"cat":"Rings","img":"https://images.unsplash.com/photo-1605100804763-247f67b3557e?w=600&q=80","mat":"18K Rose Gold, Diamond","wt":"4g","feat":True,"trend":True},
        {"name":"Floral Kundan Band","desc":"A wide Kundan band adorned with hand-set stones in floral motifs.","price":14000,"orig":17000,"cat":"Rings","img":"https://images.unsplash.com/photo-1546938576-6e1018f61a7f?w=600&q=80","mat":"22K Gold, Kundan","wt":"6g","feat":True,"trend":False},
        {"name":"Sapphire Statement Ring","desc":"Royal blue sapphire in a halo diamond setting. Unapologetically bold.","price":55000,"orig":None,"cat":"Rings","img":"https://images.unsplash.com/photo-1607703703674-df96af81dffa?w=600&q=80","mat":"18K White Gold, Sapphire","wt":"5g","feat":False,"trend":True},
        {"name":"Gold Chain Cuff","desc":"A structured 18K gold chain cuff. Minimal, powerful, timeless.","price":16000,"orig":20000,"cat":"Bracelets","img":"https://images.unsplash.com/photo-1573408301185-9519f94815b5?w=600&q=80","mat":"18K Gold","wt":"14g","feat":True,"trend":True},
        {"name":"Tennis Diamond Bracelet","desc":"A full row of brilliant diamonds set in white gold. The ultimate luxury statement.","price":95000,"orig":None,"cat":"Bracelets","img":"https://images.unsplash.com/photo-1611591437281-460bfbe1220a?w=600&q=80","mat":"18K White Gold, Diamond","wt":"10g","feat":True,"trend":False},
        {"name":"Gold Anklet Classic","desc":"A delicate 22K gold anklet with subtle gold beads. Tradition meets modernity.","price":4500,"orig":5500,"cat":"Anklets","img":"https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?w=600&q=80","mat":"22K Gold","wt":"5g","feat":False,"trend":True},
        {"name":"Pearl Charm Anklet","desc":"Freshwater pearls strung on a gold chain. Effortlessly feminine.","price":3800,"orig":None,"cat":"Anklets","img":"https://images.unsplash.com/photo-1617038260897-41a1f14a8ca0?w=600&q=80","mat":"18K Gold, Pearl","wt":"4g","feat":False,"trend":False},
        {"name":"Diamond Nose Pin","desc":"A single brilliant diamond set in 18K gold. For the discerning nose.","price":8000,"orig":None,"cat":"Nose Pins","img":"https://images.unsplash.com/photo-1626784215021-2e39ccf971cd?w=600&q=80","mat":"18K Gold, Diamond","wt":"0.5g","feat":False,"trend":True},
        {"name":"Ruby Nath","desc":"A traditional ruby nath with pearl accents. For the bride who carries culture with grace.","price":12000,"orig":15000,"cat":"Nose Pins","img":"https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=600&q=80","mat":"22K Gold, Ruby, Pearl","wt":"2g","feat":False,"trend":False},
    ]
    for p in products:
        product = Product(
            name=p["name"], description=p["desc"], price=p["price"],
            original_price=p["orig"], category=p["cat"], image_url=p["img"],
            material=p["mat"], weight=p["wt"], is_featured=p["feat"],
            is_trending=p["trend"], stock=15
        )
        db.session.add(product)

    db.session.commit()


def ensure_admin_account():
    # An admin is created/rotated only when explicit deployment credentials are supplied.
    email = os.environ.get('ADMIN_EMAIL', '').strip().lower()
    password = os.environ.get('ADMIN_PASSWORD', '')
    if not email or not password:
        return
    if not valid_email(email) or len(password) < 12:
        raise RuntimeError('ADMIN_EMAIL must be valid and ADMIN_PASSWORD must be at least 12 characters.')

    admin = User.query.filter_by(email=email).first()
    if not admin:
        admin = User(name='ZÉR Admin', email=email, password='', is_admin=True)
        db.session.add(admin)
    admin.is_admin = True
    admin.password = generate_password_hash(password)
    db.session.commit()


with app.app_context():
    db.create_all()
    seed_data()
    ensure_admin_account()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
