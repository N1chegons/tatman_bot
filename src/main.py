import asyncio
import os
from datetime import datetime
from math import ceil
import logging

import aiofiles
from maxapi import Bot, Dispatcher, F
from maxapi.context import MemoryContext
from maxapi.filters.command import Command
from maxapi.types import MessageCreated, BotStarted, CallbackButton, RequestContactButton, MessageCallback, InputMedia
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

from src.manager_sending import SendingManager
from src.models import Registration, Questions, Mailing
from src.repository import UserRepository, QuestionsRepository
from src.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("psy_bot")

bot = Bot(settings.TOKEN)
dp = Dispatcher()

async def get_admin_panel(callback: MessageCallback):
    reply_kb = InlineKeyboardBuilder()
    reply_kb.row(CallbackButton(text="Список записанных", payload="recorders_list"))
    reply_kb.row(CallbackButton(text="Ответы пользователей", payload="answers_list"))
    reply_kb.row(CallbackButton(text="Отправить уведомления", payload="send_message"))
    reply_kb.row(CallbackButton(text="Статистика", payload="statistics"))

    await callback.message.edit(
        text=(
            "Вы в панели администратора."
            "\nОписание:"
            "\nСписок записанных - просмотр список записанных участников."
            "\nОтветы пользователей - просмотр ответов пользователей для записи."
            "\nОтправить уведомления - отправить сообщение всем участником бота."
            "\nСтатистика - просмотр статистики по боту."
            "\n\nВыберите действия на кнопках."
        ),
        attachments=[reply_kb.as_markup()]
    )
async def show_users_page(callback: MessageCallback, user_id: int,  page: int = 1):
    users_list = await UserRepository.get_users_recorded()

    if not users_list:
        kb_back = InlineKeyboardBuilder()
        kb_back.add(CallbackButton(text="В галвное меню", payload="admin_panel"))
        await callback.message.edit(text="Пользователей пока нет.", attachments=[kb_back.as_markup()])
        return

    per_page = 5
    total_pages = ceil(len(users_list) / per_page)

    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    current_users = users_list[start_idx:end_idx]

    text = f"📋 Пользователи:\n\n"
    for user in current_users:
        text += (
            f"Пользователь {user.id}\n"
            f"   👤 Имя: {user.name}\n"
            f"   💬 Проблема: {user.description}\n"
            f"   📞 Телефон: +{user.phone_number}\n\n"
        )

    kb = InlineKeyboardBuilder()

    if page > 1:
        kb.row(CallbackButton(text="⬅️ Назад", payload=f"admin_page_{page - 1}"))

    if page < total_pages:
        kb.row(CallbackButton(text="Вперед ➡️", payload=f"admin_page_{page + 1}"))

    kb.add(CallbackButton(text="В галвное меню", payload="admin_panel"))

    await callback.message.edit(
        text=text + f"\nСтраница {page} из {total_pages}",
        attachments=[kb.as_markup()]
    )
async def show_answers_users_menu(callback: MessageCallback, page: int = 1):
    users_list = await UserRepository.get_users_recorded()

    if not users_list:
        kb_back = InlineKeyboardBuilder()
        kb_back.add(CallbackButton(text="В галвное меню", payload="admin_panel"))
        await callback.message.edit(text="Пока никто не прошел запись на консультацию.", attachments=[kb_back.as_markup()])
        return

    per_page = 6
    total_pages = ceil(len(users_list) / per_page)
    page = max(1, min(page, total_pages))

    start = (page - 1) * per_page
    current_users = users_list[start:start + per_page]

    kb = InlineKeyboardBuilder()

    for i, user in enumerate(current_users):
        name = user.name if user.name else f"ID: {user.id}"

        if user.is_viewed_answers:
            button_text = f"✅ {name}"
        else:
            button_text = f"🆕 {name}"

        button = CallbackButton(text=button_text, payload=f"view_ans_{user.id}_{page}")

        kb.add(button)
        if (i + 1) % 2 == 0:
            kb.row()

    if len(current_users) % 2 != 0:
        kb.row()

    if total_pages > 1:
        kb.row()
        if page > 1:
            kb.add(CallbackButton(text="⬅️ Назад", payload=f"ans_users_page_{page - 1}"))
        if page < total_pages:
            kb.add(CallbackButton(text="Вперед ➡️", payload=f"ans_users_page_{page + 1}"))

    kb.add(CallbackButton(text="В галвное меню", payload="admin_panel"))

    await callback.message.edit(
        text=f"Выберите человека, чтобы посмотреть его ответы (Страница {page} из {total_pages}):",
        attachments=[kb.as_markup()]
    )
async def send_answers_file(callback: MessageCallback, answers_list, target_user_id: int):
    user = await UserRepository.get_user_by_id(target_user_id)

    if not answers_list:
        kb_back = InlineKeyboardBuilder()
        kb_back.add(CallbackButton(text="В галвное меню", payload="admin_panel"))
        await callback.message.answer(text="У этого пользователя пока нет ответов.", attachments=[kb_back.as_markup()])
        return

    md_content = f"📋 Ответы пользователя\n"
    md_content += f"Информация о клиенте:\n"
    md_content += f"   Имя: {user.name}\n"
    md_content += f"   Проблема: {user.description}\n"
    md_content += f"   Телефон: +{user.phone_number}"
    md_content += f"Дата выгрузки: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"

    for i, ans in enumerate(answers_list, start=1):
        md_content += f"{ans.answer}\n\n"

    filename = f"Ответы_{user.name}_.md"

    async with aiofiles.open(filename, "w", encoding="utf-8") as f:
        await f.write(md_content)

    try:
        await callback.message.edit(
            text="Секунду, файл загружается...",
            attachments=[]
        )
        await callback.message.edit(
            text="📄 Вот файл с ответами:",
            attachments=[InputMedia(path=filename)]
        )

    except Exception as e:
        logger.error(f"Ошибка при отправке файла для {user.name}: {e}")
        await callback.message.answer(text="⚠️ Не удалось отправить файл.")

    finally:
        if os.path.exists(filename):
            os.remove(filename)
async def user_panel_fun(user_id: int):
    reply_kb = InlineKeyboardBuilder()
    reply_kb.row(CallbackButton(text="👤 Мой профиль", payload="my_profile"))
    reply_kb.row(CallbackButton(text="📋 Статус заявки", payload="my_status"))

    await bot.send_message(
        user_id=user_id,
        text=(
            "👋 Вы в личном кабинете.\n\n"
            "Здесь вы можете посмотреть свои данные или узнать статус вашей заявки на консультацию.\n\n"
            "Выберите действие на кнопках ниже:"
        ),
        attachments=[reply_kb.as_markup()]
    )
# start
@dp.bot_started()
async def bot_started(event: BotStarted):
    user_id = event.user.user_id
    user = await UserRepository.get_user(user_id)
    logger.info(f"Пользователь {user_id} запустил бота (BotStarted)")

    if not user:
        reply_kb = InlineKeyboardBuilder()
        reply_kb.row(
            CallbackButton(
                text="Пройти регистрацию",
                payload="start_register"
            ),
        )

        await bot.send_message(
            user_id=user_id,
            text=(
                "Привет 👋\n"
                "Вы здесь чтобы записаться на бесплатную консультацию.\nПеред началом нужно пройти небольшую регистрацию для того, чтобы я о вас больше узнала. Начнем?"
            ),
            attachments=[reply_kb.as_markup()]
        )
    else:
        if not user.already_recorded:
            text = "Привет 👋\nТы уже зарегистрирован, но не ответил(-ла) на вопросы.\nОтветь на вопросы чтобы записаться на бесплатную консультацию."
            questions_kb = InlineKeyboardBuilder()
            questions_kb.row(
                CallbackButton(
                    text="Ответить на вопросы",
                    payload="question_answer"
                ),
            )
            await bot.send_message(
                user_id=user_id,
                text=text,
                attachments=[questions_kb.as_markup()]
            )
        else:
            await user_panel_fun(user_id)

@dp.message_created(Command('start'))
async def start_bot(event: MessageCreated):
    user_id = event.message.sender.user_id
    user = await UserRepository.get_user(user_id)
    logger.info(f"Пользователь {user_id} ввел команду /start")

    if not user:
        reply_kb = InlineKeyboardBuilder()
        reply_kb.row(
            CallbackButton(
                text="Пройти регистрацию",
                payload="start_register"
            ),
        )

        await bot.send_message(
            user_id=user_id,
            text=(
                "Привет 👋\n"
                "Вы здесь чтобы записаться на бесплатную консультацию.\nПеред началом нужно пройти небольшую регистрацию для того, чтобы я о вас больше узнала. Начнем?"
            ),
            attachments=[reply_kb.as_markup()]
        )
    else:
        if not user.already_recorded:
            text = "Привет 👋\nТы уже зарегистрирован, но не ответил(-ла) на вопросы.\nОтветь на вопросы чтобы записаться на бесплатную консультацию."
            questions_kb = InlineKeyboardBuilder()
            questions_kb.row(
                CallbackButton(
                    text="Ответить на вопросы",
                    payload="question_answer"
                ),
            )
            await bot.send_message(
                user_id=user_id,
                text=text,
                attachments=[questions_kb.as_markup()]
            )
        else:
            await user_panel(event)

# registration logic
@dp.message_callback(F.callback.payload == "start_register")
async def start_registration(callback: MessageCallback, context: MemoryContext):
    logger.info(f"Пользователь {callback.callback.user.user_id} начал регистрацию")
    await context.set_state(Registration.name)
    await context.set_data({})
    await callback.message.edit(text="Начнем с знакомства. Как вас зовут?", attachments=[])

@dp.message_created(F.message.body.text, Registration.name)
async def handle_name(message: MessageCreated, context: MemoryContext):
    await context.update_data(name=message.message.body.text)
    await context.set_state(Registration.description)

    await bot.send_message(
        user_id=message.message.sender.user_id,
        text="Расскажи, с какой проблемой ты здесь. Если не знаешь что ответить ставь '-'"
    )

@dp.message_created(F.message.body.text, Registration.description)
async def handle_description(message: MessageCreated, context: MemoryContext):
    await context.update_data(description=message.message.body.text)
    await context.set_state(Registration.phone)

    reply_kb = InlineKeyboardBuilder()
    reply_kb.row(RequestContactButton(text="📱 Поделиться номером"))

    await bot.send_message(
        user_id=message.message.sender.user_id,
        text="Отлично! Остался последний шаг. Поделись своим номером для связи.",
        attachments=[reply_kb.as_markup()]
    )

@dp.message_created(F.message.body.attachments, Registration.phone)
async def handle_phone(message: MessageCreated, context: MemoryContext):
    data = await context.get_data()
    name = data.get("name")
    description = data.get("description")

    user_id = message.message.sender.user_id

    contact = message.message.body.attachments[0].payload
    vcf = contact.vcf_info
    phone = vcf.split('TEL;TYPE=cell:')[1].split('\n')[0]
    try:
        await UserRepository.create_user(
            user_id,
            name,
            phone,
            description
        )
        logger.info(f"Пользователь {user_id} ({name}) успешно зарегистрирован")

        await context.clear()

        reply_kb = InlineKeyboardBuilder()
        reply_kb.row(
            CallbackButton(
                text="Ответить на вопросы",
                payload="question_answer"
            ),
        )

        await bot.send_message(
            user_id=user_id,
            text=f"✅ {name}, регистрация прошла успешно! Все данные сохранены.\nТеперь вам нужно ответить на некоторые вопросы, чтобы записаться на консультацию.\nЕсли готовы отвечать на вопросы, жми на кнопку!",
            attachments=[reply_kb.as_markup()]
        )
    except Exception as e:
        logger.exception(f"Ошибка при создании пользователя {user_id}: {e}")
        await bot.send_message(
            user_id=user_id,
            text=f"Неизвестная ошибка.",
        )

# questions logic
@dp.message_callback(F.callback.payload == "question_answer")
async def answer_question_first(callback: MessageCallback, context: MemoryContext):
    logger.info(f"Пользователь {callback.callback.user.user_id} начал отвечать на вопросы")
    await context.set_state(Questions.question1)
    await context.set_data({})
    await callback.message.edit(text="Посторайся отвечать максимально открыто. Если не знаешь что ответить на вопрос, отправляй '-'.", attachments=[])
    await callback.message.answer(text="Вопрос №1.\nКогда значимый человек рядом с тобой вдруг холоднеет или отдаляется — что происходит в теле в первые секунды?\n\nОпиши ощущение, не мысль.")

@dp.message_created(F.message.body.text, Questions.question1)
async def answer_question_second(message: MessageCreated, context: MemoryContext):
    user_id = message.message.sender.user_id
    user = await UserRepository.get_user(user_id)

    try:
        if not user:
            await bot.send_message(
                user_id=user_id,
                text=f"Вы не зарегестрированы! Отправьте в чат - /start для повторной регестрации.",
            )
        else:
            await QuestionsRepository.add_questions_user(user.id, f"Ответ на вопрос № 1:\n{message.message.body.text}")
            await context.set_state(Questions.question2)

            await bot.send_message(
                user_id=message.message.sender.user_id,
                text="Вопрос №2.\nКогда тебя несправедливо обвиняют — что ты ДЕЛАЕШЬ? Не чувствуешь — а делаешь.\n\nОпиши действие."
            )

    except Exception as e:
        logger.exception(f"Ошибка на вопросе 1 у {user_id}: {e}")
        await bot.send_message(
            user_id=user_id,
            text=f"Неизвестная ошибка.",
        )

@dp.message_created(F.message.body.text, Questions.question2)
async def answer_question_third(message: MessageCreated, context: MemoryContext):
    user_id = message.message.sender.user_id
    user = await UserRepository.get_user(user_id)

    try:
        if not user:
            await bot.send_message(
                user_id=user_id,
                text=f"Вы не зарегестрированы! Отправьте в чат - /start для повторной регестрации.",
            )
        else:
            await QuestionsRepository.add_questions_user(user.id, f"Ответ на вопрос № 2:\n{message.message.body.text}")
            await context.set_state(Questions.question3)

            await bot.send_message(
                user_id=message.message.sender.user_id,
                text="Вопрос №3.\nВспомни конкретный момент из детства, когда кто-то старше или сильнее был недоволен тобой или наказывал тебя.\nКто это был? Что произошло? Что ты сделал(а)?"
            )

    except Exception as e:
        logger.exception(f"Ошибка на вопросе 2 у {user_id}: {e}")
        await bot.send_message(
            user_id=user_id,
            text=f"Неизвестная ошибка.",
        )

@dp.message_created(F.message.body.text, Questions.question3)
async def answer_question_fourth(message: MessageCreated, context: MemoryContext):
    user_id = message.message.sender.user_id
    user = await UserRepository.get_user(user_id)

    try:
        if not user:
            await bot.send_message(
                user_id=user_id,
                text=f"Вы не зарегестрированы! Отправьте в чат - /start для повторной регестрации.",
            )
        else:
            await QuestionsRepository.add_questions_user(user.id, f"Ответ на вопрос № 3:\n{message.message.body.text}")
            await context.set_state(Questions.question4)

            await bot.send_message(
                user_id=message.message.sender.user_id,
                text="Вопрос №4.\nЧто делала мать (или главная женская фигура в семье), когда в доме возникало напряжение или конфликт?\nОна вмешивалась, молчала, страдала, уходила?"
            )

    except Exception as e:
        logger.exception(f"Ошибка на вопросе 3 у {user_id}: {e}")
        await bot.send_message(
            user_id=user_id,
            text=f"Неизвестная ошибка.",
        )

@dp.message_created(F.message.body.text, Questions.question4)
async def answer_question_fifth(message: MessageCreated, context: MemoryContext):
    user_id = message.message.sender.user_id
    user = await UserRepository.get_user(user_id)

    try:
        if not user:
            await bot.send_message(
                user_id=user_id,
                text=f"Вы не зарегестрированы! Отправьте в чат - /start для повторной регестрации.",
            )
        else:
            await QuestionsRepository.add_questions_user(user.id, f"Ответ на вопрос № 4:\n{message.message.body.text}")
            await context.set_state(Questions.question5)

            await bot.send_message(
                user_id=message.message.sender.user_id,
                text="Вопрос №5.\nБыло ли в детстве ощущение, что твои сильные чувства (злость, слёзы, радость, страх) — небезопасны или неудобны для кого-то рядом?\nДля кого именно?"
            )

    except Exception as e:
        logger.exception(f"Ошибка на вопросе 4 у {user_id}: {e}")
        await bot.send_message(
            user_id=user_id,
            text=f"Неизвестная ошибка.",
        )

@dp.message_created(F.message.body.text, Questions.question5)
async def answer_question_sixth(message: MessageCreated, context: MemoryContext):
    user_id = message.message.sender.user_id
    user = await UserRepository.get_user(user_id)

    try:
        if not user:
            await bot.send_message(
                user_id=user_id,
                text=f"Вы не зарегестрированы! Отправьте в чат - /start для повторной регестрации.",
            )
        else:
            await QuestionsRepository.add_questions_user(user.id, f"Ответ на вопрос № 5:\n{message.message.body.text}")
            await context.set_state(Questions.question6)

            await bot.send_message(
                user_id=message.message.sender.user_id,
                text="Вопрос №6.\nЗакончи фразу:\n«Чтобы сохранить любовь и безопасность, я должен(а) быть ___ и ни в коем случае не быть ___»."
            )

    except Exception as e:
        logger.exception(f"Ошибка на вопросе 5 у {user_id}: {e}")
        await bot.send_message(
            user_id=user_id,
            text=f"Неизвестная ошибка.",
        )

@dp.message_created(F.message.body.text, Questions.question6)
async def answer_question_seventh(message: MessageCreated, context: MemoryContext):
    user_id = message.message.sender.user_id
    user = await UserRepository.get_user(user_id)

    try:
        if not user:
            await bot.send_message(
                user_id=user_id,
                text=f"Вы не зарегестрированы! Отправьте в чат - /start для повторной регестрации.",
            )
        else:
            await QuestionsRepository.add_questions_user(user.id, f"Ответ на вопрос № 6:\n{message.message.body.text}")
            await context.set_state(Questions.question7)

            await bot.send_message(
                user_id=message.message.sender.user_id,
                text="Вопрос №7.\nГде в теле ты ощущаешь эту фразу?(горло, грудь, живот, плечи, затылок, солнечное сплетение — или другое место)"
            )

    except Exception as e:
        logger.exception(f"Ошибка на вопросе 6 у {user_id}: {e}")
        await bot.send_message(
            user_id=user_id,
            text=f"Неизвестная ошибка.",
        )

@dp.message_created(F.message.body.text, Questions.question7)
async def answer_question_eighth(message: MessageCreated, context: MemoryContext):
    user_id = message.message.sender.user_id
    user = await UserRepository.get_user(user_id)

    try:
        if not user:
            await bot.send_message(
                user_id=user_id,
                text=f"Вы не зарегестрированы! Отправьте в чат - /start для повторной регестрации.",
            )
        else:
            await QuestionsRepository.add_questions_user(user.id, f"Ответ на вопрос № 7:\n{message.message.body.text}")
            await context.set_state(Questions.question8)

            await bot.send_message(
                user_id=message.message.sender.user_id,
                text="Вопрос №8.\nВ текущих отношениях, когда возникает напряжение — чего ты больше всего боишься, что произойдёт, если ты полностью покажешь, свои чувства?"
            )

    except Exception as e:
        logger.exception(f"Ошибка на вопросе 7 у {user_id}: {e}")
        await bot.send_message(
            user_id=user_id,
            text=f"Неизвестная ошибка.",
        )

@dp.message_created(F.message.body.text, Questions.question8)
async def answer_question_nineth(message: MessageCreated, context: MemoryContext):
    user_id = message.message.sender.user_id
    user = await UserRepository.get_user(user_id)

    try:
        if not user:
            await bot.send_message(
                user_id=user_id,
                text=f"Вы не зарегестрированы! Отправьте в чат - /start для повторной регестрации.",
            )
        else:
            await QuestionsRepository.add_questions_user(user.id, f"Ответ на вопрос № 8:\n{message.message.body.text}")
            await context.set_state(Questions.question9)

            await bot.send_message(
                user_id=message.message.sender.user_id,
                text="Вопрос №9.\nЕсли бы ты полностью перестал(а) сдерживаться и проявился/проявилась по-настоящему — кто в твоей жизни от этого пострадал бы?\nНазови конкретно."
            )

    except Exception as e:
        logger.exception(f"Ошибка на вопросе 8 у {user_id}: {e}")
        await bot.send_message(
            user_id=user_id,
            text=f"Неизвестная ошибка.",
        )

@dp.message_created(F.message.body.text, Questions.question9)
async def answer_question_tenth(message: MessageCreated, context: MemoryContext):
    user_id = message.message.sender.user_id
    user = await UserRepository.get_user(user_id)

    try:
        if not user:
            await bot.send_message(
                user_id=user_id,
                text=f"Вы не зарегестрированы! Отправьте в чат - /start для повторной регестрации.",
            )
        else:
            await QuestionsRepository.add_questions_user(user.id, f"Ответ на вопрос № 9:\n{message.message.body.text}")
            await context.set_state(Questions.question10)

            await bot.send_message(
                user_id=message.message.sender.user_id,
                text="Вопрос №10\nЕсли бы тот человек из вопроса 3 (кто был сильнее или наказывал) однажды сказал тебе:\n«Я боялся твоей силы» или «Я не справлялся» — что бы ты почувствовал(а)?"
            )

    except Exception as e:
        logger.exception(f"Ошибка на вопросе 9 у {user_id}: {e}")
        await bot.send_message(
            user_id=user_id,
            text=f"Неизвестная ошибка.",
        )

@dp.message_created(F.message.body.text, Questions.question10)
async def answer_question_eleventh(message: MessageCreated, context: MemoryContext):
    user_id = message.message.sender.user_id
    user = await UserRepository.get_user(user_id)

    try:
        if not user:
            await bot.send_message(
                user_id=user_id,
                text=f"Вы не зарегестрированы! Отправьте в чат - /start для повторной регестрации.",
            )
        else:
            await QuestionsRepository.add_questions_user(user.id, f"Ответ на вопрос № 10:\n{message.message.body.text}")
            await context.set_state(Questions.question11)

            await bot.send_message(
                user_id=message.message.sender.user_id,
                text="Вопрос №11\nПредставь, что ты живёшь свободно, проявляешься ярко, не боишься неодобрения.\nЧто самое страшное кто-то из твоей семьи мог бы о тебе подумать?"
            )

    except Exception as e:
        logger.exception(f"Ошибка на вопросе 10 у {user_id}: {e}")
        await bot.send_message(
            user_id=user_id,
            text=f"Неизвестная ошибка.",
        )

@dp.message_created(F.message.body.text, Questions.question11)
async def answer_question_last(message: MessageCreated, context: MemoryContext):
    user_id = message.message.sender.user_id
    user = await UserRepository.get_user(user_id)

    try:
        if not user:
            await bot.send_message(
                user_id=user_id,
                text=f"Вы не зарегестрированы! Отправьте в чат - /start для повторной регестрации.",
            )
        else:
            await QuestionsRepository.add_questions_user(user.id, f"Ответ на вопрос № 11:\n{message.message.body.text}")
            await context.set_state(Questions.question12)

            await bot.send_message(
                user_id=message.message.sender.user_id,
                text="Вопрос №12\nПредставь пятилетнего себя в тот момент, когда он/она принял(а) решение из вопроса 6.\nТы подходишь к этому ребёнку.\nЧто ты ДЕЛАЕШЬ? (Не говоришь — делаешь.)"
            )

    except Exception as e:
        logger.exception(f"Ошибка на вопросе 11 у {user_id}: {e}")
        await bot.send_message(
            user_id=user_id,
            text=f"Неизвестная ошибка.",
        )

@dp.message_created(F.message.body.text, Questions.question12)
async def save_answers(message: MessageCreated, context: MemoryContext):
    user_id = message.message.sender.user_id
    user = await UserRepository.get_user(user_id)

    try:
        if not user:
            await bot.send_message(
                user_id=user_id,
                text=f"Вы не зарегестрированы! Отправьте в чат - /start для повторной регестрации.",
            )
        else:
            await QuestionsRepository.add_questions_user(user.id, f"Ответ на вопрос № 12:\n{message.message.body.text}")
            await context.clear()

            await UserRepository.update_recorded_status(user.id)
            logger.info(f"Пользователь {user_id} ({user.name}) завершил все вопросы и записан.")

            await bot.send_message(
                user_id=message.message.sender.user_id,
                text="✅ Спасибо за ответы! Ваши ответы переданы и вскоре с вами свяжутся! До встречи!"
            )

            kb = InlineKeyboardBuilder()
            kb.row(CallbackButton(text="🔙 К списку", payload=f"answers_list"))
            await SendingManager.send_notification_max_to_admins(
                "❗ Новая запись на бесплатную консультацию.\n"
                f"   Имя: {user.name}\n"
                f"   С какой проблемой обратились: {user.description}\n"
                f"   Телефон: +{user.phone_number}\n", attachments=[kb.as_markup()]
            )
        await asyncio.sleep(1)
        await user_panel(message)

    except Exception as e:
        logger.exception(f"Ошибка при сохранении ответов у {user_id}: {e}")
        await bot.send_message(
            user_id=user_id,
            text=f"Неизвестная ошибка.",
        )

# user logic
@dp.message_created(Command('panel'))
async def user_panel(event: MessageCreated):
    user_id = event.message.sender.user_id
    logger.info(f"Пользователь {user_id} вызвал панель")

    reply_kb = InlineKeyboardBuilder()
    reply_kb.row(CallbackButton(text="👤 Мой профиль", payload="my_profile"))
    reply_kb.row(CallbackButton(text="📋 Статус заявки", payload="my_status"))

    await bot.send_message(
        user_id=user_id,
        text=(
            "👋 Вы в личном кабинете.\n\n"
            "Здесь вы можете посмотреть свои данные или узнать статус вашей заявки на консультацию.\n\n"
            "Выберите действие на кнопках ниже:"
        ),
        attachments=[reply_kb.as_markup()]
    )


@dp.message_callback(F.callback.payload == "my_profile")
async def show_profile(callback: MessageCallback):
    user_id = callback.callback.user.user_id
    logger.info(f"Пользователь {user_id} запросил профиль")

    try:
        user = await UserRepository.get_user(user_id)
        if not user:
            await callback.message.edit(
                text="❌ Вы не зарегистрированы. Напишите /start для регистрации.",
                attachments=[]
            )
            return

        text = (
            f"👤 Ваш профиль\n\n"
            f"Имя: {user.name}\n"
            f"Телефон: +{user.phone_number}\n"
            f"Ваш запрос: {user.description if user.description else 'Не указан'}\n\n"
        )

        kb = InlineKeyboardBuilder()
        kb.row(CallbackButton(text="🔙 Назад", payload="user_panel_back"))

        await callback.message.edit(text=text, attachments=[kb.as_markup()])

    except Exception as e:
        logger.exception(f"Ошибка при показе профиля для {user_id}: {e}")
        await callback.message.answer(text="⚠️ Произошла ошибка при загрузке профиля.")


@dp.message_callback(F.callback.payload == "my_status")
async def show_status(callback: MessageCallback):
    user_id = callback.callback.user.user_id
    logger.info(f"Пользователь {user_id} запросил статус заявки")

    try:
        user = await UserRepository.get_user(user_id)
        if not user:
            await callback.message.edit(
                text="❌ Вы не зарегистрированы. Напишите /start для регистрации.",
                attachments=[]
            )
            return

        if user.already_recorded:
            status_text = "✅ Ваша заявка принята. Ожидайте звонка для подтверждения консультации."
        else:
            status_text = "⏳ Вы еще не ответили на все вопросы. Заявка не оформлена.\nНажмите кнопку 'Ответить на вопросы' в главном меню, чтобы завершить запись."

        text = f"📋 Статус вашей заявки\n\n{status_text}"

        kb = InlineKeyboardBuilder()
        kb.row(CallbackButton(text="🔙 Назад", payload="user_panel_back"))

        await callback.message.edit(text=text, attachments=[kb.as_markup()])

    except Exception as e:
        logger.exception(f"Ошибка при показе статуса для {user_id}: {e}")
        await callback.message.answer(text="⚠️ Произошла ошибка при загрузке статуса.")


@dp.message_callback(F.callback.payload == "user_panel_back")
async def back_to_user_panel(callback: MessageCallback):
    user_id = callback.callback.user.user_id
    logger.info(f"Пользователь {user_id} вернулся в личный кабинет")

    reply_kb = InlineKeyboardBuilder()
    reply_kb.row(CallbackButton(text="👤 Мой профиль", payload="my_profile"))
    reply_kb.row(CallbackButton(text="📋 Статус заявки", payload="my_status"))

    await callback.message.edit(
        text=(
            "👋 Вы в личном кабинете.\n\n"
            "Здесь вы можете посмотреть свои данные или узнать статус вашей заявки на консультацию.\n\n"
            "Выберите действие на кнопках ниже:"
        ),
        attachments=[reply_kb.as_markup()]
    )

@dp.message_created(Command('profile'))
async def user_profile(event: MessageCreated):
    await user_panel(event)


@dp.message_created(Command('status_rec'))
async def user_status(event: MessageCreated):
    await user_panel(event)

# admin logic
@dp.message_created(Command('admin'))
async def admin_panel(event: MessageCreated):
    user_id = event.message.sender.user_id
    user = await UserRepository.get_user(user_id)

    try:
        is_admin = await UserRepository.check_admin(user_id)

        if is_admin:
            logger.info(f"Админ {user_id} зашел в панель")
            reply_kb = InlineKeyboardBuilder()
            reply_kb.row(CallbackButton(text="Список записанных", payload="recorders_list"))
            reply_kb.row(CallbackButton(text="Посмотртеь ответы пользователей", payload="answers_list"))
            reply_kb.row(CallbackButton(text="Отправить уведомления", payload="send_message"))
            reply_kb.row(CallbackButton(text="Статистика", payload="statistics"))

            await bot.send_message(
                user_id=user_id,
                text=(
                    "Вы в панели администратора."
                    "\nОписание:"
                    "\nСписок записанных - просмотр список записанных участников."
                    "\nОтветы пользователей - просмотр ответов пользователей для записи."
                    "\nОтправить уведомления - отправить сообщение всем участником бота."
                    "\nСтатистика - просмотр статистики по боту."
                    "\n\nВыберите действия на кнопках."
                ),
                attachments=[reply_kb.as_markup()]
            )

        else:
            logger.warning(f"Пользователь {user_id} пытался зайти в админку без прав")
            await bot.send_message(
                user_id=user_id,
                text="❌ Вы не являетесь администратором."
            )

    except Exception as e:
        logger.exception(f"Ошибка в admin_panel у {user_id}: {e}")
        await bot.send_message(
            user_id=user_id,
            text=f"Неизвестная ошибка.",
        )

@dp.message_callback(F.callback.payload == "admin_panel")
async def get_admin_panel(callback: MessageCallback):
    reply_kb = InlineKeyboardBuilder()
    reply_kb.row(CallbackButton(text="Список записанных", payload="recorders_list"))
    reply_kb.row(CallbackButton(text="Ответы пользователей", payload="answers_list"))
    reply_kb.row(CallbackButton(text="Отправить уведомления", payload="send_messages"))
    reply_kb.row(CallbackButton(text="Статистика", payload="statistics"))

    await callback.message.edit(
        text=(
            "Вы в панели администратора."
            "\nОписание:"
            "\nСписок записанных - просмотр список записанных участников."
            "\nОтветы пользователей - просмотр ответов пользователей для записи."
            "\nОтправить уведомления - отправить сообщение всем участником бота."
            "\nСтатистика - просмотр статистики по боту."
            "\n\nВыберите действия на кнопках."
        ),
        attachments=[reply_kb.as_markup()]
    )

@dp.message_callback(F.callback.payload == "recorders_list")
async def get_recorders_list(callback: MessageCallback):
    user_id = callback.message.sender.user_id
    user = await UserRepository.get_user(user_id)

    try:
        is_admin = await UserRepository.check_admin(user_id)
        await show_users_page(callback, user_id, page=1)

    except Exception as e:
        logger.exception(f"Ошибка в recorders_list у {user_id}: {e}")
        await callback.message.send(
            text=f"Неизвестная ошибка."
        )

@dp.message_callback(F.callback.payload.startswith("admin_page_"))
async def handle_admin_pagination(callback: MessageCallback):
    page = int(callback.callback.payload.split("_")[-1])

    await show_users_page(callback, callback.callback.user.user_id, page=page)

@dp.message_callback(F.callback.payload == "answers_list")
async def get_recorders_list(callback: MessageCallback):
    user_id = callback.callback.user.user_id

    if await UserRepository.check_admin(user_id):
        await show_answers_users_menu(callback, page=1)
    else:
        await callback.message.answer(text="❌ Вы не являетесь администратором.")

@dp.message_callback(F.callback.payload.startswith("ans_users_page_"))
async def paginate_answers_users(callback: MessageCallback):
    page = int(callback.callback.payload.split("_")[-1])
    await show_answers_users_menu(callback, page=page)

@dp.message_callback(F.callback.payload.startswith("view_ans_"))
async def send_user_answers(callback: MessageCallback):
    parts = callback.callback.payload.split("_")
    target_user_id = int(parts[2])
    return_page = int(parts[3])

    logger.info(f"Админ {callback.callback.user.user_id} просматривает ответы пользователя {target_user_id}")

    answers = await QuestionsRepository.get_answers_user(target_user_id)
    await send_answers_file(callback, answers, target_user_id)
    await UserRepository.update_user_is_viewed_answers(target_user_id)

    kb = InlineKeyboardBuilder()
    kb.row(CallbackButton(text="🔙 К списку", payload=f"ans_users_page_{return_page}"))

    await callback.message.answer(
        text="✅ Файл с ответами отправлен. Пользователь отмечен как просмотренный.",
        attachments=[kb.as_markup()]
    )

@dp.message_callback(F.callback.payload.startswith("send_messages"))
async def send_all_users_message(callback: MessageCallback, context: MemoryContext):
    await context.set_state(Mailing.wait_text)
    await context.set_data({})
    await callback.message.edit(text="Отправьте текст для отправки сообщения всем участникам.", attachments=[])

@dp.message_created(F.message.body.text, Mailing.wait_text)
async def ask_mailing_confirmation(event: MessageCreated, context: MemoryContext):
    text_to_send = event.message.body.text

    await context.update_data(mail_text=text_to_send)
    await context.set_state(Mailing.confirm)

    kb = InlineKeyboardBuilder()
    kb.row(
        CallbackButton(text="✅ ДА, отправить", payload="confirm_mailing"),
        CallbackButton(text="❌ НЕТ, отменить", payload="admin_panel")
    )

    await bot.send_message(
        user_id=event.message.sender.user_id,
        text=f"Внимательно прочитайте текст!\n\nВы уверены, что хотите отправить его всем?",
        attachments=[kb.as_markup()]
    )

@dp.message_callback(F.callback.payload == "confirm_mailing")
async def confirm_mailing(callback: MessageCallback, context: MemoryContext):
    data = await context.get_data()
    text_to_send = data.get("mail_text")

    if not text_to_send:
        await callback.message.edit(text="❌ Текст потерян. Начните заново.", attachments=[])
        await context.clear()
        return

    await callback.message.edit(text="🔄 Начинаю рассылку...", attachments=[])
    logger.info(f"Админ {callback.callback.user.user_id} начал рассылку")

    users_list = await UserRepository.get_users_list()

    success = 0
    fail = 0

    for user in users_list:
        try:
            await SendingManager.send_notification_max(user.max_id, text_to_send)
            success += 1
            await asyncio.sleep(1.5)
        except Exception as e:
            fail += 1
            logger.error(f"Ошибка отправки {user.max_id}: {e}")

    await context.clear()
    logger.info(f"Рассылка завершена. Успешно: {success}, Ошибок: {fail}")

    await callback.message.answer(
        text=f"✅ Рассылка завершена!\nУспешно: {success}\nОшибок: {fail}"
    )

    await asyncio.sleep(1)
    await get_admin_panel(callback)

@dp.message_callback(F.callback.payload == "statistics")
async def get_statistics(callback: MessageCallback):
    user_id = callback.callback.user.user_id

    if not await UserRepository.check_admin(user_id):
        await callback.message.answer(text="❌ Вы не являетесь администратором.")
        return

    stats = await UserRepository.get_statistics()

    conversion = 0
    if stats['total'] > 0:
        conversion = round((stats['recorded'] / stats['total']) * 100, 1)

    text = (
        "📊 Статистика бота\n\n"
        f"👥 Всего запустили бота: {stats['total']}\n\n"
        f"📝 Начали, но не закончили: {stats['in_progress']}\n\n"
        f"✅ Успешно записались: {stats['recorded']}\n\n"
        f"🆕 Новых ответов (не просмотрено): {stats['new_recorded']}\n\n"
        f"📈 Конверсия в запись: {conversion}%\n"
    )

    kb = InlineKeyboardBuilder()
    kb.row(CallbackButton(text="В галвное меню", payload="admin_panel"))

    await callback.message.edit(
        text=text,
        attachments=[kb.as_markup()]
    )


async def main():
    logger.info("Бот запущен webhook")

    webhook_url = "https://mtv-psy.ru/webhook"
    webhook_secret = settings.SECRET_WEBHOOK_KEY

    await bot.subscribe_webhook(url=webhook_url, secret=webhook_secret)

    await dp.handle_webhook(
        bot=bot,
        host='0.0.0.0',
        port=8080,
        secret=webhook_secret,
        path='/webhook'
    )


if __name__ == "__main__":
    asyncio.run(main())