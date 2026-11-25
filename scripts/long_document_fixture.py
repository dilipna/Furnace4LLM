"""Synthetic 25-page text PDF for actual extraction/staged-inference trials; no customer data."""

import io
import textwrap

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def make_pdf() -> bytes:
    writer = PdfWriter()
    sections = [
        "Scope and ownership",
        "Document register",
        "Access requests",
        "Review schedule",
        "Draft preparation",
        "Meeting records",
        "Change requests",
        "Risk register",
        "Supplier coordination",
        "Budget records",
        "Quality review",
        "Accessibility review",
        "Incident reporting",
        "Record retention",
        "Handover notes",
        "Training arrangements",
        "Equipment inventory",
        "Data classification",
        "Travel arrangements",
        "Progress reporting",
        "Stakeholder feedback",
        "Release checklist",
        "Archive procedure",
        "Final review",
        "Submission",
    ]
    for number, title in enumerate(sections, 1):
        text = (
            f"Project Birch operations handbook. Page {number}: {title}. "
            "Project owner: Maya. This is a fictional administrative example for testing, not legal advice. "
            f"Section {number} records the responsibilities for {title.lower()}. The team keeps an index of "
            "approved records, identifies the responsible reviewer and checks that readers have the latest version. "
            "A proposed change must describe its purpose, affected work and expected outcome. Reviewers record "
            "questions in the shared register rather than silently changing another person's decision. "
            "Approval of a draft does not imply permission to spend money or publish personal information. "
            "The coordinator checks dependencies before assigning work, and asks the owner when a prerequisite is missing. "
            "Notes should separate observations from assumptions, retain failed checks, and link the source document. "
            "Dates in old proposals are historical; only an explicitly approved final date is binding in this handbook. "
            "Each completed activity needs a short handover note with the responsible person, evidence and remaining issues. "
            "Do not infer a deadline from a page number or from the order of sections. This section does not add a new deadline. "
            "Readers should check the original wording before acting on a summary. The fictional names do not refer to customers. "
        )
        if number == 25:
            text += "The final submission deadline is 2027-02-19. Maya owns the final submission."
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        lines = textwrap.wrap(text, 85)
        assert len(lines) <= 45
        escaped = [
            line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines
        ]
        stream = DecodedStreamObject()
        stream.set_data(
            (
                "BT /F1 10 Tf 14 TL 35 750 Td "
                + " T* ".join("(" + line + ") Tj" for line in escaped)
                + " ET"
            ).encode("ascii")
        )
        page[NameObject("/Contents")] = writer._add_object(stream)
    target = io.BytesIO()
    writer.write(target)
    return target.getvalue()
