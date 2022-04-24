PYTHON ?= python3
RUN_PY = $(PYTHON) -m
BLACK_CMD = $(RUN_PY) black --line-length 100 .
# NOTE: exclude any virtual environment subdirectories here
PY_FIND_COMMAND = find -name '*.py' ! -path './venv/*'

install:
	pip3 install -r requirements.txt

format:
	$(BLACK_CMD)

check_format:
	$(BLACK_CMD) --check --diff

mypy:
	$(RUN_PY) mypy $(shell $(PY_FIND_COMMAND))

pylint:
	$(RUN_PY) pylint $(shell $(PY_FIND_COMMAND))

lint: check_format mypy pylint

test:
	$(RUN_PY) unittest discover -s test/ -p *_test.py -v

.PHONY: install format check_format check_types pylint lint test
