# Полигон рефакторинга

Практическое задание: **25 команд** получают одинаковое legacy-приложение
на Flask + Python + SQLite и за ограниченное время улучшают его по
измеримым метрикам. Судья управляет всем через локальный веб-интерфейс.

Никаких Docker, Gunicorn и Kubernetes — только `python app.py`,
локальный SQLite и браузер.

---

## Быстрый старт

```bash
# 1. Сгенерировать 25 папок команд из эталона
python setup_teams.py --reset --seed

# 2. Установить зависимости судьи
cd judge_app
pip install -r requirements.txt

# 3. Запустить веб-интерфейс судьи
python app.py --port 8080
```

Открыть в браузере: <http://localhost:8080>

---

## Структура проекта

```
polygon/
├── README.md
├── setup_teams.py          генератор папок команд
├── .gitignore
├── docs/
│   ├── CONCEPT.md          общая концепция
│   ├── JUDGE.md            инструкция судьи
│   └── STUDENTS.md         инструкция командам
├── template/
│   └── legacy_app/         ЭТАЛОН плохого приложения
│       ├── app.py
│       ├── seed.py
│       ├── requirements.txt
│       ├── README.md
│       └── templates/
│           └── index.html
├── tools/                  скрипты замеров (менять нельзя)
│   ├── bench.py
│   ├── check_logs.py
│   └── acceptance_tests.py
├── judge_app/              веб-интерфейс судьи
│   ├── app.py
│   ├── db.py
│   ├── runner.py
│   ├── metrics.py
│   ├── grading.py
│   ├── requirements.txt
│   └── templates/
│       ├── base.html
│       ├── dashboard.html
│       ├── leaderboard.html
│       ├── team.html
│       └── events.html
└── teams/                  создаётся скриптом, руками не трогаем
    ├── team01/legacy_app/
    ├── team02/legacy_app/
    └── ... team25/legacy_app/
```

---

## Что делает судья

Через браузер на `http://localhost:8080`:

| Кнопка | Действие |
|---|---|
| **Start all** | Поднимает приложения всех команд на портах 5001…5025 |
| **Stop all** | Останавливает все приложения |
| **Re-seed all** | Пересоздаёт `app.db` из `seed.py` у каждой команды |
| **Acceptance all** | Прогоняет скрытые тесты (gate) |
| **Metrics all** | Собирает метрики и выставляет оценки 2–5 |

---

## Метрики и оценка

Сначала **gate** (acceptance-тесты). Не пройден → оценка **2**.

Если пройден, считается score:

```
score = 0.30·speed + 0.20·tests + 0.20·quality
      + 0.15·reliab + 0.10·sec + 0.05·docs
```

Перевод в оценку:

| Score | Оценка |
|---|---|
| ≥ 0.85 | 5 |
| 0.70–0.84 | 4 |
| 0.50–0.69 | 3 |
| < 0.50 | 2 |

Предохранители: нет тестов → максимум 3, `coverage < 30%` → максимум 3,
подмена `tools/*` → 2, сломанный API → 2.

---

## Документация

- [`docs/CONCEPT.md`](docs/CONCEPT.md) — общая концепция полигона
- [`docs/JUDGE.md`](docs/JUDGE.md) — инструкция судьи
- [`docs/STUDENTS.md`](docs/STUDENTS.md) — инструкция командам

---

## Порты команд

После генерации смотри `teams/ports.txt`:

```
team01  5001
team02  5002
...
team25  5025
```

Судья использует `localhost:8080`.