# Production
FROM python:3.8-slim

# install Russian localization
RUN apt-get update && apt-get install locales -y
RUN sed -i '/ru_RU.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen
ENV LANG ru_RU.UTF-8
ENV LANGUAGE ru_RU:en
ENV LC_ALL ru_RU.UTF-8

ENV DEBIAN_FRONTEND noninteractive
ENV TZ=Asia/Novosibirsk
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN pip install --no-cache-dir poetry~=1.1.3

COPY poetry.lock pyproject.toml ./
RUN poetry config virtualenvs.create false
RUN poetry install

COPY . /app

WORKDIR /app
