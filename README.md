# FieldShift — Crop Rotation Planner

Decision-support tool for adaptive crop rotations in Kazakhstan's grain belt.
Built for NASA Space Apps Challenge 2026: **Field Shift: Adapting Farms with NASA Data**.

## Запуск FieldShift

Из корня полного репозитория, с Python 3.12 и Node.js 22.13+:

```sh
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm ci --prefix web
python scripts/run_fieldshift.py
```

Откройте [планировщик](http://localhost:3001). Команда запускает Next.js и FastAPI. Для остановки нажмите Ctrl+C. При занятых портах используйте `--port 3010 --api-port 8010`.

Кнопка «Получить план» отправляет параметры в Next.js, затем в Python на `POST /api/recommendation`. Фасад загружает региональные данные NASA из кеша и передаёт их агродвижку. Вернётся три стратегии на выбранные три или четыре года. После установки зависимостей кеш и справочники работают локально.

В каждом из семи инструментов меню доступна сводка Python по региону или выбранной культуре. Локальные графики по районным точкам и редактируемые сценарии сохраняют собственные периоды и методики. Архивные оценки и примеры мощностей не являются текущими остатками элеваторов.

[Все маршруты Python API](http://127.0.0.1:8000/docs) · [Руководство по фронтенду](web/README.md). Для автономной демонстрации интерфейса используйте `npm run dev --prefix web` с режимом `fixture`. Альтернативный интерфейс Streamlit запускается командой `streamlit run dashboard/app.py`.

## Sprint docs

- Contract: `docs/features/fieldshift/00_CONTRACT.md`
- NASA Data: `docs/features/fieldshift/01_NASA_DATA.md`
- Agro Engine: `docs/features/fieldshift/02_AGRO_ENGINE.md`
- Frontend: `docs/features/fieldshift/03_FRONTEND_UI.md`
- Integration/QA: `docs/features/fieldshift/04_INTEGRATOR_QA.md`
- UI fixture: `docs/features/fieldshift/fixtures/contract_response.json`
