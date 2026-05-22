import os
import io
import json
from pathlib import Path

import anthropic
import PyPDF2
from docx import Document

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
KNOWLEDGE_EXCERPT_CHARS = 3000

SYSTEM_PROMPT = """Sei un avvocato giuslavorista italiano di primo livello, specializzato in patti di non concorrenza ex art. 2125 c.c.

Il tuo compito è analizzare il testo di un patto di non concorrenza e verificare la presenza e la validità dei 4 requisiti cumulativi previsti dalla legge a pena di nullità:

1. FORMA SCRITTA (ad substantiam) — il patto deve essere redatto per iscritto
2. DETERMINAZIONE DELL'OGGETTO — le attività vietate devono essere specificate con precisione (settore, clientela, tipologia di concorrenza)
3. LIMITI DI DURATA E TERRITORIO — durata massima: 5 anni per dirigenti, 3 anni per tutti gli altri; ambito geografico circoscritto e ragionevole
4. CORRISPETTIVO CONGRUO — deve essere determinato o determinabile, proporzionato al sacrificio imposto, non simbolico, non già incluso nella RAL

Fornisci sempre una valutazione precisa, giuridicamente motivata, con riferimento alla giurisprudenza della Cassazione quando pertinente.
Rispondi SEMPRE in italiano.
Rispondi SEMPRE e SOLO con un oggetto JSON valido, senza testo prima o dopo.
"""

ANALYSIS_SCHEMA = """{
  "valido": true | false | null,
  "punteggio": <0-100, dove 100=pienamente valido, 0=totalmente nullo>,
  "sintesi": "<2-3 frasi: giudizio complessivo sul patto>",
  "requisiti": {
    "forma_scritta": {"ok": true|false|null, "note": "<valutazione specifica>"},
    "limiti_oggetto": {"ok": true|false|null, "note": "<valutazione specifica>"},
    "limiti_tempo_luogo": {"ok": true|false|null, "note": "<valutazione specifica>"},
    "corrispettivo": {"ok": true|false|null, "note": "<valutazione specifica>"}
  },
  "problemi": ["<problema 1>", "<problema 2>"],
  "raccomandazioni": "<testo con suggerimenti pratici, sia per l'azienda che per il lavoratore>",
  "disclaimer": "Questa analisi ha carattere orientativo e non costituisce parere legale. Per una valutazione professionale contattare l'Avv. Michele Masi."
}"""


def extract_text_from_pdf(content: bytes) -> str:
    reader = PyPDF2.PdfReader(io.BytesIO(content))
    parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n".join(parts)


def extract_text_from_docx(content: bytes) -> str:
    doc = Document(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text(filename: str, content: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        return extract_text_from_pdf(content)
    if name.endswith(".docx") or name.endswith(".doc"):
        return extract_text_from_docx(content)
    return content.decode("utf-8", errors="replace")


def _load_knowledge_context() -> str:
    if not KNOWLEDGE_DIR.exists():
        return ""
    excerpts = []
    for f in sorted(KNOWLEDGE_DIR.iterdir()):
        if f.suffix.lower() not in (".pdf", ".docx", ".doc", ".txt", ".md"):
            continue
        try:
            raw = f.read_bytes()
            if f.suffix.lower() == ".pdf":
                text = extract_text_from_pdf(raw)
            elif f.suffix.lower() in (".docx", ".doc"):
                text = extract_text_from_docx(raw)
            else:
                text = raw.decode("utf-8", errors="replace")
            excerpt = text[:KNOWLEDGE_EXCERPT_CHARS].strip()
            if excerpt:
                excerpts.append(f"=== {f.name} ===\n{excerpt}")
        except Exception as e:
            print(f"[knowledge] Errore lettura {f.name}: {e}")
    return "\n\n".join(excerpts)


def analyze_patto(filename: str, content: bytes) -> dict:
    patto_text = extract_text(filename, content)
    if not patto_text.strip():
        return {
            "valido": None,
            "punteggio": 0,
            "sintesi": "Impossibile estrarre testo dal documento. Verificare che il file non sia protetto o corrotto.",
            "requisiti": {
                "forma_scritta": {"ok": None, "note": "Testo non estraibile"},
                "limiti_oggetto": {"ok": None, "note": "Testo non estraibile"},
                "limiti_tempo_luogo": {"ok": None, "note": "Testo non estraibile"},
                "corrispettivo": {"ok": None, "note": "Testo non estraibile"},
            },
            "problemi": ["Documento non leggibile — possibile PDF scansionato o protetto."],
            "raccomandazioni": "Caricare il documento in formato DOCX o PDF con testo selezionabile.",
            "disclaimer": "Questa analisi ha carattere orientativo e non costituisce parere legale. Per una valutazione professionale contattare l'Avv. Michele Masi.",
        }

    knowledge_ctx = _load_knowledge_context()

    user_message = ""
    if knowledge_ctx:
        user_message += f"### MATERIALE DI RIFERIMENTO (sentenze e dottrina)\n\n{knowledge_ctx}\n\n---\n\n"

    user_message += f"### PATTO DI NON CONCORRENZA DA ANALIZZARE\n\nFile: {filename}\n\n{patto_text[:8000]}\n\n---\n\n"
    user_message += f"Analizza il patto rispettando esattamente il seguente schema JSON:\n\n{ANALYSIS_SCHEMA}"

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()
    # strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)
