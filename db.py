"""NIVORA Shop Bot — Database Layer (SQLite) | M2: services catalog, request-based orders"""
import sqlite3
import time
from pathlib import Path

DB_FILE = Path(__file__).parent / 'shop.db'


def connect():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL DEFAULT '',
    username TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    last_seen REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    customer_name TEXT NOT NULL,
    contact TEXT NOT NULL,
    brief TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS inquiries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    text TEXT NOT NULL,
    answer TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'human',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    action TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS bans (
    user_id INTEGER PRIMARY KEY,
    reason TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    inquiry_id INTEGER,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL DEFAULT 'photo',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_interactions_user ON interactions(user_id);
"""

SEED = {
    'categories': [
        ('أتمتة ومشاريع Python',),
        ('Websites',),
        ('تصميم وإبداع',),
        ('Notion',),
    ],
    'products': [
        (1, 'تطوير بوتات المحادثة', 'بوتات تليجرام وواتساب للمتاجر والشركات: استقبال الطلبات، خدمة العملاء، والتنبيهات الفورية'),
        (1, 'تحليل البيانات ولوحات المعلومات', 'تحويل بياناتك ومبيعاتك إلى تقارير ولوحات تفاعلية تدعم قراراتك'),
        (1, 'أتمتة العمليات والأعمال', 'برمجة المهام المتكررة وربط الأدوات والأنظمة ببعضها لتوفير الوقت وتقليل الأخطاء'),
        (2, 'إنشاء مواقع كاملة', 'مواقع احترافية متجاوبة مع جميع الأجهزة، سريعة ومهيأة لمحركات البحث'),
        (2, 'Landing Pages', 'صفحات هبوط احترافية عالية التحويل لخدماتك ومنتجاتك وحملاتك التسويقية'),
        (2, 'إنشاء صفحات HTML', 'صفحات ويب أنيقة وسريعة جاهزة للنشر بأي عدد'),
        (2, 'منصات ويب متكاملة', 'أنظمة ويب متقدمة حسب احتياجك: لوحات تحكم، إدارة مستخدمين، وتقارير'),
        (3, 'عروض تقديمية احترافية', 'جميع الأنواع: شركات، ستارت أب، أكاديمية — تصميم يحكي قصة (تخصصنا)'),
        (3, 'تصميم الهوية البصرية واللوجوهات', 'شعار مميز + ألوان وخطوط + تطبيقات الهوية كاملة'),
        (3, 'تصاميم السوشيال ميديا', 'بوستات وكاروسيلات بهوية متسقة، جاهزة للنشر'),
        (3, 'حملة تسويقية شاملة للعلامة التجارية', 'من الهوية إلى المحتوى: كامبين كامل متكامل لبراندك'),
        (4, 'أنظمة Notion متكاملة', 'قواعد بيانات ولوحات مترابطة لإدارة أعمالك في مكان واحد'),
        (4, 'قوالب Notion', 'قوالب جاهزة لمجالك أو إعادة تنظيم مساحتك باحترافية'),
    ],
}


def init_db():
    conn = connect()
    conn.executescript(SCHEMA)
    if conn.execute('SELECT COUNT(*) c FROM categories').fetchone()['c'] == 0:
        conn.executemany('INSERT INTO categories(name) VALUES (?)', SEED['categories'])
        conn.executemany(
            'INSERT INTO products(category_id, name, description) VALUES (?,?,?)',
            SEED['products'])
    conn.commit()
    conn.close()


def upsert_user(chat_id, first_name='', username=''):
    now = time.time()
    conn = connect()
    conn.execute(
        'INSERT INTO users(chat_id, first_name, username, created_at, last_seen) VALUES (?,?,?,?,?) '
        'ON CONFLICT(chat_id) DO UPDATE SET first_name=excluded.first_name, '
        'username=excluded.username, last_seen=excluded.last_seen',
        (str(chat_id), first_name[:60], (username or '')[:60], now, now))
    conn.commit()
    row = conn.execute('SELECT id FROM users WHERE chat_id=?', (str(chat_id),)).fetchone()
    conn.close()
    return row['id']


def log_action(user_id, action):
    conn = connect()
    conn.execute('INSERT INTO interactions(user_id, action, created_at) VALUES (?,?,?)',
                 (user_id, action[:40], time.time()))
    conn.commit()
    conn.close()


def get_categories():
    conn = connect()
    rows = conn.execute('SELECT id, name FROM categories ORDER BY id').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_products(category_id):
    conn = connect()
    rows = conn.execute(
        'SELECT id, name, description FROM products WHERE category_id=? ORDER BY id',
        (category_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_product(product_id):
    conn = connect()
    row = conn.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_order(user_id, product_id, customer_name, contact, brief):
    if not customer_name.strip() or not contact.strip() or not brief.strip():
        return None
    conn = connect()
    cur = conn.execute(
        'INSERT INTO orders(user_id, product_id, customer_name, contact, brief, created_at) '
        'VALUES (?,?,?,?,?,?)',
        (user_id, product_id, customer_name.strip()[:60], contact.strip()[:80], brief.strip()[:600], time.time()))
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id


def order_full(order_id):
    conn = connect()
    row = conn.execute(
        'SELECT o.id, o.customer_name, o.contact, o.brief, o.status, o.created_at, '
        'p.name AS service_name FROM orders o '
        'JOIN products p ON p.id = o.product_id WHERE o.id=?', (order_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_inquiry(user_id, text, answer='', source='human'):
    conn = connect()
    cur = conn.execute(
        'INSERT INTO inquiries(user_id, text, answer, source, created_at) VALUES (?,?,?,?,?)',
        (user_id, text[:500], answer[:1000], source, time.time()))
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def update_inquiry(inquiry_id, answer, source):
    conn = connect()
    conn.execute('UPDATE inquiries SET answer=?, source=? WHERE id=?',
                 ((answer or '')[:1000], source[:20], inquiry_id))
    conn.commit()
    conn.close()


def search_products(text):
    """Free-text routing: score products by words appearing in name+description."""
    import re as _re
    words = [w for w in _re.split(r'[\s،.,؟!?]+', text) if len(w) >= 3]
    if not words:
        return []
    conn = connect()
    rows = conn.execute('SELECT id, name, description FROM products').fetchall()
    conn.close()
    scored = []
    for p in rows:
        hay = (p['name'] + ' ' + p['description'])
        score = sum(1 for w in words if w in hay)
        if score:
            scored.append({'id': p['id'], 'name': p['name'], 'score': score})
    scored.sort(key=lambda x: -x['score'])
    return scored[:2]


def stats_summary():
    conn = connect()
    users = conn.execute('SELECT COUNT(*) c FROM users').fetchone()['c']
    orders = conn.execute('SELECT COUNT(*) c FROM orders').fetchone()['c']
    new_orders = conn.execute("SELECT COUNT(*) c FROM orders WHERE status='new'").fetchone()['c']
    inquiries = conn.execute('SELECT COUNT(*) c FROM inquiries').fetchone()['c']
    conn.close()
    return {'users': users, 'orders': orders, 'new_orders': new_orders, 'inquiries': inquiries}


def orders_recent(limit=5):
    conn = connect()
    rows = conn.execute(
        'SELECT o.id, o.customer_name, o.contact, o.brief, o.status, p.name AS service_name '
        'FROM orders o JOIN products p ON p.id = o.product_id '
        'ORDER BY o.id DESC LIMIT ?', (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def is_banned(user_id):
    conn = connect()
    row = conn.execute('SELECT 1 FROM bans WHERE user_id=?', (user_id,)).fetchone()
    conn.close()
    return row is not None


def ban_user(user_id, reason=''):
    conn = connect()
    conn.execute('INSERT OR IGNORE INTO bans(user_id, reason, created_at) VALUES (?,?,?)',
                 (user_id, reason[:200], time.time()))
    conn.commit()
    conn.close()


def unban_user(user_id):
    conn = connect()
    conn.execute('DELETE FROM bans WHERE user_id=?', (user_id,))
    conn.commit()
    conn.close()


def user_orders(user_id):
    conn = connect()
    rows = conn.execute(
        'SELECT o.id, o.status, o.created_at, p.name AS service_name '
        'FROM orders o JOIN products p ON p.id = o.product_id '
        'WHERE o.user_id=? ORDER BY o.id DESC LIMIT 5', (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_media(user_id, file_path, file_type='photo', inquiry_id=None):
    conn = connect()
    conn.execute('INSERT INTO media(user_id, inquiry_id, file_path, file_type, created_at) VALUES (?,?,?,?,?)',
                 (user_id, inquiry_id, str(file_path)[:300], file_type[:20], time.time()))
    conn.commit()
    conn.close()


def all_user_chat_ids():
    conn = connect()
    rows = conn.execute('SELECT chat_id FROM users').fetchall()
    conn.close()
    return [r['chat_id'] for r in rows]
