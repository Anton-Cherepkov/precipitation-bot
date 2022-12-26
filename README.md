# precipitation-bot
Данный бот можно протестировать в любое время по адресу https://t.me/precipitation_bot.

Если бот не отвечает / упал / что-то ещё, то свяжитесь с:
* https://t.me/nikitayusupov (nikitayusupov@gmail.com) 
* или https://t.me/acherepkov (cherepkov.ayu@phystech.edu).

## О боте
Данный Telegram-бот умеет отвечать на вопроc: «Какие осадки ожидаются в ближайшее время?». Есть возможность сохранять/изменять избранные локации.

Прогноз погоды получается с помощью GET-запроса к [API Яндекс Погоды](https://yandex.ru/dev/weather/doc/dg/concepts/forecast-test.html).

Избранные локации пользователя хранятся в базе данных [PostgreSQL](https://hub.docker.com/_/postgres).

## Пример взаимодействия
![image](https://user-images.githubusercontent.com/11422372/209538103-89106755-5537-46cc-985b-f18b920763eb.png)


## Системные требования
1. docker
2. docker-compose
3. internet connection

## Запуск
1. В файле `env/weather_bot.env` указать токен Telegram-бота `TELEGRAM_TOKEN` и токен Yandex-погоды `WEATHER_TOKEN`
2. `docker-compose build`
3. `docker-compose up`
