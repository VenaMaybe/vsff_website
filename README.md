# VSFF repository

`frontend/` is the existing Vue/Vite website and `backend/` is its Flask API.
`pdf_review/` is an independent Flask/Socket.IO PDF review service with its own
dependencies, SQLite migrations, authentication, and private runtime storage.
See [PDF Review setup](pdf_review/README.md) and its
[architecture](pdf_review/ARCHITECTURE.md).

PDF Review shares source hosting only. It is not integrated into the Vue router,
VSFF API, sessions, or database. The existing deployment workflow remains
unchanged and does not install, migrate, start, or restart PDF Review.

Future intended services bind separately to loopback: VSFF on port 8001 and PDF
Review on port 8002, behind separate reverse-proxy hosts. PDF Review production
data belongs outside the checkout, for example `/var/lib/vsff-review`.
Service units, proxy/DNS/TLS, protected environments, Google callbacks, backups,
and deployment-script permissions require a later dedicated deployment task.

# To run PDF Reviewer locally on windows laptop
```powershell
cd "C:\vena\Obsidian\writing\Code\vsff_website\pdf_review"
.\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
# Set your persistent SECRET_KEY and Google development credentials in .env.
python app.py
```
