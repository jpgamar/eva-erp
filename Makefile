.PHONY: dev dev-backend dev-frontend install migrate seed db-create

# Run both frontend and backend
dev:
	@echo "Starting EVA ERP..."
	@make dev-backend & make dev-frontend & wait

dev-backend:
	cd backend && uvicorn src.main:app --reload --port 4010

dev-frontend:
	cd frontend && npm run dev

# Install all dependencies
install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

# Database
db-create:
	@echo "Creating eva_erp database..."
	PGPASSWORD=postgres psql -h localhost -p 54322 -U postgres -c "CREATE DATABASE eva_erp;" 2>/dev/null || echo "Database already exists"

migrate:
	cd backend && alembic upgrade head

migrate-new:
	cd backend && alembic revision --autogenerate -m "$(msg)"

seed:
	cd backend && python -m seeds.run_all

# Full setup
setup: db-create install migrate seed
	@echo "Setup complete!"
