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

The proposed [PDF Review deployment bundle and root operator runbook](ops/pdf_review/README.md)
prepare that manual installation without changing the live service or workflow.

# To run PDF Reviewer locally on windows laptop
```powershell
cd "C:\vena\Obsidian\writing\Code\vsff_website\pdf_review"
.\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
# Set your persistent SECRET_KEY and Google development credentials in .env.
python app.py
```

# For opening it on mobile locally
The tunnel is running, and sign-in protection is working.

1. Open [Google Cloud Clients](https://console.cloud.google.com/auth/clients), select your project, and open the existing **Web application** OAuth client.
2. Under **Authorized redirect URIs**, add this exact address and click **Save**. Keep your existing entries. [Google’s instructions](https://developers.google.com/identity/protocols/oauth2/web-server#creatingcred)

   ```text
   https://arrangement-gently-previously-diary.trycloudflare.com/auth/google/callback
   ```

3. On your iPhone, open [the test site](https://arrangement-gently-previously-diary.trycloudflare.com) in Safari and sign in.
4. Open a PDF and test pinch zoom near the top and farther down.

Keep your laptop awake during testing. To stop afterward, run this from the `pdf_review` directory:

```powershell
.\mobile_https.ps1 -Stop
```