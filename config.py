from os import getenv
import logging

API_TOKEN = getenv('API_TOKEN')

# Configure logging
DEBUG = False if getenv('DEBUG') == 'false' else True
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Database Postgres
DB_NAME = getenv('DB_NAME')
DB_HOST = getenv('DB_HOST')
DB_PORT = getenv('DB_PORT')
DB_USER = getenv('DB_USER')
DB_PASSWORD = getenv('DB_PASSWORD')

# Database Redis
REDIS_HOST = getenv('REDIS_HOST') or 'localhost'
REDIS_PORT = getenv('REDIS_PORT') or 6379
REDIS_DB = getenv('REDIS_DB') or 2
