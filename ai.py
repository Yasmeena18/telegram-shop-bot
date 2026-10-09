"""NIVORA Shop Bot — Optional AI replies (Gemini) | M4-v2"""
import json
import urllib.request

PROMPT = (
    'أنت موظف خدمة عملاء في متجر خدمات NIVORA '
    '(مواقع ووردبريس، برمجة وأتمتة Python، هوية بصرية وعروض تقديمية، تعليم برمجة C++/OOP، '
    'أنظمة Notion، مراجعة جودة وكود).\n'
    'قواعد الرد:\n'
    '- جاوب على سؤال العميل نفسه مباشرة وبفائدة حقيقية — ممنوع مقدمات تسويقية عامة أو عبارات جاهزة.\n'
    '- بالعامية المصرية الودودة، من سطرين لتلاتة كحد أقصى، بدون ذكر أسعار.\n'
    '- اختم ردك دايماً بجملة واحدة تطلب منه يسيب رقم واتساب أو يوزر تليجرام للتواصل معاه.\n'
    'سؤال العميل:\n')


def ask_gemini(api_key, question):
    """Returns answer text or None on any failure."""
    if not api_key:
        return None
    try:
        url = ('https://generativelanguage.googleapis.com/v1beta/models/'
               'gemini-3.6-flash:generateContent?key=' + api_key)
        body = json.dumps({'contents': [{'parts': [{'text': PROMPT + question}]}]}).encode()
        req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
        r = json.loads(urllib.request.urlopen(req, timeout=25).read().decode('utf-8', 'replace'))
        parts = r.get('candidates', [{}])[0].get('content', {}).get('parts', [])
        text = parts[0].get('text', '').strip() if parts else ''
        return text[:500] or None
    except Exception:
        return None
