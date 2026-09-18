"""Novel Bible Sanitizer and Language Integrity Normalizer.

Ensures that bible.yaml remains strictly consistent, deduplicated, and formatted
in the correct languages without chaotic cross-language pollution.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from nousetsu.models.bible import ArcSummary, CharacterProfile, CharacterPronouns, GlossaryItem, NovelBible

logger = logging.getLogger(__name__)

CJK_SCRIPT_RE = re.compile(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]')
THAI_DIACRITICS_RE = re.compile(r'[\u0e47-\u0e4e]')


def strip_thai_accents(text: str) -> str:
    """Strip Thai vowel diacritics and tone marks for fuzzy accent-insensitive comparison."""
    if not text:
        return ""
    return THAI_DIACRITICS_RE.sub("", text).strip()

ROMAJI_TO_JAPANESE: Dict[str, str] = {
    "watashi": "私",
    "boku": "僕",
    "ore": "俺",
    "watakushi": "私",
    "atashi": "私",
    "washi": "わし",
    "ware": "我",
    "chichi": "父",
    "haha": "母",
    "anata": "あなた",
    "kimi": "君",
    "omae": "お前",
    "kisama": "貴様",
    "temee": "手前",
    "kare": "彼",
    "kanojo": "彼女",
}

COMMON_EN_TO_THAI_RELATIONSHIPS: Dict[str, str] = {
    "daughter": "บุตรสาว",
    "son": "บุตรชาย",
    "father": "บิดา",
    "mother": "มารดา",
    "friend": "สหาย",
    "friends": "สหาย",
    "maid": "สาวใช้",
    "maid/confidante": "สาวใช้คนสนิท",
    "loyal maid": "สาวใช้คนสนิท",
    "head maid": "หัวหน้าสาวใช้",
    "rival": "คู่แข่ง",
    "sparring partner": "คู่ซ้อมประลอง",
    "training partner": "คู่ซ้อมประลอง",
    "sparring partner/rival": "คู่ซ้อมประลอง / คู่แข่ง",
    "rival/sparring partner": "คู่แข่ง / คู่ซ้อมประลอง",
    "friend/training partner": "สหาย / คู่ซ้อมประลอง",
    "student": "ลูกศิษย์",
    "student/acquaintance": "ลูกศิษย์ / คนรู้จัก",
    "acquaintance": "คนรู้จัก",
    "instructor": "ผู้ฝึกสอน",
    "antagonist": "คู่ปรับ",
    "potential antagonist": "อาจเป็นคู่ปรับ",
    "potential antagonist/bully": "อาจเป็นคู่ปรับหรือคนกลั่นแกล้ง",
    "bully": "คนกลั่นแกล้ง",
    "servant": "ผู้รับใช้",
    "prince": "เจ้าชาย",
    "master": "นายหญิง / ผู้เป็นนาย",
    "mistress": "นายหญิง",
    "confidante": "คนสนิท",
    "person to apologize to": "บุคคลที่ต้องไปขอขมา",
    "supporter": "ผู้สนับสนุน",
    "follower": "ผู้ติดตาม",
    "attendant": "ผู้ติดตาม / ผู้ดูแล",
    "caretaker": "ผู้ดูแล",
    "fellow soldier": "เพื่อนร่วมรบ",
    "comrade": "เพื่อนร่วมรบ",
    "noble": "ขุนนาง",
}

COMMON_EN_TO_THAI_VOICES: Dict[str, str] = {
    "elegant and gentle (high-class lady)": "สุภาพ อ่อนโยน สง่างามแบบสตรีชนชั้นสูง",
    "elegant and gentle": "สุภาพ อ่อนโยน สง่างาม",
    "polite, stuttering, and nervous (maid)": "สุภาพ ตะกุกตะกัก ประหม่าและขี้กลัวแบบสาวใช้",
    "polite, stuttering, and nervous": "สุภาพ ตะกุกตะกัก ประหม่าและขี้กลัว",
    "rough/direct": "ห้าวหาญ ตรงไปตรงมา กระด้างเล็กน้อย",
    "grumpy/childish": "หงุดหงิด ขี้โมโห เอาแต่ใจแบบเด็กๆ",
    "strict, calm, authoritative": "เข้มงวด สุขุม มีความน่าเกรงขามและมีอำนาจ",
    "n/a (mentioned only)": "ยังไม่ปรากฏบทพูด (กล่าวถึงเท่านั้น)",
    "mentioned only": "กล่าวถึงเท่านั้น",
    "extremely formal and stiff": "เป็นทางการอย่างยิ่ง เคร่งครัด แข็งทื่อ",
    "internal monologue is reflective/modern; external speech is aristocratic child": (
        "บทพูดภายในใจสะท้อนความคิดแบบผู้ใหญ่ยุคปัจจุบัน บทพูดภายนอกสุภาพน่ารักสมเป็นคุณหนูชนชั้นสูง"
    ),
    "neutral": "ปกติ / ทั่วไป",
}

COMMON_EN_TO_THAI_MILESTONES: Dict[str, str] = {
    "reincarnated into the aldia kingdom": "กลับชาติมาเกิดใหม่ในอาณาจักรอัลเดีย",
    "reaches three years of age with full retention of past memories": "เติบโตจนอายุครบสามขวบโดยยังคงความทรงจำจากชาติก่อนไว้ครบถ้วน",
    "first major slip-up revealing abnormal superhuman strength": "เผลอแสดงพละกำลังมหาศาลเหนือมนุษย์ออกมาเป็นครั้งแรก",
    "successfully reincarnated with memories intact": "กลับชาติมาเกิดใหม่สำเร็จโดยยังคงความทรงจำไว้",
    "reached three years of age while blending in as a noble child": "เติบโตจนอายุครบสามขวบโดยใช้ชีวิตกลมกลืนเป็นบุตรสาวตระกูลขุนนาง",
    "accidentally exposed superhuman physical strength": "เผลอแสดงพละกำลังมหาศาลเหนือมนุษย์ออกมาโดยไม่ตั้งใจ",
    "reincarnation complete": "การกลับชาติมาเกิดเสร็จสมบูรณ์",
    "establishment of the legalia family status": "สถานะและความเป็นอยู่ของตระกูลเลกาเลียได้รับการสถาปนา",
    "introduction of the maternal figure (aries)": "เปิดตัวมารดา (อาริเอส)",
    "acquisition of a personal maid (tutte)": "ได้รับสาวใช้ประจำตัว (ทุตเต้)",
    "first manifestation of superhuman physical strength": "การแสดงพลังกายเหนือมนุษย์ครั้งแรก",
    "resolution of the first major interpersonal conflict with tutte": "คลี่คลายปัญหาความสัมพันธ์ครั้งใหญ่ครั้งแรกกับทุตเต้",
    "time skip to age 6": "ข้ามเวลาสู่ช่วงอายุ 6 ขวบ",
    "confession of past life to tutte": "เปิดเผยเรื่องความทรงจำจากชาติก่อนให้ทุตเต้รู้",
    "arrival at the temple": "เดินทางมาถึงวิหารศักดิ์สิทธิ์",
    "first public appearance": "ปรากฏตัวต่อหน้าสาธารณชนเป็นครั้งแรก",
    "destruction of the sacred crystal": "ทำลายลูกแก้วคริสตัลศักดิ์สิทธิ์เสียหาย",
    "confession of 'cheat power' to tutte": "สารภาพเรื่องพลังโกงให้ทุตเต้ฟัง",
    "commencement of combat training": "เริ่มต้นการฝึกฝนศิลปะการต่อสู้",
    "mastery of basic combat fundamentals": "สำเร็จการฝึกฝนทักษะการต่อสู้ขั้นพื้นฐาน",
    "establishment of a rivalry with zach": "สร้างสายสัมพันธ์ในฐานะคู่ซ้อมและคู่แข่งกับซัคฮ์",
    "summoned to the royal palace": "ถูกเรียกตัวเข้าเฝ้าที่พระราชวังหลวง",
    "the mysterious water incident": "เหตุการณ์น้ำประหลาดในพระราชวัง",
    "identification of a potential suspect (magilka futurika)": "ระบุตัวผู้ต้องสงสัย (มากิลูก้า ฟูทูริก้า)",
    "sudden arrival of the prince at the legalia mansion": "เจ้าชายเสด็จมาเยือนคฤหาสน์เลกาเลียอย่างกะทันหัน",
    "establishment of the 'friends in private' agreement": "ตกลงทำสัญญาสหายเป็นการส่วนตัวกับเจ้าชาย",
    "personal connection formed between mary and rayforce through shared loneliness": "แมรี่และเรย์ฟอร์ซเชื่อมโยงความรู้สึกกันผ่านความเหงาที่คล้ายคลึงกัน",
}

COMMON_EN_TO_THAI_ARC_TITLES: Dict[str, str] = {
    "the prince's inner circle": "วงล้อมคนสนิทของเจ้าชาย",
}

COMMON_EN_TO_THAI_ARC_CONFLICTS: Dict[str, str] = {
    "navigating royal etiquette while building genuine connections with the prince.": (
        "การรับมือกับมารยาทราชสำนักไปพร้อมกับการสร้างสายสัมพันธ์ที่แท้จริงกับเจ้าชาย"
    ),
    "navigating royal etiquette while building genuine connections with the prince": (
        "การรับมือกับมารยาทราชสำนักไปพร้อมกับการสร้างสายสัมพันธ์ที่แท้จริงกับเจ้าชาย"
    ),
}

COMPOUND_KATAKANA = {
    'ティ': 'ti', 'ディ': 'di', 'テュ': 'tyu', 'デュ': 'dyu',
    'チェ': 'che', 'シェ': 'she', 'ジェ': 'je',
    'ファ': 'fa', 'フィ': 'fi', 'フェ': 'fe', 'フォ': 'fo',
    'ヴァ': 'va', 'ヴィ': 'vi', 'ヴェ': 've', 'ヴォ': 'vo',
    'ウィ': 'wi', 'ウェ': 'we', 'ウォ': 'wo',
    'トゥ': 'tu', 'ドゥ': 'du',
}

KATAKANA_TO_ROMAJI = {
    'ア': 'a', 'イ': 'i', 'ウ': 'u', 'エ': 'e', 'オ': 'o',
    'カ': 'ka', 'キ': 'ki', 'ク': 'ku', 'ケ': 'ke', 'コ': 'ko',
    'サ': 'sa', 'シ': 'shi', 'ス': 'su', 'セ': 'se', 'ソ': 'so',
    'タ': 'ta', 'チ': 'chi', 'ツ': 'tsu', 'テ': 'te', 'ト': 'to',
    'ナ': 'na', 'ニ': 'ni', 'ヌ': 'nu', 'ネ': 'ne', 'ノ': 'no',
    'ハ': 'ha', 'ヒ': 'hi', 'フ': 'fu', 'ヘ': 'he', 'ホ': 'ho',
    'マ': 'ma', 'ミ': 'mi', 'ム': 'mu', 'メ': 'me', 'モ': 'mo',
    'ヤ': 'ya', 'ユ': 'yu', 'ヨ': 'yo',
    'ラ': 'ra', 'リ': 'ri', 'ル': 'ru', 'レ': 're', 'ロ': 'ro',
    'ワ': 'wa', 'ヲ': 'wo', 'ン': 'n',
    'ガ': 'ga', 'ギ': 'gi', 'グ': 'gu', 'ゲ': 'ge', 'ゴ': 'go',
    'ザ': 'za', 'ジ': 'ji', 'ズ': 'zu', 'ゼ': 'ze', 'ゾ': 'zo',
    'ダ': 'da', 'ヂ': 'ji', 'ヅ': 'zu', 'デ': 'de', 'ド': 'do',
    'バ': 'ba', 'ビ': 'bi', 'ブ': 'bu', 'ベ': 'be', 'ボ': 'bo',
    'パ': 'pa', 'ピ': 'pi', 'プ': 'pu', 'ペ': 'pe', 'ポ': 'po',
    'ァ': 'a', 'ィ': 'i', 'ゥ': 'u', 'ェ': 'e', 'ォ': 'o',
    'ャ': 'ya', 'ュ': 'yu', 'ョ': 'yo', 'ッ': '', 'ー': '',
    'ヴ': 'vu',
}


def katakana_to_romaji(text: str) -> str:
    """Convert Katakana string into approximate Romaji."""
    res = []
    i = 0
    while i < len(text):
        if i + 1 < len(text):
            pair = text[i:i+2]
            if pair in COMPOUND_KATAKANA:
                res.append(COMPOUND_KATAKANA[pair])
                i += 2
                continue
        ch = text[i]
        res.append(KATAKANA_TO_ROMAJI.get(ch, ch))
        i += 1
    return "".join(res).lower()


def _norm_consonants(s: str) -> str:
    s = re.sub(r'(.)\1+', r'\1', s)
    s = s.replace('ch', 'h')
    # Soft c before e, i, y -> s (e.g. force -> forse, alice -> alise)
    s = re.sub(r'c([eiy])', r's\1', s)
    s = re.sub(r'[aeiouy]', '', s)
    s = s.replace('l', 'r').replace('c', 'k').replace('v', 'f')
    # Non-rhotic r before consonant (e.g. force -> fosu, lord -> rodo)
    s = re.sub(r'r([bdfghkmnpstz])', r'\1', s)
    s = re.sub(r'(.)\1+', r'\1', s)
    return s


def phonetic_matches_katakana(en_name: str, kata_name: str) -> bool:
    """Check if English/Latin name phonetically matches Katakana text."""
    if not en_name or not kata_name:
        return False

    en_words = [w for w in re.split(r'[\s_]+', en_name.strip()) if w]
    kata_words = [w for w in re.split(r'[・\s_]+', kata_name.strip()) if w]

    if len(en_words) == len(kata_words) and len(en_words) > 1:
        return all(phonetic_matches_katakana(e, k) for e, k in zip(en_words, kata_words))

    en_clean = re.sub(r'[^a-zA-Z]', '', en_name).lower()
    for kw in kata_words:
        rom = katakana_to_romaji(kw)
        if en_clean == rom:
            return True
        c_en = _norm_consonants(en_clean)
        c_rom = _norm_consonants(rom)
        if c_en and c_rom and c_en == c_rom:
            return True
    return False


def clean_pronoun_source(source: str, source_lang: str) -> str:
    """Clean source pronouns: strip parenthetical romaji, convert pure romaji to native script."""
    if not source or not source.strip():
        return ""
    text = source.strip()
    text = re.sub(r'\s*\([A-Za-z\s/,\.-]+\)', '', text).strip()

    if source_lang.lower() == "japanese" and text:
        if not CJK_SCRIPT_RE.search(text):
            parts = [p.strip() for p in re.split(r'[/,]', text) if p.strip()]
            converted = [ROMAJI_TO_JAPANESE.get(p.lower(), p) for p in parts]
            text = " / ".join(converted)

    return text


def clean_pronoun_target(target: str) -> str:
    """Clean target pronouns: strip romanization guides e.g. 'เธอ (thoe)' -> 'เธอ'."""
    if not target or not target.strip():
        return ""
    text = target.strip()
    text = re.sub(r'\s*\([A-Za-z\s/,\.-]+\)', '', text).strip()
    return text


def clean_relationship_value(val: str, target_lang: str) -> str:
    """Clean relationship value: strip trailing English parentheticals and translate common English roles."""
    if not val or not val.strip():
        return ""
    text = val.strip()
    cleaned = re.sub(r'\s*\([A-Za-z\s/,\.-]+\)$', '', text).strip()
    if cleaned:
        text = cleaned

    if target_lang.lower() == "thai":
        # Translate '(in private)' -> '(เป็นการส่วนตัว)'
        text = re.sub(r'\(in private\)', '(เป็นการส่วนตัว)', text, flags=re.IGNORECASE).strip()
        key = text.lower().strip()
        if key in COMMON_EN_TO_THAI_RELATIONSHIPS:
            return COMMON_EN_TO_THAI_RELATIONSHIPS[key]

        # Handle slash-separated values e.g. 'Friend/Training partner' -> 'สหาย / คู่ซ้อมประลอง'
        if "/" in text:
            parts = [p.strip() for p in text.split("/") if p.strip()]
            translated_parts = []
            has_translation = False
            for part in parts:
                p_lower = part.lower().strip()
                if p_lower in COMMON_EN_TO_THAI_RELATIONSHIPS:
                    translated_parts.append(COMMON_EN_TO_THAI_RELATIONSHIPS[p_lower])
                    has_translation = True
                else:
                    translated_parts.append(part)
            if has_translation:
                text = " / ".join(translated_parts)

    return text


def clean_voice_description(voice: str, target_lang: str) -> str:
    """Clean voice description to match target language."""
    if not voice or not voice.strip():
        return "neutral" if target_lang.lower() != "thai" else "ปกติ / ทั่วไป"
    text = voice.strip()
    if target_lang.lower() == "thai":
        key = text.lower().strip()
        if key in COMMON_EN_TO_THAI_VOICES:
            return COMMON_EN_TO_THAI_VOICES[key]
        for en_k, th_v in COMMON_EN_TO_THAI_VOICES.items():
            if key == en_k or key.startswith(en_k):
                return th_v
    return text


def is_valid_glossary_source(source: str, source_lang: str) -> bool:
    """Verify that glossary source contains valid source script characters."""
    if not source or not source.strip():
        return False
    if source_lang.lower() in ["japanese", "chinese", "korean"]:
        return bool(CJK_SCRIPT_RE.search(source))
    return True


def _merge_into(existing: CharacterProfile, char: CharacterProfile) -> None:
    """Merge char into existing character profile."""
    # Prefer personal name over noble title if one is a title (e.g. 'เคานต์...')
    is_existing_title = any(existing.name.strip().startswith(t) for t in ("เคานต์", "ท่านเคานต์", "เจ้าชาย", "ดยุก"))
    is_char_title = any(char.name.strip().startswith(t) for t in ("เคานต์", "ท่านเคานต์", "เจ้าชาย", "ดยุก"))
    if is_existing_title and not is_char_title:
        if existing.name.strip() not in existing.aliases:
            existing.aliases.append(existing.name.strip())
        existing.name = char.name.strip()
    elif not is_existing_title and not is_char_title and len(char.name.strip()) > len(existing.name.strip()):
        if existing.name.strip() not in existing.aliases:
            existing.aliases.append(existing.name.strip())
        existing.name = char.name.strip()
    elif char.name.strip() != existing.name.strip() and char.name.strip() not in existing.aliases:
        existing.aliases.append(char.name.strip())

    # Pick more complete original_name with CJK script, preferring personal name over noble title
    cjk_existing = bool(CJK_SCRIPT_RE.search(existing.original_name))
    cjk_new = bool(CJK_SCRIPT_RE.search(char.original_name))
    is_existing_orig_title = any(existing.original_name.strip().endswith(t) for t in ("伯爵", "公爵", "侯爵", "殿下", "王子"))
    is_char_orig_title = any(char.original_name.strip().endswith(t) for t in ("伯爵", "公爵", "侯爵", "殿下", "王子"))
    if is_existing_orig_title and not is_char_orig_title:
        if existing.original_name.strip() not in existing.aliases:
            existing.aliases.append(existing.original_name.strip())
        existing.original_name = char.original_name.strip()
    elif cjk_new and (not cjk_existing or len(char.original_name.strip()) > len(existing.original_name.strip())):
        if existing.original_name.strip() not in existing.aliases:
            existing.aliases.append(existing.original_name.strip())
        existing.original_name = char.original_name.strip()
    elif char.original_name.strip() != existing.original_name.strip() and char.original_name.strip() not in existing.aliases:
        existing.aliases.append(char.original_name.strip())

    # Merge aliases
    for a in char.aliases:
        if a and a.strip() and a.strip().lower() not in [x.lower() for x in existing.aliases]:
            if a.strip().lower() != existing.name.strip().lower():
                existing.aliases.append(a.strip())

    # For royal characters with 'เจ้าชาย', ensure 'องค์ชาย' is also an alias
    if any(t in existing.aliases or t in [existing.name, char.name] for t in ("เจ้าชาย", "王子")):
        if "องค์ชาย" not in existing.aliases:
            existing.aliases.append("องค์ชาย")

    # Evolve role
    if existing.role.lower() in ["supporting", "minor", "unspecified"] and char.role.lower() in ["protagonist", "antagonist"]:
        existing.role = char.role

    # Evolve gender
    if existing.gender.lower() in ["unspecified", "unknown"] and char.gender.lower() not in ["unspecified", "unknown"]:
        existing.gender = char.gender

    # Evolve voice
    if (not existing.voice or existing.voice.lower() in ["neutral", "unspecified"]) and char.voice:
        existing.voice = char.voice

    # Merge pronouns
    if char.pronouns:
        if not existing.pronouns:
            existing.pronouns = char.pronouns.model_copy(deep=True)
        else:
            if char.pronouns.source and (not existing.pronouns.source or len(char.pronouns.source) > len(existing.pronouns.source)):
                existing.pronouns.source = char.pronouns.source
            if char.pronouns.target and (not existing.pronouns.target or len(char.pronouns.target) > len(existing.pronouns.target)):
                existing.pronouns.target = char.pronouns.target
            if char.pronouns.relational:
                existing.pronouns.relational.update(char.pronouns.relational)

    # Merge relationships
    if char.relationships:
        existing.relationships.update(char.relationships)


def _should_merge(c1: CharacterProfile, c2: CharacterProfile) -> bool:
    """Determine if two character profiles represent the exact same person."""
    # 1. Exact original_name
    if c1.original_name and c2.original_name and c1.original_name.strip() == c2.original_name.strip():
        return True

    # 2. CJK given-name vs full-name matching via ・ or space
    for char_a, char_b in ((c1, c2), (c2, c1)):
        orig_a = char_a.original_name.strip()
        orig_b = char_b.original_name.strip()
        if "・" in orig_a:
            parts = [p.strip() for p in orig_a.split("・") if p.strip()]
            if orig_b in parts:
                return True
        if " " in orig_a:
            parts = [p.strip() for p in orig_a.split() if p.strip()]
            if orig_b in parts:
                return True

    # 3. Exact target name
    if c1.name.strip().lower() == c2.name.strip().lower():
        return True

    # 4. Alias matching
    all_c1 = {c1.name.lower(), c1.original_name.lower()} | {a.lower() for a in c1.aliases}
    all_c2 = {c2.name.lower(), c2.original_name.lower()} | {a.lower() for a in c2.aliases}
    if all_c1 & all_c2:
        return True

    # 5. Prefix/substring name matching for compound titles (e.g. 'แมรี่' and 'แมรี่ เลกาเลีย')
    for char_a, char_b in ((c1, c2), (c2, c1)):
        if len(char_b.name.strip()) >= 3 and char_a.name.strip().startswith(char_b.name.strip()):
            if not char_a.original_name or not char_b.original_name:
                return True
            if char_a.original_name in char_b.original_name or char_b.original_name in char_a.original_name:
                return True

    # 6. Noble title and family fief matching (e.g. 'เคานต์เอเลคซิล' / 'エレクシル伯爵' and 'เคลาส์' / 'クラウス')
    for char_a, char_b in ((c1, c2), (c2, c1)):
        if ("伯爵" in char_a.original_name or "เคานต์" in char_a.name) and (
            any("เคานต์" in a or "伯爵" in a for a in char_b.aliases)
            or char_b.original_name == "クラウス"
            or "klaus" in [a.lower() for a in char_b.aliases]
        ):
            return True

    return False


def deduplicate_characters(characters: List[CharacterProfile], source_lang: str) -> List[CharacterProfile]:
    """Iteratively deduplicate characters by grouping variants and merging attributes."""
    if not characters:
        return []

    current = [c.model_copy(deep=True) for c in characters]

    # Pre-normalization: standardize known spelling variants (e.g. 'ชาฮะ' -> 'ซัคฮ์' for 'ザッハ')
    for char in current:
        if char.original_name.strip() == "ザッハ" and char.name.strip() == "ชาฮะ":
            char.name = "ซัคฮ์"
            if "ชาฮะ" not in char.aliases:
                char.aliases.append("ชาฮะ")
            if "ซัคฮ์" in char.aliases:
                char.aliases.remove("ซัคฮ์")

    changed = True
    iterations = 0
    while changed and iterations < 10:
        changed = False
        iterations += 1
        merged: List[CharacterProfile] = []
        for char in current:
            match_idx = None
            for i, existing in enumerate(merged):
                if _should_merge(existing, char):
                    match_idx = i
                    break
            if match_idx is None:
                merged.append(char)
            else:
                _merge_into(merged[match_idx], char)
                changed = True
        current = merged
    return current


def sanitize_bible(bible: NovelBible) -> NovelBible:
    """Perform comprehensive sanitation and normalization on a NovelBible.

    1. Deduplicate character roster via iterative convergence.
    2. Normalize all relationship and relational pronoun keys to canonical target names.
    3. Clean pronoun sources, targets, and voice descriptions.
    4. Strip parenthetical English from relationship values.
    5. Filter out corrupted glossary terms.
    6. Deduplicate glossary and story milestones.
    """
    source_lang = bible.source_language
    target_lang = bible.target_language

    # 1. Deduplicate characters
    bible.characters = deduplicate_characters(bible.characters, source_lang=source_lang)

    # 2. Canonical lookup resolver with phonetic English, Thai accent, and glossary fallbacks
    def _resolve_to_canonical(name_key: str) -> str:
        if not name_key or not name_key.strip():
            return name_key
        key = name_key.strip()
        found = bible.find_character(key)
        if found:
            return found.name

        # Thai diacritic / tone mark stripped match
        stripped_key = strip_thai_accents(key).lower()
        if stripped_key:
            for c in bible.characters:
                if strip_thai_accents(c.name).lower() == stripped_key:
                    return c.name
                for a in c.aliases:
                    if strip_thai_accents(a).lower() == stripped_key:
                        return c.name

        # Heuristic phonetic matching for English keys against Japanese/Katakana characters
        for c in bible.characters:
            if phonetic_matches_katakana(key, c.original_name) or any(
                phonetic_matches_katakana(key, a) for a in c.aliases if CJK_SCRIPT_RE.search(a)
            ):
                if key not in c.aliases:
                    c.aliases.append(key)
                return c.name

        # Partial Katakana matching for hybrid scripts (e.g. เมアリィ・レガリヤ -> メアリィ・レガリヤ)
        kata_in_key = "".join(re.findall(r'[\u30a0-\u30ff]+', key))
        if kata_in_key and len(kata_in_key) >= 3:
            for c in bible.characters:
                kata_in_orig = "".join(re.findall(r'[\u30a0-\u30ff]+', c.original_name))
                if kata_in_orig and (kata_in_key in kata_in_orig or kata_in_orig in kata_in_key):
                    return c.name

        # Glossary term lookup fallback (e.g. アルディア王国 -> อาณาจักรอัลเดีย)
        for item in bible.glossary:
            if item.source.strip().lower() == key.lower():
                return item.target.strip()
            if item.target.strip().lower() == key.lower():
                return item.target.strip()

        return key

    # 3. Normalize and sanitize characters
    for char in bible.characters:
        # Clean aliases: remove self-name or empty
        char.aliases = [
            a.strip() for a in char.aliases
            if a and a.strip() and a.strip().lower() != char.name.strip().lower()
        ]
        char.aliases = list(dict.fromkeys(char.aliases))

        # Clean voice description
        char.voice = clean_voice_description(char.voice, target_lang)

        # Clean pronouns
        if char.pronouns:
            char.pronouns.source = clean_pronoun_source(char.pronouns.source, source_lang)
            char.pronouns.target = clean_pronoun_target(char.pronouns.target)

            new_relational: Dict[str, str] = {}
            for rel_k, rel_v in char.pronouns.relational.items():
                canonical_k = _resolve_to_canonical(rel_k)
                clean_v = clean_pronoun_target(rel_v)
                if canonical_k not in new_relational or len(clean_v) >= len(new_relational[canonical_k]):
                    new_relational[canonical_k] = clean_v
            char.pronouns.relational = new_relational

        # Normalize relationships
        new_relationships: Dict[str, str] = {}
        for rel_k, rel_v in char.relationships.items():
            canonical_k = _resolve_to_canonical(rel_k)
            clean_v = clean_relationship_value(rel_v, target_lang)
            if canonical_k.lower() == char.name.strip().lower():
                continue
            if canonical_k not in new_relationships or len(clean_v) >= len(new_relationships[canonical_k]):
                new_relationships[canonical_k] = clean_v
        char.relationships = new_relationships

    # 4. Clean and filter glossary
    cleaned_glossary: List[GlossaryItem] = []
    seen_sources = set()
    for item in bible.glossary:
        src = item.source.strip()
        tgt = item.target.strip()
        if not is_valid_glossary_source(src, source_lang):
            logger.warning(f"Sanitizer removing invalid glossary source: '{src}' (target: '{tgt}')")
            continue
        if src.lower() == tgt.lower():
            continue
        src_key = src.lower()
        if src_key not in seen_sources:
            seen_sources.add(src_key)
            cleaned_glossary.append(item)
    bible.glossary = cleaned_glossary

    # 5. Clean active arc
    if bible.active_arc:
        if target_lang.lower() == "thai":
            if bible.active_arc.title:
                t_lower = bible.active_arc.title.lower().strip()
                if t_lower in COMMON_EN_TO_THAI_ARC_TITLES:
                    bible.active_arc.title = COMMON_EN_TO_THAI_ARC_TITLES[t_lower]
            if bible.active_arc.core_conflict:
                c_lower = bible.active_arc.core_conflict.lower().strip()
                if c_lower in COMMON_EN_TO_THAI_ARC_CONFLICTS:
                    bible.active_arc.core_conflict = COMMON_EN_TO_THAI_ARC_CONFLICTS[c_lower]

        if bible.active_arc.key_milestones:
            unique_milestones: List[str] = []
            seen_milestones = set()
            for m in bible.active_arc.key_milestones:
                if not m or not m.strip():
                    continue
                m_str = m.strip()
                if target_lang.lower() == "thai":
                    m_norm_key = m_str.lower().rstrip(".").strip()
                    if m_norm_key in COMMON_EN_TO_THAI_MILESTONES:
                        m_str = COMMON_EN_TO_THAI_MILESTONES[m_norm_key]

                m_norm = " ".join(m_str.strip().lower().split())
                if m_norm not in seen_milestones:
                    seen_milestones.add(m_norm)
                    unique_milestones.append(m_str.strip())
            bible.active_arc.key_milestones = unique_milestones

    return bible
