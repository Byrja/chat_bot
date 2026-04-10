#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Утилиты для работы со знаками зодиака
"""


def get_zodiac_sign_by_date(day: int, month: int) -> str:
    """
    Определяет знак зодиака по дню и месяцу рождения

    Args:
        day (int): День рождения (1-31)
        month (int): Месяц рождения (1-12)

    Returns:
        str: Название знака зодиака на русском языке
    """
    # Проверка корректности входных данных
    if not (1 <= day <= 31) or not (1 <= month <= 12):
        return None

    # Определяем знак зодиака по дате
    if (month == 3 and day >= 21) or (month == 4 and day <= 19):
        return "Овен"
    elif (month == 4 and day >= 20) or (month == 5 and day <= 20):
        return "Телец"
    elif (month == 5 and day >= 21) or (month == 6 and day <= 20):
        return "Близнецы"
    elif (month == 6 and day >= 21) or (month == 7 and day <= 22):
        return "Рак"
    elif (month == 7 and day >= 23) or (month == 8 and day <= 22):
        return "Лев"
    elif (month == 8 and day >= 23) or (month == 9 and day <= 22):
        return "Дева"
    elif (month == 9 and day >= 23) or (month == 10 and day <= 22):
        return "Весы"
    elif (month == 10 and day >= 23) or (month == 11 and day <= 21):
        return "Скорпион"
    elif (month == 11 and day >= 22) or (month == 12 and day <= 21):
        return "Стрелец"
    elif (month == 12 and day >= 22) or (month == 1 and day <= 19):
        return "Козерог"
    elif (month == 1 and day >= 20) or (month == 2 and day <= 18):
        return "Водолей"
    elif (month == 2 and day >= 19) or (month == 3 and day <= 20):
        return "Рыбы"

    # Если не удалось определить знак (например, некорректная дата)
    return None


def is_valid_birthdate(day: int, month: int, year: int = None) -> bool:
    """
    Проверяет, является ли дата рождения корректной

    Args:
        day (int): День рождения
        month (int): Месяц рождения
        year (int, optional): Год рождения

    Returns:
        bool: True, если дата корректна, иначе False
    """
    # Проверка месяца
    if not (1 <= month <= 12):
        return False

    # Проверка дня
    if not (1 <= day <= 31):
        return False

    # Проверка соответствия дня и месяца
    days_in_month = [
        31,
        29 if year and is_leap_year(year) else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ]
    if day > days_in_month[month - 1]:
        return False

    return True


def is_leap_year(year: int) -> bool:
    """
    Проверяет, является ли год високосным

    Args:
        year (int): Год

    Returns:
        bool: True, если год високосный, иначе False
    """
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
