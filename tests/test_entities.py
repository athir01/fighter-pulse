from ingest.entities import find_fighter_mentions

ROSTER = [
    {"slug": "jon-jones", "full_name": "Jon Jones", "aliases": ["Bones Jones"]},
    {"slug": "tom-aspinall", "full_name": "Tom Aspinall", "aliases": []},
]


def test_finds_exact_name_mention():
    mentions = find_fighter_mentions("Jon Jones defends his title this weekend.", ROSTER)
    slugs = [m.fighter_slug for m in mentions]
    assert "jon-jones" in slugs
    assert "tom-aspinall" not in slugs


def test_finds_alias_mention():
    mentions = find_fighter_mentions("Bones Jones is back in the gym.", ROSTER)
    assert "jon-jones" in [m.fighter_slug for m in mentions]


def test_finds_multiple_fighters_in_one_article():
    mentions = find_fighter_mentions(
        "Jon Jones vs Tom Aspinall is finally official.", ROSTER
    )
    slugs = {m.fighter_slug for m in mentions}
    assert slugs == {"jon-jones", "tom-aspinall"}


def test_no_mentions_returns_empty():
    mentions = find_fighter_mentions("The weather today is sunny.", ROSTER)
    assert mentions == []
