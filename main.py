
import os
from pathlib import Path

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Effective Configuration API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}


def normalize_key(key):
    key = key.strip().lower()

    if key.startswith("app_"):
        key = key[4:]

    return key


def env_layer(values):
    result = {}

    for key, value in values.items():
        if value is None:
            continue

        if key.upper() == "NUM_WORKERS":
            result["workers"] = value
        elif key.upper().startswith("APP_"):
            result[normalize_key(key)] = value

    return result


def coerce(key, value):
    if key in ("port", "workers"):
        return int(value)

    if key == "debug":
        if isinstance(value, bool):
            return value

        return str(value).strip().lower() in {
            "true", "1", "yes", "on"
        }

    if isinstance(value, bool):
        return str(value).lower()

    return str(value)


def build_config(overrides):
    config = DEFAULTS.copy()

    # Layer 2: environment-specific YAML
    env_name = os.environ.get("APP_ENV", "development")
    yaml_path = BASE_DIR / f"config.{env_name}.yaml"

    if yaml_path.exists():
        with open(yaml_path, encoding="utf-8") as file:
            yaml_config = yaml.safe_load(file) or {}

        config.update({
            normalize_key(key): value
            for key, value in yaml_config.items()
        })

    # Layer 3: .env file
    file_env = dotenv_values(BASE_DIR / ".env")
    config.update(env_layer(file_env))

    # Layer 4: real OS environment variables
    os_env = {
        key: value
        for key, value in os.environ.items()
        if key.upper().startswith("APP_")
        and key.upper() != "APP_ENV"
    }
    config.update(env_layer(os_env))

    # Layer 5: dynamic CLI/query overrides
    for item in overrides:
        if "=" not in item:
            continue

        key, value = item.split("=", 1)
        key = normalize_key(key)

        if key:
            config[key] = value

    # Apply consistent types after merging all layers.
    config = {
        key: coerce(key, value)
        for key, value in config.items()
    }

    # Never reveal the actual API key.
    config["api_key"] = "****"

    return config


@app.get("/")
@app.get("/effective-config")
def effective_config(set: list[str] | None = Query(default=None)):
    return build_config(set or [])
