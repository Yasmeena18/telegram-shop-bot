"""NIVORA Shop Bot — Order Wizard Logic (pure, testable) | M2"""


QUESTION_MARKERS = (
    '؟', 'عايز اسال', 'عيز اسال', 'اسال', 'سؤال', 'استفسر', 'استفسار عن',
    'هل ', 'ازاي ', 'إزاي ', 'ايه ', 'إيه ', 'ليه ', 'امتى ', 'إمتى ', 'فين ',
    'كام ', 'مين ', 'ممكن اعرف', 'بتعملوا', 'بتشتغلوا', 'عندكم ',
)


def is_question(text):
    t = ' ' + (text or '').strip() + ' '
    for m in QUESTION_MARKERS:
        if m in t:
            return True
    return False


def v_name(text):
    t = (text or '').strip()
    if len(t) < 2 or len(t) > 60:
        return None
    return t


def v_contact(text):
    t = (text or '').strip()
    if len(t) < 3 or len(t) > 80:
        return None
    return t


def v_brief(text):
    t = (text or '').strip()
    if len(t) < 5 or len(t) > 600:
        return None
    return t


VALIDATORS = {'name': v_name, 'contact': v_contact, 'brief': v_brief}
HINTS = {
    'name': 'اسمك الكامل:',
    'contact': 'رقم موبايل أو يوزر تليجرام أو إيميل للتواصل:',
    'brief': 'احكيلنا باختصار عن مشروعك:',
}

INQ_INTRO = 'اكتب استفسارك، وبعدها سيب رقم واتساب أو يوزر تليجرام وهنتواصل معاك في أقرب وقت 📝'
INQ_ASK_CONTACT = 'سيب رقم واتساب أو يوزر تليجرام وهنتواصل معاك 👇'
INQ_CLOSING = 'سيتم التواصل مع حضرتك في أقرب وقت ✅'


def looks_like_contact(text):
    t = (text or '').strip()
    if t.startswith('@') and 4 <= len(t) <= 40:
        return True
    digits = ''.join(c for c in t if c.isdigit())
    return len(digits) >= 7


class OrderFlow:
    """State machine: service -> name -> contact -> brief -> confirm -> done"""

    def __init__(self):
        self.reset()

    def reset(self):
        self.step = None
        self.service_id = None
        self.service_name = None
        self.data = {}

    @property
    def active(self):
        return self.step is not None

    def start(self, service_id, service_name):
        self.reset()
        self.service_id = service_id
        self.service_name = service_name
        self.step = 'name'
        return HINTS['name']

    def feed(self, text):
        """Returns tuple: (kind, payload)
        kind in {'error', 'next', 'confirm', 'done'}
        """
        if not self.active:
            return ('error', 'لا يوجد طلب جاري.')
        if (text or '').strip() == 'إلغاء':
            self.reset()
            return ('done', None)
        validator = VALIDATORS.get(self.step)
        value = validator(text) if validator else None
        if value is None:
            return ('error', HINTS[self.step] + '\n\n(بيانات غير صالحة — حاول تاني أو اكتب "إلغاء")')
        self.data[self.step] = value
        if self.step == 'name':
            self.step = 'contact'
            return ('next', HINTS['contact'])
        if self.step == 'contact':
            self.step = 'brief'
            return ('next', HINTS['brief'])
        if self.step == 'brief':
            self.step = 'confirm'
            return ('confirm', self.summary())
        return ('error', 'حالة غير معروفة')

    def summary(self):
        return ('تأكيد الطلب:\n\n'
                '🛠️ الخدمة: ' + (self.service_name or '-') +
                '\n👤 الاسم: ' + self.data.get('name', '-') +
                '\n📞 التواصل: ' + self.data.get('contact', '-') +
                '\n📝 المشروع: ' + self.data.get('brief', '-'))

    def confirm(self):
        if self.step != 'confirm':
            return None
        payload = {
            'service_id': self.service_id,
            'service_name': self.service_name,
            'name': self.data.get('name'),
            'contact': self.data.get('contact'),
            'brief': self.data.get('brief'),
        }
        self.reset()
        return payload

    def edit(self, field):
        """Return to a previous step to re-enter it (keeps other data)."""
        if field in VALIDATORS and self.data:
            self.step = field
            return HINTS[field]
        return None


class InquiryFlow:
    """Two-stage inquiry: text -> contact -> done. Silent by design."""

    def __init__(self):
        self.stage = None
        self.text = None
        self.contact = None

    @property
    def active(self):
        return self.stage is not None

    def start(self):
        self.stage = 'text'
        return INQ_INTRO

    def receive_text(self, text):
        self.text = (text or '').strip()[:500]
        self.stage = 'contact'
        return INQ_ASK_CONTACT

    def finish(self, contact):
        self.contact = (contact or '').strip()[:80]
        self.stage = None
        return INQ_CLOSING
