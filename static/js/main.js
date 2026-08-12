/* ZÉR Jewellery — Main JavaScript */

// ─── Loader ────────────────────────────────────────────────────────────────
window.addEventListener('load', () => {
  setTimeout(() => {
    const loader = document.getElementById('loader');
    if (loader) loader.classList.add('hidden');
  }, 1600);
});

// ─── Navbar Scroll ──────────────────────────────────────────────────────────
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
  if (window.scrollY > 20) navbar.classList.add('scrolled');
  else navbar.classList.remove('scrolled');
}, { passive: true });

// ─── Mobile Nav ─────────────────────────────────────────────────────────────
const navToggle = document.getElementById('navToggle');
const navLinks = document.getElementById('navLinks');

if(navToggle){navToggle.addEventListener('click',()=>{
  if(navLinks.classList.contains('open')){
    navLinks.classList.remove('open');
    navLinks.removeAttribute('style');
  } else {
    navLinks.classList.add('open');
    navLinks.style.cssText='display:flex!important;position:fixed!important;top:72px!important;left:0!important;right:0!important;bottom:0!important;width:100%!important;height:calc(100vh - 72px)!important;background:#FAF7F2!important;z-index:999999!important;flex-direction:column!important;padding:1.5rem 2rem!important;overflow-y:auto!important;';
  }
  const spans=navToggle.querySelectorAll('span');
  if(navLinks.classList.contains('open')){
    spans[0].style.transform='rotate(45deg) translate(5px, 5px)';
    spans[1].style.opacity='0';
    spans[2].style.transform='rotate(-45deg) translate(5px, -5px)';
  } else {
    spans.forEach(s=>{s.style.transform='';s.style.opacity='';});
  }
});}

// ─── Theme Toggle ───────────────────────────────────────────────────────────
const themeToggle = document.getElementById('themeToggle');
const savedTheme = localStorage.getItem('zer-theme') || 'light';

if (savedTheme === 'dark') {
  document.documentElement.setAttribute('data-theme', 'dark');
  if (themeToggle) themeToggle.querySelector('i').className = 'fas fa-sun';
}

if (themeToggle) {
  themeToggle.addEventListener('click', () => {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';

    if (isDark) {
      document.documentElement.removeAttribute('data-theme');
      localStorage.setItem('zer-theme', 'light');
      themeToggle.querySelector('i').className = 'fas fa-moon';
    } else {
      document.documentElement.setAttribute('data-theme', 'dark');
      localStorage.setItem('zer-theme', 'dark');
      themeToggle.querySelector('i').className = 'fas fa-sun';
    }
  });
}

// ─── Search ─────────────────────────────────────────────────────────────────
const searchToggle = document.getElementById('searchToggle');
const searchClose = document.getElementById('searchClose');
const searchOverlay = document.getElementById('searchOverlay');
const searchInput = document.getElementById('searchInput');

if (searchToggle) {
  searchToggle.addEventListener('click', () => {
    searchOverlay.classList.toggle('active');
    if (searchOverlay.classList.contains('active')) searchInput.focus();
  });
}

if (searchClose) {
  searchClose.addEventListener('click', () => {
    searchOverlay.classList.remove('active');
  });
}

// ─── Toast Auto-dismiss ─────────────────────────────────────────────────────
document.querySelectorAll('.toast').forEach(toast => {
  setTimeout(() => {
    toast.style.transition = 'opacity .4s,transform .4s';
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(120%)';
    setTimeout(() => toast.remove(), 400);
  }, 6000);
});

// ─── Scroll Reveal ──────────────────────────────────────────────────────────
const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
      revealObserver.unobserve(entry.target);
    }
  });
}, { threshold: 0.1, rootMargin: '0px 0px -60px 0px' });

document.querySelectorAll('.reveal').forEach(el => revealObserver.observe(el));

// ─── Product Gallery (Detail Page) ─────────────────────────────────────────
const mainImg = document.querySelector('.main-image img');
const thumbs = document.querySelectorAll('.thumb');

thumbs.forEach(thumb => {
  thumb.addEventListener('click', () => {
    if (mainImg) mainImg.src = thumb.src;
    thumbs.forEach(t => t.classList.remove('active'));
    thumb.classList.add('active');
  });
});

// ─── Quantity Control ───────────────────────────────────────────────────────
document.querySelectorAll('.qty-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const input = btn.closest('.qty-control').querySelector('.qty-input');
    let val = parseInt(input.value) || 1;

    if (btn.dataset.action === 'minus') val = Math.max(1, val - 1);
    if (btn.dataset.action === 'plus') val = Math.min(99, val + 1);

    input.value = val;
  });
});

// ─── Wishlist Toggle ────────────────────────────────────────────────────────
document.querySelectorAll('.wishlist-btn').forEach(btn => {
  btn.addEventListener('click', async (e) => {
    e.preventDefault();
    const productId = btn.dataset.productId;
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';

    try {
      const resp = await fetch(`/wishlist/toggle/${productId}`, {
        method: 'POST',
        headers: {'X-CSRF-Token': csrf, 'Accept': 'application/json'}
      });
      const data = await resp.json();

      if (data.status === 'added') {
        btn.classList.add('active');
        btn.title = 'Remove from wishlist';
        showToast('Added to wishlist', 'success');
      } else if (data.status === 'removed') {
        btn.classList.remove('active');
        btn.title = 'Add to wishlist';
        showToast('Removed from wishlist', 'info');
      } else if (data.status === 'login_required') {
        showToast('Please log in to use wishlist', 'error');
        setTimeout(() => window.location.href = '/login', 1500);
      }
    } catch (err) {
      console.error(err);
    }
  });
});

// ─── Toast Helper ───────────────────────────────────────────────────────────
function showToast(msg, type = 'info') {
  const icons = {
    success: 'fa-check',
    error: 'fa-times',
    info: 'fa-info'
  };

  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');

  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span class="toast-icon"><i class="fas ${icons[type] || 'fa-info'}"></i></span>
    <span>${msg}</span>
    <button class="toast-close" onclick="this.parentElement.remove()">×</button>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.transition = 'opacity 0.4s, transform 0.4s';
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(120%)';
    setTimeout(() => toast.remove(), 400);
  }, 3500);
}

// ─── Dashboard Tabs ─────────────────────────────────────────────────────────
document.querySelectorAll('.dash-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.dash-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.dash-panel').forEach(p => p.classList.remove('active'));

    tab.classList.add('active');

    const target = document.getElementById(tab.dataset.panel);
    if (target) target.classList.add('active');
  });
});

// ─── Payment Method Selection ────────────────────────────────────────────────
document.querySelectorAll('.payment-option').forEach(opt => {
  opt.addEventListener('click', () => {
    document.querySelectorAll('.payment-option').forEach(o => o.classList.remove('selected'));
    opt.classList.add('selected');
    opt.querySelector('input[type="radio"]').checked = true;
  });
});

// ─── Star Rating ────────────────────────────────────────────────────────────
const starLabels = document.querySelectorAll('.star-rating label');

starLabels.forEach(label => {
  label.addEventListener('click', () => {
    const input = label.previousElementSibling;
    if (input && input.type === 'radio') input.checked = true;
  });
});

// ─── Hero Parallax ──────────────────────────────────────────────────────────
const heroImg = document.querySelector('.hero-image-wrap img');

if (heroImg) {
  window.addEventListener('scroll', () => {
    const scrolled = window.scrollY;
    heroImg.style.transform = `scale(1) translateY(${scrolled * 0.15}px)`;
  }, { passive: true });
}

// ─── Smooth Dropdown for Mobile ─────────────────────────────────────────────
if (window.innerWidth <= 768) {
  document.querySelectorAll('.nav-dropdown > .nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      link.closest('.nav-dropdown').classList.toggle('open');
    });
  });
}

// ─── Custom Cursor (Desktop only) ───────────────────────────────────────────
if (window.matchMedia('(pointer: fine)').matches) {
  const cursor = document.createElement('div');
  cursor.id = 'custom-cursor';
  cursor.style.cssText = `
    position: fixed;
    width: 8px;
    height: 8px;
    background: var(--gold);
    border-radius: 50%;
    pointer-events: none;
    z-index: 99999;
    transform: translate(-50%, -50%);
    transition: transform 0.15s, width 0.3s, height 0.3s, opacity 0.3s;
    mix-blend-mode: multiply;
  `;

  const cursorRing = document.createElement('div');
  cursorRing.id = 'cursor-ring';
  cursorRing.style.cssText = `
    position: fixed;
    width: 32px;
    height: 32px;
    border: 1px solid var(--gold);
    border-radius: 50%;
    pointer-events: none;
    z-index: 99998;
    transform: translate(-50%, -50%);
    transition: all 0.4s cubic-bezier(0.25,0.1,0.25,1);
    opacity: 0.5;
  `;

  document.body.appendChild(cursor);
  document.body.appendChild(cursorRing);

  let mx = 0, my = 0;

  document.addEventListener('mousemove', e => {
    mx = e.clientX;
    my = e.clientY;

    cursor.style.left = mx + 'px';
    cursor.style.top = my + 'px';

    setTimeout(() => {
      cursorRing.style.left = mx + 'px';
      cursorRing.style.top = my + 'px';
    }, 80);
  });

  document.querySelectorAll('a, button, .product-card').forEach(el => {
    el.addEventListener('mouseenter', () => {
      cursor.style.width = '16px';
      cursor.style.height = '16px';
      cursorRing.style.width = '48px';
      cursorRing.style.height = '48px';
      cursorRing.style.opacity = '0.3';
    });

    el.addEventListener('mouseleave', () => {
      cursor.style.width = '8px';
      cursor.style.height = '8px';
      cursorRing.style.width = '32px';
      cursorRing.style.height = '32px';
      cursorRing.style.opacity = '0.5';
    });
  });
}

// ─── Lazy Load Images ───────────────────────────────────────────────────────
if ('IntersectionObserver' in window) {
  const imgObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const img = entry.target;

        if (img.dataset.src) {
          img.src = img.dataset.src;
          img.removeAttribute('data-src');
          imgObserver.unobserve(img);
        }
      }
    });
  }, { rootMargin: '200px' });

  document.querySelectorAll('img[data-src]').forEach(img => imgObserver.observe(img));
}

// ─── Admin: Confirm Delete ──────────────────────────────────────────────────
document.querySelectorAll('.confirm-delete').forEach(btn => {
  btn.addEventListener('click', (e) => {
    if (!confirm('Are you sure you want to delete this item?')) {
      e.preventDefault();
    }
  });
});

// ─── Quick add cart feedback ─────────────────────────────────────────────────
document.querySelectorAll('form[action*="add_to_cart"]').forEach(form => {
  form.addEventListener('submit', () => {
    const btn = form.querySelector('[type="submit"]');

    if (btn) {
      const orig = btn.textContent;
      btn.textContent = 'Adding...';
      btn.style.opacity = '0.7';

      setTimeout(() => {
        btn.textContent = orig;
        btn.style.opacity = '';
      }, 1500);
    }
  });
});