# ZÉR Jewellery — Luxury E-Commerce Website

A complete premium luxury jewellery e-commerce website built with Flask, SQLite, and vanilla HTML/CSS/JS.

---

## 🚀 Quick Start

### 1. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the App
```bash
python app.py
```

### 3. Open in Browser
```
http://localhost:5000
```

The database is auto-created and seeded with 16 jewellery products on first run.

---

## 🔐 Admin Access

- **URL:** `http://localhost:5000/admin`
- **Email:** `admin@zer.com`
- **Password:** `admin123`

---

## 📁 Project Structure

```
zer/
├── app.py                   # Main Flask application (routes + models)
├── requirements.txt
├── README.md
├── static/
│   ├── css/
│   │   └── main.css         # Complete luxury CSS
│   ├── js/
│   │   └── main.js          # All JavaScript interactions
│   └── images/
│       └── logo.jpeg        # ZÉR brand logo
└── templates/
    ├── base.html            # Base layout (navbar, footer, loader)
    ├── home.html            # Home page
    ├── shop.html            # Shop / category page
    ├── product.html         # Product detail + reviews
    ├── cart.html            # Shopping cart
    ├── checkout.html        # Checkout form
    ├── order_confirmed.html # Order success
    ├── login.html           # Login
    ├── signup.html          # Register
    ├── dashboard.html       # User dashboard
    ├── about.html           # About the brand
    ├── contact.html         # Contact page
    └── admin/
        ├── base.html        # Admin layout
        ├── dashboard.html   # Admin stats
        ├── products.html    # Product management
        ├── add_product.html # Add / edit product
        ├── orders.html      # Order management
        ├── users.html       # User management
        └── messages.html    # Contact messages
```

---

## ✨ Features

**Frontend**
- Luxury editorial design with Cormorant Garamond + Jost typography
- Animated loading screen, scroll reveal, custom cursor
- Dark / light mode toggle
- Fully responsive (mobile, tablet, desktop)
- Product image zoom, gallery thumbnails
- Toast notifications, smooth transitions

**E-Commerce**
- Add to cart, update quantities, remove items
- Wishlist (logged-in users)
- Product filtering by category + search + sort
- Checkout with multiple payment methods
- Order tracking in dashboard

**Backend**
- Flask + SQLAlchemy ORM
- SQLite database (auto-created)
- Secure password hashing (Werkzeug)
- Session management
- Admin panel with full CRUD
- Newsletter + contact message storage

---

## 🎨 Brand

- **Name:** ZÉR (Persian for "gold")
- **Palette:** Ivory cream, warm beige, matte black, soft gold
- **Typography:** Cormorant Garamond (headings) + Jost (body)
- **Vibe:** Quiet luxury, editorial fashion, feminine, minimal
