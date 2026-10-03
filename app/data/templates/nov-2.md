+++
title = "Second notice of violation"
group = "Enforcement"
order = 20
description = "After the first deadline passes: earlier notice, reinspection, the violation remains, new deadline, referral warning."
shared = ["_violation_types.toml"]
notes = """
The MOCA Legal Issues Manual (2017), ch. 7, p. 91, says a second letter should state: (1) that a previous notice was given and its date, (2) the nature of the violation and the section, (3) that the property was inspected again and the violation still exists, (4) the corrective measures and a specific date, and (5) that if the violation continues the CEO will recommend referral to a municipal attorney for legal action, with the possibility of paying the City's legal fees.

The template treats the second notice as an enforcement order and repeats the appeal language. No source settles whether a repeat notice restarts the appeal period, so the letter carries a [VERIFY] tag there. Ch. 205 notices still go to the mortgagee (§ 205-7).
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
name = "first_deadline"
label = "Deadline set in the first notice"
kind = "date"
required = true
section = "Violation"

[[fields]]
name = "reinspection_date"
label = "Date of reinspection"
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
label = "What the reinspection found"
kind = "textarea"
rows = 5
required = true
ai = true
ai_prompt = "the paragraph of a second notice of violation describing what the reinspection found and how it compares with the first notice"
section = "Violation"

[[fields]]
name = "corrective_action"
label = "Corrective action ordered"
kind = "textarea"
rows = 4
required = true
section = "Order"

[[fields]]
name = "correct_by"
label = "New deadline"
kind = "date"
required = true
section = "Order"

[[fields]]
name = "prior_conviction"
label = "Previous conviction of the same party within 2 years for the same law or ordinance?"
kind = "select"
required = true
default = "no"
section = "Order"
options = [
  { value = "no", label = "No, or not shown" },
  { value = "yes", label = "Yes, and the record shows it" },
]
help = "A repeat complaint or an earlier notice is not a conviction (30-A M.R.S. § 4452(3)(F))."

[[fields]]
name = "cc_extra"
label = "Other copies to"
kind = "text"
section = "Order"

[variants.prior_conviction.no]
prior_text = ""

[variants.prior_conviction.yes]
# Depends on the violation type: § 4452(3)(F) raises only the
# paragraph B and B-1 maximums (see _violation_types.toml).
prior_text = "{prior_conviction_text}"

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
from = "first_deadline"
to = "reinspection_date"
days = 1
message = "The reinspection took place after the first deadline."

[[checks]]
kind = "min_days"
from = "letter_date"
to = "correct_by"
days = 1
message = "The new deadline is after the date of the letter."
+++
{letter_date_long}

**{delivery_method}**

{owner_name}
{owner_address}

?{mortgagee_block} {mortgagee_block}

**Re: Second notice of violation and order to correct**
Property: {property_address}
?{map_lot} Tax map and lot: {map_lot}
?{case_ref} City case: {case_ref}

Dear {owner_name}:

On {first_notice_date_long}, this office sent you a notice of violation of {section_cited} of the Code of the City of Waterville at {property_address}. That notice ordered you to correct the violation by {first_deadline_long}.

On {reinspection_date_long}, I inspected the property again. The violation still exists.

## Violation

{facts}

These conditions violate {section_cited} of the Code of the City of Waterville. {duty_line}

## Order

You are ordered to take the following corrective action no later than **{correct_by_long}**:

{corrective_action}

If the violation continues after that date, I will recommend that the City refer this violation to the City Solicitor for legal action. If the City is the prevailing party in court, you may be required to pay the City's attorney fees, expert witness fees and costs (30-A M.R.S. § 4452(3)(D)).

## Penalties

{penalty_text}

?{prior_text} {prior_text}

## Your right to appeal

{appeal_text}

[VERIFY: whether a repeat notice is a new appealable decision. No source says a repeat notice restarts the 30 days of § 275-6.2E(1); the first notice of {first_notice_date_long} started that period, and under 30-A M.R.S. § 2691(4) a decision not timely appealed has preclusive effect. Ask the City Solicitor before sending; if the first notice controls, replace the paragraph above with the first notice's appeal period.]

You may still contact this office to discuss an administrative consent agreement (§ 5-2.10B of the City Code). If you have questions about this notice, call the Code Enforcement Office at {office_phone}.

Sincerely,

{signer_name}
{signer_title}
City of Waterville, Code Enforcement Office

?{cc_line} cc: {cc_line}
