import yaml, os, threading

_lock = threading.Lock()
_config = {}
_path = os.path.join(os.path.dirname(__file__), "config.yaml")


def load():
    global _config
    with open(_path, "r") as f:
        _config = yaml.safe_load(f)
    return _config


def get():
    if not _config:
        load()
    return _config


def update(patch: dict):
    with _lock:
        cfg = get()
        _deep_merge(cfg, patch)
        with open(_path, "w") as f:
            yaml.dump(cfg, f, allow_unicode=True)
    return cfg


def _deep_merge(base, override):
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
