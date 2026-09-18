"""Unit tests for Novel Bible Sanitizer and Language Integrity Normalizer."""
import pytest
from nousetsu.models.bible import ArcSummary, CharacterProfile, CharacterPronouns, GlossaryItem, NovelBible
from nousetsu.storage.bible_sanitizer import (
    clean_pronoun_source,
    clean_pronoun_target,
    clean_relationship_value,
    clean_voice_description,
    deduplicate_characters,
    is_valid_glossary_source,
    sanitize_bible,
)


class TestBibleSanitizer:
    def test_clean_pronoun_source_romaji_conversion(self):
        assert clean_pronoun_source("watashi / boku", source_lang="Japanese") == "私 / 僕"
        assert clean_pronoun_source("俺 (ore)", source_lang="Japanese") == "俺"
        assert clean_pronoun_source("私", source_lang="Japanese") == "私"

    def test_clean_pronoun_target_strip_parentheses(self):
        assert clean_pronoun_target("เธอ (thoe) / คุณหนู (khun nu)") == "เธอ / คุณหนู"
        assert clean_pronoun_target("ดิฉัน (dichan)") == "ดิฉัน"
        assert clean_pronoun_target("ผม/ฉัน (as child)") == "ผม/ฉัน"

    def test_clean_relationship_value(self):
        assert clean_relationship_value("ลูกสาว (daughter)", target_lang="Thai") == "ลูกสาว"
        assert clean_relationship_value("daughter", target_lang="Thai") == "บุตรสาว"
        assert clean_relationship_value("sparring partner/rival", target_lang="Thai") == "คู่ซ้อมประลอง / คู่แข่ง"

    def test_is_valid_glossary_source(self):
        assert is_valid_glossary_source("王宮", source_lang="Japanese") is True
        assert is_valid_glossary_source("ปราสาทหลวง", source_lang="Japanese") is False
        assert is_valid_glossary_source("English Term", source_lang="English") is True

    def test_deduplicate_characters_by_given_name_and_original(self):
        c1 = CharacterProfile(
            name="แมรี่ เลกาเลีย",
            original_name="メアリィ・レガリヤ",
            aliases=["คุณหนูแมรี่"],
            role="protagonist",
            gender="female",
        )
        c2 = CharacterProfile(
            name="แมรี่",
            original_name="メアリィ",
            aliases=["คุณหนู"],
            role="protagonist",
            gender="female",
        )
        merged = deduplicate_characters([c1, c2], source_lang="Japanese")
        assert len(merged) == 1
        res = merged[0]
        assert res.name == "แมรี่ เลกาเลีย"
        assert res.original_name == "メアリィ・レガリヤ"
        assert "แมรี่" in res.aliases
        assert "คุณหนู" in res.aliases
        assert "คุณหนูแมรี่" in res.aliases

    def test_sanitize_bible_normalizes_relationship_keys(self):
        bible = NovelBible(
            title="Test",
            source_language="Japanese",
            target_language="Thai",
            characters=[
                CharacterProfile(
                    name="แมรี่ เลกาเลีย",
                    original_name="メアリィ・レガリヤ",
                    aliases=["Mary Legalia", "Mary"],
                    relationships={
                        "Ferid Legalia": "ลูกสาว (daughter)",
                        "Klaus": "student",
                        "Zach": "rival",
                    },
                    pronouns=CharacterPronouns(
                        source="watashi / boku",
                        target="ฉัน (chan)",
                        relational={
                            "Ferid Legalia": "ท่านพ่อ (than pho)",
                            "Zach": "นาย (nai)",
                        }
                    )
                ),
                CharacterProfile(
                    name="เฟอร์ดิด เลกาเลีย",
                    original_name="フェルディッド・レガリヤ",
                    aliases=["Ferid Legalia", "Ferdid"],
                    relationships={"Mary Legalia": "father"},
                ),
                CharacterProfile(
                    name="เคลาส์",
                    original_name="クラウス",
                    aliases=["Klaus"],
                    relationships={},
                ),
                CharacterProfile(
                    name="ซัคฮ์",
                    original_name="ザッハ",
                    aliases=["Zach"],
                    relationships={},
                ),
            ],
            glossary=[
                GlossaryItem(source="王宮", target="พระราชวัง", category="location"),
                GlossaryItem(source="ปราสาทหลวง", target="ปราสาทหลวง", category="location"),  # Corrupt
            ],
            active_arc=ArcSummary(
                arc_id="arc_0001",
                arc_num=1,
                title="Test Arc",
                synopsis="Synopsis",
                core_conflict="Conflict",
                key_milestones=[
                    "Reincarnation complete",
                    "  reincarnation complete  ",  # Duplicate
                    "Second milestone",
                ]
            )
        )

        sanitized = sanitize_bible(bible)

        # Characters deduplicated & normalized
        mary = sanitized.find_character("แมรี่ เลกาเลีย")
        assert mary is not None
        assert "เฟอร์ดิด เลกาเลีย" in mary.relationships
        assert "Ferid Legalia" not in mary.relationships
        assert mary.relationships["เฟอร์ดิด เลกาเลีย"] == "ลูกสาว"

        assert "เคลาส์" in mary.relationships
        assert mary.relationships["เคลาส์"] == "ลูกศิษย์"

        assert "ซัคฮ์" in mary.relationships
        assert mary.relationships["ซัคฮ์"] == "คู่แข่ง"

        # Pronouns cleaned
        assert mary.pronouns.source == "私 / 僕"
        assert mary.pronouns.target == "ฉัน"
        assert "เฟอร์ดิด เลกาเลีย" in mary.pronouns.relational
        assert mary.pronouns.relational["เฟอร์ดิด เลกาเลีย"] == "ท่านพ่อ"
        assert mary.pronouns.relational["ซัคฮ์"] == "นาย"

        # Father's relationship normalized
        father = sanitized.find_character("เฟอร์ดิด เลกาเลีย")
        assert "แมรี่ เลกาเลีย" in father.relationships
        assert father.relationships["แมรี่ เลกาเลีย"] == "บิดา"

        # Glossary filtered
        assert len(sanitized.glossary) == 1
        assert sanitized.glossary[0].source == "王宮"

        # Milestones deduplicated & translated
        assert len(sanitized.active_arc.key_milestones) == 2
        assert "การกลับชาติมาเกิดเสร็จสมบูรณ์" in sanitized.active_arc.key_milestones

    def test_clean_voice_description(self):
        assert clean_voice_description("Elegant and gentle (High-class lady)", "Thai") == "สุภาพ อ่อนโยน สง่างามแบบสตรีชนชั้นสูง"
        assert clean_voice_description("Rough/Direct", "Thai") == "ห้าวหาญ ตรงไปตรงมา กระด้างเล็กน้อย"
        assert clean_voice_description("Strict, calm, authoritative", "Thai") == "เข้มงวด สุขุม มีความน่าเกรงขามและมีอำนาจ"
        assert clean_voice_description("neutral", "Thai") == "ปกติ / ทั่วไป"

    def test_strip_thai_accents(self):
        from nousetsu.storage.bible_sanitizer import strip_thai_accents
        assert strip_thai_accents("แมรี่ เลกาเลีย") == "แมรี เลกาเลีย"
        assert strip_thai_accents("ซัคฮ์") == "ซัคฮ"

    def test_title_and_personal_name_merging(self):
        c_title = CharacterProfile(
            name="เคานต์เอเลคซิล",
            original_name="エレクシル伯爵",
            role="supporting",
            gender="male",
        )
        c_name = CharacterProfile(
            name="เคลาส์",
            original_name="クラウス",
            aliases=["ท่านเคานต์"],
            role="supporting",
            gender="male",
        )
        merged = deduplicate_characters([c_title, c_name], source_lang="Japanese")
        assert len(merged) == 1
        res = merged[0]
        # Should prefer personal name over noble title
        assert res.name == "เคลาส์"
        assert res.original_name == "クラウス"
        assert "เคานต์เอเลคซิล" in res.aliases
        assert "エレクシル伯爵" in res.aliases
