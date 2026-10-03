+++
title = "Special exception decision to abutters"
group = "Zoning notices"
order = 55
description = "The second first-class letter to abutters when a special exception permit issues, with the appeal right (§ 275-5.20A(2)(f))."
notes = """
§ 275-5.20A(2)(f): when the CEO issues a special exception permit, he sends a second letter to abutters by first class mail notifying them of the decision and advising them of their right to appeal, with a reference to § 275-6.2E(1).

§ 275-6.2E(1): any interested party may appeal within 30 days of the CEO's decision; the ZBA hears the appeal de novo. § 275-6.2H(2): $25 fee plus the cost of advertising.

Send it to the same list as the first notice. Check that the decision date is at least 14 days after the first mailing.
"""

[[fields]]
name = "applicant_name"
label = "Applicant"
kind = "text"
required = true
section = "Decision"

[[fields]]
name = "property_address"
label = "Property address"
kind = "text"
required = true
from_case = "address"
section = "Decision"

[[fields]]
name = "map_lot"
label = "Tax map and lot"
kind = "text"
required = true
from_case = "map_lot"
section = "Decision"

[[fields]]
name = "use_description"
label = "Use permitted"
kind = "textarea"
rows = 3
required = true
section = "Decision"

[[fields]]
name = "first_mailing_date"
label = "Date of the first abutter notice"
kind = "date"
required = true
section = "Decision"

[[fields]]
name = "decision_date"
label = "Date the permit was issued"
kind = "date"
required = true
section = "Decision"

[[fields]]
name = "decision"
label = "Decision"
kind = "select"
required = true
default = "approved"
section = "Decision"
options = [
  { value = "approved", label = "Approved" },
  { value = "approved_conditions", label = "Approved with conditions" },
]

[[fields]]
name = "conditions"
label = "Conditions of approval"
kind = "textarea"
rows = 4
section = "Decision"
required_when = { decision = ["approved_conditions"] }

[variants.decision.approved]
decision_text = "The permit was issued without conditions beyond those the Code requires."

[variants.decision.approved_conditions]
decision_text = "The permit was issued with the following conditions. Under § 275-5.20C, a violation of any of these conditions is a violation of Chapter 275.\n\n{conditions}"

[[computed]]
name = "appeal_by"
from = "decision_date"
days = 30

[[checks]]
kind = "min_days"
from = "first_mailing_date"
to = "decision_date"
days = 14
message = "The permit issued at least 14 days after the first abutter mailing (§ 275-5.20A(2)(a))."
+++
{letter_date_long}

**By first class mail**

To: Abutting property owners

**Re: Decision on a special exception permit**
Property: {property_address}
Tax map and lot: {map_lot}

Dear property owner:

On {first_mailing_date_long}, this office notified you of an application by {applicant_name} for a special exception permit at {property_address}. On {decision_date_long}, the Code Enforcement Officer issued the special exception permit for the following use:

{use_description}

{decision_text}

## Your right to appeal

Section 275-5.20A(2)(f) of the Code of the City of Waterville requires this letter to tell you of the decision and of your right to appeal it. Under § 275-6.2E(1), any interested party may appeal a decision of the Code Enforcement Officer to the Waterville Zoning Board of Appeals within 30 days of the decision, which for this permit is by **{appeal_by_long}**. The Board hears the appeal de novo. File the appeal with the Code Enforcement Office; the fee is $25 plus the cost of advertising (§ 275-6.2H(2)).

If you have questions, call the Code Enforcement Office at {office_phone}.

Sincerely,

{signer_name}
{signer_title}
City of Waterville, Code Enforcement Office
