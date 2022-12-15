import json
import logging
import os
import pandas
import sqlite3
import sys

from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    TelegramError
)
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    Filters,
    MessageHandler,
    Updater
)

from exceptions import (
    FailedToRead,
    MessageNotSent,
    WrongNumberColumns
)

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(funcName)s, %(lineno)s',
    filemode='w'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s, %(funcName)s, %(lineno)s'
)
handler.setFormatter(formatter)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
NAME_LOAD_FILE = {}
ALLOWED_FORMAT = ('xlsx', 'xls')

updater = Updater(token=TELEGRAM_TOKEN)


def get_chat_id(update):
    """Получение id чата"""

    return update.effective_message.chat_id


def send_message(context, chat_id, message):
    """Отправляет сообщение в Telegram чат."""

    try:
        context.bot.send_message(
            chat_id=chat_id,
            text=message,
            reply_markup=get_base_inline_keybord()
        )
        logger.info(f'Сообщение в чат {chat_id}: {message}')
    except TelegramError:
        raise MessageNotSent('Ошибка отправки сообщения')


def chec_file_format(read_file):
    """Проверка формата файла."""

    if len(read_file.keys()) != 3:
        raise WrongNumberColumns(f'Не верное количество колонок - '
                                 f'{len(read_file.keys())}. Должно быть - 3!')

    title = ('name', 'URL', 'xpath')
    for i in range(3):
        if read_file.keys()[i] != title[i]:
            raise KeyError(f'{i+1} колонка должна называться - {title[i]}!')

    return True


def start_bot(update, context):
    """Начало общения с ботом."""

    name = update.message.chat.first_name
    context.bot.send_message(
        chat_id=get_chat_id(update),
        text=f'Спасибо, что вы включили меня, {name}!',
        reply_markup=get_base_inline_keybord()
        )


def get_base_inline_keybord():
    """Inline клавиатура."""

    keybord = [
        [InlineKeyboardButton('Загрузить файл', callback_data='load')],
    ]
    return InlineKeyboardMarkup(keybord)


def get_load(update, context):
    """Запуск основной работы бота при нажатии кнопки - Загрузить файл."""

    query = update.callback_query
    data = query.data

    if data == 'load':
        main(update, context)


def downloader(update, context):
    """Получение и сохранение файла."""

    name_file = (
        str(get_chat_id(update)) + '_' +
        update.effective_message.document.file_name
    )
    file_format = name_file.split('.')[-1]

    if file_format in ALLOWED_FORMAT:
        with open(f'files/{name_file}', 'wb') as f:
            context.bot.get_file(update.message.document).download(out=f)

        NAME_LOAD_FILE[get_chat_id(update)] = name_file
    else:
        message = f'У файла не верный формат - {file_format}!'
        send_message(context, get_chat_id(update), message)


def answer_text(update, context):
    """Ответ на любое сообщение."""

    message = 'Прикрепите файл xlsx и нажмите кнопку - Загрузить файл'
    send_message(context, get_chat_id(update), message)


def get_save_db(update, context, read_file):
    """Создание и сохрание информации базе данных"""

    connect = sqlite3.connect('db.sqlite3')
    cursor = connect.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS new(
        name VARCHAR,
        URL VARCHAR,
        xpath VARCHAR)""")
    connect.commit()

    name = tuple(read_file["name"].values)
    URL = tuple(read_file["URL"].values)
    xpath = tuple(read_file["xpath"].values)

    cursor.execute(f'SELECT * '
                   f'FROM new '
                   f'WHERE name IN {name} AND '
                   f'URL IN {URL} AND '
                   f'xpath IN {xpath}')
    data = cursor.fetchall()
    distict_data = []
    if not data:
        database_entry(read_file.values, cursor, connect)
    else:
        for i in read_file.values.tolist():
            if tuple(i) not in data:
                distict_data.append(i)
        database_entry(distict_data, cursor, connect)


def database_entry(array, cursor, connect):
    """Запись данных в БД"""

    for value in array:
        cursor.execute(
            'INSERT INTO new(name, URL, xpath) VALUES(?, ?, ?);',
            [value[0], value[1], value[2]]
        )
        connect.commit()


def get_read_file(update):
    """Чтение полученного файла"""

    try:
        read_file = pandas.read_excel(
            f'files/{NAME_LOAD_FILE[get_chat_id(update)]}'
        )
        return read_file
    except Exception:
        raise FailedToRead('Вы не подгрузили файл!')


def main(update, context):
    """Основная логика работы бота."""

    while True:
        try:
            read_file = get_read_file(update)
            chec_file_format(read_file)
            values = json.dumps(read_file.values.tolist())
            send_message(context, get_chat_id(update), values)
            get_save_db(update, context, read_file)
        except Exception as error:
            logger.error(f'Сбой в работе программы: {error}', exc_info=True)
            message = f'Сбой в работе программы: {error}'
            send_message(context, get_chat_id(update), message)
        finally:
            updater.start_polling()
            updater.idle()


updater.dispatcher.add_handler(
    CommandHandler('start', start_bot)
)
updater.dispatcher.add_handler(
    CallbackQueryHandler(callback=get_load, pass_chat_data=True)
)
updater.dispatcher.add_handler(
    MessageHandler(Filters.document, downloader)
)
updater.dispatcher.add_handler(
    MessageHandler(Filters.text, answer_text)
)


if __name__ == '__main__':
    updater.start_polling()
    updater.idle()
