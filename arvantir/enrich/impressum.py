"""Impressum lesen: Entscheider, Kontakt, Register. Regeln zuerst, LLM nur als Rückfall.

§ 5 DDG verlangt auf fast jeder geschäftlichen Website Name des Vertretungsberechtigten,
E-Mail, Anschrift und (falls eingetragen) Registergericht + Registernummer. Für Firmen, die
keine Lead-Datenbank kennt, ist das oft der einzige Fußabdruck.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..common import llm_json
from ..harvest import PLZ_ORT, fetch
from ..realbrowser import fetch_real

IMPRESSUM_LINK = re.compile(r"impressum|imprint|legal[\s-]?notice|anbieterkennzeichnung|rechtliche[\s-]hinweise", re.I)
ROLE = re.compile(
    r"(Gesch(?:ä|ae)ftsf(?:ü|ue)hr(?:er(?:in)?|ung|ende[rn]?)|Inhaber(?:in)?|Praxisinhaber(?:in)?|"
    r"Apotheker(?:in)?|Vorstand(?:svorsitzende[rn]?)?|Vertretungsberechtigte?[rn]?(?:\s+Gesch(?:ä|ae)ftsf(?:ü|ue)hrer(?:in)?)?|"
    r"[Vv]ertreten\s+durch(?:\s+(?:den|die)\s+Gesch(?:ä|ae)ftsf(?:ü|ue)hrer(?:in)?)?|Managing\s+Directors?|CEO|Owner)"
    r"\s*[:\-–]?\s*", re.I)
NAME = re.compile(r"^(?:(?:Dr|Prof|Dipl\.-\w+)\.?\s+)*[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?"
                  r"(?:\s+(?:von|van|de|der|zu|vom)\b)?(?:\s+[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?){1,2}$")
# Kein Personenname: Behörden, Kammern, Länder, Rechts-/Berufsangaben (Bug 14:55: "Bundesrepublik Deutschland (Apothekerin)")
NOT_A_NAME = re.compile(r"\b(Bundesrepublik|Deutschland|Österreich|Schweiz|Kammer|\w*kammer|Amtsgericht|Behörde|Aufsicht|"
                        r"Ministerium|Regierungspräsidium|Gesundheitsamt|Landkreis|Landesamt|Bundesamt|Verband|"
                        r"Berufsbezeichnung|Berufsordnung|Approbation|Datenschutz|Impressum|Kontakt|Telefon|Straße)\b", re.I)
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+\s?(?:@|\(at\)|\[at\]|\sat\s)\s?[A-Za-z0-9.\-]+\s?(?:\.|\(dot\)|\[dot\])\s?[A-Za-z]{2,}")
PHONE = re.compile(r"(?:Tel(?:efon)?|Fon|Phone|T)\.?\s*[:\-]?\s*(\+?[\d][\d\s/()\-.]{5,}\d)", re.I)
FAX = re.compile(r"(?:Tele)?[Ff]ax\.?\s*[:\-]?\s*(\+?[\d][\d\s/()\-.]{5,}\d)")
HRB = re.compile(r"\b(HR\s?[AB]|GnR|PR|VR|FN)\s*[:.]?\s*(?:([A-ZÄÖÜ][a-zäöüß]+(?:\s(?:am|an der|i\.\s?Br\.)\s?[A-ZÄÖÜ]?[a-zäöüß]*)?)\s+)?(\d{2,7}\s?[A-Z]{0,2})\b")
COURT = re.compile(r"(?:Amtsgericht|Registergericht[:\s]*(?:Amtsgericht)?)[ \t]+([A-ZÄÖÜ][\wäöüß.\- ]{2,30}?)(?=[,;:\n]|[ \t]+(?:HR|unter|Nr|Registernummer)|$)")
VAT = re.compile(r"\b(DE\s?\d{3}\s?\d{3}\s?\d{3}|ATU\s?\d{8}|CHE[-\s]?\d{3}\.\d{3}\.\d{3})\b")
STREET = re.compile(r"([A-ZÄÖÜ][\wäöüß.\- ]{2,40}(?:straße|strasse|str\.|weg|allee|platz|ring|gasse|damm|ufer|chaussee)\s*\d+\s?[a-z]?)", re.I)
GENERIC = re.compile(r"^(info|kontakt|contact|office|mail|hello|hallo|service|post|team|buero|büro|praxis|apotheke|"
                     r"datenschutz|privacy|support|adressen|anfrage|vertrieb|sales|marketing|bewerbung|jobs|karriere|"
                     r"presse|press|webmaster|admin|zentrale|empfang|verwaltung|buchhaltung|rechnung|order|bestellung)@", re.I)


def find_impressum(html: str, base: str) -> List[str]:
    soup = BeautifulSoup(html or "", "lxml")
    urls = []
    for a in soup.find_all("a", href=True):
        if IMPRESSUM_LINK.search(a.get_text(" ", strip=True) + " " + a["href"]):
            u = urljoin(base, a["href"])
            if urlparse(u).netloc.replace("www.", "") == urlparse(base).netloc.replace("www.", ""):
                urls.append(u)
    root = f"{urlparse(base).scheme or 'https'}://{urlparse(base).netloc}"
    urls += [root + p for p in ("/impressum", "/impressum/", "/imprint", "/de/impressum")]
    return list(dict.fromkeys(urls))


def page_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    body = soup.body or soup  # ganzer Body: HRB und USt-ID stehen oft außerhalb von <main>
    return re.sub(r"\n\s*\n+", "\n", body.get_text("\n", strip=True))


TLD = re.compile(r"^(.+?\.(?:de|com|at|ch|eu|net|org|io|info|biz|berlin|hamburg|bayern|nrw|koeln|ruhr|"
                 r"online|shop|gmbh|co|app|ai|tech|digital|email|li|lu|nl|fr|it|es|uk|us|me))(?:\.|$)", re.I)


def _deobfuscate(s: str) -> str:
    s = re.sub(r"\s?(?:\(at\)|\[at\]|\sat\s)\s?", "@", s)
    s = re.sub(r"\s?(?:\(dot\)|\[dot\])\s?", ".", s).replace(" ", "")
    local, _, dom = s.partition("@")
    m = TLD.match(dom)  # "trovarit.com.Weitere" -> "trovarit.com"
    return f"{local}@{m.group(1)}" if m else s


def _names_after_role(text: str) -> List[Tuple[str, str]]:
    """Namen hinter einem Rollen-Label: in derselben Zeile (Komma/und) oder eine pro Zeile darunter."""
    found = []
    for m in ROLE.finditer(text):
        role = re.sub(r"\s+", " ", m.group(1)).strip()
        lines = [ln.strip() for ln in text[m.end(): m.end() + 300].split("\n")]
        if lines and not lines[0]:
            lines = lines[1:]
        for i, line in enumerate(lines[:5]):
            hits = []
            for part in re.split(r",|;|\s+und\s+|\s+&\s+|\s+sowie\s+", line):
                part = re.sub(r"\(.*?\)", "", part).strip(" .:")
                if (NAME.match(part) and not re.search(r"GmbH|AG\b|KG\b|Straße|Str\.", part)
                        and not NOT_A_NAME.search(part)):
                    hits.append((part, role))
            if not hits and (i > 0 or found):
                break  # erste Zeile ohne Namen beendet die Liste
            found += hits
    return list(dict.fromkeys(found))


def parse(text: str) -> Dict:
    out: Dict = {}
    people = _names_after_role(text)
    if people:
        out["decision_makers"] = [{"name": n, "role": r} for n, r in people[:4]]
    emails = list(dict.fromkeys(_deobfuscate(e).lower() for e in EMAIL.findall(text)))
    emails = [e for e in emails if not e.endswith((".png", ".jpg")) and "example" not in e]
    if emails:
        out["emails"] = emails[:5]
    for key, rx in (("phone", PHONE), ("fax", FAX)):
        m = rx.search(text)
        if m:
            out[key] = re.sub(r"\s+", " ", m.group(1)).strip()
    m = HRB.search(text)
    if m:
        out["hrb"] = f"{m.group(1).replace(' ', '')} {m.group(3).strip()}"
        c = COURT.search(text)
        court = c.group(1).strip() if c else (m.group(2) or "")
        if court:
            out["register_court"] = court
    m = VAT.search(text)
    if m:
        out["vat_id"] = m.group(1).replace(" ", "")
    m = STREET.search(text)
    if m:
        out["street"] = m.group(1).strip()
    m = PLZ_ORT.search(text)
    if m:
        out["postcode"], out["city"] = m.group(1), m.group(2).strip()
    return out


def _llm(text: str) -> Optional[Dict]:
    """Rückfall, nur wenn OPENAI_API_KEY gesetzt ist (OPENAI_BASE_URL für andere Anbieter)."""
    d = llm_json(
        "Impressum einer deutschen Firma. Gib JSON: {\"decision_makers\":[{\"name\":\"\",\"role\":\"\"}],"
        "\"email\":\"\",\"phone\":\"\",\"fax\":\"\",\"hrb\":\"\",\"register_court\":\"\"}. "
        "Nur was wörtlich im Text steht, sonst leer.\n\n" + text[:4000])
    if not d:
        return None
    d["decision_makers"] = [p for p in d.get("decision_makers", []) if p.get("name")]
    if d.get("email"):
        d["emails"] = [d.pop("email").lower()]
    return {k: v for k, v in d.items() if v}


def get(website: str) -> Tuple[Dict, str, str]:
    """(Felder, impressum_url, Weg). Weg = http | realbrowser | llm."""
    html, final = fetch(website, timeout=15)
    via = "http"
    if len(html) < 2000:
        html, final = fetch_real(website)
        via = "realbrowser"
    for url in find_impressum(html, final or website)[:4]:
        page, purl = fetch(url, timeout=15)
        txt = page_text(page)
        if len(txt) < 200 or not re.search(r"impressum|imprint|angaben gem|§\s?5", txt, re.I):
            page, purl = fetch_real(url)
            txt, via = page_text(page), "realbrowser"
        if len(txt) < 200:
            continue
        fields = parse(txt)
        if not fields.get("decision_makers"):
            llm = _llm(txt)
            if llm:
                fields = {**llm, **{k: v for k, v in fields.items() if v}}
                via = "llm"
        if fields:
            return fields, purl or url, via
    return {}, "", via
