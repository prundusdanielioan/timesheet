from datetime import date, timedelta

FIXED_HOLIDAYS = [
    (1, 1, "Anul Nou"), (1, 2, "Anul Nou"),
    (1, 6, "Boboteaza"), (1, 7, "Sf. Ioan Botezatorul"),
    (1, 24, "Ziua Unirii"), (5, 1, "Ziua Muncii"),
    (6, 1, "Ziua Copilului"), (8, 15, "Adormirea Maicii Domnului"),
    (11, 30, "Sfantul Andrei"), (12, 1, "Ziua Nationala"),
    (12, 25, "Craciunul"), (12, 26, "Craciunul"),
]

def orthodox_easter(year):
    a, b, c = year % 4, year % 7, year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month = (d + e + 114) // 31
    day = ((d + e + 114) % 31) + 1
    return date(year, month, day) + timedelta(days=13)

def get_holidays_for_year(year):
    holidays = {}
    for m, d, name in FIXED_HOLIDAYS:
        holidays[date(year, m, d).isoformat()] = name
    easter = orthodox_easter(year)
    holidays[(easter - timedelta(days=2)).isoformat()] = "Vinerea Mare"
    holidays[easter.isoformat()] = "Pastele"
    holidays[(easter + timedelta(days=1)).isoformat()] = "A doua zi de Paste"
    holidays[(easter + timedelta(days=49)).isoformat()] = "Rusalii"
    holidays[(easter + timedelta(days=50)).isoformat()] = "A doua zi de Rusalii"
    return holidays

def get_holidays_for_month(year, month):
    all_h = get_holidays_for_year(year)
    prefix = f"{year}-{month:02d}"
    return {k: v for k, v in all_h.items() if k.startswith(prefix)}
