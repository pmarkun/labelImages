import json
from datetime import datetime, date
from typing import List, Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from utils.config import load_config
from .models import Base, Race, Participant
from core.data_manager import DataManager


def get_engine_from_config(config_path: str):
    cfg = load_config(config_path)
    url = cfg.get("url", "sqlite:///database.db")
    return create_engine(url, future=True)


class DBManager:
    def __init__(self, config_path: str = "db_config.yaml"):
        self.config_path = config_path
        self.engine = get_engine_from_config(config_path)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)

    def list_races(self) -> List[Dict[str, Any]]:
        session = self.Session()
        races = session.query(Race).all()
        result = []
        for race in races:
            participants_data = [json.loads(p.data) for p in race.participants]
            num_participants = len(participants_data)
            images = 0
            categories = set()
            for p in participants_data:
                if p.get("run_category"):
                    categories.add(p["run_category"])
                for r in p.get("runners_found", []):
                    if r.get("image") or r.get("image_path"):
                        images += 1
            result.append({
                "id": race.id,
                "name": race.name,
                "date": race.date.isoformat() if race.date is not None else "",
                "location": race.location,
                "num_participants": num_participants,
                "num_images": images,
                "categories": ", ".join(sorted(categories))
            })
        session.close()
        return result

    def add_race(self, name: str, location: str, date: date, json_path: str) -> int:
        session = self.Session()
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            race = Race(name=name, location=location, date=date)
            session.add(race)
            session.flush()
            # Access the ID while session is still active
            race_id = race.id  # type: ignore
            for item in data:
                session.add(Participant(race_id=race_id, data=json.dumps(item)))
            session.commit()
            return race_id  # type: ignore
        finally:
            session.close()

    def delete_race(self, race_id: int) -> None:
        session = self.Session()
        try:
            race = session.get(Race, race_id)
            if race:
                session.delete(race)
                session.commit()
        finally:
            session.close()

    def load_race_data(self, race_id: int) -> List[Dict[str, Any]]:
        session = self.Session()
        try:
            race = session.get(Race, race_id)
            data = [json.loads(p.data) for p in race.participants] if race else []
            return data
        finally:
            session.close()

    def export_race_to_json(self, race_id: int, path: str) -> None:
        data = self.load_race_data(race_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def export_race_to_csv(self, race_id: int, path: str) -> int:
        data = self.load_race_data(race_id)
        dm = DataManager()
        dm.load_data(data)
        return dm.export_simplified_csv(path)
