"""NIVORA Shop Bot — Main Engine + UI (Final: M2+M3+M4) | Python stdlib only"""
import json
import logging
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

import ai
import db
from flow import OrderFlow, InquiryFlow, is_question, looks_like_contact, INQ_ASK_CONTACT

BASE = Path(__file__).parent
CONFIG_FILE = BASE / 'config.json'
LOG_FILE = BASE / 'bot.log'
STATE_FILE = BASE / 'state.json'

logging.basicConfig(
    filename=LOG_FILE, level=logging.INFO, encoding='utf-8',
    format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('shopbot')

ABOUT_TEXT = (
    'NIVORA | خدمات رقمية متكاملة\n\n'
    'نطوّر بوتات المحادثة وأنظمة الأتمتة ولوحات تحليل البيانات بلغة Python، '
    'ونُنشئ المواقع الكاملة وصفحات الهبوط والمنصات، '
    'ونقدّم تصميم الهوية البصرية والعروض التقديمية وتصاميم السوشيال ميديا، '
    'ونبني أنظمة Notion متكاملة.\n\n'
    'التزام بالمواعيد، تواصل واضح، وجودة لا تقبل الحلول الوسط.\n\n'
    'للطلب أو الاستفسار — استخدم الأزرار تحت 👇')

WELCOME = ('أهلاً بيك في NIVORA 🛒\n\n'
           'دي خدماتنا كاملة بالأقسام 👇')

ORDER_FLOWS = {}
INQ_FLOWS = {}
PENDING_TEXTS = {}
RATE = {}
CANCEL_WORDS = ('إلغاء', 'الغاء', 'إلغاء الطلب', 'الغاء الطلب', 'cancel')
CATALOG_WORDS = ('خدمات', 'خدماتكم', 'خدمة', 'اقسام', 'أقسام', 'الأقسام', 'منيو', 'المنيو',
                 'القائمة', 'قائمة', 'بيعملوا', 'بتقدموا', 'اعرض', 'أعرض', 'اشوف', 'أشوف',
                 'عندكم ايه', 'عندك ايه', 'موقع', 'مواقع', 'ويبسايت', 'ويب سايت', 'لاندنج')
RATE_LIMIT = 8
RATE_WINDOW = 60


def clear_flows(user_id):
    ORDER_FLOWS.pop(user_id, None)
    INQ_FLOWS.pop(user_id, None)


def rate_ok(user_id):
    now = time.time()
    hits = [t for t in RATE.get(user_id, []) if now - t < RATE_WINDOW]
    hits.append(now)
    RATE[user_id] = hits
    return len(hits) <= RATE_LIMIT


def cb_id(data):
    try:
        return int(data.split(':')[1])
    except Exception:
        return None


def load_config():
    if not CONFIG_FILE.exists():
        raise SystemExit('config.json غير موجود — انسخي config.example.json واملئيه')
    cfg = json.loads(CONFIG_FILE.read_text(encoding='utf-8-sig'))
    for key in ('bot_token', 'owner_chat_id'):
        if not str(cfg.get(key, '')).strip() or 'PUT_' in str(cfg.get(key, '')).upper():
            raise SystemExit('config.json ناقص: ' + key)
    return cfg


def tg(token, method, params=None, timeout=35):
    url = 'https://api.telegram.org/bot%s/%s' % (token, method)
    data = urllib.parse.urlencode(params).encode() if params is not None else None
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def send(token, chat_id, text, keyboard=None, retries=2):
    params = {'chat_id': chat_id, 'text': text[:4000]}
    if keyboard:
        params['reply_markup'] = json.dumps(keyboard, ensure_ascii=False)
    for attempt in range(retries + 1):
        try:
            return tg(token, 'sendMessage', params)
        except Exception as e:
            if attempt == retries:
                log.error('send failed chat=%s: %s', chat_id, str(e)[:120])
                return None
            time.sleep(2 * (attempt + 1))


def edit_msg(token, chat_id, message_id, text, keyboard=None):
    params = {'chat_id': chat_id, 'message_id': message_id, 'text': text[:4000]}
    if keyboard:
        params['reply_markup'] = json.dumps(keyboard, ensure_ascii=False)
    try:
        return tg(token, 'editMessageText', params)
    except Exception as e:
        if 'not modified' in str(e):
            return None
        return send(token, chat_id, text, keyboard)


def cb_answer(token, callback_id, text=''):
    try:
        tg(token, 'answerCallbackQuery', {'callback_query_id': callback_id, 'text': text[:180]})
    except Exception:
        pass


def inline(rows):
    return {'inline_keyboard': rows}


def kb_main():
    # Home = categories directly (no extra click needed)
    return kb_cats()


def kb_cats():
    rows = [[{'text': c['name'], 'callback_data': 'cat:%d' % c['id']}] for c in db.get_categories()]
    rows.append([{'text': '💬 استفسار', 'callback_data': 'ask'}, {'text': '📦 طلباتي', 'callback_data': 'myorders'}])
    rows.append([{'text': 'ℹ️ عن NIVORA', 'callback_data': 'about'}, {'text': '🚀 ابدأ من الأول', 'callback_data': 'restart'}])
    return inline(rows)


def kb_services(cat_id):
    rows = [[{'text': p['name'], 'callback_data': 'svc:%d' % p['id']}] for p in db.get_products(cat_id)]
    rows.append([{'text': '🔙 الأقسام', 'callback_data': 'cats'}, {'text': '🏠 الرئيسية', 'callback_data': 'menu'}])
    return inline(rows)


def kb_service(svc_id):
    return inline([
        [{'text': '📩 اطلب الخدمة دي', 'callback_data': 'order:%d' % svc_id}],
        [{'text': '🔙 الخدمات', 'callback_data': 'cat_service:%d' % svc_id},
         {'text': '🏠 الرئيسية', 'callback_data': 'menu'}],
    ])


def kb_wizard(cancel_data):
    return inline([[{'text': '🏠 الرئيسية', 'callback_data': 'menu'},
                    {'text': '❌ إلغاء', 'callback_data': cancel_data}]])


def start_inquiry(token, chat_id, user_id):
    ORDER_FLOWS.pop(user_id, None)
    flow = InquiryFlow()
    INQ_FLOWS[user_id] = flow
    send(token, chat_id, flow.start())


def process_inquiry(cfg, chat_id, user_id, text, first_name, username):
    """Receive an inquiry text: AI answer (threaded) + ask for contact. One message only."""
    token = cfg['bot_token']
    flow = INQ_FLOWS.get(user_id) or InquiryFlow()
    INQ_FLOWS[user_id] = flow
    flow.receive_text(text)
    inquiry_id = db.save_inquiry(user_id, text, '', 'pending')

    def worker():
        answer = None
        if cfg.get('ai_enabled') and cfg.get('gemini_api_key'):
            answer = ai.ask_gemini(cfg['gemini_api_key'], text)
        db.update_inquiry(inquiry_id, answer or '', 'ai' if answer else 'human')
        reply = answer if answer else INQ_ASK_CONTACT
        send(token, chat_id, reply)

    threading.Thread(target=worker, daemon=True).start()


WA_BRIDGE = r"C:\Users\deel\Desktop\web\tools\wa-bridge\wa_desktop_send.py"


def wa_notify(cfg, text):
    """Owner notifications to her WhatsApp — via her logged-in WhatsApp Desktop app."""
    phone = cfg.get('wa_phone', '')
    if not phone:
        return False
    import threading
    result = {'ok': False}

    def _run():
        try:
            import subprocess as _sp
            r = _sp.run([sys.executable, WA_BRIDGE, phone.lstrip('+'), text],
                        capture_output=True, timeout=45)
            result['ok'] = (r.returncode == 0)
        except Exception as e:
            log.error('wa desktop: %s', str(e)[:120])

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=50)
    return result['ok']


def mail_notify(cfg, text):
    """Owner alerts to her Gmail via SMTP SSL (Google app password)."""
    try:
        to = cfg.get('mail_to', '')
        key = cfg.get('mail_appkey', '')
        if not to or not key:
            return False
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(text, 'plain', 'utf-8')
        msg['Subject'] = 'NIVORA | تنبيه جديد'
        msg['From'] = to
        msg['To'] = to
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=20) as s:
            s.login(to, key)
            s.send_message(msg)
        return True
    except Exception as e:
        log.error('mail_notify: %s', str(e)[:120])
        return False


def owner_notify(cfg, text):
    """Alerts chain: WhatsApp (if configured) → Gmail → Internal Alerts bot → shop bot (last resort)."""
    if wa_notify(cfg, text):
        return
    if mail_notify(cfg, text):
        return
    alerts_token = cfg.get('alerts_bot_token', '')
    if alerts_token:
        try:
            send(alerts_token, str(cfg['owner_chat_id']), text)
            return
        except Exception as e:
            log.error('owner_notify alerts: %s', str(e)[:120])
    send(cfg['bot_token'], str(cfg['owner_chat_id']), '(احتياط) ' + text)


def finish_inquiry(cfg, chat_id, user_id, contact, first_name, username):
    """Contact received: exact closing line + ONE clean owner notification. Nothing else."""
    token = cfg['bot_token']
    flow = INQ_FLOWS.pop(user_id, None)
    stored_text = flow.text if flow and flow.text else '(استفسار بدون نص)'
    conn = db.connect()
    row = conn.execute('SELECT id, answer FROM inquiries WHERE user_id=? ORDER BY id DESC LIMIT 1',
                       (user_id,)).fetchone()
    conn.close()
    if row:
        db.update_inquiry(row['id'], (row['answer'] or '') + ' | تواصل: ' + contact, 'ai')
    send(token, chat_id, 'سيتم التواصل مع حضرتك في أقرب وقت ✅')
    answer_line = ('\n🤖 الرد: ' + row['answer']) if row and row['answer'] else ''
    text = ('🔔 استفسار جديد\n👤 %s (@%s)\n📝 %s\n📞 %s%s'
            % (first_name or '-', username or '-', stored_text, contact, answer_line or ''))
    owner_notify(cfg, text)


def admin_orders(cfg, chat_id):
    rows = db.orders_recent(5)
    if not rows:
        send(cfg['bot_token'], chat_id, 'مفيش طلبات لسه.')
        return
    lines = ['آخر %d طلبات:' % len(rows), '']
    for o in rows:
        lines.append('#%d | %s | %s | %s' % (o['id'], o['service_name'], o['customer_name'], o['status']))
        lines.append('   📞 %s | %s' % (o['contact'], (o['brief'] or '')[:80]))
        lines.append('')
    send(cfg['bot_token'], chat_id, '\n'.join(lines))


def admin_stats(cfg, chat_id):
    s = db.stats_summary()
    send(cfg['bot_token'], chat_id,
         '📊 إحصائيات NIVORA Store\n\n'
         '👤 المستخدمين: %d\n'
         '📦 الطلبات: %d (جديد: %d)\n'
         '💬 الاستفسارات: %d' % (s['users'], s['orders'], s['new_orders'], s['inquiries']))


def admin_done(cfg, chat_id, arg):
    if not arg or not arg.strip().isdigit():
        send(cfg['bot_token'], chat_id, 'الاستخدام: /done رقم_الطلب')
        return
    oid = int(arg.strip())
    conn = db.connect()
    conn.execute("UPDATE orders SET status='done' WHERE id=?", (oid,))
    conn.commit()
    changes = conn.total_changes
    conn.close()
    send(cfg['bot_token'], chat_id, ('الطلب #%d اتقفل ✓' % oid) if changes else 'الطلب مش موجود.')


def handle_media(cfg, msg, user_id, chat_id, first_name, username):
    """Photos/files from users: archive + forward copy to owner."""
    token = cfg['bot_token']
    photo = (msg.get('photo') or [None])[-1]
    doc = msg.get('document')
    video = msg.get('video')
    kind, file_id = None, None
    if photo:
        kind, file_id, method = 'photo', photo['file_id'], 'sendPhoto'
    elif doc:
        kind, file_id, method = 'document', doc['file_id'], 'sendDocument'
    elif video:
        kind, file_id, method = 'video', video['file_id'], 'sendVideo'
    else:
        return False
    try:
        res = tg(token, 'getFile', {'file_id': file_id})
        fpath = res['result']['file_path']
        url = 'https://api.telegram.org/file/bot%s/%s' % (token, fpath)
        ext = '.' + fpath.rsplit('.', 1)[-1] if '.' in fpath else ''
        local = BASE / 'media' / ('%s_%d_%s%s' % (kind, user_id, time.strftime('%Y%m%d_%H%M%S'), ext))
        local.write_bytes(urllib.request.urlopen(urllib.request.Request(url), timeout=90).read())
        db.save_media(user_id, str(local), kind)
    except Exception as e:
        log.error('media download: %s', str(e)[:120])
    owner_notify(cfg, '📎 وصل %s من %s (@%s) — id %s\n(الملف محفوظ في مجلد media على السيرفر)'
                 % (kind, first_name or '-', username or '-', chat_id))
    send(token, chat_id, 'وصلت ✓')
    return True


def admin_broadcast(cfg, chat_id, text):
    token = cfg['bot_token']
    if not text.strip():
        send(token, chat_id, 'الاستخدام: /broadcast نص الرسالة')
        return

    def worker():
        ids = db.all_user_chat_ids()
        ok = 0
        for i, cid in enumerate(ids):
            try:
                tg(token, 'sendMessage', {'chat_id': cid, 'text': text[:4000]})
                ok += 1
            except Exception:
                pass
            if (i + 1) % 25 == 0:
                time.sleep(1)
        send(token, str(cfg['owner_chat_id']), '📢 البرودكاست وصل لـ %d/%d مستخدم' % (ok, len(ids)))

    threading.Thread(target=worker, daemon=True).start()
    send(token, chat_id, '📢 جاري الإرسال لكل المستخدمين...')


def handle_message(cfg, msg):
    chat_id = str(msg.get('chat', {}).get('id', ''))
    if not chat_id:
        return
    text = (msg.get('text') or '').strip()
    first_name = msg.get('from', {}).get('first_name', '')
    username = msg.get('from', {}).get('username', '')
    user_id = db.upsert_user(chat_id, first_name, username)
    is_owner = chat_id == str(cfg['owner_chat_id'])
    if db.is_banned(user_id):
        return
    if not is_owner and not rate_ok(user_id):
        send(token, chat_id, 'هدّي شوية 😅')
        return
    db.log_action(user_id, text[:40] if text else 'non-text')
    token = cfg['bot_token']

    if msg.get('photo') or msg.get('document') or msg.get('video'):
        handle_media(cfg, msg, user_id, chat_id, first_name, username)
        return

    if text == '/start':
        clear_flows(user_id)
        send(token, chat_id, '✨', {'remove_keyboard': True})
        send(token, chat_id, WELCOME, kb_main())
        return
    if text.startswith('/ping') and is_owner:
        send(token, chat_id, 'pong ✓ ' + time.strftime('%H:%M:%S'))
        return
    if text.startswith('/broadcast') and is_owner:
        admin_broadcast(cfg, chat_id, text[10:])
        return
    if text.startswith('/ban') and is_owner:
        arg = text[4:].strip()
        if arg.isdigit():
            db.ban_user(int(arg), 'manual')
            send(token, chat_id, 'تم حظر %s ✓' % arg)
        else:
            send(token, chat_id, 'الاستخدام: /ban رقم_المستخدم (بتلاقيه في الإشعارات جنب id)')
        return
    if text.startswith('/unban') and is_owner:
        arg = text[6:].strip()
        if arg.isdigit():
            db.unban_user(int(arg))
            send(token, chat_id, 'تم فتح %s ✓' % arg)
        else:
            send(token, chat_id, 'الاستخدام: /unban رقم_المستخدم')
        return
    if text.startswith('/orders') and is_owner:
        admin_orders(cfg, chat_id)
        return
    if text.startswith('/stats') and is_owner:
        admin_stats(cfg, chat_id)
        return
    if text.startswith('/done') and is_owner:
        admin_done(cfg, chat_id, text[5:])
        return
    if text.startswith('/'):
        send(token, chat_id, 'أمر غير معروف.')
        return

    inq = INQ_FLOWS.get(user_id)
    if inq and inq.active:
        if text in CANCEL_WORDS:
            INQ_FLOWS.pop(user_id, None)
            send(token, chat_id, 'تم إلغاء الاستفسار.', kb_main())
            return
        if inq.stage == 'contact' and looks_like_contact(text):
            finish_inquiry(cfg, chat_id, user_id, text, first_name, username)
            return
        process_inquiry(cfg, chat_id, user_id, text, first_name, username)
        return

    flow = ORDER_FLOWS.get(user_id)
    if flow and flow.active:
        if text in CANCEL_WORDS:
            ORDER_FLOWS.pop(user_id, None)
            send(token, chat_id, 'تم إلغاء الطلب.', kb_main())
            return
        if text in ('استفسار', 'الاستفسار', '💬 استفسار'):
            start_inquiry(token, chat_id, user_id)
            return
        if is_question(text) and flow.step in ('name', 'contact'):
            PENDING_TEXTS[user_id] = text
            send(token, chat_id,
                 'شكلك عايز تسأل مش تكمّل طلب 🤔\nده سؤال ولا بيانات طلب؟',
                 inline([
                     [{'text': '💬 ده سؤال — جاوبني', 'callback_data': 'q_to_inq'}],
                     [{'text': '📝 ده بياناتي — كمّل الطلب', 'callback_data': 'q_continue'}],
                 ]))
            return
        kind, payload = flow.feed(text)
        if kind == 'error':
            send(token, chat_id, payload)
        elif kind == 'next':
            send(token, chat_id, payload, kb_wizard('cancel'))
        elif kind == 'confirm':
            send(token, chat_id, payload + '\n\nتأكد؟', inline([
                [{'text': '✅ تأكيد الطلب', 'callback_data': 'confirm'}],
                [{'text': '🏠 الرئيسية', 'callback_data': 'menu'}, {'text': '❌ إلغاء', 'callback_data': 'cancel'}],
            ]))
        elif kind == 'done':
            ORDER_FLOWS.pop(user_id, None)
            send(token, chat_id, 'تم إلغاء الطلب.', kb_main())
        return

    if text in ('استفسار', '💬 استفسار', 'الاستفسار'):
        start_inquiry(token, chat_id, user_id)
        return

    if any(w in text for w in CATALOG_WORDS):
        send(token, chat_id, 'أكيد 👌 دي كل أقسامنا — اختار اللي يعجبك:', kb_cats())
        return

    matches = db.search_products(text)
    if matches:
        rows = [[{'text': '🛠️ ' + m['name'], 'callback_data': 'svc:%d' % m['id']}] for m in matches]
        rows.append([{'text': '🛠️ شوف كل الخدمات', 'callback_data': 'cats'},
                     {'text': '💬 عندي سؤال بدل الطلب', 'callback_data': 'ask'}])
        send(token, chat_id, 'شكلك محتاج واحد من الخدمات دي 👇', inline(rows))
        return

    if len(text) >= 8:
        process_inquiry(cfg, chat_id, user_id, text, first_name, username)
        return

    send(token, chat_id,
         'اختار من الأزرار تحت 👇 — ولو عندك سؤال اكتبه وأنا هرد عليك.')


def handle_callback(cfg, cb):
    token = cfg['bot_token']
    msg = cb.get('message') or {}
    chat_id = str(msg.get('chat', {}).get('id', ''))
    if not chat_id:
        cb_answer(token, cb.get('id', ''))
        return
    data = cb.get('data', '')
    message_id = msg.get('message_id')
    first_name = cb.get('from', {}).get('first_name', '')
    username = cb.get('from', {}).get('username', '')
    user_id = db.upsert_user(chat_id, first_name, username)
    db.log_action(user_id, 'cb:' + data[:30])

    if data == 'menu':
        clear_flows(user_id)
        edit_msg(token, chat_id, message_id, WELCOME, kb_main())
    elif data == 'restart':
        clear_flows(user_id)
        send(token, chat_id, WELCOME, kb_main())
    elif data == 'about':
        clear_flows(user_id)
        edit_msg(token, chat_id, message_id, ABOUT_TEXT, kb_main())
    elif data == 'cats':
        clear_flows(user_id)
        edit_msg(token, chat_id, message_id, 'الأقسام — اختار القسم اللي يخصك:', kb_cats())
    elif data.startswith('cat:'):
        clear_flows(user_id)
        cid = cb_id(data)
        if cid:
            edit_msg(token, chat_id, message_id, 'الخدمات المتاحة:', kb_services(cid))
    elif data.startswith('cat_service:'):
        sid = cb_id(data)
        svc = db.get_product(sid) if sid else None
        if svc:
            clear_flows(user_id)
            edit_msg(token, chat_id, message_id, 'الخدمات المتاحة:', kb_services(svc['category_id']))
    elif data.startswith('svc:'):
        sid = cb_id(data)
        svc = db.get_product(sid) if sid else None
        if svc:
            clear_flows(user_id)
            edit_msg(token, chat_id, message_id,
                     '🛠️ %s\n\n%s' % (svc['name'], svc['description']), kb_service(svc['id']))
    elif data.startswith('order:'):
        sid = cb_id(data)
        svc = db.get_product(sid) if sid else None
        if svc:
            INQ_FLOWS.pop(user_id, None)
            flow = OrderFlow()
            hint = flow.start(svc['id'], svc['name'])
            ORDER_FLOWS[user_id] = flow
            send(token, chat_id, 'طلبت: %s 📩\n\n%s' % (svc['name'], hint), kb_wizard('cancel'))
    elif data == 'cancel':
        ORDER_FLOWS.pop(user_id, None)
        edit_msg(token, chat_id, message_id, 'تم إلغاء الطلب.', kb_main())
    elif data == 'cancelinq':
        INQ_FLOWS.pop(user_id, None)
        edit_msg(token, chat_id, message_id, 'تم إلغاء الاستفسار.', kb_main())
    elif data == 'ask':
        start_inquiry(token, chat_id, user_id)
    elif data == 'myorders':
        rows = db.user_orders(user_id)
        if not rows:
            edit_msg(token, chat_id, message_id, 'مفيش طلبات لسه — ابدأ أول طلب من 🛠️ خدماتنا 👇', kb_main())
        else:
            STATUS_ICON = {'new': '🆕', 'done': '✅'}
            lines = ['طلباتك:', '']
            for o in rows:
                lines.append('%s #%d | %s' % (STATUS_ICON.get(o['status'], '⏳'), o['id'], o['service_name']))
                lines.append('   🕐 %s' % time.strftime('%Y-%m-%d', time.localtime(o['created_at'])))
            edit_msg(token, chat_id, message_id, '\n'.join(lines), kb_main())
    elif data == 'q_to_inq':
        ORDER_FLOWS.pop(user_id, None)
        text = PENDING_TEXTS.pop(user_id, '')
        if text:
            handle_inquiry_text(cfg, chat_id, user_id, text, first_name, username)
        else:
            start_inquiry(token, chat_id, user_id)
    elif data == 'q_continue':
        text = PENDING_TEXTS.pop(user_id, '')
        flow = ORDER_FLOWS.get(user_id)
        if flow and flow.active and text:
            kind, payload = flow.feed(text)
            if kind == 'error':
                send(token, chat_id, payload, kb_wizard('cancel'))
            elif kind == 'next':
                send(token, chat_id, payload, kb_wizard('cancel'))
            elif kind == 'confirm':
                send(token, chat_id, payload + '\n\nتأكد؟', inline([
                    [{'text': '✅ تأكيد الطلب', 'callback_data': 'confirm'}],
                    [{'text': '🏠 الرئيسية', 'callback_data': 'menu'}, {'text': '❌ إلغاء', 'callback_data': 'cancel'}],
                ]))
        else:
            send(token, chat_id, 'مفيش طلب جاري.', kb_main())
    elif data == 'confirm':
        flow = ORDER_FLOWS.get(user_id)
        if flow and flow.step == 'confirm':
            payload = flow.confirm()
            ORDER_FLOWS.pop(user_id, None)
            order_id = db.create_order(
                user_id, payload['service_id'], payload['name'], payload['contact'], payload['brief'])
            if order_id:
                send(token, chat_id,
                     '✅ تم استلام طلبك رقم #%d\nفريق NIVORA هيتواصل معاك قريب جداً 🚀' % order_id,
                     kb_main())
                o = db.order_full(order_id)
                if o:
                    text = ('🔔 طلب خدمة جديد #%d (id %s)\n\n🛠️ %s\n👤 %s\n📞 %s\n📝 %s\n🕐 %s'
                            % (o['id'], chat_id, o['service_name'], o['customer_name'],
                               o['contact'], o['brief'], time.strftime('%Y-%m-%d %H:%M')))
                    owner_notify(cfg, text)
            else:
                send(token, chat_id, 'حصلت مشكلة في حفظ الطلب — جرب تاني.', kb_main())
        else:
            edit_msg(token, chat_id, message_id, 'مفيش طلب جاري.', kb_main())
    cb_answer(token, cb.get('id', ''))


def handle_update(cfg, upd):
    if 'callback_query' in upd:
        handle_callback(cfg, upd['callback_query'])
    elif 'message' in upd:
        handle_message(cfg, upd['message'])


def main():
    cfg = load_config()
    db.init_db()
    offset = 0
    if STATE_FILE.exists():
        try:
            offset = json.loads(STATE_FILE.read_text()).get('offset', 0)
        except Exception:
            offset = 0
    log.info('=== Shop Bot started (FINAL M2+M3+M4) | ai=%s ===', cfg.get('ai_enabled'))
    print('SHOP_BOT_FINAL_UP')
    while True:
        try:
            res = tg(cfg['bot_token'], 'getUpdates', {'offset': offset + 1, 'timeout': 20}, timeout=25)
            for upd in res.get('result', []):
                offset = max(offset, upd['update_id'])
                try:
                    handle_update(cfg, upd)
                except Exception as e:
                    log.error('handler: %s', str(e)[:150])
            STATE_FILE.write_text(json.dumps({'offset': offset, 'beat': time.time()}))
        except Exception as e:
            log.error('poll: %s', str(e)[:150])
            time.sleep(2)


def beat_ok(max_age=180):
    if not STATE_FILE.exists():
        return False
    try:
        st = json.loads(STATE_FILE.read_text())
        return time.time() - st.get('beat', 0) < max_age
    except Exception:
        return False


if __name__ == '__main__':
    main()
