"""Impressum-Parser: Entscheider-Namen, auch die Fehlerfälle aus den Läufen."""
import pytest

from arvantir.enrich.impressum import parse

CASES = [
    # run_144623 (Sami, 14:55): Aufsichts-/Länderzeile wurde als Name gelesen
    ("Impressum\nInhaberin: Dr. Maria Becker\nBerufsbezeichnung: Apothekerin\nBundesrepublik Deutschland\n"
     "Zuständige Kammer: Apothekerkammer Berlin", ["Dr. Maria Becker"]),
    ("Apotheker\nBundesrepublik Deutschland\nAufsichtsbehörde: Landesamt für Gesundheit", []),
    ("Vertreten durch:\nDr. Anna Schmidt, Peter Meier\nRegistergericht: Amtsgericht Charlottenburg\nHRB 123456 B",
     ["Dr. Anna Schmidt", "Peter Meier"]),
    ("Vorstand:\nDr. Karsten Sontow (Vors.)\nDr. Volker Liestmann\nPeter Treutlein\nAufsichtsrat",
     ["Dr. Karsten Sontow", "Dr. Volker Liestmann", "Peter Treutlein"]),
]


@pytest.mark.parametrize("text,want", CASES)
def test_decision_makers(text, want):
    assert [p["name"] for p in parse(text).get("decision_makers", [])] == want


def test_register_and_court():
    f = parse("Eingetragen beim Amtsgericht Aachen:\nHRB Aachen 8213\nUSt-IdNr:\nDE 212237140")
    assert f["hrb"] == "HRB 8213" and f["register_court"] == "Aachen" and f["vat_id"] == "DE212237140"
