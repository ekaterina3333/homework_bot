from http import HTTPStatus
import json
import logging
import os
import time

from dotenv import load_dotenv
import requests
from telebot import TeleBot

from exceptions import (CurrentDateError, JsonError,
                        RequestError, StatusError)

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
    missing_tokens = []
    tokens = {
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN
    }
    for token_name, token_value in tokens.items():
        if token_value is None:
            missing_tokens.append(token_name)
    return missing_tokens


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except TeleBot.apihelper.ApiException:
        logger.error('Ошибка отправки сообщения в Telegram')
    else:
        logger.debug('Удачная отправка сообщения в Telegram')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(ENDPOINT, headers=HEADERS,
                                         params=payload)
        if homework_statuses.status_code != HTTPStatus.OK:
            raise StatusError('Ошибка в ответе сервера')
        return homework_statuses.json()
    except requests.exceptions.RequestException:
        raise RequestError('Ошибка при запросе к API')
    except json.JSONDecodeError:
        raise JsonError('Ошибка декодирования JSON')


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
        raise CurrentDateError('Нет ключа current_date')
    if not isinstance(current_date, int):
        raise CurrentDateError('Значению ключа - не число')
    return homeworks


def parse_status(homework):
    """Извлекает статус о домашней работе."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_name is None:
        raise KeyError('Нет ключа homework_name')
    if homework_status not in HOMEWORK_VERDICTS:
        message = (
            f'Недокументированный статус {homework_status} домашней работы.'
        )
        raise ValueError(message)
    verdict = HOMEWORK_VERDICTS[homework['status']]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    missing_tokens = check_tokens()
    if missing_tokens:
        message = f'Отсутствуют токены: {", ".join(missing_tokens)}'
        logger.critical(message)
        raise ValueError(message)
    last_sent_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            checked_response = check_response(response)
            if checked_response:
                status = parse_status(checked_response[0])
                if status != last_sent_message:
                    send_message(bot, status)
                    last_sent_message = status
            else:
                message = 'Отсутствие в ответе новых статусов'
                logger.debug(message)
        except CurrentDateError:
            logger.error('Ошибка в ключе current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if last_sent_message != message:
                logger.error(message)
                last_sent_message = message
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
