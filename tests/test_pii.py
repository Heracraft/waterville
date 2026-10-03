from __future__ import annotations

import pytest

from app.pii import scrub


@pytest.mark.parametrize(
    "text,gone,kept,tag",
    [
        # email
        ("Email me at jane.doe@example.com about fences", ["jane.doe", "example.com"], ["fences"], "[email]"),
        ("my email is bob_smith+cec@mail.maine.edu, can I keep goats?", ["bob_smith", "maine.edu"], ["goats"], "[email]"),
        # phone
        ("Call 207-555-1234 or (207) 555 1234 about my deck", ["555"], ["deck"], "[phone]"),
        ("reach me at 207.555.0199 re: shed permit", ["555", "0199"], ["shed permit"], "[phone]"),
        ("my cell is +1 207 555 0100 x22, is a carport allowed", ["555", "x22"], ["carport"], "[phone]"),
        ("call 2075550123 about chickens", ["2075550123"], ["chickens"], "[phone]"),
        ("phone 555-0142 after 5", ["0142"], ["after 5"], "[phone]"),
        # addresses
        ("Can I put a shed at 44 Elm Street apt 2?", ["44 Elm", "apt 2"], ["shed"], "[address]"),
        ("I live at 12 N. Main St. and want a fence", ["12 N", "Main St"], ["fence"], "[address]"),
        ("Is 5 Kennedy Memorial Dr in the commercial zone?", ["Kennedy Memorial"], ["commercial zone"], "[address]"),
        ("Our house on 3 Main St Ext floods", ["Main St Ext"], ["floods"], "[address]"),
        ("12B College Ave needs a sign permit", ["12B College"], ["sign permit"], "[address]"),
        ("21-23 Pleasant Street is a duplex", ["Pleasant"], ["duplex"], "[address]"),
        ("my camp is at 1234 Route 201 near the river", ["1234 Route 201"], ["near the river"], "[address]"),
        ("88 US Rte. 2 has junk cars", ["88 US"], ["junk cars"], "[address]"),
        ("RR 2 Box 15, Waterville - septic question", ["RR 2", "Box 15"], ["septic question"], "[address]"),
        ("mail goes to HC 63 Box 10", ["HC 63", "Box 10"], [], "[address]"),
        ("P.O. Box 44 in Waterville", ["Box 44"], ["Waterville"], "[address]"),
        ("17 West River Road, Waterville, ME 04901 setback", ["West River", "04901"], ["setback"], "[address]"),
        ("23 Pond Rd. unit 4 rental registration", ["Pond Rd", "unit 4"], ["rental registration"], "[address]"),
        ("I'm at 9 Silver and the furnace is out", ["9 Silver"], ["furnace"], "[address]"),
        ("the house at 40 Mayflower Hill", ["Mayflower"], ["house"], "[address]"),
        ("200 Messalonskee Shores Lane dock", ["Messalonskee"], ["dock"], "[address]"),
        ("lowercase 44 elm street fence height", ["44 elm street"], ["fence height"], "[address]"),
        # parcels
        ("Map 21 Lot 45 setback question", ["Lot 45", "Map 21"], ["setback"], "[parcel]"),
        ("Tax Map 12, Lot 34-A shoreland", ["Map 12", "34-A"], ["shoreland"], "[parcel]"),
        ("map/lot 21-45 zoning district?", ["21-45"], ["zoning district"], "[parcel]"),
        ("M21 L45 variance", ["M21", "L45"], ["variance"], "[parcel]"),
        ("parcel 012-045-000 subdivision", ["012-045"], ["subdivision"], "[parcel]"),
        ("parcel ID 0123A is wet", ["0123A"], ["wet"], "[parcel]"),
        ("lot #45 in the subdivision", ["#45"], ["subdivision"], "[parcel]"),
        ("lot 7 of Eastern Acres", ["lot 7"], ["Eastern Acres"], "[parcel]"),
        ("deed at Book 1234 Page 56 easement", ["1234", "Page 56"], ["easement"], "[parcel]"),
        # names
        ("My name is John Smith and I want chickens", ["John", "Smith"], ["chickens"], "[name]"),
        ("my neighbor Bob Jones has a junk car", ["Bob", "Jones"], ["junk car"], "[name]"),
        ("Mr. Peters said the fence is too tall", ["Peters"], ["fence"], "[name]"),
        ("Mrs Ann-Marie O'Neil keeps 20 cats", ["Ann-Marie", "O'Neil"], ["20 cats"], "[name]"),
        ("Dr. Lee wants a home office", ["Lee"], ["home office"], "[name]"),
        ("mr smith next door burns trash", ["smith"], ["burns trash"], "[name]"),
        ("My landlord, Sue Brown, won't fix the heat", ["Sue", "Brown"], ["heat"], "[name]"),
        ("my neighbor's (Tom) dog barks all night", ["Tom"], ["dog barks"], "[name]"),
        ("our tenant Kayla left trash out", ["Kayla"], ["trash"], "[name]"),
        ("I am Maria Lopez, can I run a daycare?", ["Maria", "Lopez"], ["daycare"], "[name]"),
        ("a contractor named Jim Beam did my roof", ["Jim", "Beam"], ["roof"], "[name]"),
        ("Do I need a permit for a deck? Thanks, Karen", ["Karen"], ["permit for a deck"], "[name]"),
        ("John Q. Public is my neighbor? no: my neighbor John Q. Public", ["Q. Public is my neighbor? no: my neighbor John"], [], "[name]"),
        # review findings, 2026-10-03
        ("Can Bob Smith build a fence? He lives on Silver Street", ["Bob", "Smith", "Silver"], ["build a fence"], "[name]"),
        ("Can Bob Smith build a fence? He lives on Silver Street", ["Silver Street"], ["lives on"], "[address]"),
        ("Jennifer Lopez at 22 Pleasant St", ["Jennifer", "Lopez", "Pleasant"], [], "[name]"),
        ("my landlord john smith wont fix heat", ["john", "smith"], ["wont fix heat"], "[name]"),
        ("my neighbor bob has a junk car", ["bob"], ["has a junk car"], "[name]"),
        ("house number 17 on Gilman street", ["17", "Gilman"], [], "[address]"),
        ("I rent from Mike at the Elm St apartments", ["Mike"], ["apartments"], "[name]"),
        ("I rent from Mike at the Elm St apartments", ["Elm St"], ["apartments"], "[address]"),
        ("My name is jane doe", ["jane", "doe"], [], "[name]"),
        ("Jane Doe here, can I keep hens", ["Jane", "Doe"], ["keep hens"], "[name]"),
        ("Can I run a business from my house on College Avenue?", ["College Avenue"], ["business"], "[address]"),
    ],
)
def test_scrub(text, gone, kept, tag):
    out = scrub(text)
    for g in gone:
        assert g not in out, out
    for k in kept:
        assert k in out, out
    assert tag in out, out


@pytest.mark.parametrize(
    "text",
    [
        "Can I build a 6 foot fence along the road?",
        "How many chickens can I keep in the R-A zone?",
        "What is the setback for a 10 x 12 shed?",
        "Do I need a permit for 2 units in a single family home?",
        "Can a 12 by 16 shed sit 5 feet from the road?",
        "What does § 275-4.27K(3) say about 30% expansion?",
        "Explain 30-A M.R.S. § 4452 penalties",
        "Is § 205-7A still in force after Ord. No. 167-2026?",
        "Can I keep 6 hens on a 10000 square foot lot?",
        "What is the minimum lot size in the RR district?",
        "How tall can a sign be on Main Street?",
        "Is Kennedy Memorial Drive in a commercial district?",
        "My neighbor has a junk car in the yard",
        "Can my landlord enter without notice?",
        # A street name with no house number and no residence cue is kept.
        "Can I open a business on College Avenue?",
        "Can I build in the Shoreland Overlay District?",
        "How Tall Can A Fence Be In The Residential Zone?",
        "My neighbor keeps goats in the yard",
        "I am going to build a deck",
        "Does Thomas College need a permit for a sign?",
        "Is the Kennebec River in the shoreland zone?",
        "When does the Planning Board meet in January?",
        "What permits do I need for 3 bedrooms and 2 bathrooms?",
        "Who do I call at Code Enforcement about a fire hazard?",
        "Is a lot 100 feet wide enough for a duplex?",
        "In 2024 the council changed the rules for 4 units, right?",
        "Can I build 2 stories within 250 feet of the river?",
        "What is chapter 205 about?",
        "Fireworks allowed on July 4?",
    ],
)
def test_scrub_keeps_ordinary_questions(text):
    assert scrub(text) == text


def test_scrub_handles_empty_and_none():
    assert scrub("") == ""
    assert scrub(None) == ""  # type: ignore[arg-type]


def test_scrub_collapses_whitespace_and_repeats():
    out = scrub("Mr. Smith  and   Mrs. Smith at 4 Elm St")
    assert "  " not in out
    assert out.count("[address]") == 1


def test_scrub_combined_question():
    q = (
        "Hi, my name is Jane Roe (207-555-0100, jane@roe.net). My neighbor Bob Jones at 14 Western Ave, "
        "Map 3 Lot 12, has 9 junk cars. Is that allowed under chapter 205? Thanks, Jane"
    )
    out = scrub(q)
    for g in ("Jane", "Roe", "555", "roe.net", "Bob", "Jones", "14 Western", "Lot 12"):
        assert g not in out, out
    for k in ("9 junk cars", "chapter 205", "allowed"):
        assert k in out, out
