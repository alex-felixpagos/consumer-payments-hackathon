.PHONY: run backend frontend install install-backend install-frontend

PORT ?= 8080

# Start both backend (port 8080) and frontend (port 5173) in parallel
run: install
	@trap 'kill 0' EXIT; \
	$(MAKE) backend & \
	$(MAKE) frontend & \
	wait

backend:
	. .venv/bin/activate && uvicorn app.main:app --reload --port $(PORT)

frontend:
	cd frontend && npm run dev

install: install-backend install-frontend

install-backend:
	@test -d .venv || python3 -m venv .venv
	. .venv/bin/activate && pip install -q -r requirements.txt

install-frontend:
	cd frontend && npm install --silent
