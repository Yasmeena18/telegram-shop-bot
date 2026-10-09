"""Unit Tests — Database Layer | M2 (python -m unittest discover -s tests)"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import db

db.DB_FILE = Path(__file__).parent.parent / 'test_shop.db'
if db.DB_FILE.exists():
    db.DB_FILE.unlink()


class TestDB(unittest.TestCase):

    def setUp(self):
        db.init_db()

    def test_seed_loaded(self):
        cats = db.get_categories()
        self.assertEqual(len(cats), 4)
        counts = [len(db.get_products(c['id'])) for c in cats]
        self.assertEqual(counts, [3, 4, 4, 2])
        total = sum(counts)
        self.assertEqual(total, 13)

    def test_no_prices_anywhere(self):
        for cat in db.get_categories():
            for p in db.get_products(cat['id']):
                self.assertNotIn('price', p)

    def test_user_upsert_idempotent(self):
        a = db.upsert_user('111', 'مستخدم', 'test_user')
        b = db.upsert_user('111', 'مستخدم', 'test_user')
        self.assertEqual(a, b)

    def test_order_created(self):
        uid = db.upsert_user('222', 'عميل', 'client')
        oid = db.create_order(uid, 4, 'محمد أحمد', '01012345678', 'عايز موقع لشركتي 5 صفحات')
        self.assertIsNotNone(oid)
        full = db.order_full(oid)
        self.assertEqual(full['customer_name'], 'محمد أحمد')
        self.assertEqual(full['service_name'], 'إنشاء مواقع كاملة')
        self.assertIn('شركتي', full['brief'])

    def test_order_rejected_missing_fields(self):
        uid = db.upsert_user('333', 'ناقص', 'missing')
        self.assertIsNone(db.create_order(uid, 1, '', '0100', 'وصف'))
        self.assertIsNone(db.create_order(uid, 1, 'اسم', '  ', 'وصف'))
        self.assertIsNone(db.create_order(uid, 1, 'اسم', '0100', ''))

    def test_stats_and_recent(self):
        uid = db.upsert_user('444', 'احصاء', 'stats')
        db.create_order(uid, 1, 'سارة', 'email@x.com', 'اتمته لصفحتي')
        s = db.stats_summary()
        self.assertGreaterEqual(s['orders'], 1)
        self.assertEqual(s['new_orders'], s['orders'])
        r = db.orders_recent(5)
        self.assertEqual(r[0]['customer_name'], 'سارة')

    def test_inquiry_saved_with_id(self):
        uid = db.upsert_user('555', 'سائل', 'asker')
        iid = db.save_inquiry(uid, 'بتشتغلوا ازاي؟', '', 'pending')
        self.assertIsInstance(iid, int)
        db.update_inquiry(iid, 'أيوه', 'ai')
        self.assertGreaterEqual(db.stats_summary()['inquiries'], 1)

    def test_search_products(self):
        hits = db.search_products('عايز مواقع لمشروعي')
        self.assertTrue(any('مواقع' in h['name'] for h in hits))
        self.assertEqual(db.search_products('kkk zzz'), [])

    def test_ban_flow(self):
        uid = db.upsert_user('777', 'مزعج', 'spammer')
        self.assertFalse(db.is_banned(uid))
        db.ban_user(uid, 'سبام')
        self.assertTrue(db.is_banned(uid))
        db.unban_user(uid)
        self.assertFalse(db.is_banned(uid))

    def test_user_orders(self):
        uid = db.upsert_user('888', 'طلب', 'orderer')
        oid = db.create_order(uid, 1, 'منى', '0123', 'اتمته للمتجر')
        rows = db.user_orders(uid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['status'], 'new')

    def test_broadcast_list(self):
        self.assertIsInstance(db.all_user_chat_ids(), list)


if __name__ == '__main__':
    unittest.main()
