FROM python:3.10-slim

RUN pip install --upgrade pip

COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt
RUN rm /requirements.txt

COPY . /app
RUN pip install /app

WORKDIR /app
RUN ls
CMD python weather_bot/app.py