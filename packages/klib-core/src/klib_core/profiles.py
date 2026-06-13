from __future__ import annotations

import json
from pathlib import Path

from .errors import KlibError
from .library import slugify
from .models import ModelProfile


class ModelProfileManager:
    def __init__(self, home: Path):
        self.path = home / "model-profiles.json"

    def list(self) -> list[ModelProfile]:
        if not self.path.exists():
            return []
        return [
            ModelProfile.model_validate(item)
            for item in json.loads(self.path.read_text(encoding="utf-8"))
        ]

    def save(self, profile: ModelProfile) -> ModelProfile:
        profiles = self.list()
        existing = next((item for item in profiles if item.id == profile.id), None)
        if existing:
            profiles[profiles.index(existing)] = profile
        else:
            profiles.append(profile)
        self.path.write_text(
            json.dumps(
                [item.model_dump(mode="json") for item in profiles],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return profile

    def create(
        self,
        *,
        name: str,
        provider: str,
        model: str,
        base_url: str | None = None,
        api_key_env: str | None = None,
        options: dict | None = None,
        profile_id: str | None = None,
    ) -> ModelProfile:
        return self.save(
            ModelProfile(
                id=slugify(profile_id or name),
                name=name,
                provider=provider,
                model=model,
                base_url=base_url,
                api_key_env=api_key_env,
                options=options or {},
            )
        )

    def delete(self, profile_id: str) -> None:
        profiles = self.list()
        kept = [item for item in profiles if item.id != profile_id]
        if len(kept) == len(profiles):
            raise KlibError(f"Model profile not found: {profile_id}")
        self.path.write_text(
            json.dumps(
                [item.model_dump(mode="json") for item in kept],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
