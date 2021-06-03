import datetime

from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import KeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.redis import RedisStorage
from aiogram.utils.markdown import bold
from peewee import IntegrityError, fn

from config import API_TOKEN, REDIS_DB, REDIS_PORT, REDIS_HOST
from models import Category, Product, Payer, ReportPeriod, db, User, PiggyBank

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
    await message.answer(
        f"Вы ввели покупку {bold(user_data['chosen_name'])} в категорию {bold(user_data['chosen_category'])}"
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
    message_text = message.text.split()
    if len(message_text) != 2:
        await message.reply("Необходимо добавить сумму на месяц")
        return
    balance = message_text[1]

    date_now = datetime.datetime.now()
    try:
        report = ReportPeriod.create(month=date_now.month, year=date_now.year, balance=balance)
        answer = f'{report.month}.{report.year} - сумма на месяц: {balance}'
    except IntegrityError:
        db.rollback()
        answer = 'Данный месяц еще не закончился, попробуйте изменить отчетный период 1го числа следующего месяца'
    await message.reply(answer)


async def is_user_register(message):
    try:
        user = User.get(id=message.chat['id'])
    except User.DoesNotExist:
        await message.reply("Для вашего пользователя отчета нет")
        user = None
    return user


@dp.message_handler(commands=['show_report'])
async def show_report(message):
    user = await is_user_register(message)
    if user is None:
        return
    report_period = ReportPeriod.select().order_by(ReportPeriod.id.desc()).get()
    spent_money = Product.select(fn.SUM(Product.price)) \
        .where((Product.user == user) & (Product.report_month == report_period)) \
        .get()
    piggy_bank = PiggyBank.select(fn.SUM(PiggyBank.balance)).get()
    total_balance = report_period.balance - spent_money.sum
    plan_and_real = Product.select(fn.SUM(Product.price), Category.name, Category.plan_money).join(Category)\
        .where((Product.user == user) & (Product.report_month == report_period))\
        .group_by(Category.id, Category.name, Category.plan_money).order_by(Category.id)
    spent = ' Потрачено '
    plan_t = ' Запланировано '
    total = ' Остаток '
    category = ' Категория\n'
    answer = '|'.join([spent, plan_t, total, category])
    for plan in plan_and_real:
        answer += f'{__get_beauty_table(plan.sum, spent)}| {__get_beauty_table(plan.category.plan_money, plan_t)}|' \
                  f' {__get_beauty_table(plan.category.plan_money - plan.sum, total)}|' \
                  f' {plan.category.name}\n'
    answer += f"\nОстаток в этом месяце: {round(total_balance, 2)}\nОстаток на карте(+отложенные) {round(total_balance + piggy_bank.sum, 2)}"
    await message.reply(answer)


def __get_beauty_table(money, pattern):
    string = str(round(money, 2))
    space_count = (len(pattern) - len(string)) * 2
    return string + ' ' * space_count if space_count > 0 else string


@dp.message_handler(commands=['show_last_products'])
async def show_last_products(message):
    user = await is_user_register(message)
    if user is None:
        return

    message_text = message.text.split()
    try:
        limit = int(message_text[1]) if len(message_text) == 2 else 20
    except ValueError:
        limit = 20

    products = Product.select().where(Product.user == user).order_by(Product.id.desc()).limit(limit)
    answer = ''
    for prod in products:
        answer += f'{prod.id} - {prod.name} - {prod.price} - {prod.creation_date.strftime("%d.%m.%y %H:%M:%S")}\n'

    await message.reply(answer)


@dp.message_handler(commands=['remove_product_by_id'])
async def remove_product_by_id(message):
    user = await is_user_register(message)
    if user is None:
        return

    message_text = message.text.split()
    if len(message_text) != 2:
        await message.reply("Необходимо добавить id для удаления покупки")
        return
    product_id = message_text[1]
    try:
        product = Product.get(id=product_id, user=user)
        product.delete_instance()
        answer = f'Покупка с айди {product_id} удалена'
    except Product.DoesNotExist:
        answer = 'Покупки с таким ID для данного пользователя не существует'
    await message.reply(answer)


@dp.message_handler()
async def answer_tmpl(message):
    answer = """
       /add_product - Добавить запись о покупке
       /last_date_check - Показать последнюю дату добавления покупки
       /show_report_period - Показать отчетный месяц
       /next_report_period 80000 - Перейти в следующий отчетный месяц c балансом 80000
       /show_report - Показать отчет за текущий месяц
       /show_last_products - Показать последние 10 добавленных записей
       /remove_product_by_id - удалить покупку по айдишнику
       """
    await message.reply(answer)


# добавить фронт для отображения таблицы с данными - сколько потрачено, в каких категориях, и кем,
# добавить возможность изменять piggybank из фронта,
# добавить планированный бюджет и если бюджет привышен, то алерт
# Как идея перенести все данные в гугл таблицу по кнопке, чтобы там тоже смотреть можно было


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
