"""Validate and import an authored destination as its initial immutable version."""
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.datasets.schema import Dataset

MAX_BYTES = 2 * 1024 * 1024


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def load_dataset(path: Path) -> tuple[Dataset, str]:
    raw = path.read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError("dataset exceeds 2 MiB")
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite number")))
    return Dataset.model_validate(data), hashlib.sha256(raw).hexdigest()


async def import_initial(engine: AsyncEngine, path: Path) -> str:
    """Insert initial active dataset atomically; never replace a version in use."""
    dataset, checksum = load_dataset(path)
    dataset_id = uuid4()
    async with engine.begin() as conn:
        if (await conn.execute(text("SELECT 1 FROM datasets WHERE destination=:destination LIMIT 1"),
                               {"destination": dataset.destination})).first():
            raise ValueError("destination already exists; version activation is not implemented")
        await conn.execute(text("""INSERT INTO datasets
            (id,destination,version,timezone,currency,status,provenance,checksum)
            VALUES (:id,:destination,1,:timezone,:currency,'active',CAST(:provenance AS jsonb),:checksum)"""),
            dict(id=dataset_id, destination=dataset.destination, timezone=dataset.timezone,
                 currency=dataset.currency, provenance=dataset.provenance.model_dump_json(), checksum=checksum))
        for venue in dataset.venues:
            venue_id = uuid4()
            await conn.execute(text("""INSERT INTO venue_metadata
                (id,dataset_id,source_id,name,category,price_per_person_minor,currency,latitude,longitude,rating,description,hours)
                VALUES (:id,:dataset_id,:source_id,:name,:category,:price,:currency,:lat,:lng,:rating,:description,CAST(:hours AS jsonb))"""),
                dict(id=venue_id, dataset_id=dataset_id, source_id=venue.sourceId, name=venue.name,
                     category=venue.category, price=int(venue.pricePerPerson * 100), currency=dataset.currency,
                     lat=venue.coordinates.lat, lng=venue.coordinates.lng, rating=venue.rating,
                     description=venue.description, hours=venue.hours.model_dump_json()))
            for tag in venue.dietaryTags:
                await conn.execute(text("INSERT INTO venue_dietary_tags (venue_id,dataset_id,tag) VALUES (:venue_id,:dataset_id,:tag)"),
                                   dict(venue_id=venue_id, dataset_id=dataset_id, tag=tag))
        for entry in dataset.transit:
            await conn.execute(text("INSERT INTO transit_metadata (id,dataset_id,source_id,data) VALUES (:id,:dataset_id,:source_id,CAST(:data AS jsonb))"),
                               dict(id=uuid4(), dataset_id=dataset_id, source_id=entry.sourceId, data=entry.model_dump_json()))
        for entry in dataset.weather:
            await conn.execute(text("INSERT INTO weather_metadata (id,dataset_id,source_id,local_date,data) VALUES (:id,:dataset_id,:source_id,:local_date,CAST(:data AS jsonb))"),
                               dict(id=uuid4(), dataset_id=dataset_id, source_id=entry.sourceId, local_date=entry.date, data=entry.model_dump_json()))
    return str(dataset_id)
