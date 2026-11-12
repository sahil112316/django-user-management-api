# User Management & Authentication API

A RESTful API built using Python, Django and Django REST Framework for managing users, profiles, clients, projects and project tasks, with JWT authentication and email-based OTP verification.

## Technologies Used

- Python
- Django
- Django REST Framework
- SQLite
- JWT Authentication (Simple JWT)
- Pillow
- SMTP / Django Email Backend

## Features

### User Management
- Custom User Model using `AbstractUser`
- Create, list, retrieve and update users
- Soft-delete users by changing their status to Inactive
- Search, filtering and pagination
- Password hashing

### Authentication
- Login using email and password
- JWT access and refresh tokens
- Email OTP verification
- Forgot password and reset password using OTP

### Profiles
- Six protected default profiles:
  - Super Admin
  - Admin
  - Manager
  - Team Leader
  - Developer
  - Human Resource
- Create and manage custom profiles
- Prevent modification or deletion of protected default profiles

### Client and Project Management
- Client CRUD APIs
- Project CRUD APIs
- Assign project managers (Manager role only)
- Project search and filtering
- Project attachments
- Soft-delete projects

### Project Tasks
- Create and manage project tasks
- Assign developers and team leaders
- Task comments

### Email Notifications
- Welcome email when a user is created
- OTP emails
- Password reset emails
- Project notification emails for clients and assigned managers

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/sahil112316/django-user-management-api.git
cd django-user-management-api
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it on Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Apply database migrations

```bash
python manage.py migrate
```

### 5. Start the development server

```bash
python manage.py runserver
```

API base URL:

`http://127.0.0.1:8000/api/`

## API Testing

Use Postman or the Django REST Framework browsable API to test the endpoints.

Test cases should include:
- Valid and invalid login credentials
- Duplicate email addresses
- Valid, invalid and expired OTPs
- Password reset
- JWT-protected endpoints
- Default profile protection
- Invalid project manager assignments
- Search, filtering and pagination
- Project and task operations

## Email Configuration

Configure the following environment variables before testing email-based features:

- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`

Keep email credentials and secret keys private. Never commit actual credentials to GitHub.

## Important Notes

- The project uses SQLite as its default database.
- Existing migration files are included in the repository.
- User and project soft deletion preserves database records.
- Protected default profiles cannot be modified or deleted.

## Author

Sahil Kumar