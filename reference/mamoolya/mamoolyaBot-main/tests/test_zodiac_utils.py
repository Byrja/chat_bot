#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Тесты для утилит работы со знаками зодиака
"""

import sys
import os
import unittest

# Добавляем путь к модулю утилит
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "mamoolyaBot"))

from zodiac_utils import get_zodiac_sign_by_date, is_valid_birthdate, is_leap_year


class TestZodiacUtils(unittest.TestCase):
    """Тесты для утилит работы со знаками зодиака"""

    def test_get_zodiac_sign_by_date(self):
        """Тест определения знака зодиака по дате"""
        # Тест для каждого знака зодиака
        test_cases = [
            # Овен (21.03 - 19.04)
            (21, 3, "Овен"),
            (19, 4, "Овен"),
            # Телец (20.04 - 20.05)
            (20, 4, "Телец"),
            (20, 5, "Телец"),
            # Близнецы (21.05 - 20.06)
            (21, 5, "Близнецы"),
            (20, 6, "Близнецы"),
            # Рак (21.06 - 22.07)
            (21, 6, "Рак"),
            (22, 7, "Рак"),
            # Лев (23.07 - 22.08)
            (23, 7, "Лев"),
            (22, 8, "Лев"),
            # Дева (23.08 - 22.09)
            (23, 8, "Дева"),
            (22, 9, "Дева"),
            # Весы (23.09 - 22.10)
            (23, 9, "Весы"),
            (22, 10, "Весы"),
            # Скорпион (23.10 - 21.11)
            (23, 10, "Скорпион"),
            (21, 11, "Скорпион"),
            # Стрелец (22.11 - 21.12)
            (22, 11, "Стрелец"),
            (21, 12, "Стрелец"),
            # Козерог (22.12 - 19.01)
            (22, 12, "Козерог"),
            (19, 1, "Козерог"),
            # Водолей (20.01 - 18.02)
            (20, 1, "Водолей"),
            (18, 2, "Водолей"),
            # Рыбы (19.02 - 20.03)
            (19, 2, "Рыбы"),
            (20, 3, "Рыбы"),
        ]

        for day, month, expected_sign in test_cases:
            with self.subTest(day=day, month=month):
                result = get_zodiac_sign_by_date(day, month)
                self.assertEqual(
                    result,
                    expected_sign,
                    f"Для даты {day}.{month} ожидался знак '{expected_sign}', но получен '{result}'",
                )

    def test_get_zodiac_sign_by_date_invalid(self):
        """Тест определения знака зодиака для некорректных дат"""
        # Тест для некорректных дат
        invalid_cases = [(0, 1), (32, 1), (1, 0), (1, 13), (-1, 5), (15, -3)]

        for day, month in invalid_cases:
            with self.subTest(day=day, month=month):
                result = get_zodiac_sign_by_date(day, month)
                self.assertIsNone(
                    result,
                    f"Для некорректной даты {day}.{month} ожидался None, но получен '{result}'",
                )

    def test_is_leap_year(self):
        """Тест проверки високосного года"""
        # Тест для високосных годов
        leap_years = [2000, 2004, 2008, 2012, 2016, 2020, 2024]
        for year in leap_years:
            with self.subTest(year=year):
                self.assertTrue(
                    is_leap_year(year), f"Год {year} должен быть високосным"
                )

        # Тест для невисокосных годов
        non_leap_years = [1900, 2001, 2002, 2003, 2005, 2006, 2007, 2100]
        for year in non_leap_years:
            with self.subTest(year=year):
                self.assertFalse(
                    is_leap_year(year), f"Год {year} не должен быть високосным"
                )

    def test_is_valid_birthdate(self):
        """Тест проверки корректности даты рождения"""
        # Тест для корректных дат
        valid_dates = [(1, 1), (29, 2, 2020), (31, 12), (15, 6), (29, 2, 2000)]
        for day, month, *year in valid_dates:
            y = year[0] if year else None
            with self.subTest(day=day, month=month, year=y):
                result = is_valid_birthdate(day, month, y)
                self.assertTrue(
                    result,
                    f"Дата {day}.{month}{('.' + str(y)) if y else ''} должна быть корректной",
                )

        # Тест для некорректных дат
        invalid_dates = [
            (0, 1),
            (32, 1),
            (1, 0),
            (1, 13),
            (29, 2, 2021),
            (31, 4),
            (31, 6),
        ]
        for day, month, *year in invalid_dates:
            y = year[0] if year else None
            with self.subTest(day=day, month=month, year=y):
                result = is_valid_birthdate(day, month, y)
                self.assertFalse(
                    result,
                    f"Дата {day}.{month}{('.' + str(y)) if y else ''} не должна быть корректной",
                )


if __name__ == "__main__":
    unittest.main()
