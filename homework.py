from http import HTTPStatus
import logging
import os
import time

from dotenv import load_dotenv
import requests
from telebot import TeleBot

from exceptions import Current_dateError, JsonError, RequestError, StatusError

load_dotenv()
logger = logging.getLogger(__name__)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN])


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    logger.debug('Удачная отправка любого сообщения в Telegram')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(ENDPOINT, headers=HEADERS,
                                         params=payload)
        if homework_statuses.status_code != HTTPStatus.OK:
            raise StatusError('Ошибка в ответе сервера')
        homework_statuses = homework_statuses.json()
    except requests.exceptions.RequestException:
        raise RequestError('Ошибка при запросе к API')
    except ValueError:
        raise JsonError('Ошибка декодирования JSON')
    return homework_statuses


def check_response(response):
    """Функция проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API - не словарь')
    homeworks = response.get('homeworks')
    if homeworks is None:
        raise KeyError('Нет ключа homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Значению ключа - не список')
    current_date = response.get('current_date')
    if current_date is None:
        raise Current_dateError('Нет ключа current_date')
    return homeworks


def parse_status(homework):
    """Извлекает статус о домашней работе."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_name is None:
        raise KeyError('Нет ключа homework_name')
    if homework_status not in HOMEWORK_VERDICTS:
        message = 'Недокументированный статус домашней работы.'
        raise KeyError(message)
    verdict = HOMEWORK_VERDICTS[homework['status']]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    if not check_tokens():
        message = 'Отсутствуют токены'
        logger.critical(message)
        send_message(bot, message)
        raise StatusError
    while True:
        try:
            response = get_api_answer(timestamp)
            checked_response = check_response(response)
            if checked_response:
                status = parse_status(checked_response[0])
                send_message(bot, status)
            else:
                message = 'Отсутствие в ответе новых статусов'
                logger.debug(message)
                send_message(bot, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if error != Current_dateError:
                send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format=(
            '%(asctime)s - %(name)s - %(levelname)s - '
            '%(lineno)d - %(funcName)s - %(message)s'),
        level=logging.DEBUG,
    )
    main()
