import os
import json
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# --- WEB SERVER FOR RENDER COMPLIANCE ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Music Bot is running safely!"

def run_web_server():
    port = int(os.getenv("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

# --- LOAD AUDIO LIST DATABASE ---
with open('songs.json', 'r') as f:
    SONGS_DB = json.load(f)

# --- MENU KEYBOARD LAYOUTS ---
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton('🔥 TOP 10 HITS')],
        [KeyboardButton('🎭 BROWSE BY GENRE')],
        [KeyboardButton('🔍 SEARCH A SONG')]
    ],
    resize_keyboard=True
)

GENRE_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton('🎻 Traditional'), KeyboardButton('💖 Romantic')],
        [KeyboardButton('🎧 DJ Remix'), KeyboardButton('💧 Sad')],
        [KeyboardButton('🏹 Hul Songs')],
        [KeyboardButton('↩️ BACK TO MENU')]
    ],
    resize_keyboard=True
)

def get_cancel_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton('↩️ CANCEL')]], resize_keyboard=True)

# --- COMMAND HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends welcome layout with navigation dashboard"""
    await update.message.reply_text(
        "👋 Welcome to your Curated Santali Music Bot!\n\nUse the buttons below to explore the playlist catalog.",
        reply_markup=MAIN_KEYBOARD
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main routing dashboard engine for text commands"""
    text = update.message.text

    # 1. Main Navigation Routing
    if text == '🔥 TOP 10 HITS':
        top_songs = [s for s in SONGS_DB if s.get('is_top_song')][:10]
        response = "🔥 <b>Top Hand-Picked Hits:</b>\n\n"
        for s in top_songs:
            response += f"🆔 <code>{s['song_id']}</code> - <b>{s['title']}</b> ({s['artist']})\n"
        response += "\n👉 <i>Reply with the ID number of the track to download and listen!</i>"
        await update.message.reply_text(response, parse_mode="HTML", reply_markup=MAIN_KEYBOARD)
        return

    if text == '🎭 BROWSE BY GENRE':
        await update.message.reply_text("Select a music genre to browse our catalog:", reply_markup=GENRE_KEYBOARD)
        return

    if text in ['↩️ BACK TO MENU', '↩️ CANCEL']:
        await update.message.reply_text("Returned to main menu dashboard.", reply_markup=MAIN_KEYBOARD)
        if 'awaiting_search' in context.user_data:
            del context.user_data['awaiting_search']
        return

    if text == '🔍 SEARCH A SONG':
        context.user_data['awaiting_search'] = True
        await update.message.reply_text("⌨️ Type the name of the song or artist you want to find:", reply_markup=get_cancel_keyboard())
        return

    # 2. Genre Category Sorting Interface
    genre_mapping = {
        '🎻 Traditional': 'Traditional',
        '💖 Romantic': 'Romantic',
        '🎧 DJ Remix': 'DJ Remix',
        '💧 Sad': 'Sad',
        '🏹 Hul Songs': 'Hul Songs'
    }

    if text in genre_mapping:
        target_genre = genre_mapping[text]
        filtered = [s for s in SONGS_DB if s.get('genre') == target_genre][:15]
        
        if not filtered:
            await update.message.reply_text(f"No songs mapped under {text} layout yet.", reply_markup=GENRE_KEYBOARD)
            return
            
        response = f"{text} <b>Tracks Available:</b>\n\n"
        for s in filtered:
            response += f"🆔 <code>{s['song_id']}</code> - <b>{s['title']}</b> ({s['artist']})\n"
        response += "\n👉 <i>Reply with the ID number of the track to listen!</i>"
        await update.message.reply_text(response, parse_mode="HTML", reply_markup=GENRE_KEYBOARD)
        return

    # 3. Dynamic Text Query Search Execution
    if context.user_data.get('awaiting_search'):
        del context.user_data['awaiting_search']
        matches = [s for s in SONGS_DB if text.lower() in s['title'].lower() or text.lower() in s['artist'].lower()]
        
        if matches:
            response = f"🔍 <b>Search Results matching '{text}':</b>\n\n"
            for s in matches[:10]:
                response += f"🆔 <code>{s['song_id']}</code> - <b>{s['title']}</b> ({s['artist']})\n"
            response += "\n👉 <i>Reply with the ID number to listen!</i>"
            await update.message.reply_text(response, parse_mode="HTML", reply_markup=MAIN_KEYBOARD)
        else:
            await update.message.reply_text("❌ No match found in the database. Returning to main menu.", reply_markup=MAIN_KEYBOARD)
        return

    # 4. Audio Processing Pipeline
    if text.isdigit():
        song_id = int(text)
        song = next((s for s in SONGS_DB if s['song_id'] == song_id), None)
        
        if not song:
            await update.message.reply_text("❌ Invalid track selection ID number.")
            return

        status_msg = await update.message.reply_text(f"⏳ Processing <b>'{song['title']}'</b>...\nBypassing network verification checks. Please wait.")
        
        output_filename = f"{song_id}.%(ext)s"
        ydl_opts = {
            # 🚀 CHANGE: Allows fallback to combined formats (ba*) if audio-only fails on mobile clients
            'format': 'bestaudio/best/ba*',
            'cookiefile': 'cookies.txt',  
            'outtmpl': output_filename,
            'quiet': True,
            'nocheckcertificate': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web_embedded']
                }
            }
        }

        try:
            loop = asyncio.get_event_loop()
            
            # Extract internal download parameters safely
            info = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(song['youtube_url'], download=True))
            actual_filename = yt_dlp.YoutubeDL(ydl_opts).prepare_filename(info)
            
            await status_msg.edit_text("🚀 Uploading media back to Telegram chat space...")
            
            with open(actual_filename, 'rb') as audio_file:
                await update.message.reply_audio(
                    audio=audio_file, 
                    title=song['title'], 
                    performer=song['artist']
                )
            
            # Clear temporary disk footprint immediately to save system storage limits
            if os.path.exists(actual_filename):
                os.remove(actual_filename)
                
            await status_msg.delete()

        except Exception as e:
            error_message = str(e).split('\n')[0]
            await status_msg.edit_text(f"❌ Connection Trace Error:\n<code>{error_message}</code>", parse_mode="HTML")
            
            # Safe checking for filename cleanup if it got created under another fallback extension name
            if 'info' in locals():
                try:
                    fallback_name = yt_dlp.YoutubeDL(ydl_opts).prepare_filename(info)
                    if os.path.exists(fallback_name):
                        os.remove(fallback_name)
                except:
                    pass
        return

    await update.message.reply_text("❌ Unrecognized command. Use the control buttons below.", reply_markup=MAIN_KEYBOARD)

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        print("Error: Missing TELEGRAM_BOT_TOKEN system configuration key.")
        return

    Thread(target=run_web_server, daemon=True).start()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot configuration active. Initiating polling loop profiles...")
    app.run_polling()

if __name__ == '__main__':
    main()
