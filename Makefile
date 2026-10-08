PYTHON ?= python

.PHONY: check test
check:
	$(PYTHON) -m compileall -q src tests bserve bcurl
test:
	$(PYTHON) -m unittest discover -s tests -v
