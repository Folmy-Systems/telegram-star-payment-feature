import os
import logging
import asyncio
from typing import Optional
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, 
    PreCheckoutQuery, 
    SuccessfulPayment, 
    LabeledPrice,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=os.getenv('BOT_TOKEN'))
dp = Dispatcher()

# Константы
STARS_AMOUNT = 1  # Количество Stars для оплаты
PRODUCT_TITLE = "Премиум-контент"
PRODUCT_DESCRIPTION = "Доступ к эксклюзивному премиум-контенту на 30 дней"
PAYLOAD = "premium_subscription_001"

class PaymentBot:
    def __init__(self):
        self.bot = bot
        self.dp = dp
        self.setup_handlers()
    
    def setup_handlers(self):
        """Регистрация всех обработчиков"""
        # Команды
        self.dp.message.register(self.start_command, Command("start"))
        self.dp.message.register(self.help_command, Command("help"))
        self.dp.message.register(self.buy_command, Command("buy"))
        
        # Обработка платежей
        self.dp.pre_checkout_query.register(self.pre_checkout_handler)
        self.dp.message.register(self.successful_payment_handler, F.successful_payment)
        
        # Обработка callback-кнопок
        self.dp.callback_query.register(self.buy_callback_handler, F.data == "buy_premium")
    
    async def start_command(self, message: Message):
        """Обработка команды /start"""
        try:
            welcome_text = (
                "🌟 Добро пожаловать в Stars Payment Bot! 🌟\n\n"
                "Этот бот демонстрирует работу платежей через Telegram Stars.\n"
                "Вы можете приобрести премиум-контент за Stars.\n\n"
                "Доступные команды:\n"
                "/buy - Купить премиум-контент\n"
                "/help - Показать справку"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🌟 Купить премиум", callback_data="buy_premium")]
            ])
            
            await message.answer(welcome_text, reply_markup=keyboard)
            logger.info(f"Пользователь {message.from_user.id} запустил бота")
            
        except Exception as e:
            logger.error(f"Ошибка в команде start: {e}")
            await message.answer("❌ Произошла ошибка. Попробуйте позже.")
    
    async def help_command(self, message: Message):
        """Обработка команды /help"""
        help_text = (
            "🤖 Справка\n\n"
            "Этот бот позволяет совершать платежи через Telegram Stars.\n\n"
            "🌟 Как использовать:\n"
            "1. Нажмите кнопку 'Купить премиум' или используйте команду /buy\n"
            "2. Подтвердите оплату в интерфейсе Telegram\n"
            "3. После успешного платежа получите доступ к премиум-контенту\n\n"
            "💡 Важно: у вас должно быть достаточно Stars на балансе."
        )
        await message.answer(help_text)
    
    async def buy_command(self, message: Message):
        """Обработка команды /buy"""
        await self.create_invoice(message)
    
    async def buy_callback_handler(self, callback_query: CallbackQuery):
        """Обработка нажатия на кнопку покупки"""
        try:
            await self.create_invoice(callback_query.message)
            await callback_query.answer()
        except Exception as e:
            logger.error(f"Ошибка в buy callback: {e}")
            await callback_query.answer("❌ Не удалось создать счёт", show_alert=True)
    
    async def create_invoice(self, message: Message):
        """Создание и отправка счёта на оплату"""
        try:
            prices = [LabeledPrice(label="Премиум-подписка", amount=STARS_AMOUNT)]
            
            await self.bot.send_invoice(
                chat_id=message.chat.id,
                title=PRODUCT_TITLE,
                description=PRODUCT_DESCRIPTION,
                payload=PAYLOAD,
                provider_token="",  # Для Stars токен не нужен
                currency="XTR",     # Код валюты Telegram Stars
                prices=prices,
                start_parameter="premium_subscription",
                need_name=False,
                need_phone_number=False,
                need_email=False,
                need_shipping_address=False,
                is_flexible=False,
                disable_notification=False,
                protect_content=False,
                request_timeout=15
            )
            
            logger.info(f"Счёт отправлен пользователю {message.from_user.id}")
            
        except TelegramBadRequest as e:
            logger.error(f"Ошибка Telegram API в create_invoice: {e}")
            await message.answer("❌ Платежный сервис временно недоступен. Попробуйте позже.")
        except TelegramNetworkError as e:
            logger.error(f"Сетевая ошибка в create_invoice: {e}")
            await message.answer("❌ Ошибка сети. Проверьте подключение и попробуйте снова.")
        except Exception as e:
            logger.error(f"Неизвестная ошибка в create_invoice: {e}")
            await message.answer("❌ Произошла неожиданная ошибка. Попробуйте позже.")
    
    async def pre_checkout_handler(self, pre_checkout_query: PreCheckoutQuery):
        """Обработка запроса перед оплатой"""
        try:
            if pre_checkout_query.invoice_payload != PAYLOAD:
                await pre_checkout_query.answer(ok=False, error_message="Неверный идентификатор платежа")
                return
            
            await pre_checkout_query.answer(ok=True)
            logger.info(f"Pre-checkout подтверждён для пользователя {pre_checkout_query.from_user.id}")
            
        except Exception as e:
            logger.error(f"Ошибка в pre_checkout_handler: {e}")
            await pre_checkout_query.answer(ok=False, error_message="Ошибка валидации платежа")
    
    async def successful_payment_handler(self, message: Message):
        """Обработка успешного платежа"""
        try:
            payment: SuccessfulPayment = message.successful_payment
            
            success_text = (
                "🎉 Платёж успешен! 🎉\n\n"
                f"Спасибо за покупку!\n"
                f"Сумма: {payment.total_amount} Stars\n"
                f"Продукт: {PRODUCT_TITLE}\n\n"
                "Ваш премиум-доступ активирован на 30 дней!\n"
                "Наслаждайтесь эксклюзивным контентом 🚀"
            )
            
            await message.answer(success_text)
            
            logger.info(
                f"Успешный платёж - Пользователь: {message.from_user.id}, "
                f"Сумма: {payment.total_amount} Stars, "
                f"Payload: {payment.invoice_payload}"
            )
            
            admin_id = os.getenv('ADMIN_ID')
            if admin_id:
                admin_notification = (
                    f"💰 Получен новый платёж!\n"
                    f"Пользователь: {message.from_user.full_name} (@{message.from_user.username})\n"
                    f"Сумма: {payment.total_amount} Stars\n"
                    f"ID пользователя: {message.from_user.id}"
                )
                await self.bot.send_message(chat_id=admin_id, text=admin_notification)
                
        except Exception as e:
            logger.error(f"Ошибка при обработке успешного платежа: {e}")
            await message.answer("✅ Платёж получен! Но произошла ошибка при активации доступа. Свяжитесь с поддержкой.")

    async def run(self):
        """Запуск бота"""
        try:
            logger.info("Запуск Stars Payment Bot...")
            await self.bot.delete_webhook(drop_pending_updates=True)
            await self.dp.start_polling(self.bot, allowed_updates=dp.resolve_used_update_types())
            
        except Exception as e:
            logger.error(f"Не удалось запустить бота: {e}")
        finally:
            await self.bot.session.close()

async def main():
    """Главная функция"""
    if not os.getenv('BOT_TOKEN'):
        logger.error("Переменная окружения BOT_TOKEN не задана!")
        return
    
    payment_bot = PaymentBot()
    await payment_bot.run()

if __name__ == "__main__":
    asyncio.run(main())
