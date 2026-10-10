.PHONY: setup images wheelhouse test bench demo-check cleanup api ui hardened-smoke

setup:
	python3 scripts/dev.py setup

images:
	python3 scripts/dev.py images

hardened-smoke:
	python3 scripts/dev.py hardened-smoke

wheelhouse:
	python3 scripts/dev.py wheelhouse

test:
	python3 scripts/dev.py test

bench:
	python3 scripts/dev.py bench

demo-check:
	python3 scripts/dev.py demo-check

cleanup:
	python3 scripts/dev.py cleanup

api:
	python3 scripts/dev.py api

ui:
	python3 scripts/dev.py ui
