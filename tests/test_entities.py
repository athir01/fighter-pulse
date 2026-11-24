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


def test_does_not_confuse_similar_names():
    # Regression: fuzzy partial_ratio matched "Alex Perez" inside "Alex Pereira".
    roster = [
        {"slug": "alex-pereira", "full_name": "Alex Pereira", "aliases": ["Poatan"]},
        {"slug": "alex-perez", "full_name": "Alex Perez", "aliases": []},
    ]
    slugs = {m.fighter_slug for m in find_fighter_mentions("Alex Pereira wins again", roster)}
    assert slugs == {"alex-pereira"}


def test_matches_through_accents_and_apostrophes():
    roster = [
        {"slug": "jiri-prochazka", "full_name": "Jiri Prochazka", "aliases": []},
        {"slug": "sean-omalley", "full_name": "Sean O'Malley", "aliases": []},
    ]
    text = "Jiří Procházka calls out Sean O’Malley"
    slugs = {m.fighter_slug for m in find_fighter_mentions(text, roster)}
    assert slugs == {"jiri-prochazka", "sean-omalley"}


def test_single_word_alias_is_case_sensitive():
    roster = [{"slug": "colby-covington", "full_name": "Colby Covington", "aliases": ["Chaos"]}]
    assert find_fighter_mentions("There was chaos at the weigh-ins.", roster) == []
    assert find_fighter_mentions("Chaos is back.", roster)[0].fighter_slug == "colby-covington"


def test_name_inside_longer_word_does_not_match():
    roster = [{"slug": "petr-yan", "full_name": "Petr Yan", "aliases": []}]
    assert find_fighter_mentions("Petr Yankovic is not a fighter", roster) == []
