import os
import sys
import json
import uuid
import secrets
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from analyzer import analyze_patto
from email_service import notify_new_upload, notify_contact

UPLOADS_DIR = Path(__file__).parent / "uploads"
KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}
MAX_FILE_MB = 10

app = FastAPI(title="Patto di Non Concorrenza API", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(security)):
    ok_user = secrets.compare_digest(credentials.username.encode(), b"admin")
    ok_pass = secrets.compare_digest(
        credentials.password.encode(), ADMIN_PASSWORD.encode()
    )
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ── ANALYZE ──────────────────────────────────────────────────────────────────

@app.post("/api/analyze")
async def analyze(
    request: Request,
    file: UploadFile = File(...),
    gdpr_consent: str = Form(...),
    user_name: str = Form(""),
    user_email: str = Form(""),
):
    if gdpr_consent.lower() not in ("true", "1", "yes"):
        raise HTTPException(400, "È necessario il consenso al trattamento dei dati personali.")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Formato non supportato. Carica un file PDF o DOCX.")

    content = await file.read()
    if len(content) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(400, f"File troppo grande. Limite: {MAX_FILE_MB} MB.")

    upload_id = str(uuid.uuid4())[:8]
    safe_name = f"{upload_id}_{file.filename}"
    upload_path = UPLOADS_DIR / safe_name
    upload_path.write_bytes(content)

    try:
        result = analyze_patto(file.filename, content)
    except Exception as e:
        print(f"[analyze] Errore Claude API: {e}")
        raise HTTPException(500, "Errore durante l'analisi AI. Riprova tra qualche minuto.")

    meta = {
        "id": upload_id,
        "filename": file.filename,
        "safe_filename": safe_name,
        "user_name": user_name,
        "user_email": user_email,
        "gdpr_consent": True,
        "gdpr_timestamp": datetime.utcnow().isoformat(),
        "ip": request.client.host if request.client else "unknown",
        "uploaded_at": datetime.utcnow().isoformat(),
        "analysis": result,
    }
    (UPLOADS_DIR / f"{upload_id}_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    try:
        notify_new_upload(
            filename=file.filename,
            user_name=user_name,
            user_email=user_email,
            valido=result.get("valido"),
            sintesi=result.get("sintesi", ""),
            upload_id=upload_id,
        )
    except Exception as e:
        print(f"[email] Notifica fallita: {e}")

    return JSONResponse(result)


# ── CONTACT ───────────────────────────────────────────────────────────────────

@app.post("/api/contact")
async def contact(
    name: str = Form(...),
    email: str = Form(...),
    tipo: str = Form(...),
    messaggio: str = Form(...),
):
    if not name.strip() or not email.strip() or not messaggio.strip():
        raise HTTPException(400, "Compila tutti i campi obbligatori.")
    try:
        notify_contact(name=name, email=email, tipo=tipo, messaggio=messaggio)
    except Exception as e:
        print(f"[email] Contatto fallito: {e}")
        raise HTTPException(500, "Errore invio email. Riprova o scrivi direttamente a michelemasi.legal@gmail.com")
    return {"ok": True, "message": "Messaggio inviato. L'Avv. Masi la contatterà a breve."}


# ── ADMIN: UPLOADS ────────────────────────────────────────────────────────────

@app.get("/api/admin")
def admin_list(_: str = Depends(require_admin)):
    records = []
    for meta_file in sorted(UPLOADS_DIR.glob("*_meta.json"), reverse=True):
        try:
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            records.append({
                "id": data["id"],
                "filename": data["filename"],
                "user_name": data.get("user_name", ""),
                "user_email": data.get("user_email", ""),
                "uploaded_at": data["uploaded_at"],
                "valido": data["analysis"].get("valido"),
                "punteggio": data["analysis"].get("punteggio"),
                "sintesi": data["analysis"].get("sintesi", ""),
                "download_url": f"/api/admin/download/{data['safe_filename']}",
            })
        except Exception:
            pass
    return {"records": records}


@app.get("/api/admin/download/{filename}")
def admin_download(filename: str, _: str = Depends(require_admin)):
    path = UPLOADS_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "File non trovato.")
    return FileResponse(path, filename=filename)


# ── ADMIN: KNOWLEDGE BASE ─────────────────────────────────────────────────────

@app.get("/api/admin/knowledge")
def knowledge_list(_: str = Depends(require_admin)):
    files = []
    for f in sorted(KNOWLEDGE_DIR.iterdir()):
        if f.suffix.lower() in (".pdf", ".docx", ".doc", ".txt", ".md"):
            files.append({"name": f.name, "size_kb": round(f.stat().st_size / 1024, 1)})
    return {"files": files}


@app.post("/api/admin/knowledge")
async def knowledge_upload(
    file: UploadFile = File(...),
    _: str = Depends(require_admin),
):
    ext = Path(file.filename).suffix.lower()
    if ext not in (".pdf", ".docx", ".doc", ".txt", ".md"):
        raise HTTPException(400, "Formato non supportato per la knowledge base.")
    content = await file.read()
    (KNOWLEDGE_DIR / file.filename).write_bytes(content)
    return {"ok": True, "name": file.filename}


@app.delete("/api/admin/knowledge/{filename}")
def knowledge_delete(filename: str, _: str = Depends(require_admin)):
    path = KNOWLEDGE_DIR / filename
    if not path.exists():
        raise HTTPException(404, "File non trovato.")
    path.unlink()
    return {"ok": True}


# ── STATIC FILES ──────────────────────────────────────────────────────────────

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
