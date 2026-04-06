import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN_FEEDBACK")

# Change the example IDs to real telegram IDs
ADMINS = [
    111111111,
    222222222,
    333333333,
    444444444
]

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "<b>Привет!</b>\n"
"Это бот <b>для обратной связи по проекту Знайка</b>\n"
"Напиши сюда своё впечатление о нашем проекте и мы это увидим!\n"
"Вы можете написать сюда что бы вы хотели видеть в проекте, поделиться багом или оставить отзыв\n\n"
"<b>Нам будет очень приятно!</b>",
        parse_mode="HTML"
    )


@dp.message(F.text | F.photo | F.video | F.voice | F.document | F.animation | F.sticker)
async def forward_all(message: types.Message):

    # Информация об отправителе
    user_info = (
        f"📩 <b>Новое сообщение!</b>\n"
        f"👤 <b>Имя:</b> {message.from_user.full_name}\n"
        f"🔗 <b>Username:</b> @{message.from_user.username if message.from_user.username else 'нет'}\n"
        f"🆔 <b>Chat ID:</b> <code>{message.from_user.id}</code>"
        parse_mode="HTML"
    )

    # Рассылка каждому админу
    for admin_id in ADMINS:

        # сначала текст с данными отправителя
        await bot.send_message(admin_id, user_info, parse_mode="HTML")

        # затем само сообщение (пересылка)
        await message.copy_to(admin_id)


    # ответ пользователю
    await message.answer("✔ Ваше сообщение отправлено администрации!")


async def main():
    print("Бот запущен...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
