PYTHON := python

.PHONY: help ingest clean-data test docs dashboard pipeline

help:
	@echo "MOSPI Airfare Index - Make targets:"
	@echo "  make ingest       Run Role 1 scraper (raw staging JSONL)"
	@echo "  make clean-data   Run Role 2 engineering pipeline (clean Parquet/JSONL)"
	@echo "  make test         Execute the pytest test suite"
	@echo "  make docs         Generate PDF documentation for all roles"
	@echo "  make dashboard    Launch the Streamlit web dashboard (port 8501)"
	@echo "  make pipeline     Run full end-to-end pipeline (ingest + clean-data)"

ingest:
	$(PYTHON) -m src.ingestion.scraper_lead

clean-data:
	$(PYTHON) -m src.engineering.clean_staging_lead

test:
	$(PYTHON) -m pytest tests/ -v -p no:cacheprovider

docs:
	$(PYTHON) generate_pdf.py
	$(PYTHON) -m src.engineering.generate_role2_pdf

dashboard:
	$(PYTHON) -m streamlit run src/frontend/app.py

pipeline: ingest clean-data
	@echo "[OK] Full pipeline executed."