"""Unit tests for unified structured character roster formatter."""
import pytest
from nousetsu.models.bible import CharacterProfile, CharacterPronouns
from nousetsu.prompts.character_formatter import format_character_roster


def test_format_character_roster_empty():
    assert format_character_roster([]) == "No explicit character cards registered."
    assert format_character_roster([], empty_fallback="None") == "None"


def test_format_character_roster_drafter():
    c1 = CharacterProfile(
        name="Mary Regalia",
        original_name="メアリィ・レガリヤ",
        gender="female",
        role="protagonist",
        voice="Polite, adult wit, fast thinker",
        source_pronoun="私 / 僕",
        target_pronoun="ฉัน / แมรี่",
        aliases=["Lady Mary", "Mary"],
        relationships={"Tutte": "Maid and companion"}
    )
    c1.pronouns.relational = {"Tutte": "เธอ", "Rayforce": "เรย์ฟอร์ซ... คะ"}

    c2 = CharacterProfile(
        name="Tutte",
        original_name="テュッテ",
        gender="female",
        role="supporting",
        voice="Hesitant, shy maid",
        source_pronoun="私",
        target_pronoun="ดิฉัน",
    )
    c2.pronouns.relational = {"Mary Regalia": "คุณหนู"}

    result = format_character_roster([c1, c2], agent_role="drafter")

    # Check c1 formatting
    assert "- **Mary Regalia** (メアリィ・レガリヤ | female | protagonist)" in result
    assert "  * Voice & Tone: Polite, adult wit, fast thinker" in result
    assert "  * Pronouns (Zero-Anaphora): [Source: 私 / 僕] -> [Target: ฉัน / แมรี่]" in result
    assert "  * Relational Address:" in result
    assert "    - with Tutte: เธอ" in result
    assert "  * Relationships: Tutte (Maid and companion)" in result
    assert "  * Aliases: Lady Mary, Mary" in result

    # Check c2 formatting
    assert "- **Tutte** (テュッテ | female | supporting)" in result
    assert "  * Voice & Tone: Hesitant, shy maid" in result
    assert "  * Pronouns (Zero-Anaphora): [Source: 私] -> [Target: ดิฉัน]" in result
    assert "    - with Mary Regalia: คุณหนู" in result


def test_format_character_roster_critic():
    c = CharacterProfile(
        name="Ifia",
        original_name="イフィア",
        gender="female",
        role="protagonist",
        source_pronoun="she/her, I",
        target_pronoun="เธอ, ฉัน"
    )
    c.pronouns.relational = {"Amelia": "หนู/พี่"}

    c2 = CharacterProfile(
        name="Amelia",
        original_name="Amelia",
        gender="female",
        role="protagonist"
    )

    result = format_character_roster([c], context_characters=[c, c2], agent_role="critic")
    assert "- **Ifia** (イフィア | female | protagonist)" in result
    assert "  * Expected Pronouns: [Source: she/her, I] -> [Target: เธอ, ฉัน]" in result
    assert "  * Relational Address Rules:" in result
    assert "    - with Amelia: หนู/พี่" in result


def test_format_character_roster_extractor():
    c = CharacterProfile(
        name="Ferid Legalia",
        original_name="フェルディッド・レガリヤ",
        gender="male",
        role="supporting",
        voice="Stern, authoritative noble",
        source_pronoun="俺",
        target_pronoun="ผม",
        aliases=["Duke Legalia"]
    )
    result = format_character_roster([c], agent_role="extractor")

    # Extractor uses compact header
    assert "- **Ferid Legalia** (フェルディッド・レガリヤ | supporting)" in result
    assert "  * Voice: Stern, authoritative noble" in result
    assert "  * Pronouns: [Source: 俺] -> [Target: ผม]" in result
    assert "  * Aliases: Duke Legalia" in result
    # Extractor does not include relational address rules
    assert "Relational Address" not in result


def test_format_character_roster_polisher():
    c = CharacterProfile(
        name="Hero",
        original_name="勇者",
        gender="male",
        role="protagonist",
        voice="Resolute, heroic",
        source_pronoun="俺",
        target_pronoun="ข้า"
    )
    result = format_character_roster([c], agent_role="polisher")
    assert "- **Hero** (勇者 | male | protagonist)" in result
    assert "  * Voice & Tone: Resolute, heroic" in result
    assert "  * Pronouns (Zero-Anaphora): [Source: 俺] -> [Target: ข้า]" in result
