import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineQuery, InlineQueryResultCachedVoice, InlineQueryResultCachedAudio
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

TOKEN = "8613837654:AAFJr98E2tvhy0EnEikXdGmxgGtuvh4tym4"
ADMIN_ID = 777574845  # Telegram ID raqamingiz

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Foydalanuvchi holati (nom kutish)
class MemeState(StatesGroup):
    waiting_for_name = State()

async def init_db():
    async with aiosqlite.connect("memes.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS memes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                file_id TEXT,
                file_type TEXT
            )
        """)
        await db.commit()

# 1-QADAM: Voice kelganda qabul qilib, nomini so'raymiz
@dp.message(F.from_user.id == ADMIN_ID, F.voice)
async def handle_voice(message: Message, state: FSMContext):
    await state.update_data(file_id=message.voice.file_id, file_type="voice")
    await state.set_state(MemeState.waiting_for_name)
    await message.reply("🎤 Voice qabul qilindi!\nEndi bu memega qanday **nom** qo'ymoqchisiz? Nomini yozib yuboring:", parse_mode="Markdown")

# 1-QADAM (Audio): Agar oddiy audio fayl (.mp3) kelganda
@dp.message(F.from_user.id == ADMIN_ID, F.audio)
async def handle_audio(message: Message, state: FSMContext):
    await state.update_data(file_id=message.audio.file_id, file_type="audio")
    await state.set_state(MemeState.waiting_for_name)
    await message.reply("🎵 Audio qabul qilindi!\nEndi bu memega qanday **nom** qo'ymoqchisiz? Nomini yozib yuboring:", parse_mode="Markdown")

# 2-QADAM: Foydalanuvchi yuborgan nomni bazaga saqlaymiz
@dp.message(F.from_user.id == ADMIN_ID, MemeState.waiting_for_name, F.text)
async def save_meme_with_name(message: Message, state: FSMContext):
    meme_title = message.text.strip()
    data = await state.get_data()
    file_id = data.get("file_id")
    file_type = data.get("file_type")

    async with aiosqlite.connect("memes.db") as db:
        await db.execute(
            "INSERT INTO memes (title, file_id, file_type) VALUES (?, ?, ?)",
            (meme_title, file_id, file_type)
        )
        await db.commit()

    await state.clear()
    await message.reply(f"✅ Meme saqlandi: <b>{meme_title}</b>", parse_mode="HTML")

# Inline qidiruv (o'zgarmadi)
@dp.inline_query()
async def inline_search(query: InlineQuery):
    text = query.query.strip().lower()
    results = []

    async with aiosqlite.connect("memes.db") as db:
        if text:
            cursor = await db.execute("SELECT id, title, file_id, file_type FROM memes WHERE LOWER(title) LIKE ? LIMIT 20", (f"%{text}%",))
        else:
            cursor = await db.execute("SELECT id, title, file_id, file_type FROM memes ORDER BY id DESC LIMIT 20")
        rows = await cursor.fetchall()

    for row in rows:
        m_id, title, file_id, f_type = row
        if f_type == "voice":
            results.append(InlineQueryResultCachedVoice(id=str(m_id), voice_file_id=file_id, title=title))
        else:
            results.append(InlineQueryResultCachedAudio(id=str(m_id), audio_file_id=file_id))

    await query.answer(results, cache_time=1, is_personal=True)

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())