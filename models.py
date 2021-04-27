import config
from datetime import datetime

from peewee import Model, FloatField, CharField, ForeignKeyField, IntegerField
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


class Payer(BaseModel):
    name = CharField(max_length=255, unique=True)


class Product(BaseModel):
    name = CharField(max_length=512, null=True)
    price = FloatField(null=False)
    category = ForeignKeyField(Category)
    payer = ForeignKeyField(Payer)



def first_init_db():
    db.create_tables([Product, Category, Payer])

    # add default Categories
    categories = ['транспорт', 'еда', 'подарки',
                  'медицина', 'развлечение', 'автомобильные принадлежности', 'дети',
                  'связь', 'вещи для дома', 'накопления', 'одежда и обувь', 'работа',
                  'красота', 'кредиты', 'кварплата']
    for category in categories:
        Category.create(name=category)

    payers = ['антон', "наташа", "егор", "общее"]
    for payer in payers:
        Payer.create(name=payer)

# first_init_db()
