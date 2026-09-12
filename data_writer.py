"""Keep polling-only timestamps out of dataset change detection."""
import json


def comparable(value):
    if isinstance(value, dict):
        return {key: comparable(item) for key, item in value.items()
                if key not in {"checked_at", "fetched_at"}}
    if isinstance(value, list):
        return [comparable(item) for item in value]
    return value


def write_changed(path, data, only_if_changed=True):
    if only_if_changed and path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        if comparable(previous) == comparable(data):
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)
    return True
