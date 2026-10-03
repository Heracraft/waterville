"""Scrub personal details from public question text before it is logged (A7a).

`scrub(text)` replaces, in this order:

  [email]    email addresses
  [phone]    phone numbers (10 digits in the usual forms, 7-digit local numbers, extensions)
  [parcel]   map/lot numbers ("Map 21 Lot 45", "map/lot 21-45", "M21 L45", "Tax Map 12, Lot 34-A",
             "parcel 012-045-000", "lot #45", "Book 1234 Page 56" deed references)
  [address]  street addresses: a house number plus a street name and a street word
             (Street, Rd, Ave, Lane, Extension, Hill, Pond Road and the rest), Maine
             rural forms ("1234 Route 201", "RR 2 Box 15", "HC 63 Box 10", "PO Box 4"),
             "at 12 Elm" without a street word, unit numbers, and "ME 04901" ZIP codes
             "house number 17", and a street name after a place cue ("lives on
             Silver Street", "at the Elm St apartments")
  [name]     personal names after a title (Mr., Mrs., Ms., Dr., Mister), after a
             relation ("my neighbor Bob Jones", "landlord, Sue", "my wife's"),
             after "my name is", "I am", "named", "rent from", in a sign-off
             ("Thanks, John"); two or three capitalized words in a row that are
             not place, office or code words ("Can Bob Smith build"); common
             given names, capitalized anywhere ("from Mike") and lowercase after
             a relation or "my name is" ("my landlord john smith")

It errs toward removing too much: the question log only needs the topic.
Section numbers (§ 275-4.27, 205-7A, 30-A § 4452), dimensions ("6 foot fence",
"10 x 12 shed") and counts ("2 units", "6 hens") are kept.
"""

from __future__ import annotations

import re

# Street words, including the forms common in Maine town addresses.
_SUFFIX = (
    r"(?:street|str|st|avenue|ave|av|road|rd|drive|dr|lane|ln|court|ct|place|pl|terrace|terr|ter|way|"
    r"boulevard|blvd|circle|cir|highway|hwy|parkway|pkwy|square|sq|heights|hts|row|park|trail|trl|path|"
    r"landing|extension|ext|hill|hl|ridge|point|pt|cove|shore|shores|crossing|xing|loop|commons|common|"
    r"green|meadows?|woods|run|pike|turnpike|tpke|alley|aly|walk|bluff|farm|estates)"
)

# Words a street name never contains: a house number followed by these is a
# dimension or a count ("12 shed near the road", "2 units on the street").
_NOT_NAME = (
    r"(?:the|a|an|my|our|his|her|their|your|near|from|to|toward|along|of|on|in|at|by|with|for|and|or|is|are|"
    r"be|can|could|should|would|will|i|it|this|that|these|those|than|then|if|across|behind|beside|next|off|"
    r"over|under|into|onto|about|any|per|each|who|what|how|when|where|do|does|need|feet|foot|ft)"
)
_UNITS = (
    r"(?:foot|feet|ft|inch|inches|in|percent|square|sq|acres?|yards?|yds?|miles?|mi|days?|hours?|hrs?|minutes?|"
    r"units?|stor(?:y|ies)|floors?|cars?|vehicles?|trucks?|chickens?|hens?|roosters?|ducks?|goats?|dogs?|cats?|"
    r"animals?|people|persons?|bedrooms?|bathrooms?|rooms?|beds?|years?|yrs?|months?|weeks?|times?|gallons?|"
    r"lbs?|pounds?|amps?|volts?|kw|watts?|x|by|and|or|to|am|pm|a\.m\.|p\.m\.)"
)

# A capitalized name of one to three words, or with initials ("John Q. Public").
# Common capitalized words that start sentences or name places are not names.
_NOT_A_NAME = (
    r"(?:I|I'm|I've|Can|Could|Do|Does|Did|Is|Are|Was|Were|Will|Would|Should|May|Might|Must|What|When|Where|"
    r"Which|Who|Why|How|The|A|An|And|But|Or|So|If|In|On|At|To|For|Of|My|Our|Their|His|Her|It|This|That|There|"
    r"They|We|You|He|She|Has|Have|Had|Says|Said|Told|Wants|Keeps|Built|Put|Just|Also|Not|No|Yes|Please|Thanks|"
    r"Waterville|Maine|City|Code|Town|State|County|Kennedy|Main|Planning|Zoning|Board|Council|Department|DEP|"
    r"Hello|Hi|Hey)"
)
_NAME_WORD = r"(?:(?!" + _NOT_A_NAME + r"\b)[A-Z](?:[a-z]*(?:['\-][A-Z]?[a-z]+)+|[a-z]+)|[A-Z]\.)"
_NAME = _NAME_WORD + r"(?:\s+" + _NAME_WORD + r"){0,2}(?:'s)?"

_RELATIONS = (
    r"(?:neighbou?rs?|next[- ]door neighbou?r|landlord|landlady|tenants?|renters?|owner|contractor|builder|"
    r"plumber|electrician|roofer|husband|wife|spouse|partner|son|daughter|mother|father|mom|dad|brother|sister|"
    r"friend|roommate|boss|uncle|aunt|cousin|grandmother|grandfather|grandma|grandpa|realtor|agent|"
    r"inspector|officer)"
)

_TITLE = r"(?:Mr|Mrs|Ms|Mx|Miss|Mister|Dr|Doctor|Sir|Madam|Rev|Atty)"

# Common given names. Ambiguous ones that are also ordinary words or months
# (Will, Mark, Bill, May, June, Rose, Grant, Art, Hope, Faith, Joy) are left out.
_GIVEN = (
    "aaron adam alan albert alex alice alicia amanda amber amy andrea andrew angela ann anna anne anthony ashley "
    "barbara becky ben benjamin beth betty bob bobby bonnie brad brandon brenda brian brittany bruce carl carol "
    "caroline carolyn catherine charles charlie cheryl chris christina christine christopher cindy colleen connie "
    "craig crystal cynthia dan dana daniel danielle darlene dave david dawn debbie deborah debra denise dennis diana "
    "diane donald donna doris dorothy doug douglas ed eddie edward eileen elaine elizabeth ellen emily emma eric "
    "erica erin ethan eugene evelyn frank fred gary george gerald gina gloria greg gregory harold heather helen "
    "henry holly jack jacob jake james jamie jane janet janice jason jean jeff jeffrey jen jennifer jeremy jerry "
    "jesse jessica jill jim jimmy joan joe joel john johnny jon jonathan jose joseph josh joshua joyce judith judy "
    "julia julie justin karen kate katherine kathleen kathy katie kayla keith kelly ken kenneth kevin kim kimberly "
    "kristen kyle larry laura lauren lawrence linda lisa lori louis luke lynn madison margaret maria marie marilyn "
    "martha martin mary matt matthew megan melissa michael michelle mike nancy nathan nicholas nick nicole noah "
    "norma olivia pam pamela patricia patrick paul paula peggy peter phil philip phyllis rachel ralph randy ray "
    "raymond rebecca richard rick rita rob robert robin roger ron ronald roy russell ruth ryan sam samantha samuel "
    "sandra sandy sara sarah scott sean sharon shawn sheila shirley stephanie stephen steve steven susan tammy tara "
    "teresa terry theresa thomas tim timothy tina todd tom tommy tony tracy travis tyler valerie vanessa victoria "
    "vincent virginia walter wanda wayne wendy william zach"
).split()
_GIVEN_LOWER = r"(?:" + "|".join(_GIVEN) + r")"
_GIVEN_CAP = r"(?:" + "|".join(n.capitalize() for n in _GIVEN) + r")"

# Lowercase words that follow a relation or name cue and are not names.
_NOT_LOWER_NAME = (
    r"(?:has|have|had|is|are|was|were|keeps?|kept|built|builds?|put|puts|says?|said|told|tells?|wants?|wont|won't|"
    r"will|would|can|can't|cannot|could|should|does|did|doesn't|didn't|is|isn't|parks?|parked|lets?|left|burns?|"
    r"runs?|ran|lives?|lived|owns?|owned|rents?|rented|just|also|never|always|still|and|or|but|the|a|an|my|our|"
    r"his|her|their|next|door|here|there|about|from|with|without|who|that|which|in|on|at|to|for|of|by|not|no|"
    r"yes|please|thanks|cut|cuts|piles?|dumped|dumps?|leaves|plays?|blocks?|blocked|refuses?|refused|says|"
    r"wants|claims?|claimed|thinks?|thought|added|adds?|moved|moves?|started|starts?|stopped|stops?|uses?|used|"
    r"too|very|really|again|now|today|yesterday|recently|already|went|goes|go|got|gets?|made|makes?)"
)

# Capitalized words that name places, offices, codes, dates or topics rather
# than people. A run of two or three capitalized words counts as a name only
# when none of its words is here, in _NOT_A_NAME, or a street word.
_PLACE_WORDS = (
    r"(?:Acres|Aid|Appeals|Apartments?|April|Area|Article|August|Avenue|Bank|Bay|Beach|Brook|Building|Bureau|"
    r"Business|Center|Centre|Central|Certificate|Chapter|Church|Civil|Code|Colby|College|Commercial|Commission|"
    r"Committee|Community|Company|Contract|Corner|Court|December|Department|District|Downtown|East|Eastern|"
    r"Elementary|Energy|Enforcement|Environmental|Estates|Falls|Farm|February|Fire|Flood|Floodplain|Food|Friday|"
    r"Fund|Health|High|Highway|Historic|Hospital|Hospitals|House|Housing|Human|Industrial|Inland|Insurance|Island|"
    r"January|July|Kennebec|Lake|Land|Legal|Library|Life|Lodge|Maintenance|Mall|Manor|March|Market|Medical|"
    r"Memorial|Messalonskee|Middle|Mill|Monday|Motor|Mountain|Municipal|National|Natural|North|Northern|November|"
    r"October|Office|Officer|Ordinance|Overlay|Permit|Plan|Plaza|Police|Pond|Power|Procedure|Property|Protection|"
    r"Public|Recreation|Rental|Residential|Resource|Resources|Review|River|Road|Route|Rule|Rules|Rural|Safety|"
    r"Saturday|School|Section|September|Service|Services|Sewer|Shoreland|Site|South|Southern|Square|Station|"
    r"Stream|Street|Sunday|Supply|Thursday|Trail|Transportation|Tuesday|Union|United|University|Use|Valley|"
    r"Village|Water|Wednesday|West|Western|Wetland|Day|Year|Week|Month|Hall|Park|Zone|Zoning|Board|Council|"
    r"Planning|Department|Clerk|Inspector|Assessor|Registry|Deeds|Superior|District|Maine|Waterville|Winslow|"
    r"Oakland|Fairfield|Augusta|Portland|Bangor|Skowhegan|Vassalboro|Sidney|Benton|Clinton|America|American|"
    r"Facebook|Google|Amazon|Airbnb|Vrbo|Home|Depot|Lowe's|Walmart|Hannaford|Shaw's)"
)
_CAP_WORD = r"(?!(?:" + _NOT_A_NAME[3:-1] + "|" + _PLACE_WORDS[3:-1] + r")\b)(?!" + _SUFFIX + r"\b)[A-Z][a-z]+(?:['\-][A-Z]?[a-z]+)?"

_PATTERNS: list[tuple[re.Pattern, str]] = [
    # ---------------------------------------------------------------- email, phone
    (re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+"), "[email]"),
    (
        re.compile(
            r"(?<![\w§.\-])(?:\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}"
            r"(?:\s*(?:x|ext\.?|extension)\s*\d{1,5})?(?![\w\-])",
            re.I,
        ),
        "[phone]",
    ),
    # Seven digits, unless an ordinance or section number ("Ord. No. 167-2026", "§ 205-1234").
    (
        re.compile(
            r"(?<![\w§.\-#])(?<![Nn]o\.\s)(?<![Nn]o\s)(?<!§\s)(?<!ance\s)(?<!Ord\.\s)"
            r"\d{3}[\s.\-]\d{4}(?![\w\-.]\d)(?!\w)"
        ),
        "[phone]",
    ),
    # ---------------------------------------------------------------- parcels and deeds
    (
        re.compile(
            r"\b(?:tax\s+)?map\s*(?:no\.?|number|#)?\s*:?\s*\d+[A-Za-z]?\s*[,/&\-]?\s*(?:and\s+)?"
            r"lot\s*(?:no\.?|number|#)?\s*:?\s*\d+[\w\-]*",
            re.I,
        ),
        "[parcel]",
    ),
    (re.compile(r"\bmap\s*/\s*lot\s*(?:no\.?|number|#)?\s*:?\s*\d+[A-Za-z]?\s*[\-/ ]\s*\d+[\w\-]*", re.I), "[parcel]"),
    (re.compile(r"\bM\s*-?\s*\d{1,3}[A-Za-z]?\s*,?\s*L\s*-?\s*\d{1,4}[A-Za-z]?\b", re.I), "[parcel]"),
    (
        re.compile(
            r"\bparcel\s*(?:id|no\.?|number|#)?\s*:?\s*\d[\w]*(?:[\-/ ]\d[\w]*){0,3}",
            re.I,
        ),
        "[parcel]",
    ),
    (re.compile(r"\blot\s*(?:no\.?|number|#)\s*:?\s*\d+[\w\-]*", re.I), "[parcel]"),
    (re.compile(r"\blot\s+\d+[A-Za-z]?(?:-\d+[A-Za-z]?)?\b(?!\s*" + _UNITS + r"\b)(?!\s*['\"%])", re.I), "[parcel]"),
    (re.compile(r"\bbook\s+\d+\s*,?\s*page\s+\d+\b", re.I), "[parcel]"),
    # ---------------------------------------------------------------- addresses
    # Maine rural forms: rural route and highway contract boxes, PO boxes.
    (re.compile(r"\b(?:RR|R\.R\.|rural\s+route|HC|H\.C\.)\s*#?\s*\d+\s*,?\s*(?:box\s*#?\s*\d+)?", re.I), "[address]"),
    (re.compile(r"\bP\.?\s*O\.?\s*Box\s*#?\s*\d+\b", re.I), "[address]"),
    # A house number on a numbered route: "1234 Route 201", "88 US Rte. 2", "5 State Hwy 104".
    (
        re.compile(
            r"(?<![\w§.\-])\d{1,6}[A-Za-z]?\s+(?:(?:US|U\.S\.|state|ME|maine)\s+)?"
            r"(?:route|rte\.?|rt\.?|highway|hwy\.?)\s*#?\s*\d{1,4}[A-Za-z]?\b",
            re.I,
        ),
        "[address]",
    ),
    # Number + up to three name words + street word, with an optional
    # direction and unit: "44 Elm Street apt 2", "12 N. Main St.", "5 Kennedy Memorial Dr",
    # "3 Main St Ext", "12B College Ave", "21-23 Pleasant Street".
    (
        re.compile(
            r"(?<![\w§.\-])\d{1,6}[A-Za-z]?(?:\s*-\s*\d{1,6}[A-Za-z]?)?\s+"
            r"(?!" + _UNITS + r"\b)"
            r"(?:(?:north|south|east|west|n|s|e|w)\.?\s+)?"
            r"(?:(?!" + _NOT_NAME + r"\b)[A-Za-z0-9'.\-]+\s+){0,3}"
            + _SUFFIX
            + r"\b\.?(?:\s+(?:ext|extension)\b\.?)?"
            r"(?:\s*,?\s*(?:apt|apartment|unit|suite|ste|#)\.?\s*#?\s*[\w\-]+)?",
            re.I,
        ),
        "[address]",
    ),
    # "at 12 Elm" or "live at 7 Silver": a number then a capitalized name, no street word.
    (
        re.compile(r"\b(?i:at|on)\s+\d{1,6}[A-Za-z]?\s+(?!(?i:" + _UNITS + r")\b)(?!" + _NOT_A_NAME + r"\b)[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?"),
        "[address]",
    ),
    # "house number 17", "home no. 4".
    (re.compile(r"\b(?:house|home|building|apartment)\s+(?:number|no\.?|#)\s*\d+[A-Za-z]?\b", re.I), "[address]"),
    # A street name after a place cue: "lives on Silver Street", "[address] on Gilman street",
    # "at the Elm St apartments". Only the street is replaced.
    (
        re.compile(
            r"(?:\b(?i:lives?|living|lived|reside[sd]?|residing|rents?|renting|rented|owns?|located|house|home|"
            r"property|apartment|camp|stay|staying)\s+(?i:is\s+|are\s+)?(?i:on|at|off)\s+(?i:the\s+)?"
            r"|\[address\]\s+(?i:on|at|off)\s+|\b(?i:at|on)\s+the\s+(?=[A-Z]))"
            r"((?:(?!(?i:" + _NOT_NAME + r")\b)[A-Za-z][A-Za-z'.\-]*\s+){1,3}(?i:" + _SUFFIX + r")\b\.?"
            r"(?:\s+(?i:ext|extension)\b\.?)?)"
        ),
        "[address]",
    ),
    (re.compile(r",?\s*\b(?:ME|Maine)\s+0\d{4}(?:-\d{4})?\b"), " [zip]"),
    (re.compile(r"\b(?:apt|apartment|unit|suite)\.?\s*#\s*[\w\-]+", re.I), "[address]"),
    # ---------------------------------------------------------------- names
    (re.compile(r"\b(?:" + _TITLE + r"|(?i:mr|mrs|ms|mx))\.?\s+(?:" + _NAME + r"|(?!" + _NOT_NAME + r"\b)[a-z][a-z'\-]+)"), "[name]"),
    (re.compile(r"\b(?i:my name is|my name's|i am|i'm|this is|named|name of)\s+(" + _NAME + r")(?=[\s,.;:!?)]|$)"), "[name]"),
    (
        re.compile(
            r"\b(?i:" + _RELATIONS + r")(?:'s)?,?\s+(?:\((" + _NAME + r")\)|(" + _NAME + r"))(?=[\s,.;:!?')]|$)"
        ),
        "[name]",
    ),
    (
        re.compile(r"\b(?i:thanks|thank you|regards|sincerely|cheers|best)\s*[,!.\-]*\s*(" + _NAME + r")\s*[.!]?\s*$"),
        "[name]",
    ),
    # Who a home or lot is rented from, bought from or owned by.
    (
        re.compile(
            r"\b(?i:rent(?:s|ing|ed)?\s+from|lease[sd]?\s+from|leasing\s+from|bought\s+(?:it\s+)?from|"
            r"sold\s+(?:it\s+)?to|owned\s+by|rented\s+by|managed\s+by)\s+(" + _NAME + r")(?=[\s,.;:!?)]|$)"
        ),
        "[name]",
    ),
    # Lowercase names after an explicit cue: "my name is jane doe", "my landlord john smith".
    (
        re.compile(
            r"\b(?i:my name is|my name's|call me)\s+((?!" + _NOT_LOWER_NAME + r"\b)[a-z][a-z'\-]+"
            r"(?:\s+(?!" + _NOT_LOWER_NAME + r"\b)[a-z][a-z'\-]+)?)(?=[\s,.;:!?)]|$)"
        ),
        "[name]",
    ),
    (
        re.compile(
            r"\b(?i:" + _RELATIONS + r"|named|rent(?:s|ing)? from|bought from)(?:'s)?,?\s+(" + _GIVEN_LOWER + r"\b"
            r"(?:\s+(?!" + _NOT_LOWER_NAME + r"\b)(?!" + _UNITS + r"\b)[a-z][a-z'\-]+(?<!ing)(?<!ed)(?=[\s,.;:!?)]|$))?)"
        ),
        "[name]",
    ),
    # "jane doe here, ..." at the start of a message.
    (
        re.compile(r"^\s*(" + _GIVEN_LOWER + r"(?:\s+[a-z][a-z'\-]+)?)(?=\s+(?:here|speaking)\b)", re.I),
        "[name]",
    ),
]

# Two or three capitalized words in a row ("Can Bob Smith build", "Jennifer
# Lopez at"), with an optional middle initial. Skipped for text written in
# title case or capitals, where every word looks like this.
_CAP_RUN = re.compile(r"(?<![\w'\[])" + _CAP_WORD + r"(?:\s+(?:[A-Z]\.\s+)?" + _CAP_WORD + r"){1,2}(?![\w'])")
# A common given name on its own, capitalized ("I rent from Mike", "Can Bob build").
_GIVEN_RUN = re.compile(r"(?<![\w'\[])" + _GIVEN_CAP + r"(?:'s)?(?![\w'])(?!\s+" + _PLACE_WORDS + r"\b)")
_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def _mostly_capitalized(text: str) -> bool:
    words = [w for w in _WORD.findall(text) if len(w) > 2]
    if len(words) < 4:
        return False
    caps = sum(1 for w in words if w[0].isupper())
    return caps / len(words) > 0.6


def _replace(tag: str):
    """Replace the whole match, or only the name groups when the pattern has them."""

    def sub(m: re.Match) -> str:
        spans = [m.span(i) for i in range(1, (m.re.groups or 0) + 1) if m.group(i) is not None]
        if not spans:
            return tag
        out, pos = [], m.start()
        for start, end in spans:
            out.append(m.string[pos:start])
            out.append(tag)
            pos = end
        out.append(m.string[pos : m.end()])
        return "".join(out)

    return sub


def scrub(text: str) -> str:
    out = text or ""
    for pattern, tag in _PATTERNS:
        out = pattern.sub(_replace(tag), out)
    if not _mostly_capitalized(out):
        out = _CAP_RUN.sub("[name]", out)
        out = _GIVEN_RUN.sub("[name]", out)
    # Collapse repeated tags ("[name] [name]") and whitespace.
    out = re.sub(r"(\[(?:name|address|parcel|phone|email)\])(?:[\s,]*\1)+", r"\1", out)
    return re.sub(r"\s+", " ", out).strip()
