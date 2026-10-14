"""Local paths and metadata; importing this module never accesses the network."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SANAANI_ID = 'yemeni-sanaani'
SANAANI_REPO = 'mansoorSaleh/whisper-yemeni'
SANAANI_REVISION = 'a6dbcec77066d2799542aae3402b9e18a059df42'
SANAANI_PATH = ROOT / 'models/whisper-yemeni'


def sanaani_installed():
    return all((SANAANI_PATH / name).is_file() for name in ['model.bin', 'config.json', 'tokenizer.json', 'glts-model.json'])
