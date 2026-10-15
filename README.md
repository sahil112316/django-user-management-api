# Custom User Management & Authentication API

## Project Overview
This project is built using Django and Django REST Framework. It provides APIs for user management, authentication, OTP verification, password reset, and email notifications.

## Technologies Used
- Python
- Django
- Django REST Framework
- SQLite
- JWT Authentication
- Simple JWT
- Pillow
- SMTP / Email Backend

## Features
- Custom User Model inherited from `AbstractUser`
- Create, list, retrieve, update, and soft-delete users
- User status management (Active / Inactive)
- Password hashing
- Login using email and password
- JWT authentication
- Email OTP verification
- Forgot password using OTP
- Reset password
- Welcome email when a user is created
- REST API testing using Postman

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/users/` | List active users |
| POST | `/api/users/` | Create a user |
| GET | `/api/users/<id>/` | Retrieve user details |
| PUT | `/api/users/<id>/` | Update user details |
| PATCH | `/api/users/<id>/` | Partially update user details |
| DELETE | `/api/users/<id>/` | Soft-delete / deactivate a user |
| POST | `/api/auth/login/` | Login and obtain JWT tokens |
| POST | `/api/auth/send-otp/` | Send verification OTP |
| POST | `/api/auth/verify-otp/` | Verify OTP |
| POST | `/api/auth/forgot-password/` | Request password-reset OTP |
| POST | `/api/auth/reset-password/` | Reset password |

## Installation and Setup

1. Clone or download the project.
2. Open the project folder in the terminal.
3. Create and activate a virtual environment.

```bash
python -m venv venv
```

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

4. Install dependencies.

```bash
pip install -r requirements.txt
```

5. Apply database migrations.

```bash
python manage.py makemigrations
python manage.py migrate
```

6. Start the development server.

```bash
python manage.py runserver
```

7. Open the API in your browser or test it using Postman.

```text
http://127.0.0.1:8000/api/users/
```

## Testing
The APIs can be tested using Postman or the Django REST Framework browsable API. Test successful requests and invalid inputs, including incorrect passwords, duplicate email addresses, invalid or expired OTPs, and password reset.

## Notes
- User passwords are stored as hashes.
- Soft deletion changes the user's status to Inactive instead of permanently deleting the record.
- Configure email settings before testing email-based features.
- Keep email credentials and other secrets private. Do not commit them to GitHub.

## Author
Sahil Kumar
