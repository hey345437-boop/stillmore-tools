"""Read public duration badges from the brand's own YouTube uploads playlist."""
import json
import re

def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk(value)

def duration_index(raw):
    html = raw.decode("utf-8")
    match = re.search(r"var ytInitialData\s*=\s*", html)
    if not match:
        raise ValueError("Playlist data unavailable")
    data = json.JSONDecoder().raw_decode(html[match.end():])[0]
    result = {}
    for node in walk(data.get("contents", {})):
        if "playlistVideoRenderer" in node:
            row = node["playlistVideoRenderer"]
            if str(row.get("lengthSeconds", "")).isdigit():
                result[row["videoId"]] = int(row["lengthSeconds"])
        card = node.get("lockupViewModel", {})
        if card.get("contentType") != "LOCKUP_CONTENT_TYPE_VIDEO":
            continue
        for overlay in walk(card.get("contentImage", {})):
            badge = overlay.get("thumbnailBadgeViewModel", {}).get("text", "")
            if isinstance(badge,str) and re.fullmatch(r"(?:\d+:)?\d+:[0-5]\d", badge):
                seconds=0
                for part in badge.split(":"):
                    seconds=seconds*60+int(part)
                result[card["contentId"]]=seconds
                break
    return result
