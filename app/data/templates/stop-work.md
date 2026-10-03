+++
title = "Stop-work order"
group = "Enforcement"
order = 40
description = "Order to stop illegal work at once, for posting on site and for the written follow-up."
shared = ["_violation_types.toml"]
notes = """
Authority: § 275-6.1A(1) (the CEO "shall order ... discontinuance of any illegal work being done") and § 127-5A (notices or orders to secure the necessary safeguards during construction and to remove illegal or unsafe conditions).

The MOCA Legal Issues Manual (2017), ch. 7, p. 90, describes oral notice first, then a stop-work notice posted in a conspicuous place when the person doing the work is not there, then a written notice. Use the first notice of violation as the written follow-up if the work continues.

No ordinance text found in the corpus states a separate penalty for removing a posted order, so this template does not claim one.
"""

[[fields]]
name = "owner_name"
label = "Owner"
kind = "text"
required = true
from_case = "owner"
section = "Recipient"

[[fields]]
name = "owner_address"
label = "Owner mailing address"
kind = "textarea"
rows = 3
section = "Recipient"

[[fields]]
name = "contractor"
label = "Contractor or person doing the work (optional)"
kind = "text"
section = "Recipient"

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
label = "Date the work was observed"
kind = "date"
required = true
section = "Violation"

[[fields]]
name = "section_cited"
label = "Section or sections violated"
kind = "text"
required = true
section = "Violation"
help = "For work without a permit, § 127-2A (building) or the Chapter 275 section that requires the permit."

[[fields]]
name = "work_description"
label = "Work that must stop"
kind = "textarea"
rows = 5
required = true
ai = true
ai_prompt = "the description of the work observed that must stop: what work, where on the property, and when it was observed"
section = "Violation"

[[fields]]
name = "resume_conditions"
label = "Before work may resume"
kind = "textarea"
rows = 3
required = true
default = "Obtain every required permit from the Code Enforcement Office and receive written approval from this office to resume."
section = "Order"

[[fields]]
name = "posted_at"
label = "Where the order was posted (optional)"
kind = "text"
section = "Order"
help = "For example: front door of the garage. Leave blank if it was handed over."

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
join = ["cc_required"]
sep = "; "
+++
# STOP WORK ORDER

**Date:** {letter_date_long}
**Property:** {property_address}
?{map_lot} **Tax map and lot:** {map_lot}
?{case_ref} **City case:** {case_ref}

**To:** {owner_name}
?{owner_address} {owner_address}
?{contractor} **And to:** {contractor}

## Order

On {inspection_date_long}, I observed the following work at this property:

{work_description}

This work violates {section_cited} of the Code of the City of Waterville. {duty_line}

You are ordered to **stop all of the work described above immediately**. This order applies to the owner and to every contractor, builder and agent doing the work.

## Before work may resume

{resume_conditions}

?{posted_at} This order was posted at the property ({posted_at}) on {letter_date_long}.

## Penalties

{penalty_text}

## Your right to appeal

{appeal_text}

Questions: Code Enforcement Office, {office_phone}.

{signer_name}
{signer_title}
City of Waterville, Code Enforcement Office

?{cc_line} cc: {cc_line}
