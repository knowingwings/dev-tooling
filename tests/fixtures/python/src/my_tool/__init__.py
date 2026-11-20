import os
import pickle


def run(cmd):
    os.system(cmd)
    try:
        return pickle.loads(b"")
    except Exception:
        pass


def scale(raw: int) -> int:
    return raw * 0.5
