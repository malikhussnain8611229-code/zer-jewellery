# ZÉR production security

Before deploying, set these environment variables on the server:

- `SECRET_KEY`: a long random secret; never commit it.
- `ADMIN_EMAIL`: the admin login email you want to use.
- `ADMIN_PASSWORD`: a strong admin password of at least 12 characters.
- `SESSION_COOKIE_SECURE=1` when the site is served over HTTPS.

The application now:
- protects state-changing requests with CSRF tokens;
- uses secure HttpOnly/SameSite session cookies;
- no longer trusts cart prices from the browser;
- validates stock again at checkout and decrements stock atomically;
- prevents negative/oversized cart quantities;
- makes cart removal and logout POST-only;
- adds security response headers and HSTS on HTTPS;
- removes the hard-coded admin password from source code;
- validates user/product/contact inputs;
- throttles repeated login failures;
- avoids open redirects from cart actions.

If the existing production database still contains the old admin account, set `ADMIN_EMAIL` to that same admin email and `ADMIN_PASSWORD` to the new password before restarting. The app will rotate that account's password on startup.
