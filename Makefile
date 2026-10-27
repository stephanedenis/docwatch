.PHONY: test lint fmt run build clean

test:
	pytest

lint:
	ruff check .

fmt:
	ruff format .

run:
	mdserve .

build:
	python -m build

clean:
	rm -rf build dist .pytest_cache .ruff_cache src/*.egg-info
