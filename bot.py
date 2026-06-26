import os
import json
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import imageio_ffmpeg

# 1. Load the songs database
with open('songs.json', 'r') as f:
    SONGS_DB = json.load(f)

# Get the portable FFmpeg path automatically
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

# 2. Keyboards for UI
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton('🔥 TOP 10 SONGS')], [KeyboardButton('🎵 ALL SONGS')]],
    resize_keyboard=True
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user and shows the main menu"""
    await update.message.reply_text(
        "👋 Welcome to your Curated Music Bot!\n\nTap a button below to explore songs.",
        reply_markup=MAIN_KEYBOARD
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button clicks and text searching"""
    text = update.message.text

    if text == '🔥 TOP 10 SONGS':
        # Filter songs where is_top_song is true
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

    # Check if the user typed a song ID number to download
    if text.isdigit():
        song_id = int(text)
        song = next((s for s in SONGS_DB if s['song_id'] == song_id), None)
        
        if not song:
            await update.message.reply_text("❌ Invalid Song ID. Please look at the list again.")
            return

        status_msg = await update.message.reply_text(f"⏳ Processing '{song['title']}'...\nExtracting audio from YouTube. Please wait.")
        
        # Options for downloading audio using portable FFmpeg
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
            # Download and convert asynchronously
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([song['youtube_url']]))
            
            audio_path = f"downloads/{song_id}.mp3"
            
            # Send audio file natively back to Telegram user
            await status_msg.edit_text("🚀 Uploading audio to Telegram...")
            with open(audio_path, 'rb') as audio_file:
                await update.message.reply_audio(
                    audio=audio_file, 
                    title=song['title'], 
                    performer=song['artist']
                )
            
            # Cleanup downloaded file to keep server clean
            if os.path.exists(audio_path):
                os.remove(audio_path)
            await status_msg.delete()

        except Exception as e:
            await status_msg.edit_text(f"❌ Failed to process audio: Check if the video is available.")
        return

    # Text search fallback
    matches = [s for s in SONGS_DB if text.lower() in s['title'].lower() or text.lower() in s['artist'].lower()]
    if matches:
        response = f"🔍 **Search Results for '{text}':**\n\n"
        for s in matches[:10]:
            response += f"🆔 `{s['song_id']}` - **{s['title']}** ({s['artist']})\n"
        response += "\n👉 *Reply with the ID number to play!*"
        await update.message.reply_text(response, parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ No songs found matching that name in your curated list.")

def main():
    # Retrieve token safely from Render environment variables
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        print("Error: No TELEGRAM_BOT_TOKEN found!")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot is starting up...")
    app.run_polling()

if __name__ == '__main__':
    main()
