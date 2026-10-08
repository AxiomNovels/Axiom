"""Content policy: the hard filter for sexually explicit novels.

This is the single source of truth for which tags make a novel ineligible for
Axiom (see /mission.html for the public-facing policy). It is used by:

  * the Upload Novel feature (routes/novels.py), so a user can't add a novel
    that the catalogue-seeding scripts would have rejected; and
  * the discover_*_popular.py scripts, which import their per-source list from
    here so the two can never drift apart.

Each source has its own list because each site uses its own tag vocabulary
(e.g. Royal Road's "Sexual Content" warning vs. Wattpad's "smut"/"lemon").
Edit a list here and every caller picks the change up.

Matching ignores case, spaces, hyphens and other punctuation, so "Reverse
Harem", "reverse-harem" and "REVERSEHAREM" are all treated as the same tag.
"""

import re


# Machine-readable code the frontend looks for to show the policy message and
# link, instead of a generic error.
POLICY_VIOLATION_CODE = "content_policy_violation"
POLICY_VIOLATION_MESSAGE = (
    "This novel violates our content policy and can't be added to Axiom."
)

# Maps the labels used by the Upload Novel form to the keys below.
SOURCE_KEYS = {
    "royal road": "royalroad",
    "royalroad": "royalroad",
    "wattpad": "wattpad",
    "webnovel": "webnovel",
}


# ---------------------------------------------------------------------------
# Royal Road
#
# Includes Royal Road's Sexual Content warning and relationship labels,
# plus explicit-content aliases for imported or legacy metadata. These aliases
# are policy terms; they are not all official Royal Road tags.
# ---------------------------------------------------------------------------
ROYALROAD_EXCLUDED_TAGS = {
    "sexual content",
    "harem",
    "multiple love interests",
    "competing love interest",
    "competing love interests",
    "royal harem",
    "multiple lovers",
    "reverse harem",
    "smut",
    "erotica",
    "erotic",
    "sexual themes",
    "sexual scenes",
    "sex scene",
    "sex scenes",
    "explicit sexual content",
    "sexually explicit",
    "explicit content",
    "adult content",
    "mature content",
    "adult only",
    "18+",
    "nsfw",
    "porn",
    "pornographic",
    "pornography",
    "erotic romance",
    "erotic fiction",
    "smutty",
    "spicy romance",
    "steamy romance",
    "hentai",
    "ecchi",
    "lemon",
    "lemons",
    "bdsm",
    "fetish",
    "kink",
    "incest",
    "sexual violence",
    "sexual assault",
    "rape",
}

# ---------------------------------------------------------------------------
# Wattpad
# ---------------------------------------------------------------------------
WATTPAD_EXCLUDED_TAGS = {
    # General mature or explicit content
    "adultcontent",
    "adultfiction",
    "adultonly",
    "adultromance",
    "adults",
    "explicit",
    "explicitcontent",
    "explicitromance",
    "mature",
    "matureaudience",
    "maturecontent",
    "maturethemes",
    "matureromance",
    "notworkfriendly",
    "nsfw",
    "ratedm",
    "restricted",
    "spicy",
    "spicyromance",

    # Erotica and sexual content
    "erotica",
    "erotic",
    "eroticfiction",
    "eroticromance",
    "eroticstory",
    "hotromance",
    "lemon",
    "lemons",
    "lime",
    "mature scenes",
    "maturescenes",
    "naughtystory",
    "sensual",
    "sexual",
    "sexualcontent",
    "sexualthemes",
    "sexscene",
    "sexscenes",
    "smut",
    "smutfiction",
    "smutty",
    "steamy",
    "steamyromance",

    # Lust-driven characters or plots
    "carnal",
    "desire",
    "horny",
    "lecherous",
    "libido",
    "lust",
    "lustful",
    "lustfulmalelead",
    "lustfulmc",
    "lustfulprotagonist",
    "perverted",
    "pervertedmc",
    "pervertmc",
    "seduction",
    "seductive",
    "sexaddict",
    "sexaddiction",
    "sexdriven",

    # Harems and partner collecting
    "allmaleharem",
    "allfemaleharem",
    "boyharem",
    "femaleharem",
    "girlharem",
    "harem",
    "haremcollection",
    "haremcomedy",
    "haremfantasy",
    "haremking",
    "haremlit",
    "haremromance",
    "haremseeking",
    "haremseekingmc",
    "haremstory",
    "maleharem",
    "multiharem",
    "multipleloveinterests",
    "multiplepartners",
    "polygamy",
    "polyamory",
    "reverseharem",
    "rh",
    "whychoose",
    "whychooseromance",

    # Romance-first or hookup-focused content
    "badboyromance",
    "billionaireromance",
    "hookup",
    "hookups",
    "mafia romance",
    "mafiaromance",

    # Fetish-oriented content
    "agegapromance",
    "bdsm",
    "bondage",
    "breeding",
    "breedingkink",
    "dominance",
    "dominant",
    "dominantmale",
    "domsub",
    "fetish",
    "kink",
    "kinky",
    "masterandslave",
    "omegaverse",
    "possessiveromance",
    "submissive",
    "sugarbaby",
    "sugardaddy",

    # Sexualized supernatural categories
    "alphamate",
    "alpharomance",
    "demonlover",
    "fatedmates",
    "incubus",
    "matebond",
    "mates",
    "monsterromance",
    "paranormalromance",
    "succubus",
    "vampireromance",
    "werewolfromance",

    # Common relationship-category tags
    # including stories that are romantic but not sexually explicit.
    "bl",
    "boylove",
    "boys love",
    "boyxboy",
    "bx b",
    "bxb",
    "femslash",
    "girl love",
    "girls love",
    "girlxgirl",
    "gl",
    "gxg",
    "lesbianromance",
    "lgbtromance",
    "mxm",
    "wlw",
    "yaoi",
    "yuri",

    # Exploitative or abusive sexual themes
    "ageplay",
    "dubcon",
    "forcedmarriage",
    "incest",
    "noncon",
    "nonconsensual",
    "rape",
    "rapefantasy",
    "sexualabuse",
    "sexualassault",
    "stepbrotherromance",
    "stepsiblingromance",
    "teacherstudent",
    "toxicromance",

    # Pregnancy or reproduction-centered romance
    "accidentalpregnancy",
    "babydaddy",
    "mpreg",
    "pregnancy",
    "pregnancyromance",
    "secretbaby",
}

# ---------------------------------------------------------------------------
# WebNovel
# ---------------------------------------------------------------------------
WEBNOVEL_EXCLUDED_TAGS = {
    # explicit / mature labels
    "adult", "adult content", "mature content",
    "mature", "mature romance", "adult romance", "nsfw", "explicit",
    "explicit content", "hentai", "ecchi", "sex stories", "sex story",
    "smut", "erotica", "erotic", "erotic fiction", "steamy", "spicy",

    # Common relationship-category tags
    # including stories that are romantic but not sexually explicit.
    "bl", "boylove", "boys love", "boyxboy", "bx b", "bxb",
    "femslash", "girl love", "girls love", "girlxgirl", "gl", "gxg",
    "lesbianromance", "lgbtromance", "mxm", "wlw", "yaoi", "yuri",

    # explicit-scene shorthand
    "lemon", "lemons", "lime", "sex scene", "sex scenes",
    "sexual content",

    # harem / multi-partner
    "harem", "reverse harem", "all male harem", "all female harem",
    "harem seeking", "polygamy", "polyamory", "multiple partners",

    # fetish / bdsm / non-consensual
    "bdsm", "bondage", "domination", "domination play", "fetish",
    "kink", "kinky", "submissive", "dominant", "master and slave",
    "sex slave", "noncon", "non-con", "nonconsensual",
    "non-consensual", "dubcon", "dub-con", "rape", "rape fantasy",
    "netorare", "ntr", "netori", "cuckold", "mafia", "ceo", "bad boy", "bad girl"

    # bestiality / extreme
    "bestiality", "beastality",

    # incest
    "incest",

    # pregnancy/breeding fetish framing
    "mpreg", "breeding", "impregnation",

    # omegaverse
    "omegaverse", "alpha mate", "alpha romance",

    # explicit-coded character/content descriptors seen in WebNovel
    # Additional Tags lists
    "milf", "loli", "legal loli", "lolicon", "shota", "shotacon",
}

EXCLUDED_TAGS_BY_SOURCE = {
    "royalroad": ROYALROAD_EXCLUDED_TAGS,
    "wattpad": WATTPAD_EXCLUDED_TAGS,
    "webnovel": WEBNOVEL_EXCLUDED_TAGS,
}


def _compact(value) -> str:
    """Lowercase and drop everything except letters and digits."""
    return re.sub(r"[\W_]+", "", str(value).casefold())


_COMPACT_BY_SOURCE = {
    source: frozenset(filter(None, (_compact(tag) for tag in tags)))
    for source, tags in EXCLUDED_TAGS_BY_SOURCE.items()
}
_ALL_COMPACT = frozenset().union(*_COMPACT_BY_SOURCE.values())


def find_policy_violations(source: str | None, novel: dict) -> list[str]:
    """Return the tags/genres of `novel` that the policy prohibits.

    `source` is the label from the upload form ("Royal Road", "WebNovel",
    "Wattpad") or an internal key ("royalroad", ...). An empty list means the
    novel is acceptable. An unrecognised source is checked against every list
    rather than skipped, so the filter fails closed.

    Genres are checked as well as tags: scrapers file anything that isn't a
    recognised genre under tags, but nothing should be able to slip past by
    arriving in the other field.
    """
    key = SOURCE_KEYS.get(str(source or "").strip().casefold())
    banned = _COMPACT_BY_SOURCE.get(key, _ALL_COMPACT)

    violations: list[str] = []
    for value in [*(novel.get("tags") or []), *(novel.get("genres") or [])]:
        if not isinstance(value, str):
            continue
        if _compact(value) in banned and value not in violations:
            violations.append(value)
    return violations
