from sqlalchemy import select, insert, update, func
import logging

from src.db import async_session
from src.models import User, AnswerUser

logger = logging.getLogger("psy_bot.repository")

class UserRepository:
    @classmethod
    async def get_user(cls, max_id: int):
        async with async_session() as session:
            query = select(User).filter_by(max_id=max_id)
            user = await session.execute(query)
            res = user.scalar_one_or_none()
            logger.debug(f"Поиск пользователя по max_id={max_id}: {'найден' if res else 'не найден'}")
            return res

    @classmethod
    async def get_user_by_id(cls, user_id: int):
        async with async_session() as session:
            query = select(User).filter_by(id=user_id)
            user = await session.execute(query)
            return user.scalar_one_or_none()

    @classmethod
    async def get_users_list(cls):
        async with async_session() as session:
            query = select(User)
            user = await session.execute(query)
            res = user.scalars().all()
            logger.info(f"Получен список всех пользователей. Количество: {len(res)}")
            return res

    @classmethod
    async def get_users_recorded(cls):
        async with async_session() as session:
            query = select(User).filter_by(already_recorded=True).order_by(User.id.desc(), User.is_viewed_answers.desc())
            user = await session.execute(query)
            res = user.scalars().all()
            logger.info(f"Получен список записанных пользователей. Количество: {len(res)}")
            return res

    @classmethod
    async def check_admin(cls, max_id: int):
        ADMIN_IDS = [235995783, 56185590]
        is_admin = max_id in ADMIN_IDS
        if is_admin:
            logger.debug(f"Проверка прав: {max_id} - админ")
        return is_admin

    @classmethod
    async def create_user(cls, max_id: int, name: str, phone_number: str, description: str = ""):
        async with async_session() as session:
            stmt = insert(User).values(
                max_id=max_id,
                name=name,
                description=description,
                phone_number=phone_number
            )
            await session.execute(stmt)
            await session.commit()
            logger.info(f"Создан новый пользователь: {name} (max_id={max_id})")

    @classmethod
    async def update_recorded_status(cls, user_id: int):
        async with async_session() as session:
            stmt = (
                update(User)
                .where(User.id == user_id)
                .values(already_recorded=True)
            )
            await session.execute(stmt)
            await session.commit()
            logger.info(f"Пользователь с id={user_id} отмечен как записанный (already_recorded=True)")

    @classmethod
    async def update_user_is_viewed_answers(cls, user_id: int):
        async with async_session() as session:
            stmt = (
                update(User)
                .where(User.id == user_id)
                .values(is_viewed_answers=True)
            )
            await session.execute(stmt)
            await session.commit()
            logger.info(f"Ответы пользователя с id={user_id} отмечены как просмотренные")

    @classmethod
    async def get_statistics(cls):
        async with async_session() as session:
            total_users = await session.scalar(select(func.count(User.id)))
            in_progress = await session.scalar(select(func.count(User.id)).filter_by(already_recorded=False))
            recorded = await session.scalar(select(func.count(User.id)).filter_by(already_recorded=True))
            new_recorded = await session.scalar(select(func.count(User.id)).filter(
                User.already_recorded == True,
                User.is_viewed_answers == False
            ))
            stats = {
                "total": total_users or 0,
                "in_progress": in_progress or 0,
                "recorded": recorded or 0,
                "new_recorded": new_recorded or 0
            }
            logger.debug(f"Собрана статистика: {stats}")
            return stats

class QuestionsRepository:
    @classmethod
    async def get_answers_user(cls, user_id: int):
        async with async_session() as session:
            query = select(AnswerUser).filter_by(user_id=user_id)
            answers = await session.execute(query)
            res = answers.scalars().all()
            logger.debug(f"Получены ответы для user_id={user_id}. Количество: {len(res)}")
            return res

    @classmethod
    async def add_questions_user(cls, user_id: int, answer: str):
        async with async_session() as session:
            stmt = insert(AnswerUser).values(
                user_id=user_id,
                answer=answer
            )
            await session.execute(stmt)
            await session.commit()
            logger.debug(f"Добавлен ответ для user_id={user_id}")