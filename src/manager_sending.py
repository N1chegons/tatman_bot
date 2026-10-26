import logging

logger = logging.getLogger("psy_bot.sending")

class SendingManager:
    @classmethod
    async def send_notification_max(cls, user_id: int, text: str):
        try:
            from src.main import bot
            await bot.send_message(user_id=user_id, text=text)
            logger.info(f"Сообщение успешно отправлено пользователю {user_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")

    @classmethod
    async def send_notification_max_to_admins(cls, text: str, attachments = None):
        ADMIN_IDS = [235995783, 56185590]
        if attachments:
            attachments = attachments
        else:
            attachments = []
        try:
            from src.main import bot
            for id_admin in ADMIN_IDS:
                await bot.send_message(user_id=id_admin, text=text, attachments=attachments)
                logger.info(f"Уведомление отправлено админу {id_admin}")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админам: {e}")