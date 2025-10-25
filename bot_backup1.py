import psycopg2
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

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
                added_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Admin sozlamalari
        cur.execute('''
            CREATE TABLE IF NOT EXISTS admin_settings (
                id SERIAL PRIMARY KEY,
                admin_password VARCHAR(100) DEFAULT 'Saidbek101020048965'
            )
        ''')
        
        # Default admin parolini qo'shish
        cur.execute('''
            INSERT INTO admin_settings (admin_password) 
            VALUES ('Saidbek101020048965')
            ON CONFLICT DO NOTHING
        ''')
        
        conn.commit()
        cur.close()
        conn.close()
        print("Database jadvallari yaratildi")

# Bot token
BOT_TOKEN = "8261289804:AAE5RnzyZ4eLD4PJDXBqRJn_W8-s3Vj1o7k"
bot = telebot.TeleBot(BOT_TOKEN)

# Admin parolni tekshirish
def check_admin_password(password):
    conn = create_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT admin_password FROM admin_settings WHERE id = 1")
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result and result[0] == password
    return False

# Admin parolni yangilash
def update_admin_password(new_password):
    conn = create_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("UPDATE admin_settings SET admin_password = %s WHERE id = 1", (new_password,))
        conn.commit()
        cur.close()
        conn.close()
        return True
    return False

# /start komandasi
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user = message.from_user
    
    # Foydalanuvchini database ga saqlash
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

# /exit komandasi - admin paneldan chiqish
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
    
    # Agar allaqachon admin bo'lsa
    if user_id in admin_sessions and admin_sessions[user_id]:
        show_admin_panel(message)
    else:
        bot.reply_to(message, "🔐 Admin paneliga kirish uchun parolni yuboring:")
        bot.register_next_step_handler(message, check_admin_password_step)

def check_admin_password_step(message):
    user_id = message.from_user.id
    
    if check_admin_password(message.text):
        admin_sessions[user_id] = True
        show_admin_panel(message)
        print(f"🔑 Admin kirdi: {user_id}")
    else:
        admin_sessions[user_id] = False
        bot.reply_to(message, "❌ Noto'g'ri parol!")

def show_admin_panel(message):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🎬 Kino qo'shish", callback_data="add_movie"))
    keyboard.add(InlineKeyboardButton("🗑️ Kino o'chirish", callback_data="delete_movie"))
    keyboard.add(InlineKeyboardButton("📋 Barcha kinolar", callback_data="list_movies"))
    keyboard.add(InlineKeyboardButton("🔐 Admin kodini o'zgartirish", callback_data="change_password"))
    
    panel_text = """
👨‍💻 Admin panel:

📝 **Buyruqlar:**
/admin - Admin panel
/exit - Admin paneldan chiqish

🛠️ **Quyidagi tugmalardan foydalaning:**
    """
    
    bot.send_message(message.chat.id, panel_text, reply_markup=keyboard)

# Raqam qabul qilish (kino kodi)
@bot.message_handler(func=lambda message: message.text.isdigit())
def send_movie_by_id(message):
    movie_id = int(message.text)
    
    conn = create_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT file_id, caption FROM movies WHERE movie_id = %s", (movie_id,))
            result = cur.fetchone()
            cur.close()
            
            if result:
                file_id, caption = result
                bot.send_video(message.chat.id, file_id, caption=f"🎬 Kino kodi: {movie_id}\n📝 {caption}")
            else:
                bot.reply_to(message, "❌ Bu kodli kino topilmadi")
                
        except Exception as e:
            print(f"Kino yuborish xatosi: {e}")
            bot.reply_to(message, "❌ Xatolik yuz berdi")
        finally:
            conn.close()

# Callback query handler
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
    
    elif call.data == "change_password":
        bot.send_message(call.message.chat.id, "🔐 Eski parolni kiriting:")
        bot.register_next_step_handler(call.message, verify_old_password)
    
    elif call.data.startswith("confirm_delete_"):
        movie_id = int(call.data.split("_")[2])
        delete_movie_confirmed(call.message, movie_id)
    
    elif call.data.startswith("cancel_delete_"):
        bot.send_message(call.message.chat.id, "❌ O'chirish bekor qilindi")

    elif call.data == "confirm_password_change":
        # Yangi parolni olish
        new_password = call.message.text.split("\n")[-1].replace("Yangi parol: ", "")
        if update_admin_password(new_password):
            bot.send_message(call.message.chat.id, "✅ Parol muvaffaqiyatli o'zgartirildi!")
        else:
            bot.send_message(call.message.chat.id, "❌ Parol o'zgartirishda xatolik")
    
    elif call.data == "cancel_password_change":
        bot.send_message(call.message.chat.id, "❌ Parol o'zgartirish bekor qilindi")

def process_movie_addition(message):
    if message.video:
        # Video va caption ni olish
        file_id = message.video.file_id
        caption = message.caption if message.caption else ""
        
        # ID va caption ni ajratish
        if '/' in caption:
            parts = caption.split('/', 1)
            if parts[0].isdigit():
                movie_id = int(parts[0])
                movie_caption = parts[1].strip()
                
                # ID takrorlanishini tekshirish
                conn = create_connection()
                if conn:
                    try:
                        cur = conn.cursor()
                        # ID mavjudligini tekshirish
                        cur.execute("SELECT movie_id FROM movies WHERE movie_id = %s", (movie_id,))
                        existing_movie = cur.fetchone()
                        
                        if existing_movie:
                            bot.send_message(message.chat.id, f"❌ {movie_id} ID allaqachon mavjud! Boshqa ID tanlang.")
                        else:
                            # Yangi kino qo'shish
                            cur.execute('''
                                INSERT INTO movies (movie_id, file_id, caption, added_by)
                                VALUES (%s, %s, %s, %s)
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
        
        # Kino mavjudligini tekshirish
        conn = create_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("SELECT file_id, caption FROM movies WHERE movie_id = %s", (movie_id,))
                result = cur.fetchone()
                cur.close()
                
                if result:
                    file_id, caption = result
                    # VIDEO NI HAM YUBORISH
                    bot.send_video(message.chat.id, file_id, caption=f"🎬 Kino kodi: {movie_id}\n📝 {caption}")
                    
                    keyboard = InlineKeyboardMarkup()
                    keyboard.add(
                        InlineKeyboardButton("✅ Ha", callback_data=f"confirm_delete_{movie_id}"),
                        InlineKeyboardButton("❌ Yo'q", callback_data=f"cancel_delete_{movie_id}")
                    )
                    bot.send_message(
                        message.chat.id,
                        f"🗑️ Ushbu kino o'chirishni tasdiqlaysizmi?\n\nID: {movie_id}\nSarlavha: {caption}",
                        reply_markup=keyboard
                    )
                else:
                    bot.send_message(message.chat.id, "❌ Bu ID li kino topilmadi")
                    
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
            cur.execute("DELETE FROM movies WHERE movie_id = %s", (movie_id,))
            conn.commit()
            cur.close()
            bot.send_message(message.chat.id, f"✅ {movie_id} ID li kino o'chirildi")
        except Exception as e:
            print(f"Kino o'chirish xatosi: {e}")
            bot.send_message(message.chat.id, "❌ Kino o'chirishda xatolik")
        finally:
            conn.close()

def show_all_movies(message):
    conn = create_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT movie_id, caption FROM movies ORDER BY movie_id")
            movies = cur.fetchall()
            cur.close()
            
            if movies:
                # Har bir kino uchun alohida xabar
                for movie_id, caption in movies:
                    movie_text = f"🎬 **Kino kodi:** {movie_id}\n📝 **Sarlavha:** {caption}"
                    bot.send_message(message.chat.id, movie_text)
            else:
                bot.send_message(message.chat.id, "📭 Hozircha kinolar mavjud emas")
                
        except Exception as e:
            print(f"Kinolar ro'yxati xatosi: {e}")
            bot.send_message(message.chat.id, "❌ Xatolik yuz berdi")
        finally:
            conn.close()

def verify_old_password(message):
    if check_admin_password(message.text):
        bot.send_message(message.chat.id, "🔐 Yangi parolni kiriting:")
        bot.register_next_step_handler(message, process_new_password)
    else:
        bot.send_message(message.chat.id, "❌ Eski parol noto'g'ri!")

def process_new_password(message):
    new_password = message.text
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("✅ Ha", callback_data="confirm_password_change"),
        InlineKeyboardButton("❌ Yo'q", callback_data="cancel_password_change")
    )
    bot.send_message(
        message.chat.id,
        f"🔐 Parolni o'zgartirishni tasdiqlaysizmi?\n\nYangi parol: {new_password}",
        reply_markup=keyboard
    )
    # Yangi parolni saqlash
    bot.register_next_step_handler(message, lambda msg: update_admin_password(new_password))

# Database ni ishga tushirish
init_db()

# Botni ishga tushirish
print("🤖 Bot ishga tushdi...")
bot.polling()