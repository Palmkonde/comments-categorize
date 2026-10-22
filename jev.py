"""Fetch YouTube comments, ask JEV three moderation questions, save results."""
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import yt_dlp
from dotenv import load_dotenv
from typesafe_sdk import RetryPolicy, TypeSafeAuthenticationError, TypeSafeClient

load_dotenv()

MODEL = "jev-latest"
RETRY = RetryPolicy(max_retries=4)  # SDK retries 408, 429, 5xx (incl. 529) with backoff + Retry-After
PRICE_PER_M = 0.042  # USD per 1M input tokens, output free. From TypeSafe's launch post, Oct 2026.
DATA_DIR = Path(__file__).parent / "data"
THAI_DIR = DATA_DIR / "thai_questions"  # subfolder, so load_all() doesn't pick it up
EXP_DIR = DATA_DIR / "experiments"  # section 11, also a subfolder

CATEGORIES = {
    "clean": "Normal comment: opinion, praise, question, or discussion about the video",
    "spam": "Scams, bots, repeated text, fake giveaways, suspicious links",
    "self_promotion": "Advertising own channel, product, or social media",
    "harassment": "Insults or attacks against a person, the creator, or other commenters",
    "hate_speech": "Attacks on a group based on race, religion, gender, nationality, etc.",
    "misinformation": "False or misleading claims presented as fact",
    "off_topic": "Unrelated to the video",
}
SEVERITY = ["None", "Mild", "Moderate", "Severe"]

QUESTIONS = {
    "flag": {
        "type": "noul",
        "instructions": "Should a moderator review this YouTube comment?",
        "criteria": {
            "true": "The comment may break community rules: spam, scams, harassment, hate, or harmful misinformation.",
            "false": "A normal comment that is safe to keep.",
        },
    },
    "category": {
        "type": "choice",
        "instructions": "What is the main category of this YouTube comment?",
        "criteria": CATEGORIES,
    },
    "severity": {
        "type": "score",
        "instructions": "How harmful is this YouTube comment?",
        "criteria": [
            "None: harmless",
            "Mild: rude or annoying",
            "Moderate: insulting, misleading, or clearly unwanted",
            "Severe: hateful, threatening, or dangerous",
        ],
    },
}

# Same three questions in Thai. Choice keys stay English so answers can be compared one-to-one.
QUESTIONS_TH = {
    "flag": {
        "type": "noul",
        "instructions": "ผู้ดูแลควรตรวจสอบความคิดเห็น YouTube นี้หรือไม่?",
        "criteria": {
            "true": "ความคิดเห็นอาจละเมิดกฎของชุมชน: สแปม การหลอกลวง การคุกคาม ความเกลียดชัง หรือข้อมูลเท็จที่เป็นอันตราย",
            "false": "ความคิดเห็นปกติที่เก็บไว้ได้อย่างปลอดภัย",
        },
    },
    "category": {
        "type": "choice",
        "instructions": "ความคิดเห็น YouTube นี้อยู่ในหมวดหมู่หลักใด?",
        "criteria": {
            "clean": "ความคิดเห็นปกติ: ความเห็น คำชม คำถาม หรือการพูดคุยเกี่ยวกับวิดีโอ",
            "spam": "การหลอกลวง บอท ข้อความซ้ำ ๆ แจกของปลอม ลิงก์น่าสงสัย",
            "self_promotion": "โฆษณาช่อง สินค้า หรือโซเชียลมีเดียของตัวเอง",
            "harassment": "ดูถูกหรือโจมตีบุคคล ผู้สร้างวิดีโอ หรือผู้แสดงความคิดเห็นคนอื่น",
            "hate_speech": "โจมตีกลุ่มคนจากเชื้อชาติ ศาสนา เพศ สัญชาติ ฯลฯ",
            "misinformation": "อ้างข้อมูลเท็จหรือชวนให้เข้าใจผิดราวกับเป็นข้อเท็จจริง",
            "off_topic": "ไม่เกี่ยวข้องกับวิดีโอ",
        },
    },
    "severity": {
        "type": "score",
        "instructions": "ความคิดเห็น YouTube นี้เป็นอันตรายแค่ไหน?",
        "criteria": [
            "ไม่มี: ไม่เป็นอันตราย",
            "เล็กน้อย: หยาบคายหรือน่ารำคาญ",
            "ปานกลาง: ดูถูก ชวนให้เข้าใจผิด หรือไม่พึงประสงค์อย่างชัดเจน",
            "รุนแรง: แสดงความเกลียดชัง ข่มขู่ หรือเป็นอันตราย",
        ],
    },
}


# Same three questions in English, reworded: the control for the wording experiment (section 11).
# Same meaning, choice keys, and number of levels; only the words change.
QUESTIONS_EN2 = {
    "flag": {
        "type": "noul",
        "instructions": "Does this YouTube comment need to be checked by a moderator?",
        "criteria": {
            "true": "The comment might violate community guidelines: spam, scams, harassment, hate, or dangerous false information.",
            "false": "An ordinary comment that can safely stay up.",
        },
    },
    "category": {
        "type": "choice",
        "instructions": "Which category best describes this YouTube comment?",
        "criteria": {
            "clean": "Ordinary comment: an opinion, compliment, question, or discussion of the video",
            "spam": "Scams, bots, copy-pasted text, fake giveaways, or suspicious links",
            "self_promotion": "Promoting the commenter's own channel, product, or social media",
            "harassment": "Insulting or attacking a person, the video creator, or other commenters",
            "hate_speech": "Attacking a group because of race, religion, gender, nationality, or similar",
            "misinformation": "Untrue or misleading claims stated as facts",
            "off_topic": "Not related to the video",
        },
    },
    "severity": {
        "type": "score",
        "instructions": "How much harm does this YouTube comment do?",
        "criteria": [
            "None: not harmful",
            "Mild: impolite or irritating",
            "Moderate: insulting, misleading, or plainly unwelcome",
            "Severe: hateful, threatening, or dangerous",
        ],
    },
}
QUESTION_SETS = {"en": QUESTIONS, "th": QUESTIONS_TH, "en2": QUESTIONS_EN2}


def api_key():
    return os.environ.get("TYPESAFE_API_KEY", "").strip()


def build_request(comment, video_title="", questions=QUESTIONS, model=MODEL):
    return {"state": {"video_title": video_title, "comment": comment}, "model": model, "questions": questions}


def ask_jev(body, key):
    """Send one request with the official SDK and return the raw JSON response."""
    # ponytail: one client per call (docs advise one per thread); reuse per thread if connection setup gets slow.
    with TypeSafeClient(api_key=key, model=body["model"], retry=RETRY) as client:
        result = client.system_one(body["state"], body["questions"])
    return result.raw_http_response.json()


def fetch_comments(url, n=50):
    opts = {
        "skip_download": True,
        "noplaylist": True,
        "getcomments": True,
        "quiet": True,
        "no_warnings": True,
        "extractor_args": {"youtube": {"max_comments": [str(n), str(n), "0", "0"], "comment_sort": ["top"]}},
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    comments = [c for c in info.get("comments") or [] if c.get("parent") == "root"][:n]
    return info, comments


def ask_many(rows, title, key, questions=QUESTIONS, model=MODEL, on_progress=None):
    """Ask JEV about each row's text (5 in parallel). Adds "response" or "error" to each row in place."""
    with ThreadPoolExecutor(5) as pool:
        futures = {pool.submit(ask_jev, build_request(r["text"], title, questions, model), key): r for r in rows}
        for done, f in enumerate(as_completed(futures), 1):
            row = futures[f]
            try:
                row["response"] = f.result()
            except TypeSafeAuthenticationError:
                pool.shutdown(cancel_futures=True)
                raise
            except Exception as e:
                row["error"] = str(e)
            if on_progress:
                on_progress(done, len(rows))


def save(record, folder):
    folder.mkdir(parents=True, exist_ok=True)
    record["fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record["model"] = next((r["response"]["model"] for r in record["comments"] if "response" in r), record.get("model", MODEL))
    (folder / f"{record['video_id']}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def comment_rows(comments):
    return [{"id": c["id"], "author": c.get("author"), "likes": c.get("like_count"), "text": c["text"]} for c in comments]


def analyze_video(url, n, key, on_progress=None):
    """Fetch top n comments, ask JEV about each, save to data/<video_id>.json."""
    info, comments = fetch_comments(url, n)
    title = info.get("title", "")
    rows = comment_rows(comments)
    ask_many(rows, title, key, on_progress=on_progress)
    return save({"video_id": info["id"], "title": title, "url": url, "comments": rows}, DATA_DIR)


def compare_thai(record, key, on_progress=None):
    """Ask the Thai questions about the same saved comments, pinned to the English run's model version."""
    rows = [{k: c.get(k) for k in ("id", "author", "likes", "text")} for c in record["comments"]]
    ask_many(rows, record["title"], key, QUESTIONS_TH, record["model"], on_progress)
    th = {"video_id": record["video_id"], "title": record["title"], "url": record["url"], "model": record["model"], "comments": rows}
    return save(th, THAI_DIR)


def run_experiment(urls, n, key, on_progress=None):
    """Section 11: fetch each video, ask all three question sets about the same comments, save to data/experiments/.
    Every run is pinned to the model version of the first answer."""
    videos = [(url, *fetch_comments(url, n)) for url in urls]
    total = len(QUESTION_SETS) * sum(len(comments) for _, _, comments in videos)
    done_before = 0
    model = None
    saved = []
    for url, info, comments in videos:
        title = info.get("title", "")
        runs = {}
        for name, questions in QUESTION_SETS.items():
            rows = comment_rows(comments)
            ask_many(rows, title, key, questions, model or MODEL,
                     on_progress and (lambda done, _: on_progress(done_before + done, total)))
            done_before += len(rows)
            model = model or next((r["response"]["model"] for r in rows if "response" in r), None)
            runs[name] = rows
        saved.append(save({"video_id": info["id"], "title": title, "url": url, "comments": runs["en"],
                           "th": runs["th"], "en2": runs["en2"]}, EXP_DIR))
    return saved


def load_experiments():
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(EXP_DIR.glob("*.json"))] if EXP_DIR.exists() else []


def load_all():
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(DATA_DIR.glob("*.json"))]


def load_thai(video_id):
    p = THAI_DIR / f"{video_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def severity_label(answer):
    # The docs don't fix the probability keys, so map the top level through legend back to our criteria.
    probs = answer.get("probabilities") or {}
    if not probs:
        return None
    top = max(probs, key=probs.get)
    desc = (answer.get("legend") or {}).get(top, top)
    if desc in SEVERITY:
        return desc
    for questions in QUESTION_SETS.values():
        levels = questions["severity"]["criteria"]
        if desc in levels:
            return SEVERITY[levels.index(desc)]
    return str(desc)


ANSWER_FIELDS = ["flag", "category", "category_confidence", "severity", "severity_score", "severity_confidence", "input_tokens"]


def flatten(record):
    for c in record["comments"]:
        row = {"id": c.get("id"), "video": record["title"], "author": c.get("author"), "likes": c.get("likes"), "text": c["text"], "error": c.get("error")}
        row.update(dict.fromkeys(ANSWER_FIELDS))
        resp = c.get("response")
        if resp:
            a = resp["answers"]
            row.update(
                flag=a["flag"]["noul"],  # noul has no confidence field; the probability itself shows how sure JEV is
                category=a["category"]["choice"],
                category_confidence=a["category"].get("confidence"),
                severity=severity_label(a["severity"]),
                severity_score=a["severity"].get("score"),
                severity_confidence=a["severity"].get("confidence"),
                input_tokens=resp.get("usage", {}).get("input_tokens", 0),
            )
        yield row


def cost(tokens, price_per_m=PRICE_PER_M):
    return tokens * price_per_m / 1_000_000

# let's in jev
if __name__ == "__main__":
    # Self-check against the documented request/response shapes (no API key needed).
    body = build_request("Buy followers at spam.example", "My trip to Chiang Mai")
    q = body["questions"]
    assert set(q["flag"]["criteria"]) == {"true", "false"}
    assert isinstance(q["category"]["criteria"], dict) and len(q["category"]["criteria"]) <= 255
    assert isinstance(q["severity"]["criteria"], list) and 2 <= len(q["severity"]["criteria"]) <= 10
    json.dumps(body)

    crit = QUESTIONS["severity"]["criteria"]
    fake = {
        "title": "t",
        "comments": [{
            "text": "x",
            "response": {
                "model": "jev-1.13.0",
                "answers": {
                    "flag": {"type": "noul", "noul": 0.91},
                    "category": {"type": "choice", "choice": "spam", "probabilities": {"spam": 0.8, "clean": 0.2}, "confidence": 0.8},
                    "severity": {"type": "score", "score": 1.2, "legend": {str(i): d for i, d in enumerate(crit)},
                                 "probabilities": {"0": 0.1, "1": 0.6, "2": 0.2, "3": 0.1}, "confidence": 0.6},
                },
                "usage": {"input_tokens": 300, "output_tokens": 0},
            },
        }, {"text": "y", "error": "HTTP 400: too long"}],
    }
    ok, failed = list(flatten(fake))
    assert ok["flag"] == 0.91 and ok["category"] == "spam" and ok["severity"] == "Mild" and ok["input_tokens"] == 300
    assert failed["error"] and failed["flag"] is None
    assert severity_label({"probabilities": {"Severe": 0.9, "None": 0.1}}) == "Severe"
    th_levels = QUESTIONS_TH["severity"]["criteria"]
    assert severity_label({"legend": {"3": th_levels[3]}, "probabilities": {"3": 0.7, "0": 0.3}}) == "Severe"
    assert QUESTIONS_TH["category"]["criteria"].keys() == CATEGORIES.keys()
    assert len(th_levels) == len(SEVERITY) and QUESTIONS_TH.keys() == QUESTIONS.keys()
    assert build_request("x", questions=QUESTIONS_TH, model="jev-1.13.0")["model"] == "jev-1.13.0"
    assert QUESTIONS_EN2["category"]["criteria"].keys() == CATEGORIES.keys() and QUESTIONS_EN2.keys() == QUESTIONS.keys()
    en2_levels = QUESTIONS_EN2["severity"]["criteria"]
    assert len(en2_levels) == len(SEVERITY) and severity_label({"legend": {"1": en2_levels[1]}, "probabilities": {"1": 0.9}}) == "Mild"
    assert abs(cost(300) - 0.0000126) < 1e-12
    print("ok")
