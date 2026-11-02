# The Vibe RP CAD — Website-first starter

This is a **working local web application** with first-time owner setup, username/password login, a community dashboard, department creation, account creation by the owner, units, 911 incidents, unit assignment, status changes, simple Police/Fire/EMS/DOT operational reports, and an audit log. Data is stored in SQLite.

## Open on Windows
1. Extract this ZIP (do not run from inside the ZIP).
2. Install Python 3.11+ from https://www.python.org/downloads/ and enable PATH / Python Launcher.
3. Double-click `start_windows.bat` (requires internet to install Python packages on first run).
4. Visit **http://127.0.0.1:5000/setup** in your browser.
5. Enter your community name, owner username, and a strong password (12+ characters).
6. Use **Administration** to create departments and member accounts, **Units** to add apparatus, **911 Dispatch** to create and assign incidents, and **Police / Fire / EMS** for basic reports.
7. For later sessions, run the batch file and visit http://127.0.0.1:5000/login.

## Hosting a real public website
The Windows starter binds to `127.0.0.1` and **is not accessible from other devices**. To put it online, deploy to a server with Python hosting, persistent storage, HTTPS, a real `TVRP_SECRET_KEY` environment variable, and secure database backups. Set `TVRP_HTTPS=1` only when the app is behind working HTTPS. Use a managed database and a security review before public release. Never expose a development server directly to the internet.

## Not implemented yet
- FiveM / Qbox integration or in-game tablet: the old FiveM ZIP still displays the placeholder notice. This website does not yet connect to it.
- Discord OAuth, public sign-up, email verification, password recovery, advanced granular departmental access controls.
- Criminal databases, warrants, vehicle searches, EMS patient care records, DOT workflows, real-time WebSockets, subscription billing.
- Production-grade user provisioning, rate limiting, password reset, multi-factor authentication, external audit monitoring.

**Do not use this starter for real sensitive patient or law-enforcement data.** Role permissions are basic and reports are visible to all staff roles except `member`. It is a development foundation, not a finished production CAD.

## Deployment notes
- `app.py`: backend and routes
- `templates/`: web screens
- `static/style.css`: purple/black branding
- `cad.sqlite3`: generated database; back it up and do not publish it
- `requirements.txt`: Python dependencies
- `start_windows.bat`: local launcher

Health check: `GET /api/health`. No write API is exposed for FiveM yet.
