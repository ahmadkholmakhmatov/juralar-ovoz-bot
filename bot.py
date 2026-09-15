import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    InlineQueryResultCachedVoice, InlineQueryResultCachedAudio
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

TOKEN = "8613837654:AAFJr98E2tvhy0EnEikXdGmxgGtuvh4tym4"
ADMIN_IDS = [777574845, 1288069093]

bot = Bot(token=TOKEN)
dp = Dispatcher()

# FSM holatlari
class MemeState(StatesGroup):
    waiting_for_name = State()       # Yangi audio nomi
    waiting_for_new_name = State()   # Tahrirlanayotgan yangi nom

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

# --- 1. YANGI MEME QO'SHISH ---
@dp.message(F.from_user.id.in_(ADMIN_IDS), F.voice)
async def handle_voice(message: Message, state: FSMContext):
    await state.update_data(file_id=message.voice.file_id, file_type="voice")
    await state.set_state(MemeState.waiting_for_name)
    await message.reply("🎤 Voice qabul qilindi!\nNomini yozib yuboring:")

@dp.message(F.from_user.id.in_(ADMIN_IDS), F.audio)
async def handle_audio(message: Message, state: FSMContext):
    await state.update_data(file_id=message.audio.file_id, file_type="audio")
    await state.set_state(MemeState.waiting_for_name)
    await message.reply("🎵 Audio qabul qilindi!\nNomini yozib yuboring:")

@dp.message(F.from_user.id.in_(ADMIN_IDS), MemeState.waiting_for_name, F.text)
async def save_meme_with_name(message: Message, state: FSMContext):
    meme_title = message.text.strip()
    data = await state.get_data()
    async with aiosqlite.connect("memes.db") as db:
        await db.execute(
            "INSERT INTO memes (title, file_id, file_type) VALUES (?, ?, ?)",
            (meme_title, data.get("file_id"), data.get("file_type"))
        )
        await db.commit()
    await state.clear()
    await message.reply(f"✅ Meme saqlandi: <b>{meme_title}</b>", parse_mode="HTML")

# --- 2. OVOZLAR RO'YXATINI KO'RISH (/list) ---
@dp.message(F.from_user.id.in_(ADMIN_IDS), Command("list"))
async def list_memes(message: Message):
    async with aiosqlite.connect("memes.db") as db:
        cursor = await db.execute("SELECT id, title FROM memes ORDER BY id DESC")
        rows = await cursor.fetchall()

    if not rows:
        await message.reply("Bazada hali hech qanday meme yo‘q.")
        return

    keyboard = []
    for m_id, title in rows:
        keyboard.append([InlineKeyboardButton(text=f"🔊 {title}", callback_data=f"manage_{m_id}")])

    await message.reply("📂 Barcha saqlangan memelar ro'yxati (boshqarish uchun tanlang):",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

# --- 3. TANLANGAN MEMENI BOSHQARISH (Tahrirlash / O'chirish) ---
@dp.callback_query(F.data.startswith("manage_"))
async def manage_meme(callback: CallbackQuery):
    meme_id = int(callback.data.split("_")[1])
    async with aiosqlite.connect("memes.db") as db:
        cursor = await db.execute("SELECT id, title FROM memes WHERE id = ?", (meme_id,))
        row = await cursor.fetchone()

    if not row:
        await callback.answer("Meme topilmadi!")
        return

    m_id, title = row
    btns = [
        [InlineKeyboardButton(text="✏️ Nomni o'zgartirish", callback_data=f"edit_{m_id}")],
        [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del_{m_id}")],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data="back_to_list")]
    ]
    await callback.message.edit_text(f"Meme: <b>{title}</b>\nTanlang:",
                                    reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
                                    parse_mode="HTML")
    await callback.answer()

# Ortga qaytish tugmasi
@dp.callback_query(F.data == "back_to_list")
async def back_to_list_cb(callback: CallbackQuery):
    async with aiosqlite.connect("memes.db") as db:
        cursor = await db.execute("SELECT id, title FROM memes ORDER BY id DESC")
        rows = await cursor.fetchall()

    keyboard = [[InlineKeyboardButton(text=f"🔊 {title}", callback_data=f"manage_{m_id}")] for m_id, title in rows]
    await callback.message.edit_text("📂 Barcha saqlangan memelar ro'yxati:",
                                    reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()

# O'chirish
@dp.callback_query(F.data.startswith("del_"))
async def delete_meme(callback: CallbackQuery):
    meme_id = int(callback.data.split("_")[1])
    async with aiosqlite.connect("memes.db") as db:
        await db.execute("DELETE FROM memes WHERE id = ?", (meme_id,))
        await db.commit()
    await callback.message.edit_text("🗑 Meme muvaffaqiyatli o'chirildi!")
    await callback.answer("O'chirildi")

# Nomni tahrirlashni boshlash
@dp.callback_query(F.data.startswith("edit_"))
async def edit_name_start(callback: CallbackQuery, state: FSMContext):
    meme_id = int(callback.data.split("_")[1])
    await state.update_data(editing_meme_id=meme_id)
    await state.set_state(MemeState.waiting_for_new_name)
    await callback.message.reply("Ushbu meme uchun **yangi nom** yozib yuboring:")
    await callback.answer()

# Yangi nomni qabul qilib bazaga yangilash
@dp.message(F.from_user.id.in_(ADMIN_IDS), MemeState.waiting_for_new_name, F.text)
async def update_meme_name(message: Message, state: FSMContext):
    new_title = message.text.strip()
    data = await state.get_data()
    meme_id = data.get("editing_meme_id")

    async with aiosqlite.connect("memes.db") as db:
        await db.execute("UPDATE memes SET title = ? WHERE id = ?", (new_title, meme_id))
        await db.commit()

    await state.clear()
    await message.reply(f"✅ Nomi o'zgartirildi: <b>{new_title}</b>", parse_mode="HTML")

# --- 4. INLINE QIDIRUV ---
@dp.inline_query()
async def inline_search(query: InlineQuery):
    text = query.query.strip().lower()
    results = []

    async with aiosqlite.connect("memes.db") as db:
        if text:
            cursor = await db.execute("SELECT id, title, file_id, file_type FROM memes WHERE LOWER(title) LIKE ? ORDER BY title ASC LIMIT 30", (f"%{text}%",))
        else:
            cursor = await db.execute("SELECT id, title, file_id, file_type FROM memes ORDER BY id DESC LIMIT 30")
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