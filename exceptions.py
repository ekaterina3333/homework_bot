class CurrentDateError(Exception):
    """Отсутствие ключа current_date."""

    pass


class JsonError(Exception):
    """Ошибка JSON."""

    pass


class RequestError(Exception):
    """Ошибка запроса серверу."""

    pass


class StatusError(Exception):
    """Ошибка ответа сервера."""

    pass
