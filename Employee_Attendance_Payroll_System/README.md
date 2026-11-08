# Employee Attendance & Payroll Management System

A beginner-friendly full-stack starter project for a technical interview assignment.

## Technology stack
- Frontend: HTML5, CSS3, JavaScript (responsive UI; no React build step required)
- Backend: Python Flask
- Database: MySQL
- API: JSON REST endpoints
- Authentication: Flask session login with password hashing
- Authorization: Admin-only actions for employee changes, attendance marking, leave decisions and payroll generation
- IDE: Visual Studio Code

## Requirements
- Python 3.10+
- MySQL Server and MySQL Workbench (Workbench is optional but helpful)
- VS Code

## Setup (Windows)

1. Extract the ZIP and open the `Employee_Attendance_Payroll_System` folder in VS Code.
2. Open Terminal > New Terminal.
3. Create and activate a virtual environment:

   ```powershell
   py -m venv venv
   .\venv\Scripts\activate
   ```

4. Install packages:

   ```powershell
   pip install -r requirements.txt
   ```

5. In MySQL Workbench, open `database/schema.sql` and execute it. This creates the database and tables.
6. Copy `.env.example` to a new file named `.env`. Update `DB_USER` and `DB_PASSWORD` with your local MySQL details. Keep `DB_NAME=employee_payroll`.
7. Create the first admin account. In the VS Code terminal run:

   ```powershell
   python
   ```

   Then paste:

   ```python
   from app import query
   from werkzeug.security import generate_password_hash
   query("INSERT INTO users (username,password_hash,role) VALUES (%s,%s,%s)",
         ("admin", generate_password_hash("Admin@123"), "admin"), commit=True)
   exit()
   ```

   Change the demo password after your first successful login. Do not use this demo password in a deployed application.

8. Start the app:

   ```powershell
   python app.py
   ```

9. Open `http://127.0.0.1:5000` in your browser and sign in:
   - Username: `admin`
   - Password: `Admin@123`

## Included features
- Login/logout and session authentication
- Admin role checks for sensitive operations
- Employee directory, add employee and deactivate employee
- Daily attendance: Present, Absent, Half-day and Leave
- Monthly attendance view
- Leave request submission and admin approval/rejection
- Monthly payroll calculation and payroll history
- Dashboard summary and reports
- Responsive HTML/CSS interface
- REST API endpoints under `/api`

## Important assignment notes / limitations to improve
This is a working starter, not a production payroll product. Before submitting it as a final company assignment:
- Implement employee self-service login and enforce employee-to-own-record access.
- Add edit employee UI, employee profile linking, and leave balance accrual/validation.
- Review payroll policy with the company: actual calendar days, weekly offs, paid/unpaid leave, statutory deductions, overtime rates and rounding rules vary. The included formula is a simple demo using 30 days.
- Add payslip PDF generation and CSV/Excel exports.
- Add CSRF protection, rate limiting, stronger secret management, audit logs and automated tests.
- Add validation for date ranges, negative salary values and duplicate/overlapping leave.
- Do not expose debug mode in production.

## API overview
- `POST /api/login`, `POST /api/logout`, `GET /api/me`
- `GET /api/dashboard`
- `GET/POST /api/employees`, `PUT /api/employees/<id>`, `PATCH /api/employees/<id>/deactivate`
- `GET/POST /api/attendance`
- `GET/POST /api/leaves`, `PATCH /api/leaves/<id>`
- `GET /api/payroll`, `POST /api/payroll/run`
- `GET /api/reports`

## Project structure
- `app.py`: Flask pages and REST API routes
- `database/schema.sql`: MySQL schema and indexes
- `templates/`: HTML pages
- `static/css/style.css`: responsive styling
- `static/js/app.js`: frontend API calls and interactions
- `.env.example`: database configuration template
