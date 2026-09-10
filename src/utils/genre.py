"""Deterministic genre detection for creative fiction texts."""
import re
from typing import Optional


def detect_genre(text: str, default: str = "general") -> str:
    """
    Detect novel genre from source text sample using keyword heuristics
    and thematic markers across Japanese, Chinese, Korean, and English.
    Runs offline in <1ms.

    Supported output genres:
    - xianxia (Cultivation, Wuxia, Daoism, Sects)
    - isekai (Reincarnation, Fantasy World, Adventurer Guilds)
    - litrpg (Game System, Stats, Levels, Quests)
    - romance (Otome, Court Romance, Villainess, Aristocracy)
    - general (Default novel fiction)
    """
    if not text or not text.strip():
        return default

    sample = text[:15000].lower()

    # Score counters for each genre
    scores = {
        "xianxia": 0,
        "isekai": 0,
        "litrpg": 0,
        "romance": 0
    }

    # 1. Xianxia / Wuxia / Cultivation markers
    xianxia_markers = [
        "dantian", "meridian", "cultivator", "cultivation", "sect", "dao", "qi",
        "golden core", "nascent soul", "martial arts", "pill refining", "sword intent",
        "spiritual root", "tribulation", "immortal",
        "丹田", "经脉", "金丹", "元婴", "宗门", "修士", "剑气", "灵气", "修仙", "功法",
        "道友", "掌门", "武功", "内力", "筑基", "天劫", "真气", "真仙"
    ]
    for m in xianxia_markers:
        if m in sample:
            scores["xianxia"] += 2 if len(m) > 2 else 1

    # 2. LitRPG / Game System markers
    litrpg_markers = [
        "status window", "level up", "[system]", "quest completed", "hp:", "mp:",
        "skill points", "attribute points", "inventory slot", "dungeon floor",
        "ステータス", "レベルアップ", "スキルツリー", "クエスト", "経験値", "hp/mp",
        "[시스템]", "스탯창", "레벨업", "퀘스트"
    ]
    for m in litrpg_markers:
        if m in sample:
            scores["litrpg"] += 2

    # 3. Isekai / Fantasy markers
    isekai_markers = [
        "reincarnated", "transmigrated", "adventurer guild", "demon lord", "demon king",
        "otherworld", "magic circle", "summoning hero", "cheat skill",
        "転生", "異世界", "魔王", "ギルド", "冒険者", "勇者", "魔法陣", "召喚",
        "이세계", "마왕", "길드", "모험가", "빙의", "환생"
    ]
    for m in isekai_markers:
        if m in sample:
            scores["isekai"] += 2

    # 4. Romance / Otome / Court Intrigue markers
    romance_markers = [
        "villainess", "crown prince", "grand duke", "engagement broken", "ballroom",
        "fiancee", "lady-in-waiting", "high society",
        "悪役令嬢", "婚約破棄", "殿下", "公爵", "王太子", "舞踏会", "令嬢",
        "악역영애", "황태자", "공작", "약혼"
    ]
    for m in romance_markers:
        if m in sample:
            scores["romance"] += 2

    best_genre, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score >= 3:
        return best_genre

    return default
