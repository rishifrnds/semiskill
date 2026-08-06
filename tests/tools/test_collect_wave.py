import json

import pytest

from semiskill.authoring.review_collection import BatchRejected
from tools.collect_wave import load_results


def test_load_results_rejects_malformed_jsonl_instead_of_skipping_it(tmp_path):
    path = tmp_path / "results.jsonl"
    path.write_text('{"slug":"dv-a"}\nnot-json\n', encoding="utf-8")
    with pytest.raises(BatchRejected, match="malformed JSONL"):
        load_results(path)


def test_load_results_accepts_only_an_array_of_objects(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(json.dumps({"results": [{"slug": "dv-a"}]}), encoding="utf-8")
    assert load_results(path) == [{"slug": "dv-a"}]

    path.write_text(json.dumps({"results": [True]}), encoding="utf-8")
    with pytest.raises(BatchRejected, match="array of result objects"):
        load_results(path)
