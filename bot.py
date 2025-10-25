import psycopg2
import telebot
import json
import pyotp
import qrcode
import io
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import io

# Admin sessiyalari
admin_sessions = {}

# Database ulanish
def create_connection():
    try:
        connection = psycopg2.connect(
            host="localhost",
            database="tgbot1",
            user="ssadmin",
            password="Saidbek101020048965",
            port="5432"
        )
        return connection
    except Exception as e:
        print(f"Database xatosi: {e}")
        return None

# Database initialization
def init_db():
    conn = create_connection()
    if conn:
        cur = conn.cursor()
        
        # Foydalanuvchilar jadvali
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE NOT NULL,
                username VARCHAR(100),
                first_name VARCHAR(100),
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Kinolar jadvali
        cur.execute('''
            CREATE TABLE IF NOT EXISTS movies (
                id SERIAL PRIMARY KEY,
                movie_id INTEGER UNIQUE NOT NULL,
                file_id TEXT NOT NULL,
                caption TEXT,
                added_by BIGINT,
                status VARCHAR(20) DEFAULT 'active',
                view_count INTEGER DEFAULT 0,
                added_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Admin sozlamalari
        cur.execute('''
            CREATE TABLE IF NOT EXISTS admin_settings (
                id SERIAL PRIMARY KEY,
                admin_password VARCHAR(100) NOT NULL,
                edit_time TIMESTAMP DEFAULT NOW(),
                edit_by BIGINT NOT NULL,
                old_password VARCHAR(100),
                two_factor_enabled BOOLEAN DEFAULT FALSE,
                two_factor_secret VARCHAR(100)
            )
        ''')
        
        # Default admin parolini qo'shish
        cur.execute('''
            INSERT INTO admin_settings (admin_password, edit_by, old_password, two_factor_enabled) 
            VALUES ('Saidbek101020048965', 1289480590, 'Birinchiparol', FALSE)
            ON CONFLICT DO NOTHING
        ''')
        
        conn.commit()
        cur.close()
        conn.close()
        print("Database jadvallari yaratildi")

# Bot token
BOT_TOKEN = "8261289804:AAE5RnzyZ4eLD4PJDXBqRJn_W8-s3Vj1o7k"
bot = telebot.TeleBot(BOT_TOKEN)

# Google Authenticator secret yaratish
def generate_2fa_secret():
    return pyotp.random_base32()

# QR kod yaratish
def generate_qr_code(secret, username):
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=username,
        issuer_name="Kino Bot"
    )
    
    # QR kod yaratish
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # BytesIO ga saqlash
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    return buffer, secret

# TOTP kodni tekshirish
def verify_2fa_code(secret, code):
    totp = pyotp.TOTP(secret)
    return totp.verify(code)

# Admin parolni tekshirish
def check_admin_password(password):
    conn = create_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT admin_password, two_factor_enabled, two_factor_secret FROM admin_settings ORDER BY id DESC LIMIT 1")
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result and result[0] == password, result[1] if result else False, result[2] if result else None
    return False, False, None

# 2FA secret ni saqlash
def save_2fa_secret(secret):
    conn = create_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("UPDATE admin_settings SET two_factor_secret = %s WHERE id = (SELECT MAX(id) FROM admin_settings)", (secret,))
        conn.commit()
        cur.close()
        conn.close()
        return True
    return False

# 2FA holatini o'zgartirish
def toggle_2fa_status(enabled):
    conn = create_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("UPDATE admin_settings SET two_factor_enabled = %s WHERE id = (SELECT MAX(id) FROM admin_settings)", (enabled,))
        conn.commit()
        cur.close()
        conn.close()
        return True
    return False

# Parolni yangilash
def update_admin_password(new_password, edited_by_user_id):
    conn = create_connection()
    if conn:
        cur = conn.cursor()
        
        # Avvalgi parolni olish
        cur.execute("SELECT admin_password FROM admin_settings ORDER BY id DESC LIMIT 1")
        result = cur.fetchone()
        old_password = result[0] if result else 'Birinchiparol'
        
        # Yangi qator qo'shish
        cur.execute('''
            INSERT INTO admin_settings (admin_password, edit_by, old_password, two_factor_enabled, two_factor_secret)
            SELECT %s, %s, %s, two_factor_enabled, two_factor_secret
            FROM admin_settings 
            ORDER BY id DESC LIMIT 1
        ''', (new_password, edited_by_user_id, old_password))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
    return False

# PDF fayl yaratish
def create_movies_pdf():
    conn = create_connection()
    if not conn:
        return None
        
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT movie_id, caption, view_count, added_at 
            FROM movies 
            WHERE status = 'active' 
            ORDER BY movie_id
        """)
        movies = cur.fetchall()
        cur.close()
        
        if not movies:
            return None
        
        # PDF yaratish
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        
        # Sarlavha
        styles = getSampleStyleSheet()
        title = Paragraph("🎬 Kinolar Ro'yxati", styles['Title'])
        elements.append(title)
        
        # Jadval ma'lumotlari
        data = [['ID', 'Sarlavha', 'Koʻrilgan', 'Qoʻshilgan sana']]
        
        for movie_id, caption, view_count, added_at in movies:
            # Sarlavhani qisqartirish (agar uzun bo'lsa)
            short_caption = caption[:50] + "..." if len(caption) > 50 else caption
            added_date = added_at.strftime("%Y-%m-%d %H:%M")
            data.append([str(movie_id), short_caption, str(view_count), added_date])
        
        # Jadval yaratish
        table = Table(data, colWidths=[50, 200, 70, 120])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
        ]))
        
        elements.append(table)
        
        # Statistik ma'lumotlar
        stats_text = f"\n\nJami kinolar: {len(movies)} ta\nJami ko'rishlar: {sum(movie[2] for movie in movies)} marta"
        stats_paragraph = Paragraph(stats_text, styles['Normal'])
        elements.append(stats_paragraph)
        
        # PDF ni yaratish
        doc.build(elements)
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        print(f"PDF yaratish xatosi: {e}")
        return None
    finally:
        conn.close()

def generate_pdf_file(message):
    bot.send_message(message.chat.id, "📄 PDF fayl yaratilmoqda...")
    
    pdf_buffer = create_movies_pdf()
    
    if pdf_buffer:
        # PDF faylni yuborish
        pdf_buffer.name = "kinolar_royxati.pdf"
        bot.send_document(
            message.chat.id,
            pdf_buffer,
            caption="🎬 **Barcha kinolar ro'yxati**\n\nPDF formatida tayyor!"
        )
    else:
        bot.send_message(message.chat.id, "❌ Kinolar topilmadi yoki PDF yaratishda xatolik!")

# /start komandasi
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user = message.from_user
    
    conn = create_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO users (user_id, username, first_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name
            ''', (user.id, user.username, user.first_name))
            conn.commit()
            cur.close()
        except Exception as e:
            print(f"Saqlash xatosi: {e}")
        finally:
            conn.close()
    
    welcome_text = f"""
Assalomu alaykum {user.first_name}! 🎬

Kino kodini yuboring va men sizga kinoni topshiraman.

Misol: 23
    """
    bot.reply_to(message, welcome_text)

# /exit komandasi
@bot.message_handler(commands=['exit'])
def exit_admin(message):
    user_id = message.from_user.id
    
    if user_id in admin_sessions and admin_sessions[user_id]:
        admin_sessions[user_id] = False
        bot.reply_to(message, "✅ Admin paneldan chiqdingiz. Qayta kirish uchun /admin ni bosing.")
        print(f"👋 Admin chiqdi: {user_id}")
    else:
        bot.reply_to(message, "❌ Siz admin panelda emassiz!")

# /admin komandasi
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    user_id = message.from_user.id
    
    if user_id in admin_sessions and admin_sessions[user_id]:
        show_admin_panel(message)
    else:
        bot.reply_to(message, "🔐 Admin paneliga kirish uchun parolni yuboring:")
        bot.register_next_step_handler(message, check_admin_password_step)

def check_admin_password_step(message):
    user_id = message.from_user.id
    password = message.text
    
    is_correct_password, two_factor_enabled, two_factor_secret = check_admin_password(password)
    
    if is_correct_password:
        if two_factor_enabled and two_factor_secret:
            # Google Authenticator kodi so'rash
            bot.send_message(
                message.chat.id,
                "🔐 **Google Authenticator kodi**\n\n"
                "Google Authenticator ilovasidan 6 xonali kodni kiriting:"
            )
            bot.register_next_step_handler(message, verify_2fa_step, two_factor_secret)
        else:
            # 2FA o'chirilgan
            admin_sessions[user_id] = True
            show_admin_panel(message)
            print(f"🔑 Admin kirdi (2FA o'chirilgan): {user_id}")
    else:
        admin_sessions[user_id] = False
        bot.reply_to(message, "❌ Noto'g'ri parol!")

def verify_2fa_step(message, secret):
    user_id = message.from_user.id
    code = message.text.strip()
    
    if verify_2fa_code(secret, code):
        admin_sessions[user_id] = True
        show_admin_panel(message)
        print(f"🔑 Admin kirdi (2FA bilan): {user_id}")
    else:
        bot.reply_to(message, "❌ Noto'g'ri kod! Qaytadan /admin ni bosing.")

def show_admin_panel(message):
    conn = create_connection()
    last_edit_info = ""
    two_factor_status = ""
    
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT edit_time, edit_by, two_factor_enabled FROM admin_settings ORDER BY id DESC LIMIT 1")
            result = cur.fetchone()
            cur.close()
            
            if result and result[0]:
                edit_time, edit_by, two_factor_enabled = result
                last_edit_info = f"\n\n🔐 **So'ngi parol o'zgartirish:**\n⏰ {edit_time}\n👤 Admin ID: {edit_by}"
                two_factor_status = "🟢 Yoqilgan" if two_factor_enabled else "🔴 O'chirilgan"
                
        except Exception as e:
            print(f"Ma'lumot olish xatosi: {e}")
        finally:
            conn.close()
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🎬 Kino qo'shish", callback_data="add_movie"))
    keyboard.add(InlineKeyboardButton("🗑️ Kino o'chirish", callback_data="delete_movie"))
    keyboard.add(InlineKeyboardButton("📋 Barcha kinolar", callback_data="list_movies"))
    keyboard.add(InlineKeyboardButton("📊 Statistika", callback_data="show_stats"))
    keyboard.add(InlineKeyboardButton("🔐 Admin kodini o'zgartirish", callback_data="change_password"))
    keyboard.add(InlineKeyboardButton("📝 Parol tarixi", callback_data="password_history"))
    keyboard.add(InlineKeyboardButton("📄 PDF yaratish", callback_data="generate_pdf"))
    keyboard.add(InlineKeyboardButton("🔒 Google Authenticator", callback_data="google_auth_settings"))
    
    panel_text = f"""
👨‍💻 Admin panel:

📝 **Buyruqlar:**
/admin - Admin panel
/exit - Admin paneldan chiqish

🔐 **Xavfsizlik holati:**
2-Bosqich: {two_factor_status}
{last_edit_info}

🛠️ **Quyidagi tugmalardan foydalaning:**
    """
    
    bot.send_message(message.chat.id, panel_text, reply_markup=keyboard)

def show_google_auth_settings(message):
    conn = create_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT two_factor_enabled, two_factor_secret FROM admin_settings ORDER BY id DESC LIMIT 1")
            result = cur.fetchone()
            cur.close()
            
            two_factor_enabled = result[0] if result else False
            two_factor_secret = result[1] if result else None
            
            keyboard = InlineKeyboardMarkup()
            
            if not two_factor_enabled:
                if two_factor_secret:
                    keyboard.add(InlineKeyboardButton("🔐 Kodni tasdiqlash", callback_data="verify_2fa_setup"))
                    keyboard.add(InlineKeyboardButton("🔄 QR kodni qayta yaratish", callback_data="regenerate_qr"))
                else:
                    keyboard.add(InlineKeyboardButton("🔐 2FA ni yoqish", callback_data="setup_2fa"))
            else:
                keyboard.add(InlineKeyboardButton("🔓 2FA ni o'chirish", callback_data="disable_2fa"))
            
            keyboard.add(InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_panel"))
            
            status_text = "🟢 Yoqilgan" if two_factor_enabled else "🔴 O'chirilgan"
            
            settings_text = f"""
🔒 **Google Authenticator Sozlamalari**

Holat: {status_text}

Google Authenticator orqali 2-bosqichli himoyani yoqishingiz mumkin.
Bu sizning hisobingizni qo'shimcha himoya qiladi.
            """
            
            bot.send_message(message.chat.id, settings_text, reply_markup=keyboard)
            
        except Exception as e:
            print(f"Google Auth sozlamalari xatosi: {e}")
            bot.send_message(message.chat.id, "❌ Sozlamalarni olishda xatolik")
        finally:
            conn.close()

def setup_google_authenticator(message, regenerate=False):
    user = message.from_user
    username = user.username or f"user_{user.id}"
    
    # Yangi secret yaratish
    secret = generate_2fa_secret()
    
    # QR kod yaratish
    qr_buffer, secret = generate_qr_code(secret, username)
    
    # Secret ni saqlash
    if save_2fa_secret(secret):
        # QR kodni yuborish
        qr_buffer.name = "google_authenticator_qr.png"
        
        instructions = f"""
🔐 **Google Authenticator sozlamalari**

Quyidagi QR kodni Google Authenticator ilovasi orqali skanerlang yoki quyidagi kodni qo'lda kiriting:

**Secret kod:** `{secret}`

📲 **Qadamlar:**
1. Google Authenticator ilovasini oching
2. "+" tugmasini bosing
3. QR kodni skanerlang
4. 6 xonali kod paydo bo'ladi
5. **Kod paydo bo'lgach**, "🔐 Kodni tasdiqlash" tugmasini bosing
        """
        
        # Tugmalar bilan keyboard yaratish
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔐 Kodni tasdiqlash", callback_data="verify_2fa_setup"))
        keyboard.add(InlineKeyboardButton("🔄 QR kodni qayta yaratish", callback_data="regenerate_qr"))
        keyboard.add(InlineKeyboardButton("🔙 Orqaga", callback_data="google_auth_settings"))
        
        bot.send_photo(
            message.chat.id,
            qr_buffer,
            caption=instructions,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    else:
        bot.send_message(message.chat.id, "❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")

def verify_2fa_setup_step(message):
    user_id = message.from_user.id
    
    # Database dan secret ni olish
    conn = create_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT two_factor_secret FROM admin_settings ORDER BY id DESC LIMIT 1")
            result = cur.fetchone()
            cur.close()
            
            if result and result[0]:
                secret = result[0]
                code = message.text.strip()
                
                if verify_2fa_code(secret, code):
                    # Kod to'g'ri, 2FA ni yoqish
                    if toggle_2fa_status(True):
                        bot.send_message(message.chat.id, "✅ Google Authenticator muvaffaqiyatli yoqildi!")
                        show_google_auth_settings(message)
                    else:
                        bot.send_message(message.chat.id, "❌ 2FA ni yoqishda xatolik!")
                        show_google_auth_settings(message)
                else:
                    bot.send_message(message.chat.id, "❌ Noto'g'ri kod! Qaytadan urinib ko'ring.")
                    show_google_auth_settings(message)
            else:
                bot.send_message(message.chat.id, "❌ Secret kod topilmadi. Qaytadan sozlang.")
                show_google_auth_settings(message)
                
        except Exception as e:
            print(f"2FA tasdiqlash xatosi: {e}")
            bot.send_message(message.chat.id, "❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
            show_google_auth_settings(message)
        finally:
            conn.close()

def verify_2fa_disable_step(message):
    user_id = message.from_user.id
    
    # Database dan secret ni olish
    conn = create_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT two_factor_secret FROM admin_settings ORDER BY id DESC LIMIT 1")
            result = cur.fetchone()
            cur.close()
            
            if result and result[0]:
                secret = result[0]
                code = message.text.strip()
                
                if verify_2fa_code(secret, code):
                    # Kod to'g'ri, 2FA ni o'chirish
                    if toggle_2fa_status(False):
                        bot.send_message(message.chat.id, "✅ Google Authenticator muvaffaqiyatli o'chirildi!")
                        show_google_auth_settings(message)
                    else:
                        bot.send_message(message.chat.id, "❌ 2FA ni o'chirishda xatolik!")
                        show_google_auth_settings(message)
                else:
                    bot.send_message(message.chat.id, "❌ Noto'g'ri kod! 2FA o'chirilmadi.")
                    show_google_auth_settings(message)
            else:
                bot.send_message(message.chat.id, "❌ Secret kod topilmadi.")
                show_google_auth_settings(message)
                
        except Exception as e:
            print(f"2FA o'chirish xatosi: {e}")
            bot.send_message(message.chat.id, "❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
            show_google_auth_settings(message)
        finally:
            conn.close()

def enable_google_authenticator(message):
    # Avval kodni tasdiqlashni so'rash
    bot.send_message(
        message.chat.id,
        "🔐 **Google Authenticator kodini tasdiqlash**\n\n"
        "Google Authenticator ilovasidan 6 xonali kodni kiriting "
        "va 2FA ni yoqishni tasdiqlang:"
    )
    bot.register_next_step_handler(message, verify_2fa_setup_step)

def disable_google_authenticator(message):
    # Avval kodni tasdiqlashni so'rash
    bot.send_message(
        message.chat.id,
        "🔐 **Google Authenticator kodini tasdiqlash**\n\n"
        "Google Authenticator ilovasidan 6 xonali kodni kiriting "
        "va 2FA ni o'chirishni tasdiqlang:"
    )
    bot.register_next_step_handler(message, verify_2fa_disable_step)

# Qolgan funksiyalar
def show_all_movies(message):
    conn = create_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT movie_id, caption, view_count FROM movies WHERE status = 'active' ORDER BY movie_id")
            movies = cur.fetchall()
            cur.close()
            
            if movies:
                for movie_id, caption, view_count in movies:
                    movie_text = f"🎬 **Kino kodi:** {movie_id}\n📝 **Sarlavha:** {caption}\n👀 **Ko'rilganlar:** {view_count}"
                    bot.send_message(message.chat.id, movie_text)
            else:
                bot.send_message(message.chat.id, "📭 Hozircha kinolar mavjud emas")
                
        except Exception as e:
            print(f"Kinolar ro'yxati xatosi: {e}")
            bot.send_message(message.chat.id, "❌ Xatolik yuz berdi")
        finally:
            conn.close()

def show_stats(message):
    conn = create_connection()
    if conn:
        try:
            cur = conn.cursor()
            
            cur.execute("SELECT COUNT(*) FROM movies WHERE status = 'active'")
            total_movies = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM movies WHERE status = 'deleted'")
            deleted_movies = cur.fetchone()[0]
            
            cur.execute("SELECT SUM(view_count) FROM movies")
            total_views = cur.fetchone()[0] or 0
            
            cur.execute("SELECT movie_id, caption, view_count FROM movies WHERE status = 'active' ORDER BY view_count DESC LIMIT 5")
            top_movies = cur.fetchall()
            
            cur.close()
            
            stats_text = f"""
📊 **Bot Statistikasi:**

🎬 **Jami kinolar:** {total_movies}
🗑️ **O'chirilgan kinolar:** {deleted_movies}
👀 **Jami ko'rishlar:** {total_views}

🏆 **Eng ko'p ko'rilgan kinolar:**
"""
            for i, (movie_id, caption, views) in enumerate(top_movies, 1):
                stats_text += f"{i}. {movie_id} - {caption} ({views} marta)\n"
            
            bot.send_message(message.chat.id, stats_text)
            
        except Exception as e:
            print(f"Statistika xatosi: {e}")
            bot.send_message(message.chat.id, "❌ Statistika olishda xatolik")
        finally:
            conn.close()

def show_password_history(message):
    conn = create_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT admin_password, old_password, edit_time, edit_by FROM admin_settings ORDER BY id DESC LIMIT 10")
            history = cur.fetchall()
            cur.close()
            
            if history:
                history_text = "📝 **Parol o'zgartirish tarixi:**\n\n"
                
                for i, (new_pass, old_pass, edit_time, edit_by) in enumerate(history, 1):
                    history_text += f"**{i}. {edit_time}**\n"
                    history_text += f"👤 **Admin ID:** {edit_by}\n"
                    history_text += f"🔐 **Eski parol:** {old_pass}\n"
                    history_text += f"🔑 **Yangi parol:** {new_pass}\n"
                    history_text += "─" * 30 + "\n"
                
                bot.send_message(message.chat.id, history_text)
            else:
                bot.send_message(message.chat.id, "📝 Parol o'zgartirish tarixi mavjud emas")
                
        except Exception as e:
            print(f"Parol tarixi xatosi: {e}")
            bot.send_message(message.chat.id, "❌ Parol tarixini olishda xatolik")
        finally:
            conn.close()

def verify_old_password(message):
    if check_admin_password(message.text)[0]:
        bot.send_message(message.chat.id, "🔐 Yangi parolni kiriting:")
        bot.register_next_step_handler(message, process_new_password)
    else:
        bot.send_message(message.chat.id, "❌ Eski parol noto'g'ri!")

def process_new_password(message):
    new_password = message.text
    user_id = message.from_user.id
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("✅ Ha", callback_data=f"confirm_password_{new_password}"),
        InlineKeyboardButton("❌ Yo'q", callback_data="cancel_password_change")
    )
    bot.send_message(
        message.chat.id,
        f"🔐 Parolni o'zgartirishni tasdiqlaysizmi?\n\nYangi parol: {new_password}",
        reply_markup=keyboard
    )

def process_movie_addition(message):
    if message.video:
        file_id = message.video.file_id
        caption = message.caption if message.caption else ""
        
        if '/' in caption:
            parts = caption.split('/', 1)
            if parts[0].isdigit():
                movie_id = int(parts[0])
                movie_caption = parts[1].strip()
                
                conn = create_connection()
                if conn:
                    try:
                        cur = conn.cursor()
                        cur.execute("SELECT movie_id FROM movies WHERE movie_id = %s", (movie_id,))
                        existing_movie = cur.fetchone()
                        
                        if existing_movie:
                            bot.send_message(message.chat.id, f"❌ {movie_id} ID allaqachon mavjud! Boshqa ID tanlang.")
                        else:
                            cur.execute('''
                                INSERT INTO movies (movie_id, file_id, caption, added_by, status, view_count)
                                VALUES (%s, %s, %s, %s, 'active', 0)
                            ''', (movie_id, file_id, movie_caption, message.from_user.id))
                            conn.commit()
                            cur.close()
                            
                            bot.send_message(message.chat.id, f"✅ Kino qo'shildi!\nID: {movie_id}\nSarlavha: {movie_caption}")
                            
                    except Exception as e:
                        print(f"Kino qo'shish xatosi: {e}")
                        bot.send_message(message.chat.id, "❌ Kino qo'shishda xatolik")
                    finally:
                        conn.close()
            else:
                bot.send_message(message.chat.id, "❌ Noto'g'ri format. ID raqam bo'lishi kerak")
        else:
            bot.send_message(message.chat.id, "❌ Noto'g'ri format. ID/Sarlavha ko'rinishida yuboring")
    else:
        bot.send_message(message.chat.id, "❌ Iltimos, video yuboring")

def process_movie_deletion(message):
    if message.text.isdigit():
        movie_id = int(message.text)
        
        conn = create_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("SELECT file_id, caption, view_count FROM movies WHERE movie_id = %s AND status = 'active'", (movie_id,))
                result = cur.fetchone()
                cur.close()
                
                if result:
                    file_id, caption, view_count = result
                    bot.send_video(message.chat.id, file_id, caption=f"🎬 Kino kodi: {movie_id}\n📝 {caption}\n👀 Ko'rilganlar: {view_count}")
                    
                    keyboard = InlineKeyboardMarkup()
                    keyboard.add(
                        InlineKeyboardButton("✅ Ha", callback_data=f"confirm_delete_{movie_id}"),
                        InlineKeyboardButton("❌ Yo'q", callback_data=f"cancel_delete_{movie_id}")
                    )
                    bot.send_message(
                        message.chat.id,
                        f"🗑️ Ushbu kino o'chirishni tasdiqlaysizmi?\n\nID: {movie_id}\nSarlavha: {caption}\n👀 Ko'rilganlar: {view_count}",
                        reply_markup=keyboard
                    )
                else:
                    bot.send_message(message.chat.id, "❌ Bu ID li kino topilmadi yoki allaqachon o'chirilgan")
                    
            except Exception as e:
                print(f"Kino o'chirish xatosi: {e}")
                bot.send_message(message.chat.id, "❌ Xatolik yuz berdi")
            finally:
                conn.close()
    else:
        bot.send_message(message.chat.id, "❌ Iltimos, faqat raqam yuboring")

def delete_movie_confirmed(message, movie_id):
    conn = create_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("UPDATE movies SET status = 'deleted' WHERE movie_id = %s", (movie_id,))
            conn.commit()
            cur.close()
            bot.send_message(message.chat.id, f"✅ {movie_id} ID li kino o'chirildi (arxivlandi)")
        except Exception as e:
            print(f"Kino o'chirish xatosi: {e}")
            bot.send_message(message.chat.id, "❌ Kino o'chirishda xatolik")
        finally:
            conn.close()

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "add_movie":
        bot.send_message(call.message.chat.id, "🎬 Yangi kino qo'shish:\n\nVideo ni yuboring va izoh qoldiring formatda:\nID/Sarlavha\n\nMisol: 23/Salom dunyo")
        bot.register_next_step_handler(call.message, process_movie_addition)
    
    elif call.data == "delete_movie":
        bot.send_message(call.message.chat.id, "🗑️ O'chirmoqchi bo'lgan kino ID sini yuboring:")
        bot.register_next_step_handler(call.message, process_movie_deletion)
    
    elif call.data == "list_movies":
        show_all_movies(call.message)
    
    elif call.data == "show_stats":
        show_stats(call.message)
    
    elif call.data == "change_password":
        bot.send_message(call.message.chat.id, "🔐 Eski parolni kiriting:")
        bot.register_next_step_handler(call.message, verify_old_password)
    
    elif call.data == "password_history":
        show_password_history(call.message)
    
    elif call.data == "generate_pdf":
        generate_pdf_file(call.message)
    
    elif call.data == "google_auth_settings":
        show_google_auth_settings(call.message)
    
    elif call.data == "setup_2fa":
        setup_google_authenticator(call.message)
    
    elif call.data == "regenerate_qr":
        setup_google_authenticator(call.message, regenerate=True)
    
    elif call.data == "verify_2fa_setup":
        enable_google_authenticator(call.message)
    
    elif call.data == "disable_2fa":
        disable_google_authenticator(call.message)
    
    elif call.data == "back_to_panel":
        show_admin_panel(call.message)
    
    elif call.data.startswith("confirm_delete_"):
        movie_id = int(call.data.split("_")[2])
        delete_movie_confirmed(call.message, movie_id)
    
    elif call.data.startswith("cancel_delete_"):
        bot.send_message(call.message.chat.id, "❌ O'chirish bekor qilindi")

    elif call.data.startswith("confirm_password_"):
        new_password = call.data.replace("confirm_password_", "")
        user_id = call.from_user.id
        
        if update_admin_password(new_password, user_id):
            conn = create_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("SELECT edit_time, edit_by FROM admin_settings ORDER BY id DESC LIMIT 1")
                result = cur.fetchone()
                cur.close()
                conn.close()
                
                if result:
                    edit_time, edit_by = result
                    bot.send_message(call.message.chat.id, 
                                   f"✅ Parol muvaffaqiyatli o'zgartirildi!\n"
                                   f"⏰ Vaqt: {edit_time}\n"
                                   f"👤 Admin ID: {edit_by}")
            else:
                bot.send_message(call.message.chat.id, "✅ Parol muvaffaqiyatli o'zgartirildi!")
        else:
            bot.send_message(call.message.chat.id, "❌ Parol o'zgartirishda xatolik")
    
    elif call.data == "cancel_password_change":
        bot.send_message(call.message.chat.id, "❌ Parol o'zgartirish bekor qilindi")

# Raqam qabul qilish (kino kodi)
@bot.message_handler(func=lambda message: message.text.isdigit())
def send_movie_by_id(message):
    movie_id = int(message.text)
    
    conn = create_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT file_id, caption, view_count FROM movies WHERE movie_id = %s AND status = 'active'", (movie_id,))
            result = cur.fetchone()
            
            if result:
                file_id, caption, current_count = result
                
                new_count = current_count + 1
                cur.execute("UPDATE movies SET view_count = %s WHERE movie_id = %s", (new_count, movie_id))
                conn.commit()
                
                bot.send_video(message.chat.id, file_id, caption=f"🎬 Kino kodi: {movie_id}\n📝 {caption}")
            else:
                bot.reply_to(message, "❌ Bu kodli kino topilmadi yoki o'chirilgan")
                
            cur.close()
                
        except Exception as e:
            print(f"Kino yuborish xatosi: {e}")
            bot.reply_to(message, "❌ Xatolik yuz berdi")
        finally:
            conn.close()

# Database ni ishga tushirish
init_db()

# Botni ishga tushirish
print("🤖 Bot ishga tushdi...")
bot.polling()