import json
from pathlib import Path


def load_profile(dataset_name: str) -> dict:
    profiles_dir = Path(__file__).parent
    profile_path = profiles_dir / f"{dataset_name.lower()}.json"

    if not profile_path.exists():
        raise FileNotFoundError(f"Profil d'analyse pour {dataset_name} introuvable : {profile_path}")

    with open(profile_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_profile(dataset_name: str, profile: dict) -> Path:
    profiles_dir = Path(__file__).parent
    profile_path = profiles_dir / f"{dataset_name.lower()}.json"
    profiles_dir.mkdir(parents=True, exist_ok=True)

    with open(profile_path, "w", encoding="utf-8") as handle:
        json.dump(profile, handle, indent=2, ensure_ascii=False)

    return profile_path


def profile_exists(dataset_name: str) -> bool:
    profiles_dir = Path(__file__).parent
    profile_path = profiles_dir / f"{dataset_name.lower()}.json"
    return profile_path.exists()
