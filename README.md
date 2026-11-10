# SpendWise — Smart Expense Tracker

A responsive full-stack personal finance tracker built with Python Flask, SQLite, HTML, CSS and Chart.js.

## Features
- User registration and login with securely hashed passwords
- Add, edit and delete income/expense transactions
- Categorise transactions and filter by type, category and month
- Monthly dashboard with income, expenses and balance
- Interactive expense breakdown chart
- Monthly category budgets with progress indicators
- Export transaction history to CSV
- Responsive layout for phones and desktops

## Requirements
- Python 3.9+
- pip

## Run locally

```bash
# 1. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\\Scripts\\activate

# macOS/Linux
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the server
python app.py
```

Open http://127.0.0.1:5000 in your browser and create an account.

## Configuration
Set a strong `SECRET_KEY` environment variable before deployment. The SQLite database is created automatically as `expenses.db` on first run.

## Project structure

```text
smart-expense-tracker/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── transactions.html
│   ├── transaction_form.html
│   └── budgets.html
└── static/
    └── style.css
```

## Notes
This is a college/demo project starter. Before public production deployment, add CSRF protection, rate limiting, secure cookie settings, database migrations, automated tests, and a production WSGI server. Do not use the development server or the default secret key in production.
