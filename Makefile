PYTHON ?= python
SRC = src

.PHONY: install install-dev test lint typecheck api dashboard pipeline format docker-build docker-api docker-dashboard

install:
	$(PYTHON) -m pip install -r requirements.txt

install-dev:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check $(SRC)

format:
	$(PYTHON) -m ruff check --fix $(SRC)

typecheck:
	$(PYTHON) -m mypy $(SRC)

api:
	PYTHONPATH=$(SRC) $(PYTHON) -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

dashboard:
	PYTHONPATH=$(SRC) $(PYTHON) -m streamlit run $(SRC)/dashboard/app.py

pipeline:
	$(PYTHON) run_app.py test

docker-build:
	docker compose build

docker-api:
	docker compose up api

docker-dashboard:
	docker compose up dashboard
