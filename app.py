from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import json

app = Flask(__name__)
app.secret_key = 'zer-luxury-jewellery-secret-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///zer.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

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

def get_cart():
    return session.get('cart', {})

def cart_count():
    cart = get_cart()
    return sum(item['qty'] for item in cart.values())

def cart_total():
    cart = get_cart()
    return sum(item['price'] * item['qty'] for item in cart.values())

def get_wishlist_ids():
    uid = session.get('user_id')
    if uid:
        items = Wishlist.query.filter_by(user_id=uid).all()
        return [w.product_id for w in items]
    return session.get('wishlist', [])

def get_admin_counts():
    pending_orders = Order.query.filter_by(status='Confirmed').count()
    new_messages = ContactMessage.query.filter_by(is_read=False).count()
    return pending_orders, new_messages
import json as json_module

@app.template_filter('fromjson')
def fromjson_filter(value):
    try:
        return json_module.loads(value)
    except:
        return {}
@app.context_processor
def inject_globals():
    uid = session.get('user_id')
    current_user = User.query.get(uid) if uid else None
    return dict(
        cart_count=cart_count(),
        wishlist_ids=get_wishlist_ids(),
        current_user=current_user,
        categories=['Earrings','Necklaces','Rings','Bracelets','Anklets','Nose Pins']
    )

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
    search = request.args.get('search', '')
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
    cart_data = get_cart()
    items = []
    for pid, item in cart_data.items():
        product = Product.query.get(int(pid))
        if product:
            items.append({'product': product, 'qty': item['qty'], 'subtotal': item['price']*item['qty']})
    return render_template('cart.html', items=items, total=cart_total())

@app.route('/add_to_cart/<int:id>', methods=['POST'])
def add_to_cart(id):
    product = Product.query.get_or_404(id)
    qty = int(request.form.get('qty', 1))
    cart = get_cart()
    pid = str(id)
    if pid in cart:
        cart[pid]['qty'] += qty
    else:
        cart[pid] = {'name': product.name, 'price': product.price, 'qty': qty, 'image': product.image_url}
    session['cart'] = cart
    flash(f'"{product.name}" added to cart!', 'success')
    return redirect(request.referrer or url_for('shop'))

@app.route('/buy_now/<int:id>', methods=['POST'])
def buy_now(id):
    product = Product.query.get_or_404(id)
    qty = int(request.form.get('qty', 1))
    cart = get_cart()
    pid = str(id)
    if pid in cart:
        cart[pid]['qty'] += qty
    else:
        cart[pid] = {'name': product.name, 'price': product.price, 'qty': qty, 'image': product.image_url}
    session['cart'] = cart
    return redirect(url_for('checkout'))

@app.route('/remove_from_cart/<int:id>')
def remove_from_cart(id):
    cart = get_cart()
    if str(id) in cart:
        del cart[str(id)]
    session['cart'] = cart
    return redirect(url_for('cart'))

@app.route('/update_cart/<int:id>', methods=['POST'])
def update_cart(id):
    cart = get_cart()
    qty = int(request.form.get('qty', 1))
    if qty < 1:
        cart.pop(str(id), None)
    else:
        if str(id) in cart:
            cart[str(id)]['qty'] = qty
    session['cart'] = cart
    return redirect(url_for('cart'))

@app.route('/wishlist/toggle/<int:id>', methods=['POST'])
def toggle_wishlist(id):
    uid = session.get('user_id')
    if not uid:
        return jsonify({'status': 'login_required'})
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

    cart_data = get_cart()

    if not cart_data:
        return redirect(url_for('cart'))

    if request.method == 'POST':

        if cart_total() < 500:
            flash(
                'Minimum order amount is PKR 500 (excluding delivery). Please add more items to proceed.',
                'error'
            )
            return redirect(url_for('checkout'))

        # Check stock BEFORE creating the order
        for pid, item in cart_data.items():
            product = Product.query.get(int(pid))

            if not product:
                flash(
                    'One of the products in your cart is no longer available.',
                    'error'
                )
                return redirect(url_for('cart'))

            if product.stock < item['qty']:
                flash(
                    f'Sorry, only {product.stock} unit(s) of "{product.name}" are available.',
                    'error'
                )
                return redirect(url_for('cart'))

        # All stock checks passed — create the order
        order = Order(
            user_id=session['user_id'],
            total=cart_total() + 200,
            shipping_name=request.form.get('name'),
            shipping_address=request.form.get('address'),
            shipping_phone=request.form.get('phone'),
            payment_method=request.form.get('payment'),
            items_json=json.dumps(cart_data),
            status='Confirmed'
        )

        db.session.add(order)

        # Reduce stock
        for pid, item in cart_data.items():
            product = Product.query.get(int(pid))
            product.stock -= item['qty']

        db.session.commit()

        session['cart'] = {}

        flash(
            'Order placed successfully! Thank you for shopping with ZER.',
            'success'
        )

        return redirect(url_for('order_confirmed', id=order.id))

    # Prepare cart items for the checkout page
    items = []

    for pid, item in cart_data.items():
        product = Product.query.get(int(pid))

        if product:
            items.append({
                'product': product,
                'qty': item['qty'],
                'subtotal': item['price'] * item['qty']
            })

    return render_template(
        'checkout.html',
        items=items,
        total=cart_total()
    )


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
    # If user is already logged in, redirect based on role
    if 'user_id' in session:
        if session.get('is_admin'):
            return redirect(url_for('admin_dashboard'))

        return redirect(url_for('home'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()

        password_field = (
            getattr(user, 'password_hash', getattr(user, 'password', None))
            if user else None
        )

        if user and password_field and check_password_hash(
            password_field,
            password
        ):
            session['user_id'] = user.id
            session['is_admin'] = user.is_admin

            flash('Welcome back!', 'success')

            if user.is_admin:
                return redirect(url_for('admin_dashboard'))

            return redirect(url_for('home'))

        else:
            flash('Invalid email or password.', 'error')

    return render_template('login.html')
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone')

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return redirect(url_for('register'))

        user = User(
            name=name,
            email=email,
            password=generate_password_hash(password),
            phone=phone
        )
        db.session.add(user)
        db.session.commit()

        session['user_id'] = user.id
        session['is_admin'] = user.is_admin
        flash('Account created successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('register.html')

@app.route('/logout')
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
    user.name = request.form.get('name', user.name)
    user.phone = request.form.get('phone', user.phone)
    user.address = request.form.get('address', user.address)
    db.session.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/review/<int:product_id>', methods=['POST'])
def add_review(product_id):
    uid = session.get('user_id')
    if not uid:
        flash('Please log in to leave a review.', 'warning')
        return redirect(url_for('login'))
    existing = Review.query.filter_by(user_id=uid, product_id=product_id).first()
    if existing:
        flash('You have already reviewed this product.', 'info')
        return redirect(url_for('product_detail', id=product_id))
    review = Review(
        user_id=uid,
        product_id=product_id,
        rating=int(request.form.get('rating', 5)),
        comment=request.form.get('comment', '')
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
        msg = ContactMessage(
            name=request.form.get('name'),
            email=request.form.get('email'),
            subject=request.form.get('subject'),
            message=request.form.get('message')
        )
        db.session.add(msg)
        db.session.commit()
        flash('Your message has been sent. We will get back to you shortly.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/newsletter', methods=['POST'])
def newsletter():
    email = request.form.get('email')
    if email:
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
        p = Product(
            name=request.form.get('name'),
            description=request.form.get('description'),
            price=float(request.form.get('price')),
            original_price=float(request.form.get('original_price') or 0) or None,
            category=request.form.get('category'),
            image_url=request.form.get('image_url'),
            stock=int(request.form.get('stock', 10)),
            material=request.form.get('material'),
            weight=request.form.get('weight'),
            is_featured='is_featured' in request.form,
            is_trending='is_trending' in request.form,
            image_url_2=request.form.get('image_url_2'),
            image_url_3=request.form.get('image_url_3'),
            image_url_4=request.form.get('image_url_4'),
        )
        db.session.add(p)
        db.session.commit()
        flash('Product added!', 'success')
        return redirect(url_for('admin_products'))
    pending_orders, new_messages = get_admin_counts()
    return render_template('admin/add_product.html',
                           pending_orders=pending_orders, new_messages=new_messages)

@app.route('/admin/product/edit/<int:id>', methods=['GET','POST'])
@admin_required
def admin_edit_product(id):
    p = Product.query.get_or_404(id)
    if request.method == 'POST':
        p.name = request.form.get('name')
        p.description = request.form.get('description')
        p.price = float(request.form.get('price'))
        p.original_price = float(request.form.get('original_price') or 0) or None
        p.category = request.form.get('category')
        p.image_url = request.form.get('image_url')
        p.stock = int(request.form.get('stock', 10))
        p.material = request.form.get('material')
        p.weight = request.form.get('weight')
        p.is_featured = 'is_featured' in request.form
        p.is_trending = 'is_trending' in request.form
        p.image_url_2 = request.form.get('image_url_2')
        p.image_url_3 = request.form.get('image_url_3')
        p.image_url_4 = request.form.get('image_url_4')
        db.session.commit()
        flash('Product updated!', 'success')
        return redirect(url_for('admin_products'))
    pending_orders, new_messages = get_admin_counts()
    return render_template('admin/add_product.html', product=p,
                           pending_orders=pending_orders, new_messages=new_messages)

@app.route('/admin/product/delete/<int:id>')
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

    if not User.query.filter_by(email='admin@zer.com').first():
        admin = User(name='ZÉR Admin', email='admin@zer.com',
                     password=generate_password_hash('ijazMalik5046564'), is_admin=True)
        db.session.add(admin)

    db.session.commit()

with app.app_context():
    db.create_all()
    seed_data()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)