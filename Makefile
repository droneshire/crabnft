PYTHON ?= python3
PY_PATH=$(PWD)/src
RUN_PY = PYTHONPATH=$(PY_PATH) $(PYTHON) -m
BLACK_CMD = $(RUN_PY) black --line-length 80 --target-version py37
# NOTE: exclude any virtual environment subdirectories here
PY_FIND_COMMAND = find -name '*.py' ! -path './venv/*'
MYPY_CONFIG=$(PY_PATH)/mypy_config.ini

install:
	pip3 install -r requirements.txt

format:
	$(BLACK_CMD) $(shell $(PY_FIND_COMMAND))

check_format:
	$(BLACK_CMD) --check --diff

mypy:
	$(RUN_PY) mypy $(shell $(PY_FIND_COMMAND)) --config-file $(MYPY_CONFIG) --no-namespace-packages

pylint:
	$(RUN_PY) pylint $(shell $(PY_FIND_COMMAND))

lint: check_format mypy pylint

test:
	$(RUN_PY) unittest discover -s test/ -p *_test.py -v

wyndblast:
	$(RUN_PY) wyndblast.executables.play_wyndblast --groups 1 2 3 4 5 --human-mode --ignore-utc --server-url http://143.198.97.119/monitor

pat:
	$(RUN_PY) plantatree.executables.play_pat --server-url http://143.198.97.119/monitor

pumpskin:
	$(RUN_PY) pumpskin.executables.play_pumpskin --update-config --server-url http://143.198.97.119/monitor

.PHONY: install format check_format check_types pylint lint test creator_bot account_bot
