# Enterprise Asset Management System (Flask/SQLAlchemy)

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.3-green.svg)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red.svg)
![License](https://img.shields.io/badge/License-MIT-purple.svg)

An enterprise-grade, modular Web Application built with **Flask**, **SQLAlchemy ORM**, and **Alembic** for managing corporate assets, maintenance logs, and personnel assignments. Engineered with a scalable Blueprint architecture and robust Role-Based Access Control (RBAC).

---

## 🏛 Architecture & Technical Stack

Unlike monolithic Flask applications, this system is architected using **Flask Blueprints** to ensure domain separation, maintainability, and scalability.

*   **Backend Framework:** Flask
*   **Database ORM:** SQLAlchemy (Declarative mapping, relational integrity)
*   **Database Migrations:** Alembic (via Flask-Migrate) for version-controlled schema changes.
*   **Authentication:** Flask-Login with secure session management and Werkzeug password hashing.
*   **Frontend Templating:** Jinja2 with modular macro components.

### Modular Blueprint Structure
The application domain is strictly divided into isolated modules:
*   `auth`: User authentication, session handling, and profile management.
*   `inventory`: Core CRUD operations for assets, lifecycle tracking, and categorization.
*   `maintenance`: Tracking defect logs, repairs, and service history.
*   `personnel`: Employee management and asset allocation (checkout/check-in system).
*   `reports`: Data aggregation, analytics, and CSV/PDF export generation.

### Relational Database Schema
The system utilizes a relational model maintaining strict constraints:
*   **User:** Handles authentication and RBAC levels.
*   **Asset:** Primary entity with unique `asset_tag` tracking status and location.
*   **MaintenanceLog:** One-to-Many relationship with `Asset`.
*   **Assignment:** Many-to-Many association bridging `Asset` and `Personnel`.

---

## 🔒 Security & Role-Based Access Control (RBAC)

The application implements a multi-tier authorization matrix enforced at the route level via custom decorators (`@requires_role`):

1.  **Level 3 (System Admin):** Full access to user management, system configurations, and destructive operations (Delete).
2.  **Level 2 (Department Manager):** Can create, assign, and update assets/personnel, but lacks global destructive privileges.
3.  **Level 1 (Technician):** Access restricted to reading assets and managing `Maintenance` logs.
4.  **Level 0 (Standard Personnel):** Read-only visibility for assigned assets.

---

## ⚙️ Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/berkaymhc/universite-demirbas.git
cd universite-demirbas
```

### 2. Create and activate a Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Configuration (.env)
Security is managed via environment variables. Copy the template and configure your local settings:
```bash
cp .env.example .env
```
Ensure your `.env` contains:
```ini
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=your_secure_random_key
DATABASE_URL=sqlite:///asset_management.db
```

### 5. Database Migrations & Seeding
Initialize the database using Alembic and populate mock data:
```bash
flask db upgrade
python seed_full.py
```

### 6. Run the Application
```bash
flask run
```

---

## 🤝 Contributing
Contributions are welcome! Please read `CONTRIBUTING.md` for details on our code of conduct and the process for submitting pull requests.

## 📄 License
This project is licensed under the MIT License - see the `LICENSE` file for details.
