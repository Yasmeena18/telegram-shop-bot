"""Unit Tests — Order Wizard Logic | M2"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from flow import (OrderFlow, InquiryFlow, is_question, looks_like_contact,
                  v_name, v_contact, v_brief)

FAKE_PHONE = '01000000001'
FAKE_USER = '@test_user'


class TestContactDetection(unittest.TestCase):

    def test_numbers_detected(self):
        self.assertTrue(looks_like_contact(FAKE_PHONE))
        self.assertTrue(looks_like_contact('واتساب: 0100 123 4567'))

    def test_usernames_detected(self):
        self.assertTrue(looks_like_contact(FAKE_USER))

    def test_questions_not_contact(self):
        self.assertFalse(looks_like_contact('عايز اعرف اسعاركم'))
        self.assertFalse(looks_like_contact('@'))


class TestQuestionDetection(unittest.TestCase):

    def test_questions_detected(self):
        self.assertTrue(is_question('عايز اسال عن شرح البرمجه عندكم'))
        self.assertTrue(is_question('بتعملوا مواقع ووردبريس؟'))
        self.assertTrue(is_question('ازاي اطلب منكم؟'))
        self.assertTrue(is_question('عندكم خدمات تصميم؟'))

    def test_data_not_flagged(self):
        self.assertFalse(is_question('محمد أحمد علي'))
        self.assertFalse(is_question('01012345678'))
        self.assertFalse(is_question('عايز موقع لشركة مقاولات خمس صفحات'))


class TestValidators(unittest.TestCase):

    def test_name(self):
        self.assertIsNone(v_name('ا'))
        self.assertIsNone(v_name(''))
        self.assertEqual(v_name('  محمد أحمد  '), 'محمد أحمد')

    def test_contact(self):
        self.assertIsNone(v_contact('1'))
        self.assertEqual(v_contact('01012345678'), '01012345678')
        self.assertEqual(v_contact(FAKE_USER), FAKE_USER)

    def test_brief(self):
        self.assertIsNone(v_brief('قصير'))
        self.assertEqual(v_brief('عايز موقع لشركة مقاولات 5 صفحات'), 'عايز موقع لشركة مقاولات 5 صفحات')
        self.assertIsNone(v_brief('x' * 601))


class TestWizard(unittest.TestCase):

    def test_full_flow(self):
        f = OrderFlow()
        hint = f.start(3, 'موقع WordPress احترافي')
        self.assertIn('اسمك', hint)
        kind, _ = f.feed('محمد أحمد')
        self.assertEqual(kind, 'next')
        kind, _ = f.feed('01012345678')
        self.assertEqual(kind, 'next')
        kind, summary = f.feed('موقع لشركتي 5 صفحات مع لوحة تحكم')
        self.assertEqual(kind, 'confirm')
        self.assertIn('موقع WordPress', summary)
        self.assertIn('محمد أحمد', summary)
        payload = f.confirm()
        self.assertEqual(payload['service_id'], 3)
        self.assertEqual(payload['contact'], '01012345678')
        self.assertFalse(f.active)

    def test_invalid_then_retry(self):
        f = OrderFlow()
        f.start(1, 'خدمة')
        kind, msg = f.feed('')
        self.assertEqual(kind, 'error')
        self.assertIn('اسمك', msg)
        kind, _ = f.feed('اسم صحيح')
        self.assertEqual(kind, 'next')

    def test_cancel(self):
        f = OrderFlow()
        f.start(1, 'خدمة')
        kind, payload = f.feed('إلغاء')
        self.assertEqual(kind, 'done')
        self.assertFalse(f.active)

    def test_confirm_without_steps_rejected(self):
        f = OrderFlow()
        self.assertIsNone(f.confirm())


class TestInquiryFlow(unittest.TestCase):

    def test_two_stage_flow(self):
        f = InquiryFlow()
        intro = f.start()
        self.assertIn('استفسارك', intro)
        self.assertTrue(f.active)
        ask = f.receive_text('عايز اعرف عن خدمات المواقع')
        self.assertIn('واتساب', ask)
        self.assertEqual(f.stage, 'contact')
        closing = f.finish(FAKE_PHONE)
        self.assertIn('أقرب وقت', closing)
        self.assertFalse(f.active)

    def test_not_active_by_default(self):
        f = InquiryFlow()
        self.assertFalse(f.active)


if __name__ == '__main__':
    unittest.main()
