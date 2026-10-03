+++
title = "Rule 80K cover memo"
group = "Court"
order = 85
description = "Internal memo asking for authorization or referral for a Rule 80K land use action, with the notice history and the penalty range."
shared = ["_violation_types.toml", "_penalty.toml"]
notes = """
The 80K Manual (2017), p. 20, advises keeping the municipal officers informed of individual enforcement actions and telling them whenever a Rule 80K action is being considered. Where an ordinance involves the municipal officers in litigation, it suggests a letter authorizing the specific case in addition to the general authorization (p. 24). For zoning, § 275-6.1A(3)(a) requires notice to the City Solicitor and City Council, and the City, acting through the Council, may institute proceedings.

30-A M.R.S. § 4452(1)(C): a CEO represents the municipality in District Court only when specifically authorized by the municipal officers.
"""

[[fields]]
name = "memo_to"
label = "To"
kind = "text"
required = true
default = "City Solicitor"
section = "Memo"

[[fields]]
name = "memo_cc"
label = "Copy to"
kind = "text"
default = "City Manager"
section = "Memo"

[[fields]]
name = "request"
label = "Action requested"
kind = "select"
required = true
section = "Memo"
options = [
  { value = "authorize", label = "Authorize the CEO to file a Rule 80K land use citation for this case" },
  { value = "refer", label = "Accept referral of this case for prosecution by the City Solicitor" },
]

[[fields]]
name = "defendant_name"
label = "Defendant"
kind = "text"
required = true
from_case = "owner"
section = "Case"

[[fields]]
name = "property_address"
label = "Property address"
kind = "text"
required = true
from_case = "address"
section = "Case"

[[fields]]
name = "map_lot"
label = "Tax map and lot"
kind = "text"
from_case = "map_lot"
section = "Case"

[[fields]]
name = "case_ref"
label = "City case number"
kind = "text"
from_case = "id"
section = "Case"

[[fields]]
name = "sections_violated"
label = "Sections violated"
kind = "text"
required = true
section = "Violation"

[[fields]]
name = "summary"
label = "Summary of the violation"
kind = "textarea"
rows = 6
required = true
ai = true
ai_prompt = "a factual summary of the violation and its history for an internal memo to the City Solicitor: what, where, since when, and what the owner has done in response"
section = "Violation"

[[fields]]
name = "first_notice_date"
label = "First notice of violation"
kind = "date"
required = true
section = "Violation"

[[fields]]
name = "second_notice_date"
label = "Second notice"
kind = "date"
section = "Violation"

[[fields]]
name = "final_notice_date"
label = "Final notice"
kind = "date"
section = "Violation"

[[fields]]
name = "last_inspection_date"
label = "Most recent inspection"
kind = "date"
required = true
section = "Violation"

[[fields]]
name = "consent_efforts"
label = "Consent agreement efforts"
kind = "textarea"
rows = 3
default = "None to date."
section = "Violation"

[[fields]]
name = "attachments"
label = "Attachments"
kind = "textarea"
rows = 4
default = """- Notices of violation with postal receipts
- Photographs with dates
- Deed from the Kennebec County Registry of Deeds
- Rule 80K packet checklist"""
section = "Violation"

[variants.request.authorize]
request_text = "I ask that the City authorize me, for this case, to file a land use citation and complaint in the Maine District Court under Rule 80K of the Maine Rules of Civil Procedure and to represent the City at the hearing. Under 30-A M.R.S. § 4452(1)(C), a code enforcement officer may represent the municipality in District Court when specifically authorized by the municipal officers."

[variants.request.refer]
request_text = "I ask that the City Solicitor take this case for prosecution, by a Rule 80K land use citation and complaint or another action the Solicitor chooses."

[[computed]]
name = "appeal_by"
from = "letter_date"
days = 30

[[computed]]
name = "atf_by"
from = "letter_date"
days = 30
+++
# Memorandum

**To:** {memo_to}
?{memo_cc} **Copy:** {memo_cc}
**From:** {signer_name}, {signer_title}
**Date:** {letter_date_long}
**Re:** Rule 80K land use enforcement, {property_address}
?{case_ref} **City case:** {case_ref}

## Request

{request_text}

## The violation

- **Defendant:** {defendant_name}
- **Property:** {property_address}
?{map_lot} - **Tax map and lot:** {map_lot}
- **Ordinance:** {chapter}
- **Sections violated:** {sections_violated}
- **Penalty tier:** {tier_summary}

{summary}

## Notice history

- First notice of violation: {first_notice_date_long}
?{second_notice_date} - Second notice: {second_notice_date_long}
?{final_notice_date} - Final notice: {final_notice_date_long}
- Most recent inspection: {last_inspection_date_long}; the violation continues.

**Consent agreement efforts:** {consent_efforts}

## Penalty range

- **Tier:** {penalty_tier_text}
- **Days counted:** {penalty_days}, {violation_start_long} through {violation_end_long}, inclusive
- **Range per day:** {penalty_range_per_day}
- **Range for the span:** {penalty_min_total} to {penalty_max_total}
?{penalty_requested_total} - **Amount I propose to request:** {penalty_requested_total}

?{penalty_verify} {penalty_verify}

{penalty_note}

## Attachments

{attachments}
