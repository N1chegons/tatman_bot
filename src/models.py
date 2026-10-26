import datetime
from typing import List

from maxapi.context import StatesGroup, State
from sqlalchemy import BigInteger, text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    max_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    name: Mapped[str]
    description: Mapped[str] = mapped_column(nullable=True)
    phone_number: Mapped[str]
    already_recorded: Mapped[bool] = mapped_column(default=False)
    is_viewed_answers: Mapped[bool] = mapped_column(default=False)
    register_at: Mapped[datetime.datetime] = mapped_column(
        server_default=text(
            "TIMEZONE('utc', now())")
    )

    answers: Mapped[List["AnswerUser"]] = relationship(back_populates="author")

class AnswerUser(Base):
    __tablename__ = "answer_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    answer: Mapped[str]

    author: Mapped["User"] = relationship(back_populates="answers")


class Registration(StatesGroup):
    name = State()
    description = State()
    phone = State()

class Questions(StatesGroup):
    question1 = State()
    question2 = State()
    question3 = State()
    question4 = State()
    question5 = State()
    question6 = State()
    question7 = State()
    question8 = State()
    question9 = State()
    question10 = State()
    question11 = State()
    question12 = State()

class Mailing(StatesGroup):
    wait_text = State()
    confirm = State()