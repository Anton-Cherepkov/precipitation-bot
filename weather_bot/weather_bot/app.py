from functools import partial
from typing import Callable, Awaitable
import os

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from weather_bot.locations_storage import DictUserLocationsStorage, GeoLocation, PostgresUserLocationsStorage, \
    PostgresUserLocationsStorageConfig, DBConnectionException
from weather_bot.weather_receiver import WeatherReceiver, WeatherReceiverConfig, WeatherRequestFailedException

MENU, GET_FORECAST_SELECT, ADD_GEO_LOCATION, ADD_GEO_NAME, DELETE_GEO_SELECT, PRINT_FORECAST = range(6)

MENU_OPTIONS = {
    "get_forecast": "Посмотреть прогноз",
    "add_geo": "Добавить локацию",
    "delete_geo": "Удалить локацию",
    "exit": "Выйти",
}

START_CMD_INFO = "Используйте /start, чтобы начать заново."
EXIT_MSG = f"Операция прервана. {START_CMD_INFO}"

# locations_storage = DictUserLocationsStorage(storage=dict())
locations_storage = PostgresUserLocationsStorage(config=PostgresUserLocationsStorageConfig())

yandex_weather = WeatherReceiver(config=WeatherReceiverConfig())


def available_locations(update: Update) -> list[str]:
    keys = sorted(locations_storage.keys(user_id=update.message.from_user.id))
    return keys


def choose_location(update: Update, next_state: int) -> tuple[str, int]:
    keys = available_locations(update=update)

    msg = "*Введите номер интересующей локации*:"
    msg += "\n0. Отмена"
    for ix, key in enumerate(keys):
        msg += f"\n{ix + 1}. {key}"

    if not keys:
        msg = f"Нет сохраненных локаций. {START_CMD_INFO}"
        next_state = ConversationHandler.END

    return msg, next_state


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks the user about their gender."""
    reply_keyboard = [
        [
            MENU_OPTIONS["get_forecast"],
            MENU_OPTIONS["add_geo"],
        ],
        [
            MENU_OPTIONS["delete_geo"],
            MENU_OPTIONS["exit"],
        ]
    ]

    await update.message.reply_text(
        "Привет! С помощью этого бота можно узнать, выпадут ли осадки в ближайшее время.\n\n"
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="Действие"
        ),
    )

    return MENU


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the selected gender and asks for a photo."""
    choice = update.message.text

    is_markdown = False

    if choice == MENU_OPTIONS["get_forecast"]:
        msg, next_state = choose_location(update, next_state=GET_FORECAST_SELECT)
        is_markdown = True
    elif choice == MENU_OPTIONS["add_geo"]:
        msg = "Прикрепите геолокацию места, которое хотите добавить в свой список:"
        next_state = ADD_GEO_LOCATION
    elif choice == MENU_OPTIONS["delete_geo"]:
        msg, next_state = choose_location(update, next_state=DELETE_GEO_SELECT)
        is_markdown = True
    elif choice == MENU_OPTIONS["exit"]:
        msg = EXIT_MSG
        next_state = ConversationHandler.END
    else:
        msg = f"Неизвестная команда. {START_CMD_INFO}"
        next_state = ConversationHandler.END

    if is_markdown:
        await update.message.reply_markdown(msg, reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text(msg, reply_markup=ReplyKeyboardRemove())

    return next_state


async def add_geo_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lat = update.message.location.latitude
    lon = update.message.location.longitude

    context.user_data["lat"] = lat
    context.user_data["lon"] = lon

    await update.message.reply_text(
        "Придумайте название для локации:"
    )

    return ADD_GEO_NAME


async def add_geo_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the location and asks for some info about the user."""
    location_name = update.message.text
    lat, lon = context.user_data["lat"], context.user_data["lon"]

    locations_storage.add(user_id=update.message.from_user.id, location_name=location_name, location=GeoLocation(lat=lat, lon=lon))
    await update.message.reply_text(f"Геолокация {location_name} сохранена. {START_CMD_INFO}")

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text(EXIT_MSG, reply_markup=ReplyKeyboardRemove())

    return ConversationHandler.END


async def callback_remove_location(update: Update, context: ContextTypes.DEFAULT_TYPE, location_name: str) -> int:
    locations_storage.delete(user_id=update.message.from_user.id, location_name=location_name)

    msg = f"Локация {location_name} удалена. {START_CMD_INFO}"
    await update.message.reply_text(msg)

    return ConversationHandler.END


async def callback_get_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE, location_name: str) -> int:
    geo = locations_storage.get(user_id=update.message.from_user.id, location_name=location_name)

    forecast_str = str(yandex_weather.request_weather(lat=geo.lat, lon=geo.lon))
    forecast_str += f"\n\n{START_CMD_INFO}"
    await update.message.reply_markdown(forecast_str)

    return ConversationHandler.END


async def geo_select(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    callback: Callable[[Update, ContextTypes.DEFAULT_TYPE, str], Awaitable[int]]
) -> int | None:
    locations = available_locations(update=update)

    ix = int(update.message.text)
    ix -= 1

    if ix == -1:
        msg = START_CMD_INFO
        await update.message.reply_text(msg)
        return ConversationHandler.END

    if ix < 0 or ix >= len(locations):
        msg = f"Локации с номером {ix + 1} не существует."
        msg += f"\n\n{choose_location(update, next_state=-1)[0]}"
        await update.message.reply_markdown(msg)
        return

    location_name = locations[ix]

    next_state = await callback(update, context, location_name)
    return next_state


async def entry_point_msg(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    await update.message.reply_markdown("Используйте /start, чтобы начать.")
    return ConversationHandler.END


async def need_location_msg(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await update.message.reply_markdown("Необходимо прикрепить геолокацию. Используйте /cancel для отмены.")
    return None


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if isinstance(context.error, DBConnectionException):
        msg = f"Случилась ошибка во время работы с базой данных:\n"
        msg += f"_{str(context.error)}_"
        msg += ""
        msg += f"\n\nПопробуйте позднее либо обратитесь к @acherepkov.\n\n{EXIT_MSG}"
    elif isinstance(context.error, WeatherRequestFailedException):
        msg = f"Случилась ошибка во время запроса к серверу погоды Yandex:\n"
        msg += f"_{str(context.error)}_"
        msg += f"\n\nПопробуйте позднее либо обратитесь к @acherepkov.\n\n{EXIT_MSG}"
    else:
        msg = f"Случилась неожиданная ошибка:\n"
        msg += f"_{str(context.error)}_"
        msg += f"\n\nПопробуйте еще раз либо обратитесь к @acherepkov.\n\n{EXIT_MSG}"

    await update.message.reply_markdown(msg)
    # return ConversationHandler.END


def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(os.environ["TELEGRAM_TOKEN"]).build()

    # Add conversation handler with the states GENDER, PHOTO, LOCATION and BIO
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex(r"^.+$"), entry_point_msg),
        ],
        states={
            MENU: [
                MessageHandler(filters.Regex(r"^.+$"), menu),
            ],
            ADD_GEO_LOCATION: [
                MessageHandler(filters.LOCATION, add_geo_location),
                CommandHandler("cancel", cancel),
                MessageHandler(filters.Regex(r"^.*$"), need_location_msg),
            ],
            ADD_GEO_NAME: [
                MessageHandler(filters.Regex(r"^.+$"), add_geo_name),
            ],
            GET_FORECAST_SELECT: [
                MessageHandler(filters.Regex(r"\d+"), partial(geo_select, callback=callback_get_forecast)),
            ],
            DELETE_GEO_SELECT: [
                MessageHandler(filters.Regex(r"\d+"), partial(geo_select, callback=callback_remove_location)),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == "__main__":
    main()
