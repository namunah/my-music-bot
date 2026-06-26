import os
import json
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import imageio_ffmpeg

# --- FIXED WEB SERVER FOR RENDER COMPLIANCE ---
web_app = Flask(__name__)  #  Fixed from App('render_server')

@web_app.route('/')
def home():
    return "Bot is running!"

def run_web_server():
    # Render automatically sets a PORT environment variable
    port = int(os.getenv("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

# --- BOT LOGIC ---
with open('songs.json', 'r') as f:
    SONGS_DB = json.load(f)

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton('🔥 TOP 10 SONGS')], [KeyboardButton('🎵 ALL SONGS')]],
    resize_keyboard=True
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to your Curated Music Bot!\n\nTap a button below to explore songs.",
        reply_markup=MAIN_KEYBOARD
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == '🔥 TOP 10 SONGS':
        top_songs = [s for s in SONGS_DB if s.get('is_top_song')][:10]
        response = "🔥 **Top Songs Available:**\n\n"
        for s in top_songs:
            response += f"🆔 `{s['song_id']}` - **{s['title']}** ({s['artist']})\n"
        response += "\n👉 *Reply with the ID number of the song to listen!*"
        await update.message.reply_text(response, parse_mode="Markdown")
        return

    if text == '🎵 ALL SONGS':
        response = "🎵 **Our Complete Catalog:**\n\n"
        for s in SONGS_DB:
            response += f"🆔 `{s['song_id']}` - **{s['title']}**\n"
        response += "\n👉 *Reply with the ID number of the song to listen!*"
        await update.message.reply_text(response, parse_mode="Markdown")
        return

    if text.isdigit():
        song_id = int(text)
        song = next((s for s in SONGS_DB if s['song_id'] == song_id), None)
        
        if not song:
            await update.message.reply_text("❌ Invalid Song ID.")
            return

        status_msg = await update.message.reply_text(f"⏳ Processing '{song['title']}'...\nExtracting audio.")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'ffmpeg_location': FFMPEG_PATH,
            'outtmpl': f"downloads/{song_id}.%(ext)s",
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True
        }

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([song['youtube_url']]))
            audio_path = f"downloads/{song_id}.mp3"
            
            await status_msg.edit_text("🚀 Uploading audio...")
            with open(audio_path, 'rb') as audio_file:
                await update.message.reply_audio(audio=audio_file, title=song['title'], performer=song['artist'])
            
            if os.path.exists(audio_path):
                os.remove(audio_path)
            await status_msg.delete()
        except Exception as e:
            await status_msg.edit_text(f"❌ Failed to process audio.")
        return

    matches = [s for s in SONGS_DB if text.lower() in s['title'].lower() or text.lower() in s['artist'].lower()]
    if matches:
        response = f"🔍 **Search Results for '{text}':**\n\n"
        for s in matches[:10]:
            response += f"🆔 `{s['song_id']}` - **{s['title']}** ({s['artist']})\n"
        response += "\n👉 *Reply with the ID number to play!*"
        await update.message.reply_text(response, parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ No songs found in your curated list.")

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        print("Error: No TELEGRAM_BOT_TOKEN found!")
        return

    # Start the web server in a separate background thread
    Thread(target=run_web_server, daemon=True).start()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot is starting up...")
    app.run_polling()

if __name__ == '__main__':
    main()
