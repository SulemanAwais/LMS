# 📚 Library Management System

A simple Django-based library management system supporting book borrowals, reservations, renewals, fines, and more.

---

## 🚀 Features

- Searchable book list with filtering
- Borrowing and reservation functionality
- Fine calculation for overdue books
- Daily automated tasks for managing reservations and fines
- Admin interface for book and user management

---

## 🛠️ Setup Instructions

1. **Clone the repository**

```bash
git clone https://github.com/your-username/your-repo.git
cd your-repo
```

2. **Create a virtual environment and activate it**
```bash
python -m venv venv
# On Mac:
source venv/bin/activate  
# On Windows: 
venv\Scripts\activate
```
3. **Install dependencies**
```commandline
pip install -r requirements.txt
```
4. **Apply migrations**
```commandline
python manage.py migrate
```
5. **Create a superuser**
```commandline
python manage.py createsuperuser
```
6. **Collect static files**
```commandline
python manage.py collectstatic
```
7. **Run the development server**
```commandline
python manage.py runserver
```

## 🕓 Daily Scheduled Tasks
A management command daily_tasks is included to:

Automatically clear expired reservations

Generate fines for overdue borrowals

### 🐧 Linux/macOS (using crontab)
1. **Open crontab:**
```commandline
crontab -e
```
2. **Add the following line (adjust the paths accordingly):**
```commandline
0 1 * * * /path/to/venv/bin/python /path/to/project/manage.py daily_tasks
```
**📝 Replace:**

`/path/to/venv/bin/python` with the path to your virtualenv's Python binary

`/path/to/project` with the absolute path where `manage.py` is located

### 🪟 Windows (using Task Scheduler)

* Open **Task Scheduler** > **Create Basic Task**
* Set schedule: **Daily** at 1:00 AM
* Action: **Start a Program**

  * **Program/script:** Full path to your Python interpreter (e.g. `C:\Users\You\envs\myenv\Scripts\python.exe`)

  * **Add arguments:** `manage.py daily_tasks`

  * **Start in:** Full path to your Django project directory

## 📂 App Structure
```
core/
├── core/                 # Project settings
├── library/              # App handling books and borrowals
├── templates/
├── static/
├── manage.py
└── daily_tasks.py        # Custom management command for daily tasks
```

