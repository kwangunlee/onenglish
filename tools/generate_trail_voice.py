"""Generate the fixed Word Trails lesson audio. Requires OPENAI_API_KEY."""
import hashlib
import json
import os
import re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from openai import OpenAI, APIError


ROOT = Path(__file__).resolve().parents[1] / "word_trails"
MODEL = "gpt-4o-mini-tts"
VOICE = "marin"
STYLE = ("You are a warm, engaging American English reading teacher. "
         "Read the supplied English text exactly once, without introductions. "
         "Use natural sentence stress, clear articulation, and an unhurried conversational pace.")


def lesson_clips():
    catalog = ROOT.parent / "data" / "word_trails.json"
    for course in json.loads(catalog.read_text(encoding="utf-8")):
        for word, _, template, _ in course["entries"]:
            if not re.fullmatch("[A-Z]+", word) or template.count("___") != 1:
                raise ValueError(f"Invalid lesson entry: {word}")
            spoken = "Earth" if word == "EARTH" else word.lower()
            yield "words", word.lower(), spoken
            yield "sentences", word.lower(), template.replace("___", spoken)



def main():
    client = OpenAI(base_url="https://api.openai.com/v1", timeout=60, max_retries=2)
    root = ROOT / "voice"
    manifest_file = root / "manifest.json"
    manifest = json.loads(manifest_file.read_text()) if manifest_file.exists() else {}
    tasks = []
    for kind, word, text in lesson_clips():
        filename = f"{kind}/{word}.mp3"
        digest = hashlib.sha256("\n".join((MODEL, VOICE, STYLE, text)).encode()).hexdigest()
        path = root / filename
        if manifest.get(filename) != digest or not path.is_file() or path.stat().st_size < 512:
            tasks.append((filename, digest, text))

    def generate(task):
        filename, digest, text = task
        path = root / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".part", delete=False) as handle:
            temp = Path(handle.name)
        try:
            with client.audio.speech.with_streaming_response.create(
                model=MODEL, voice=VOICE, instructions=STYLE, input=text, response_format="mp3"
            ) as response:
                response.stream_to_file(temp)
            if temp.stat().st_size < 512:
                raise ValueError("Empty speech response")
            os.replace(temp, path)
            return filename, digest
        finally:
            temp.unlink(missing_ok=True)

    def record(result):
        filename, digest = result
        manifest[filename] = digest
        temp = manifest_file.with_suffix(".tmp")
        temp.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        for attempt in range(7):
            try:
                os.replace(temp, manifest_file)
                break
            except PermissionError:
                if attempt == 6:
                    raise
                time.sleep(0.1 * 2**attempt)

    if tasks:
        record(generate(tasks[0]))  # Check credentials before issuing the rest.
        with ThreadPoolExecutor(max_workers=3) as pool:
            for result in pool.map(generate, tasks[1:]):
                record(result)
    print(f"Verified {len(manifest)} OpenAI speech clips.")


if __name__ == "__main__":
    try:
        main()
    except APIError as exc:
        # Some authentication error bodies echo a portion of a credential.
        print("OpenAI speech request failed:", type(exc).__name__, getattr(exc, "status_code", None), getattr(exc, "code", None))
        raise SystemExit(1)
