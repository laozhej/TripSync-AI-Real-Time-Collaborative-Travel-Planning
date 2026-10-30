import json
from pathlib import Path

from pydantic import ValidationError
import pytest
from app.datasets.schema import Dataset

PATH = Path(__file__).resolve().parents[2] / "data/destinations/lisbon.json"


def test_authored_destination_covers_filters():
    data = Dataset.model_validate_json(PATH.read_text(encoding="utf-8"))
    assert {v.category for v in data.venues} >= {"food", "lodging", "activity"}
    assert set().union(*(set(v.dietaryTags) for v in data.venues)) == {"vegetarian", "vegan", "halal", "gluten-free"}
    assert any(len(v.dietaryTags) == 4 for v in data.venues)
    assert data.transit and data.weather


@pytest.mark.parametrize("mutate", [
    lambda d: d["venues"][0].update(pricePerPerson="0"),
    lambda d: d["venues"][0].update(dietaryTags=["unknown"]),
    lambda d: d["venues"][0]["coordinates"].update(lat=90.1),
    lambda d: d["venues"][0]["hours"]["weekly"][0].update(close="10:00", closeDayOffset=0),
    lambda d: d["venues"].append(d["venues"][0]),
    lambda d: d["transit"][0].update(toVenueId="missing"),
])
def test_invalid_bundle_is_rejected(mutate):
    data = json.loads(PATH.read_text(encoding="utf-8"))
    mutate(data)
    with pytest.raises(ValidationError):
        Dataset.model_validate(data)


def test_duplicate_json_keys_are_rejected(tmp_path):
    from app.datasets.importer import load_dataset
    path = tmp_path / "duplicate.json"
    path.write_text('{"schemaVersion":1,"schemaVersion":1}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_dataset(path)


def test_overlapping_opening_hours_are_rejected():
    data = json.loads(PATH.read_text(encoding="utf-8"))
    data["venues"][0]["hours"]["weekly"].append({"days":[1], "open":"12:00", "close":"13:00", "closeDayOffset":0})
    with pytest.raises(ValidationError, match="overlapping"):
        Dataset.model_validate(data)
