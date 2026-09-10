from sales_agent.retrieval import HybridRetriever


def test_retrieval_finds_nearest_store() -> None:
    hits = HybridRetriever().search("Где ближайший магазин к Краснодару?")
    assert hits
    assert hits[0].document.id == "stores-south"


def test_retrieval_finds_custom_strap_policy() -> None:
    hits = HybridRetriever().search("Сделаете ремешок индивидуального размера?")
    assert hits
    assert hits[0].document.id == "custom-straps"
