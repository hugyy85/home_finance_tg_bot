import config
from datetime import datetime

from peewee import Model, FloatField, CharField, ForeignKeyField, IntegerField, BigIntegerField
from playhouse.postgres_ext import PostgresqlExtDatabase, DateTimeTZField

db = PostgresqlExtDatabase(config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
                           host=config.DB_HOST, port=config.DB_PORT)


class BaseModel(Model):
    creation_date = DateTimeTZField(default=datetime.now)
    # дата актуальности значения. Меняется с каждым новым загруженным файлом
    update_date = DateTimeTZField(default=datetime.now)

    class Meta:
        database = db


class Category(BaseModel):
    name = CharField(max_length=255, unique=True)
    plan_money = FloatField(null=True)


class Payer(BaseModel):
    name = CharField(max_length=255, unique=True)


class ReportPeriod(BaseModel):
    month = IntegerField()
    year = IntegerField()
    balance = FloatField()

    class Meta:
        indexes = (
            # create a unique on
            (('month', 'year'), True),
        )


class User(BaseModel):
    id = BigIntegerField(primary_key=True, unique=True)
    first_name = CharField()
    last_name = CharField()
    username = CharField()
    type = CharField()


class Product(BaseModel):
    name = CharField(max_length=512, null=True)
    price = FloatField(null=False)
    category = ForeignKeyField(Category)
    payer = ForeignKeyField(Payer)
    report_month = ForeignKeyField(ReportPeriod)
    user = ForeignKeyField(User)


class PiggyBank(BaseModel):
    name = CharField(unique=True)
    balance = FloatField(default=0)


def first_init_db():
    db.create_tables([Product, Category, Payer, ReportPeriod, User, PiggyBank])

    # add default Categories
    categories = ['транспорт', 'еда', 'подарки',
                  'медицина', 'развлечение', 'авто', 'дети',
                  'связь', 'дом', 'накопления', 'одежда', 'работа',
                  'красота', 'кредиты', 'кварплата']
    for category in categories:
        Category.create(name=category)

    payers = ['антон', "наташа", "егор", "общее"]
    for payer in payers:
        Payer.create(name=payer)

    date_now = datetime.now()
    ReportPeriod.create(month=date_now.month, year=date_now.year, balance=7495)

    piggy_bank = [{'name': 'car', 'balance': 6000}, {'name': 'holidays', 'balance': 4908},
                  {'name': 'cashback', 'balance': 4276}]
    [PiggyBank.create(**x) for x in piggy_bank]


def add_column():
    from playhouse.migrate import PostgresqlMigrator, migrate
    migrator = PostgresqlMigrator(db)
    plan_money = FloatField(default=None, null=True)

    migrate(
        migrator.add_column('category', 'plan_money', plan_money),
    )
    categories = {'транспорт': 1000, 'еда': 25000, 'подарки': 3000,
                  'медицина': 3000, 'развлечение': 2500, 'авто': 3000, 'дети': 5000,
                  'связь': 800, 'дом': 1500, 'накопления': 4000, 'одежда': 1000, 'работа': 1000,
                  'красота': 1500, 'кредиты': 20000, 'кварплата': 6000}

    for cat in Category.select():
        cat.plan_money = categories[cat.name]
        cat.save()

# add_column()
