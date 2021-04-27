# Production
FROM python:3.8-slim

RUN pip install --no-cache-dir poetry~=1.1.3

COPY poetry.lock pyproject.toml ./
RUN poetry config virtualenvs.create false
RUN poetry install

COPY . /app

WORKDIR /app
