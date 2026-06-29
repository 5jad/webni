# -*- coding: utf-8 -*-
"""
Webni — Telegram Backend
يرسل: ملخص الفريق (نص) + PDF الزبون + PDF الداخلي → قناة تيليجرام
"""

import os, json, logging
from datetime import datetime
import requests
from flask import Flask, request, jsonify, send_from_directory

# ──────────────────────────────────────────────────────────────
# الإعدادات — عدّل هذه القيم فقط
# ──────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8603558004:AAGJ0vGejJxx5wwSJ-OAC1VEw0j4qE-Zp68")

# chat_id للقناة @webni_dev
# للقنوات العامة استخدم "@webni_dev" أو الـ numeric ID
# الـ numeric ID يبدأ بـ -100 للقنوات/المجموعات
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-1003926170458")

# message_thread_id: استخدمه فقط إذا القناة supergroup مع topics
# إذا قناة عادية اتركه فارغاً ""
TELEGRAM_THREAD_ID = os.environ.get("TELEGRAM_THREAD_ID", "5")

ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webni-bot")

TG_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


# ──────────────────────────────────────────────────────────────
# CORS
# ──────────────────────────────────────────────────────────────
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"]  = ALLOWED_ORIGIN
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Requested-With"
    return response


# ──────────────────────────────────────────────────────────────
# بناء الرسالة
# ──────────────────────────────────────────────────────────────
def esc(text):
    """تهرّب أحرف MarkdownV2."""
    if text is None: return "—"
    text = str(text)
    for ch in r"_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, "\\" + ch)
    return text


def build_message(data: dict) -> str:
    g = lambda k: data.get(k) or "—"
    custom = data.get("customFields") or []
    custom_lines = ""
    if custom:
        custom_lines = "\n\n📌 *إضافات مخصصة:*\n" + "\n".join(
            f"• {esc(f.get('label'))}: {esc(f.get('value') or '✓')}"
            for f in custom
        )
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return (
        f"🆕 *طلب مشروع جديد — Webni*\n"
        f"_{esc(now)}_\n\n"
        f"👤 *الزبون:* {esc(g('clientName'))}\n"
        f"📱 *الهاتف:* {esc(g('clientPhone'))}\n"
        f"✉️ *الإيميل:* {esc(g('clientEmail'))}\n"
        f"🏢 *الشركة:* {esc(g('clientCompany'))}\n\n"
        f"💡 *المشروع:* {esc(g('projName'))} \\({esc(g('projType'))}\\)\n"
        f"📝 *الوصف:* {esc(g('projDesc'))}\n\n"
        f"⚙️ *الميزات:* {esc(g('features'))}\n"
        f"🛠️ *التقنيات:* {esc(g('techStack'))}\n"
        f"🌐 *الاستضافة:* {esc(g('hosting'))}\n\n"
        f"💰 *السعر:* {esc(g('totalPrice'))}\n"
        f"🏷️ *الخصم:* {esc(g('discount'))}\n"
        f"📆 *خطة الدفع:* {esc(g('paymentPlan'))}\n"
        f"⏳ *التسليم:* {esc(g('deadline'))}\n\n"
        f"📋 *الأولويات:* {esc(g('priorities'))}\n"
        f"📌 *ملاحظات:* {esc(g('extraNotes'))}"
        f"{custom_lines}\n\n"
        f"📎 *الملفات المرفقة أدناه ⬇️*"
    )


# ──────────────────────────────────────────────────────────────
# إرسال لتيليجرام
# ──────────────────────────────────────────────────────────────
def base_params():
    p = {"chat_id": TELEGRAM_CHAT_ID}
    if TELEGRAM_THREAD_ID:
        p["message_thread_id"] = int(TELEGRAM_THREAD_ID)
    return p


def send_text(text: str):
    params = base_params()
    params["text"] = text
    params["parse_mode"] = "MarkdownV2"
    r = requests.post(f"{TG_BASE}/sendMessage", json=params, timeout=15)
    if not r.ok:
        raise Exception(f"sendMessage {r.status_code}: {r.text}")
    return r.json()


def send_document(file_bytes: bytes, filename: str, caption: str = ""):
    params = base_params()
    if caption:
        params["caption"] = caption
    r = requests.post(
        f"{TG_BASE}/sendDocument",
        data=params,
        files={"document": (filename, file_bytes, "application/pdf")},
        timeout=60,
    )
    if not r.ok:
        raise Exception(f"sendDocument({filename}) {r.status_code}: {r.text}")
    return r.json()


# ──────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "chat_id": TELEGRAM_CHAT_ID})


@app.route("/form")
def form():
    return send_from_directory(BASE_DIR, "project-request-form-7.html")


@app.route("/test", methods=["GET"])
def test_bot():
    """اختبار اتصال البوت بالقناة."""
    try:
        result = send_text("✅ اختبار اتصال Webni Bot — يعمل بشكل صحيح\\!")
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502


@app.route("/submit", methods=["POST", "OPTIONS"])
def submit():
    if request.method == "OPTIONS":
        return add_cors(jsonify({"ok": True}))

    # قراءة البيانات
    raw = request.form.get("data") or ""
    if not raw:
        try:
            raw = request.get_data(as_text=True)
        except Exception:
            raw = ""
    try:
        data = json.loads(raw) if raw else {}
    except Exception:
        data = {}

    # دعم JSON body القديم
    if not data:
        try:
            data = request.get_json(force=True, silent=True) or {}
        except Exception:
            data = {}

    if not data.get("clientName") and not data.get("projName"):
        return add_cors(jsonify({"ok": False, "error": "missing_fields"})), 400

    pdf_client   = request.files.get("pdf_client")
    pdf_internal = request.files.get("pdf_internal")
    prompt_file  = request.files.get("prompt_file")

    errors = []

    # 1) رسالة نصية
    try:
        send_text(build_message(data))
        logger.info("✅ رسالة نصية أُرسلت")
    except Exception as e:
        logger.error(f"❌ فشل الرسالة: {e}")
        errors.append(f"text: {e}")

    # 2) PDF الزبون
    if pdf_client and pdf_client.filename:
        try:
            send_document(pdf_client.read(), pdf_client.filename or "عرض-سعر-الزبون.pdf",
                          caption="📄 عرض السعر — نسخة الزبون")
            logger.info("✅ PDF الزبون أُرسل")
        except Exception as e:
            logger.error(f"❌ فشل PDF الزبون: {e}")
            errors.append(f"pdf_client: {e}")

    # 3) PDF الداخلي
    if pdf_internal and pdf_internal.filename:
        try:
            send_document(pdf_internal.read(), pdf_internal.filename or "ملخص-الفريق.pdf",
                          caption="🗂️ ملخص الفريق — نسخة داخلية")
            logger.info("✅ PDF الداخلي أُرسل")
        except Exception as e:
            logger.error(f"❌ فشل PDF الداخلي: {e}")
            errors.append(f"pdf_internal: {e}")

    # 4) ملف الـ Prompt النصي
    if prompt_file and prompt_file.filename:
        try:
            prompt_bytes = prompt_file.read()
            import requests as req
            params = base_params()
            params["caption"] = "🤖 Prompt — للذكاء الاصطناعي"
            r = req.post(
                f"{TG_BASE}/sendDocument",
                data=params,
                files={"document": (prompt_file.filename, prompt_bytes, "text/plain")},
                timeout=30,
            )
            if not r.ok:
                raise Exception(f"sendDocument(prompt) {r.status_code}: {r.text}")
            logger.info("✅ ملف Prompt أُرسل")
        except Exception as e:
            logger.error(f"❌ فشل ملف Prompt: {e}")
            errors.append(f"prompt_file: {e}")

    if errors:
        return add_cors(jsonify({"ok": False, "errors": errors})), 502

    return add_cors(jsonify({"ok": True}))


@app.after_request
def after_request(response):
    return add_cors(response)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
