"""channel: bester Weg zum Entscheider, rechtlich sauber (§ 7 UWG).

E-Mail- und Fax-Werbung brauchen vorherige ausdrückliche Einwilligung, auch B2B.
Briefe sind erlaubt, solange kein Widerspruch vorliegt. Darum ist Brief der Standard für
lokale Betriebe (Bäcker, Metzger, Waschanlagen, Praxen); E-Mail/LinkedIn nur nach Opt-in
oder als warmer Folgekontakt; Fax nur mit Einwilligung (Demo: an uns selbst).
"""
from __future__ import annotations

from typing import Dict


def channel(c: Dict) -> Dict:
    has_addr = bool(c.get("street") and c.get("postcode"))
    if has_addr:
        kanal, warum = "Brief", "Postadresse aus dem Impressum; Brief braucht keine Einwilligung"
    elif c.get("phone"):
        kanal, warum = "Telefon", "keine Postadresse gefunden; B2B-Anruf bei mutmaßlichem Interesse"
    else:
        kanal, warum = "LinkedIn", "kein Brief- oder Telefonkontakt im Impressum"
    extra = []
    if c.get("email_typ") == "persönlich":
        extra.append("E-Mail nach Opt-in")
    if c.get("fax"):
        extra.append("Fax nur mit Einwilligung")
    return {"kanal": kanal, "kanal_grund": warum, "kanal_extra": ", ".join(extra)}
