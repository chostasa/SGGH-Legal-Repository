import os
from services import demand_service
from core.usage_tracker import check_quota, decrement_quota

def test_full_demand_generation_integration(tmp_path):
    template_path = tmp_path / "template.docx"
    output_path = tmp_path / "output.docx"

    from docx import Document
    doc = Document()
    doc.add_paragraph("{{ClientName}}")
    doc.save(template_path)

    check_quota("openai_tokens", amount=1)
    demand_service.generate_demand_letter(
        client_name="John Doe",
        defendant="Acme Corp",
        location="Chicago",
        incident_date="2025-01-01",
        summary="Incident summary",
        damages="Damages summary",
        template_path=str(template_path),
        output_path=str(output_path),
        example_text=""
    )
    decrement_quota("openai_tokens", amount=1)

    assert os.path.exists(output_path)