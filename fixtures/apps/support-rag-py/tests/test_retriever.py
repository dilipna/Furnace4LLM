from app.retriever import retrieve


def test_error_code_question_retrieves_error_codes_doc():
    chunks = retrieve("What does error E14 mean?", top_k=3)
    assert chunks[0].doc_id == "error-codes"


def test_top_k_respected():
    assert len(retrieve("billing invoices refund", top_k=2)) == 2
