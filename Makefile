PYTHON ?= python3
VENV ?= .venv
FLASK ?= $(VENV)/bin/flask

.PHONY: venv install init seed run test

venv:
	$(PYTHON) -m venv $(VENV)

install:
	$(VENV)/bin/pip install -r requirements-dev.txt

init:
	$(FLASK) --app wsgi:app init-db

seed:
	$(FLASK) --app wsgi:app seed-db

run:
	$(FLASK) --app wsgi:app run --debug

test:
	$(VENV)/bin/pytest -q
