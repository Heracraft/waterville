+++
title = "First notice of violation"
group = "Enforcement"
order = 10
description = "Written notice and order to correct: section violated, facts, corrective action, deadline, penalties, appeal right."
shared = ["_violation_types.toml"]
notes = """
Contents follow the first-notice elements in the MOCA Legal Issues Manual (2017), ch. 7, pp. 90-91: the property, the nature of the violation, the section violated, an order (not a request) to stop and correct, a reasonable deadline, the appeal right, the penalty a court could assess, and the option of a consent agreement.

- Zoning: § 275-6.1A(1) requires written notice and an order; § 275-6.1A(3)(a) requires notice to the City Solicitor and City Council.
- Property maintenance: § 205-7 requires written notice to the owner and the mortgagee, by mail or hand delivery, with a deadline.
- Building: § 127-5A (notices and orders) and § 127-7 (penalties under 30-A M.R.S. § 4452(3)).
- Appeal: § 275-6.2E(1) sets 30 days to the Zoning Board of Appeals for zoning decisions. 30-A M.R.S. § 2691(4) makes a notice of violation under a land use ordinance appealable unless the ordinance says otherwise, and gives a decision not timely appealed preclusive effect.
- Keep postal receipts or a return of service for the file (Legal Issues Manual, p. 92).
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
name = "inspection_date"
label = "Date of inspection"
kind = "date"
required = true
section = "Violation"

[[fields]]
name = "oral_notice_date"
label = "Date of oral notice (optional)"
kind = "date"
section = "Violation"

[[fields]]
name = "section_cited"
label = "Section or sections violated"
kind = "text"
required = true
section = "Violation"
help = "Exact citation, for example § 205-4C or § 275-4.26B(2). Check it against eCode360."

[[fields]]
name = "facts"
label = "Facts observed"
kind = "textarea"
rows = 6
required = true
ai = true
ai_prompt = "the facts paragraph of a notice of violation: what was observed, where and when"
section = "Violation"

[[fields]]
name = "corrective_action"
label = "Corrective action ordered"
kind = "textarea"
rows = 4
required = true
section = "Order"
help = "Write it as an order: what must be done, removed or stopped."

[[fields]]
name = "correct_by"
label = "Correct by"
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
from = "letter_date"
to = "correct_by"
days = 1
message = "The correction deadline is after the date of the letter."
+++
{letter_date_long}

**{delivery_method}**

{owner_name}
{owner_address}

?{mortgagee_block} {mortgagee_block}

**Re: Notice of violation and order to correct**
Property: {property_address}
?{map_lot} Tax map and lot: {map_lot}
?{case_ref} City case: {case_ref}

Dear {owner_name}:

On {inspection_date_long}, I inspected the property at {property_address}. This letter is a written notice of violation of {chapter} of the Code of the City of Waterville and an order to correct the violation.

?{oral_notice_date} On {oral_notice_date_long}, I told you of this violation in person. This letter confirms that notice.

## Violation

{facts}

These conditions violate {section_cited} of the Code of the City of Waterville. {duty_line}

## Order

You are ordered to take the following corrective action no later than **{correct_by_long}**:

{corrective_action}

I will inspect the property again after that date to confirm that the violation has been corrected.

## Penalties

{penalty_text}

?{prior_text} {prior_text}

If the City is the prevailing party in court, it must be awarded reasonable attorney fees, expert witness fees and costs, unless the court finds that special circumstances make the award unjust (30-A M.R.S. § 4452(3)(D)). The court may also order the violation corrected or abated (30-A M.R.S. § 4452(3)(C)).

## Your right to appeal

{appeal_text}

## Resolving this notice

You may contact this office to discuss resolving the violation by an administrative consent agreement. Section 5-2.10B of the City Code authorizes the City Manager to enter into administrative consent agreements that eliminate violations and recover fines without court action.

If you have questions about this notice, call the Code Enforcement Office at {office_phone}.

Sincerely,

{signer_name}
{signer_title}
City of Waterville, Code Enforcement Office

?{cc_line} cc: {cc_line}
