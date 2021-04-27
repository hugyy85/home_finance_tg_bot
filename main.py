import datetime

from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.redis import RedisStorage
from aiogram.utils.markdown import text, bold, italic
from peewee import IntegrityError

from config import API_TOKEN, REDIS_DB, REDIS_PORT, REDIS_HOST
from models import Category, Product, Payer, ReportPeriod, db, User


# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
storage = RedisStorage(REDIS_HOST, REDIS_PORT, db=REDIS_DB)
dp = Dispatcher(bot, storage=storage)
CATEGORIES = [x.name.lower() for x in Category.select()]
PAYER = [x.name.lower() for x in Payer.select()]

# ============= Процесс добавления нового товара в БД ================
class OrderProduct(StatesGroup):
    waiting_for_product_category = State()
    waiting_for_product_name = State()
    waiting_for_product_price = State()
    waiting_for_product_payer = State()


@dp.message_handler(commands=['add_product'], state='*')
async def product_start(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for category in CATEGORIES:
        button = KeyboardButton(category)
        keyboard.insert(button)
    await message.answer("Выберите категорию:", reply_markup=keyboard)
    await OrderProduct.waiting_for_product_category.set()


@dp.message_handler(state=OrderProduct.waiting_for_product_category)
async def product_category_chosen(message: types.Message, state: FSMContext):
    if message.text.lower() not in CATEGORIES:
        await message.answer("Пожалуйста, выберите категорию, используя клавиатуру ниже.")
        return
    await state.update_data(chosen_category=message.text.lower())

    await OrderProduct.next()
    await message.answer("Теперь выберите название покупки:")


@dp.message_handler(state=OrderProduct.waiting_for_product_name)
async def _name_chosen(message: types.Message, state: FSMContext):
    await state.update_data(chosen_name=message.text.lower())
    user_data = await state.get_data()
    await message.answer(f"Вы ввели покупку {user_data['chosen_name']} в категорию {user_data['chosen_category']}.\n")
    await OrderProduct.next()
    await message.answer("Теперь выберите цену покупки:")


@dp.message_handler(state=OrderProduct.waiting_for_product_price)
async def _price_chosen(message: types.Message, state: FSMContext):
    try:
        price = message.text.replace(',', '.')
        price = float(price)
    except ValueError:
        await message.answer("Пожалуйста, введите корректную цену, например 154.20")
        return

    await state.update_data(chosen_price=price)
    user_data = await state.get_data()
    await message.answer(f"Вы ввели покупку  {user_data['chosen_name']} в категорию {user_data['chosen_category']} "
                         f"с ценой  {user_data['chosen_price']} \n")
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for category in PAYER:
        button = KeyboardButton(category)
        keyboard.insert(button)
    await OrderProduct.next()
    await message.answer("Теперь выберите покупателя покупки:", reply_markup=keyboard)


@dp.message_handler(state=OrderProduct.waiting_for_product_payer)
async def _payer_chosen(message: types.Message, state: FSMContext):
    if message.text.lower() not in PAYER:
        await message.answer("Пожалуйста, выберите покупателя, используя клавиатуру ниже.")
        return
    await state.update_data(chosen_payer=message.text.lower())
    user_data = await state.get_data()
    user, _ = User.get_or_create(**dict(message.chat))
    Product.create(
        name=user_data['chosen_name'],
        category=Category.select().where(Category.name == user_data['chosen_category']),
        payer=Payer.select().where(Payer.name == user_data['chosen_payer']),
        price=user_data['chosen_price'],
        report_month=ReportPeriod.select().order_by(ReportPeriod.id.desc()).get(),
        user=user

    )
    await message.answer(f"Вы ввели покупку {bold(user_data['chosen_name'])} в категорию {bold(user_data['chosen_category'])}"
                         f" с ценой {bold(user_data['chosen_price'])} и покупателем {bold(user_data['chosen_payer'])}\n"
                         f" Данные записаны", parse_mode='MARKDOWN')
    await OrderProduct.next()
    await state.finish()
# ========== Конец процесса добавления нового товара в бд ==============


@dp.message_handler(commands=['last_date_check'])
async def get_last_date_check(message):
    last_product = Product.select().order_by(Product.id.desc()).get()
    await message.reply(last_product.creation_date)


@dp.message_handler(commands=['show_report_period'])
async def show_report_period(message):
    report_period = ReportPeriod.select().order_by(ReportPeriod.id.desc()).get()
    await message.reply(f'{report_period.month}.{report_period.year}')


@dp.message_handler(commands=['next_report_period'])
async def next_report_period(message):
    date_now = datetime.datetime.now()
    try:
        report = ReportPeriod.create(month=date_now.month, year=date_now.year)
        answer = f'{report.month}.{report.year}'
    except IntegrityError:
        db.rollback()
        answer = 'Данный месяц еще не закончился, попробуйте изменить отчетный период 1го числа следующего месяца'
    await message.reply(answer)


@dp.message_handler()
async def answer_tmpl(message):
    answer = """
       /add_product - Добавить запись о покупке
       /last_date_check - Показать последнюю дату добавления покупки
       /show_report_period - Показать отчетный месяц
       /next_report_period - Перейти в следующий отчетный месяц
       """
    await message.reply(answer)


# добавить отображение остатка,
# добавить сумма на месяц, добавить перерасходы, добавить отложенные деньги,
# добавить последние 10 строк, для сверки, а лучше количество строк из сообщения


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)