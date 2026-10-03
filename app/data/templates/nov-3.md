+++
title = "Final notice of violation"
group = "Enforcement"
order = 30
description = "Third letter: violation continues after two notices; referral for legal action or Rule 80K, unless a consent agreement is reached."
shared = ["_violation_types.toml"]
notes = """
The MOCA Legal Issues Manual (2017), ch. 7, pp. 91-92, says a third letter should state that the CEO inspected again, that the violation still exists despite earlier written notice, and that the CEO is recommending referral for legal action unless the violator will negotiate a consent agreement. If the CEO can file under Rule 80K, the letter may say a complaint is being prepared. If the municipal officers decide, the letter should give the date, time and place of their meeting and the violator's right to attend.

- Zoning: under § 275-6.1A(3)(a), the City, acting through the City Council, may institute proceedings.
- A CEO represents the City in District Court only when specifically authorized by the municipal officers (30-A M.R.S. § 4452(1)(C)). The 80K Manual (2017) also expects the CEO's certificate of familiarity with court procedures on file. Check both before picking the Rule 80K option.
"""

[[fields]]
name = "owner_name"
label = "Owner or person responsible"
kind = "text"
required = true
from_case = "owner"
section = "Recipient"

[[fields]]
name = "owner_address"
label = "Mailing address"
kind = "textarea"
rows = 3
required = true
section = "Recipient"

[[fields]]
name = "delivery_method"
label = "Delivery"
kind = "select"
required = true
default = "Certified mail, return receipt requested"
section = "Recipient"
options = [
  { value = "Certified mail, return receipt requested", label = "Certified mail, return receipt requested" },
  { value = "First class mail", label = "First class mail" },
  { value = "Hand delivery", label = "Hand delivery" },
]

[[fields]]
name = "property_address"
label = "Property address"
kind = "text"
required = true
from_case = "address"
section = "Property"

[[fields]]
name = "map_lot"
label = "Tax map and lot"
kind = "text"
from_case = "map_lot"
section = "Property"

[[fields]]
name = "case_ref"
label = "City case number"
kind = "text"
from_case = "id"
section = "Property"

[[fields]]
name = "first_notice_date"
label = "Date of the first notice"
kind = "date"
required = true
section = "Violation"

[[fields]]
name = "second_notice_date"
label = "Date of the second notice"
kind = "date"
required = true
section = "Violation"

[[fields]]
name = "reinspection_date"
label = "Date of the latest inspection"
kind = "date"
required = true
section = "Violation"

[[fields]]
name = "section_cited"
label = "Section or sections violated"
kind = "text"
required = true
section = "Violation"

[[fields]]
name = "facts"
label = "What the latest inspection found"
kind = "textarea"
rows = 5
required = true
ai = true
ai_prompt = "the paragraph of a final notice of violation describing what the latest inspection found"
section = "Violation"

[[fields]]
name = "referral_route"
label = "Next step"
kind = "select"
required = true
section = "Next step"
options = [
  { value = "ceo_80k", label = "I will file a Rule 80K land use citation (CEO authorized to represent the City)" },
  { value = "council", label = "I will recommend that the City Council authorize legal action" },
  { value = "solicitor", label = "I will refer the violation to the City Solicitor" },
]

[[fields]]
name = "respond_by"
label = "Respond or correct by"
kind = "date"
required = true
section = "Next step"

[[fields]]
name = "council_meeting"
label = "City Council meeting date"
kind = "date"
section = "Next step"
required_when = { referral_route = ["council"] }

[[fields]]
name = "council_time_place"
label = "Meeting time and place"
kind = "text"
section = "Next step"
required_when = { referral_route = ["council"] }

[[fields]]
name = "cc_extra"
label = "Other copies to"
kind = "text"
section = "Next step"

[variants.referral_route.ceo_80k]
next_step = "Unless the violation is corrected, or you contact this office to negotiate a consent agreement, by **{respond_by_long}**, I will prepare and file a land use citation and complaint in the Maine District Court under Rule 80K of the Maine Rules of Civil Procedure."

[variants.referral_route.council]
next_step = "Unless the violation is corrected, or you contact this office to negotiate a consent agreement, by **{respond_by_long}**, I will recommend that the City Council authorize legal action. The City Council will consider this matter on {council_meeting_long}, {council_time_place}. You have the right to attend that meeting. I will write to you again after the Council decides."

[variants.referral_route.solicitor]
next_step = "Unless the violation is corrected, or you contact this office to negotiate a consent agreement, by **{respond_by_long}**, I will refer this violation to the City Solicitor for legal action."

[[computed]]
name = "appeal_by"
from = "letter_date"
days = 30

[[computed]]
name = "atf_by"
from = "letter_date"
days = 30

[[computed]]
name = "cc_line"
join = ["cc_required", "cc_extra"]
sep = "; "

[[checks]]
kind = "min_days"
from = "letter_date"
to = "council_meeting"
days = 1
message = "The Council meeting is after the date of the letter."
when = { referral_route = ["council"] }
+++
{letter_date_long}

**{delivery_method}**

{owner_name}
{owner_address}

?{mortgagee_block} {mortgagee_block}

**Re: Final notice of violation**
Property: {property_address}
?{map_lot} Tax map and lot: {map_lot}
?{case_ref} City case: {case_ref}

Dear {owner_name}:

This office gave you written notice of a violation of {section_cited} of the Code of the City of Waterville at {property_address} on {first_notice_date_long} and again on {second_notice_date_long}.

On {reinspection_date_long}, I inspected the property again. The violation still exists.

## Violation

{facts}

These conditions violate {section_cited} of the Code of the City of Waterville. {duty_line}

## Next step

{next_step}

## Penalties

{penalty_text}

If the City is the prevailing party in court, it must be awarded reasonable attorney fees, expert witness fees and costs, unless the court finds that special circumstances make the award unjust (30-A M.R.S. § 4452(3)(D)). The court may also order the violation corrected or abated (30-A M.R.S. § 4452(3)(C)).

## Your right to appeal

{appeal_text}

[VERIFY: whether a repeat notice is a new appealable decision. No source says a repeat notice restarts the 30 days of § 275-6.2E(1); the first notice of {first_notice_date_long} started that period, and under 30-A M.R.S. § 2691(4) a decision not timely appealed has preclusive effect. Ask the City Solicitor before sending; if the first notice controls, replace the paragraph above with the first notice's appeal period.]

To discuss a consent agreement, call the Code Enforcement Office at {office_phone}.

Sincerely,

{signer_name}
{signer_title}
City of Waterville, Code Enforcement Office

?{cc_line} cc: {cc_line}
