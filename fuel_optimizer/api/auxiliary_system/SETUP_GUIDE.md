# Setup & Execution Guide

Follow these steps to get the Intelligent Fuel Route Optimization system running.

## 1. Environment Setup
Ensure you have Python 3.9+ and a virtual environment active.
```bash
pip install -r requirements.txt
```
*(Core requirements: django, djangorestframework, django-cors-headers, pandas, requests, streamlit, folium, streamlit-folium)*

## 2. Dataset Preparation
The system requires a `cleaned_fuel_prices.csv` in the project root.
```bash
python api/auxiliary_system/data_preprocessing/preprocess_dataset.py
```
This will read the raw `fuel_prices.csv`, geocode it, and save the cleaned version.

## 3. Start the Backend
Run the Django development server.
```bash
python manage.py runserver
```
The API will be available at `http://localhost:8000/api/plan-route/`.

## 4. Launch the Interactive UI
In a new terminal window:
```bash
streamlit run api/auxiliary_system/ui/ui_app.py
```
Open your browser to `http://localhost:8501`.

## 5. Run Validation Tests
To verify system correctness and performance:
```bash
python api/auxiliary_system/validation/test_api.py
```
Check `validation_report.json` for detailed results.
