import os
import sys
import time
import logging
import requests
import telegram
from dotenv import load_dotenv
from exceptions import TelegramTokenException, TelegramChatIdException
from exceptions import PracticumTokenException, StatusCodeException


load_dotenv()
VAR_NAME_PRACTICUM_TOKEN = 'PRACTICUM_TOKEN'
VAR_NAME_TELEGRAM_TOKEN = 'TELEGRAM_TOKEN'
VAR_NAME_TELEGRAM_CHAT_ID = 'TELEGRAM_CHAT_ID'
PRACTICUM_TOKEN = os.getenv(VAR_NAME_PRACTICUM_TOKEN)
TELEGRAM_TOKEN = os.getenv(VAR_NAME_TELEGRAM_TOKEN)
TELEGRAM_CHAT_ID = os.getenv(VAR_NAME_TELEGRAM_CHAT_ID)

FROM_DATE = 0
RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def start_logging():
    """Start logging."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s  [%(levelname)s]  %(message)s',
    )
    logger = logging.getLogger(__name__)
    handler = logging.StreamHandler(stream=sys.stdout)
    logger.addHandler(handler)


def check_tokens():
    """Check variables availability."""
    info = ('Отсутствует обязательная переменная '
            'окружения: {var_name} '
            'Программа принудительно остановлена.')

    if PRACTICUM_TOKEN is None:
        logging.critical(info.format(var_name=VAR_NAME_PRACTICUM_TOKEN))
        raise PracticumTokenException(
            info.format(var_name=VAR_NAME_PRACTICUM_TOKEN)
        )
    if TELEGRAM_TOKEN is None:
        logging.critical(info.format(var_name=VAR_NAME_TELEGRAM_TOKEN))
        raise TelegramTokenException(
            info.format(var_name=VAR_NAME_TELEGRAM_TOKEN)
        )
    if TELEGRAM_CHAT_ID is None:
        logging.critical(info.format(var_name=VAR_NAME_TELEGRAM_CHAT_ID))
        raise TelegramChatIdException(
            info.format(var_name=VAR_NAME_TELEGRAM_CHAT_ID)
        )


def send_message(bot, message):
    """Send message in Telegram."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug(f'Бот отправил сообщение {message}')
    except Exception as error:
        logging.error('Бот: не удалось отправить '
                      f'сообщение {message}. {error}')


def get_api_answer(timestamp):
    """Get homework statuses."""
    try:
        homework_statuses = requests.get(url=ENDPOINT,
                                         headers=HEADERS,
                                         params={'from_date': timestamp})
        status_code = homework_statuses.status_code
        if status_code != 200:
            info = (f'Эндпоинт {ENDPOINT} недоступен. '
                    f'Код ответа API: {status_code}')
            raise StatusCodeException(info)
        else:
            return homework_statuses.json()
    except requests.RequestException as error:
        logging.error(error)


def check_response(response):
    """Check API response."""
    if type(response) is not dict:
        raise TypeError('type(response) is not dict')
    if response.get('code') == 'not_authenticated':
        raise TypeError(response.get('message'))
    if response.get('code') == 'UnknownError':
        raise TypeError(response.get('error'))
    if (type(response.get('homeworks'))) is not list:
        raise TypeError('type(response.get(\'homeworks\')) is not list')


def parse_status(homework):
    """Parse response status."""
    if 'homework_name' in homework.keys():
        homework_name = homework['homework_name']
    else:
        raise IndexError('No key \'homework_name\' in homework')
    if homework['status'] in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[homework['status']]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        raise IndexError('No such key homework[status] in HOMEWORK_VERDICTS')


def main():
    """Основная логика работы бота."""
    start_logging()
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    message = None

    while True:
        try:
            api_answer = get_api_answer(timestamp=FROM_DATE)
            check_response(api_answer)
            homework = api_answer.get('homeworks')[0]
            new_message = parse_status(homework)
        except Exception as error:
            new_message = f'Сбой в работе программы: {error}'
            logging.error(new_message)
        finally:
            if new_message != message:
                message = new_message
                send_message(bot=bot, message=message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
