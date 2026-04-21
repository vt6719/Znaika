#####################
#TELEGRAM БОТ ЗНАЙКА#
#####################

import asyncio
import logging
import sys
import ssl
import os
from dotenv import load_dotenv

# Для веб-запросов (отправка данных на вебхук)
import aiohttp

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile, LabeledPrice, PreCheckoutQuery, Message
)
from aiogram.enums import ParseMode, ContentType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from db_manager_152 import init_db, add_consent

#---------------------
# --- КОНФИГУРАЦИЯ ---
#---------------------

load_dotenv()

# 1. Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN_MAIN")

# 2. Токен оплаты (Провайдер)
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_TOKEN")

# 3. URL вашего вебхука (куда отправлять сообщения для ИИ)
AI_WEBHOOK_URL = os.getenv("AI_WEBHOOK_URL")
AI_WEBHOOK_URL_CHECKING_HOME_WORK = os.getenv("AI_WEBHOOK_URL_CHECKING_HOME_WORK")

# Включаем логирование
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Создаем объекты
bot = Bot(token=BOT_TOKEN)
# Используем MemoryStorage для хранения состояний
dp = Dispatcher(storage=MemoryStorage())

POLICY_VERSION = "v1.0"


#------------------------------------
# --- ОПРЕДЕЛЕНИЕ СОСТОЯНИЙ (FSM) ---
#------------------------------------

class BotStates(StatesGroup):
    chat_active = State()      # Состояние: общение с ИИ (Учиться со Знайкой)
    homework_active = State()  # Состояние: проверка домашки (другой вебхук)


#--------------------------------
# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
#--------------------------------

async def try_delete_message(message: types.Message):
    """
    Пытается удалить сообщение. Если сообщение устарело или уже удалено,
    игнорирует ошибку, чтобы бот не падал.
    """
    try:
        if message:
            await message.delete()
    except Exception:
        pass


#-------------------
# --- КЛАВИАТУРЫ ---
#-------------------

def get_accept_keyboard():
    """Кнопка согласия на обработку данных"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Даю согласие", callback_data="btn_agree_documents")]
    ])

def get_accept_keyboard1():
    """Кнопка принятия документов после персональных данных"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принимаю", callback_data="btn_agree_documents1")]
    ])

def continue_documents_keyboard():
    """Кнопка принятия лицензии"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Продолжить", callback_data="btn_continue_documents")]
    ])


def get_main_menu_keyboard():
    """Главное меню"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❓ Что я умею", callback_data="menu_about")],
        [InlineKeyboardButton(text="💬 Учиться со Знайкой", callback_data="menu_ai_chat")],
        [InlineKeyboardButton(text="📚 Проверить решение", callback_data="menu_check_homework")],
        [InlineKeyboardButton(text="💎 Купить подписку", callback_data="menu_pay")],
        [InlineKeyboardButton(text="🤗 Поддержать проект", callback_data="menu_donate")],
        [InlineKeyboardButton(text="📩 Обратная связь", callback_data="menu_feedback")]
    ])


def get_exit_chat_keyboard():
    """Кнопка выхода из режима чата"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Завершить диалог", callback_data="exit_ai_chat")]
    ])


#-------------------------------
# --- ХЭНДЛЕРЫ: СТАРТ И ВХОД ---
#-------------------------------

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    # При старте предыдущие сообщения обычно не удаляем, так как это начало диалога
    text_message = (
        "Привет! 👋\n\n"
        "Я — <b>заяц Знайка</b>, твой личный школьный помощник по математике, и я очень люблю учиться!\n"
        "Для меня она как весёлое приключение с цифрами и задачками-головоломками. 🧩✨\n\n"
        "Я помогу тебе понять, что математика — это совсем не сложно, а наоборот, <b>очень интересно и даже здорово!</b>\n\n"
        "Мы будем играть в числа, решать хитрые задачки вместе и смотреть, как ты сам(а) станешь <b>настоящим математическим супер-героем!</b> 💪😊\n"
        "Готов(а) отправиться в это <b>увлекательное путешествие?</b>\n"
        "Я всегда рад помочь и ответить на все твои вопросы!\n\n"
        "Если тебе интересно следить за мной, ты можешь глянуть мой <a href='https://t.me/RabbitZnaika'><b>Telegram канал</b></a> 👀\n\n"
        "<b>Просим обратить внимание, что данная версия проекта Знайка ещё является бета версией и мы будем очень рады любой обратной связи и финансовой поддержке для развития проекта</b>"
    )

    button_continue = InlineKeyboardButton(text="Продолжить", callback_data="btn_continue")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button_continue]])

    await message.answer(text_message, reply_markup=keyboard, parse_mode=ParseMode.HTML)

#---------------
#---ДОКУМЕНТЫ---
#---------------

@dp.callback_query(F.data == "btn_continue")
async def process_continue_click(callback: types.CallbackQuery):
    await callback.answer()
    
    # Удаляем предыдущее сообщение
    await try_delete_message(callback.message)

    caption_text = (
        "<b>Отлично!</b>\n\n"
        "Чтобы начать обучение, мне необходимо получить согласие на <b>обработку персональных данных.</b>\n\n"
        "❗️ Если тебе нет 18 лет, пожалуйста, покажи этот экран маме или папе. Только родители или законные представители имеют право нажать кнопку ниже.\n\n"
        "✅ Нажимая на кнопку <b>'Даю согласие'</b> вы подтверждаете, что вам есть 18 лет / вы родитель или законный представитель, ознакомились с документом <b>'Согласие_на_обработку_персональных_данных.pdf'</b> и даёте согласие на обработку персональных данных"
    )

    try:
        licence_file = FSInputFile("Согласие на обработку персональных данных.pdf")
        await callback.message.answer_document(
            document=licence_file,
            caption=caption_text,
            reply_markup=get_accept_keyboard(),
            parse_mode=ParseMode.HTML
        )
    except Exception:
        await callback.message.answer(
            f"{caption_text}\n\n(Документ не найден, либо произошла ошибка\nпо вопросам поддержки обращайтесь <a href='https://t.me/ZnaikaFeedbackBot'><b>сюда</b></a>)",
            reply_markup=get_accept_keyboard(),
            parse_mode=ParseMode.HTML
        )


@dp.callback_query(F.data == "btn_agree_documents")
async def process_accept_license(callback: types.CallbackQuery):
    await callback.answer("Согласие принято! ✅")
    user = callback.from_user

    try:
        # ЗАПИСЬ В БАЗУ (Защищенная)
        ts, rec_hash = await add_consent(user.id, user.username, user.full_name, POLICY_VERSION)

        # ЗАПИСЬ В ФАЙЛ (Дубликат для удобства)
        with open("logs.txt", "a", encoding="utf-8") as f:
            f.write(f"DATE:{ts} | ID:{user.id} | HASH:{rec_hash}\n")

        # Удаляем сообщение с лицензией
        await try_delete_message(callback.message)

        # Ответ пользователю
        await callback.message.answer(
            f"✅ <b>Согласие принято!</b>\n\n"
            f"Ваш ID согласия: <code>{rec_hash[:10]}...</code>\n"
            f"Время: {ts}\n\n",
            reply_markup=continue_documents_keyboard(),
            parse_mode="HTML"
        )

    except Exception as e:
        print(f"Ошибка: {e}")
        await callback.answer("Ошибка записи.", show_alert=True)



@dp.callback_query(F.data == "btn_continue_documents")
async def process_continue_click(callback: types.CallbackQuery):
    await callback.answer()

    # Удаляем предыдущее сообщение
    await try_delete_message(callback.message)

    caption_text = (
        "Мы исполняем закон, пожалуйста прочитайте документ 'Политика конфиденциальности.pdf'.\n\n"
        "✅ Нажимая на кнопку <b>'Принимаю'</b> вы подтверждаете, что вам есть 18 лет / вы родитель или законный представитель, ознакомились с документом <b>'Политика конфиденциальности.pdf'</b> и принимаете её условия."
    )

    try:
        licence_file = FSInputFile("Политика конфиденциальности.pdf")
        await callback.message.answer_document(
            document=licence_file,
            caption=caption_text,
            reply_markup=get_accept_keyboard1(),
            parse_mode=ParseMode.HTML
        )
    except Exception:
        await callback.message.answer(
            f"{caption_text}\n\n(Документ не найден, либо произошла ошибка\nпо вопросам поддержки обращайтесь <a href='https://t.me/ZnaikaFeedbackBot'><b>сюда</b></a>)",
            reply_markup=get_accept_keyboard1(),
            parse_mode=ParseMode.HTML
        )


@dp.callback_query(F.data == "btn_agree_documents1")
async def process_continue_click(callback: types.CallbackQuery):
    await callback.answer()

    # Удаляем предыдущее сообщение
    await try_delete_message(callback.message)

    await callback.message.answer(
        "🐰 Ура! Теперь мы можем начать.\n"
        "Выбери, что ты хочешь сделать в <b>меню ниже:</b> 👇",
        reply_markup=get_main_menu_keyboard(),
        parse_mode=ParseMode.HTML

    )


#-----------------------
# --- ОБРАБОТКА МЕНЮ ---
#-----------------------

# 1. Обратная связь
@dp.callback_query(F.data == "menu_feedback")
async def menu_feedback(callback: types.CallbackQuery):
    await callback.answer()
    # Сообщения меню не удаляем, если предполагается, что пользователь может вернуться, 
    # НО по условию "удаление каждого предыдущего сообщения", удаляем меню и отправляем новое сообщение.
    await try_delete_message(callback.message)

    text = (
        "Если у тебя есть вопросы или предложения, напиши нам:\n"
        "👉 <a href='https://t.me/RabbitZnaika'>Наш канал</a>\n"
        "📧 Почта: Появится в будущем\n"
        "🤖 Бот для обратной связи: @ZnaikaFeedbackBot, либо <a href='https://t.me/ZnaikaFeedbackBot'>ссылка</a>"
    )
    # Добавляем кнопку возврата в меню, чтобы пользователь не застрял
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 В меню", callback_data="exit_ai_chat")]])
    await callback.message.answer(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=back_kb)


# 2. О себе (Что я умею)
@dp.callback_query(F.data == "menu_about")
async def menu_about(callback: types.CallbackQuery):
    await callback.answer()
    await try_delete_message(callback.message)

    text = (
        "<b>Привет, я Знайка, твой первый заяц-репетитор. Давай я кратко тебе расскажу, что я умею.</b>\n\n"
        "<b>1.</b> Я могу помогать тебе с математикой, например помочь сделать домашнее задание или разобрать непонятную тему.\n\n"
        "<b>2.</b> Я проверю задание, которое ты выполнил сам.\n\n"
        "<b>3.</b> Объясню новую тему.\n\n"
        "<b>4.</b> Разъясню тебе непонятные математические термины.\n\n"
        "<b>5.</b> Буду отличным зайцем-помощником для самопроверки.\n\n"
        "<b>6.</b> Я умею принимать текстовые и голосовые запросы, а так же изображения.\n\n"
        "<b>7.</b> Могу отвечать как текстом, так и голосом."
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 В меню", callback_data="exit_ai_chat")]])
    await callback.message.answer(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=back_kb)


# 3. Оплата (Invoice)
@dp.callback_query(F.data == "menu_pay")
async def menu_pay(callback: types.CallbackQuery):
    # Оплату и уведомления не удаляем так агрессивно, чтобы пользователь видел чек,
    # но само меню удаляем.
    await try_delete_message(callback.message)

    if PAYMENT_PROVIDER_TOKEN == "YOUR_TEST_PAYMENT_TOKEN_HERE":
        await callback.answer("Это бета-версия проекта и пока он полностью бесплатный, если хотите вы можете поддержать нас из главного меню, мы будем очень признательны!", show_alert=True)
        # Возвращаем меню, раз оплаты нет
        await callback.message.answer("Возврат в меню:", reply_markup=get_main_menu_keyboard())
        return

    await callback.answer()
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title="Подписка на Знайку",
        description="Доступ к расширенным функциям и решению сложных задач на 1 месяц.",
        payload="znaika_subscription_1month",
        provider_token=PAYMENT_PROVIDER_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label="Подписка (1 мес)", amount=19900)],
        start_parameter="subscribe",
        photo_url="https://cdn-icons-png.flaticon.com/512/2618/2618529.png",
        photo_height=512,
        photo_width=512,
        photo_size=512,
    )


@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def process_successful_payment(message: types.Message):
    total_amount = message.successful_payment.total_amount // 100
    currency = message.successful_payment.currency

    await message.answer(
        f"🎉 <b>Оплата прошла успешно!</b>\n"
        f"Сумма: {total_amount} {currency}.\n"
        f"Спасибо за подписку! Теперь тебе доступны супер-силы Знайки!",
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_keyboard() # Возвращаем меню
    )


# 4. Поддержка проекта
@dp.callback_query(F.data == "menu_donate")
async def donate(callback: types.CallbackQuery):
    await callback.answer()
    await try_delete_message(callback.message)

    caption_text = (
        "Если вы хотите, вы можете <b>поддержать наш проект!</b>\n"
        "Так вы сможете помочь <b>развитию проекта</b>"
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 В меню", callback_data="exit_ai_chat")]])

    try:
        donateQR = FSInputFile("donateqr.jpg")
        await callback.message.answer_document(
            document=donateQR,
            caption=caption_text,
            parse_mode=ParseMode.HTML,
            reply_markup=back_kb
        )
    except Exception:
        await callback.message.answer(
            f"{caption_text}\n\n(QR код не найден, либо произошла ошибка,\nпо вопросам поддержки обращайтесь <a href='https://t.me/ZnaikaFeedbackBot'><b>сюда</b></a>)",
            parse_mode=ParseMode.HTML,
            reply_markup=back_kb
        )


#---------------------------------------
# --- ВХОД В РЕЖИМЫ ОБЩЕНИЯ С ИИ ---
#---------------------------------------

# Режим 1: Обычный чат
@dp.callback_query(F.data == "menu_ai_chat")
async def start_ai_chat(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await try_delete_message(callback.message)

    # Устанавливаем состояние "В чате" (обычном)
    await state.set_state(BotStates.chat_active)

    await callback.message.answer(
        "🐰 <b>Режим обучения со Знайкой включён!</b>\n\n"
        "Напиши, запиши голосовое сообщение или отправь мне фотографию того, что тебе нужно решить\n"
        "Мы будем общаться, пока ты не нажмешь кнопку «Завершить диалог».",
        reply_markup=get_exit_chat_keyboard(),
        parse_mode=ParseMode.HTML
    )


# Режим 2: Проверка домашки (НОВЫЙ ХЭНДЛЕР)
@dp.callback_query(F.data == "menu_check_homework")
async def start_homework_chat(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await try_delete_message(callback.message)

    # Устанавливаем состояние "Проверка домашки"
    await state.set_state(BotStates.homework_active)

    # Используем тот же текст приветствия, что и в чате (чтобы не менять исходный стиль)
    await callback.message.answer(
        "🐰 <b>Режим проверки решения включён!</b>\n\n"
        "Напиши, запиши голосовое сообщение или отправь мне фотографию того, что я должен проверить\n"
        "Мы будем общаться, пока ты не нажмешь кнопку «Завершить диалог».",
        reply_markup=get_exit_chat_keyboard(),
        parse_mode=ParseMode.HTML
    )


#-------------------------------------
# --- ЛОГИКА ЧАТА С ИИ (WEBHOOKS) ---
#-------------------------------------

# Обработчик кнопки "Завершить диалог" (работает для обоих состояний)
@dp.callback_query(F.data == "exit_ai_chat", StateFilter(BotStates.chat_active, BotStates.homework_active))
async def stop_ai_chat(callback: types.CallbackQuery, state: FSMContext):
    # Сбрасываем любое активное состояние
    await state.clear()
    await callback.answer("Диалог завершен")
    await try_delete_message(callback.message)
    
    await callback.message.answer(
        "Диалог остановлен. Возвращаю меню.",
        reply_markup=get_main_menu_keyboard()
    )


# Обработчик кнопки "В меню" для информационных разделов (когда состояние пустое)
@dp.callback_query(F.data == "exit_ai_chat")
async def back_to_menu_generic(callback: types.CallbackQuery):
    await callback.answer()
    await try_delete_message(callback.message)
    await callback.message.answer("Главное меню:", reply_markup=get_main_menu_keyboard())


# --- ОБРАБОТЧИКИ КОНТЕНТА (ТЕКСТ, ФОТО, ГОЛОС) ---
# Теперь они реагируют на оба состояния: chat_active и homework_active

@dp.message(StateFilter(BotStates.chat_active, BotStates.homework_active), F.photo)
async def process_ai_photo(message: types.Message, state: FSMContext):
    # Определяем URL в зависимости от состояния
    current_state = await state.get_state()
    target_url = AI_WEBHOOK_URL_CHECKING_HOME_WORK if current_state == BotStates.homework_active.state else AI_WEBHOOK_URL

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    photo = message.photo[-1]  # выбираем самое большое изображение
    file_id = photo.file_id
    file_info = await bot.get_file(file_id)
    file_path = file_info.file_path
    downloaded_file = await bot.download_file(file_path)

    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "chat_id": message.chat.id,
                "user_id": message.from_user.id,
                "username": message.from_user.username,
                "file_type": "photo",
                "file_name": "image.jpg",
                "file_id": file_id
            }
            # Отправляем файл на выбранный URL
            files = {"file": downloaded_file}

            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            async with session.post(target_url, data=payload, ssl=ssl_context) as resp:
                if resp.status != 200:
                    await message.answer(f"⚠️ Ошибка сервера: {resp.status}", reply_markup=get_exit_chat_keyboard())
                    return

            await message.answer("✅ Изображение отправлено!", reply_markup=get_exit_chat_keyboard())

    except Exception as e:
        logging.error(f"Webhook error: {e}")
        await message.answer("⚠️ Не удалось отправить изображение.", reply_markup=get_exit_chat_keyboard())


@dp.message(StateFilter(BotStates.chat_active, BotStates.homework_active), F.voice)
async def process_ai_voice(message: types.Message, state: FSMContext):
    # Определяем URL
    current_state = await state.get_state()
    target_url = AI_WEBHOOK_URL_CHECKING_HOME_WORK if current_state == BotStates.homework_active.state else AI_WEBHOOK_URL

    await bot.send_chat_action(chat_id=message.chat.id, action="record_voice")

    voice = message.voice
    file_id = voice.file_id
    file_info = await bot.get_file(file_id)
    file_path = file_info.file_path
    downloaded_file = await bot.download_file(file_path)

    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "chat_id": message.chat.id,
                "user_id": message.from_user.id,
                "username": message.from_user.username,
                "file_type": "voice",
                "file_name": "voice.ogg",
                "file_id": file_id
            }
            files = {"file": downloaded_file}

            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            async with session.post(target_url, data=payload, ssl=ssl_context) as resp:
                if resp.status != 200:
                    await message.answer(f"⚠️ Ошибка сервера: {resp.status}", reply_markup=get_exit_chat_keyboard())
                    return

            await message.answer("✅ Голосовое сообщение отправлено!", reply_markup=get_exit_chat_keyboard())

    except Exception as e:
        logging.error(f"Webhook error: {e}")
        await message.answer("⚠️ Не удалось отправить голосовое сообщение.", reply_markup=get_exit_chat_keyboard())


@dp.message(StateFilter(BotStates.chat_active, BotStates.homework_active), F.text)
async def process_ai_message(message: types.Message, state: FSMContext):
    user_text = message.text
    
    # Определяем URL
    current_state = await state.get_state()
    target_url = AI_WEBHOOK_URL_CHECKING_HOME_WORK if current_state == BotStates.homework_active.state else AI_WEBHOOK_URL

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "chat_id": message.chat.id,
                "user_id": message.from_user.id,
                "username": message.from_user.username,
                "text": user_text
            }

            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            async with session.post(target_url, json=payload, ssl=ssl_context) as response:
                if response.status != 200:
                    await message.answer(
                        f"⚠️ Ошибка сервера: {response.status}\nПопробуй позже.",
                        reply_markup=get_exit_chat_keyboard()
                    )
                    return

                await message.answer("✅ Сообщение было успешно отправлено!", reply_markup=get_exit_chat_keyboard())

    except Exception as e:
        logging.error(f"Webhook error: {e}")
        await message.answer(
            "⚠️ Не получилось связаться с сервером Знайки.\nПопробуй позже!",
            reply_markup=get_exit_chat_keyboard()
        )


# Команда /stop для выхода из чата (на случай если кнопки нет)
@dp.message(StateFilter(BotStates.chat_active, BotStates.homework_active), Command("stop"))
async def cmd_stop_chat(message: types.Message, state: FSMContext):
    await state.clear()
    await try_delete_message(message) # Удаляем команду стоп
    await message.answer("Режим чата выключен.", reply_markup=get_main_menu_keyboard())


#---------------
# --- ЗАПУСК ---
#---------------

async def main():
    print("Бот запущен...")
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен")