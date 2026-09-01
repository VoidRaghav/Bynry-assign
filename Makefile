install:
	pip install -r requirements.txt -r requirements-dev.txt && playwright install --with-deps

demo:
	./scripts/run_demo.sh

smoke:
	pytest -m smoke -n 4

api:
	pytest -m api -n 8

web:
	pytest -m "web and not mobile" -n 4 --browser=chromium --browser=firefox --browser=webkit

mobile:
	pytest -m mobile --device-suite=nightly

regression:
	pytest -n 6 --reruns 1 --reruns-delay 3 --alluredir=allure-results

part1:
	pytest part1_flaky_login -v
