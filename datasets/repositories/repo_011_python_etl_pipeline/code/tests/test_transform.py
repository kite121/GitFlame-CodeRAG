from pipeline.transform import deduplicate


def test_deduplicate_keeps_first():
    rows = [{"id": 1}, {"id": 1}, {"id": 2}]
    assert deduplicate(rows) == [{"id": 1}, {"id": 2}]
