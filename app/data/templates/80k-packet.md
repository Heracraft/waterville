+++
title = "Rule 80K packet checklist"
group = "Court"
order = 80
description = "Checklist for a Rule 80K land use citation and complaint: owners from registry deeds, attested ordinance copies, service, filing, hearing date and the penalty computation."
letterhead = false
shared = ["_violation_types.toml", "_penalty.toml"]
notes = """
Source: MOCA Rule 80K Manual (2017), chs. 4 and 5, pp. 12-24, and Appendix A. The manual is training guidance written against the rule as it stood in 2017. Every timing and content rule from it is tagged [VERIFY] until someone checks the current text of M.R. Civ. P. 80K and Rule 4.

- 30-A M.R.S. § 4452(1)(C): a code enforcement officer represents the municipality in District Court only when specifically authorized by the municipal officers.
- § 275-6.1A(3)(a): for zoning violations, the CEO notifies the City Solicitor and City Council, and the City acting through the Council may institute proceedings. The 80K Manual suggests a case-specific authorization letter when an ordinance involves the municipal officers in litigation.
- Penalty tiers: 30-A M.R.S. § 4452(3); Chapter 205 sets $100 per day beyond the correction period (§ 205-8).
"""

[[fields]]
name = "defendant_name"
label = "Defendant (person who committed the violation)"
kind = "text"
required = true
from_case = "owner"
section = "Parties"

[[fields]]
name = "defendant_address"
label = "Defendant address"
kind = "textarea"
rows = 2
required = true
section = "Parties"

[[fields]]
name = "owner_name"
label = "Owner or owners of record, if different"
kind = "text"
section = "Parties"
help = "From the deed at the Kennebec County Registry of Deeds, not assessor records."

[[fields]]
name = "owner_address"
label = "Owner address"
kind = "textarea"
rows = 2
section = "Parties"

[[fields]]
name = "deed_book"
label = "Registry of Deeds book"
kind = "text"
required = true
section = "Parties"

[[fields]]
name = "deed_page"
label = "Registry of Deeds page"
kind = "text"
required = true
section = "Parties"

[[fields]]
name = "property_address"
label = "Property address"
kind = "text"
required = true
from_case = "address"
section = "Parties"

[[fields]]
name = "map_lot"
label = "Tax map and lot"
kind = "text"
required = true
from_case = "map_lot"
section = "Parties"

[[fields]]
name = "case_ref"
label = "City case number"
kind = "text"
from_case = "id"
section = "Parties"

[[fields]]
name = "sections_violated"
label = "Sections violated"
kind = "text"
required = true
section = "Violation"

[[fields]]
name = "violation_description"
label = "Brief description of the violation"
kind = "textarea"
rows = 5
required = true
ai = true
ai_prompt = "a brief description of the violation for a Rule 80K land use citation and complaint: what, where, and the inclusive dates it continued"
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
name = "injunction"
label = "Ask for a preliminary injunction?"
kind = "select"
default = "no"
section = "Violation"
options = [
  { value = "no", label = "No" },
  { value = "yes", label = "Yes" },
]

[[fields]]
name = "relief"
label = "Relief requested"
kind = "textarea"
rows = 3
required = true
default = "Civil penalties under 30-A M.R.S. § 4452(3); an order to correct or abate the violation (§ 4452(3)(C)); reasonable attorney fees, expert witness fees and costs (§ 4452(3)(D))."
section = "Violation"

[[fields]]
name = "court"
label = "Court"
kind = "text"
required = true
default = "Maine District Court"
section = "Court dates"
help = "Confirm the court location and get the hearing date from the clerk."

[[fields]]
name = "service_date"
label = "Date of service (planned or done)"
kind = "date"
section = "Court dates"

[[fields]]
name = "hearing_date"
label = "Hearing date from the clerk"
kind = "date"
section = "Court dates"

[variants.injunction.no]
injunction_text = "No preliminary injunction requested."

[variants.injunction.yes]
injunction_text = "Preliminary injunction requested; plan for the court to set an early hearing on it. [VERIFY: Rule 80K procedure for injunctive relief.]"

# M.R. Civ. P. 80K (rules text of 2026-06-01) sets no minimum period between
# service and the appearance date and no fixed filing period: the original is
# filed "as soon as practicable after service" (80K(b)(3)). The 20-day figures
# in the 2017 manual are shown as guidance only, with no computed date.

[[computed]]
name = "appeal_by"
from = "letter_date"
days = 30

[[computed]]
name = "atf_by"
from = "letter_date"
days = 30

[[checks]]
kind = "min_days"
from = "service_date"
to = "hearing_date"
days = 0
message = "The hearing date falls on or after the date of service."

[[checks]]
kind = "min_days"
from = "violation_start"
to = "violation_end"
days = 0
message = "The violation dates run forward in time."
+++
# Rule 80K packet checklist

**Defendant:** {defendant_name}
**Property:** {property_address} (tax map and lot {map_lot})
?{case_ref} **City case:** {case_ref}
**Ordinance:** {chapter}
**Prepared by:** {signer_name}, {signer_title}, {letter_date_long}

Internal working document. It does not replace the Land Use Citation and Complaint form or the City Solicitor's review.

## Authority

- [ ] Written authorization from the municipal officers for {signer_name} to represent the City in District Court (30-A M.R.S. § 4452(1)(C)), filed with the court clerk the first time this official files a complaint (80K Manual 2017, p. 24) [VERIFY]
- [ ] Certificate of familiarity with court procedures, filed with the authorization when first appearing (M.R. Civ. P. 80K(h); 80K Manual 2017, p. 24)
- [ ] {notify_check}
- [ ] Municipal officers kept informed that a Rule 80K action is being considered (80K Manual 2017, p. 20)

## Ownership

- [ ] Owner or owners identified from the deed at the Kennebec County Registry of Deeds, Book {deed_book}, Page {deed_page}, not from assessor records (80K Manual 2017, pp. 22-23) [VERIFY]
?{owner_name} - [ ] Owner of record: {owner_name}, {owner_address}
- [ ] Attested copy of the deed for the hearing (80K Manual 2017, Appendix evidence list)

## Notices already sent

- [ ] First notice of violation, {first_notice_date_long}, with postal receipt or return of service
?{second_notice_date} - [ ] Second notice, {second_notice_date_long}, with postal receipt or return of service
?{final_notice_date} - [ ] Final notice, {final_notice_date_long}, with postal receipt or return of service
- [ ] Attested copies of each notice for evidence

## Citation and complaint contents

The 80K Manual (2017), pp. 12-13, lists what the citation and complaint must state. [VERIFY against the current M.R. Civ. P. 80K.]

- [ ] Name and address of the defendant: {defendant_name}, {defendant_address}
- [ ] Name and address of each owner, if different from the defendant
- [ ] Time and place of the violation, with inclusive dates for a continuing violation: {violation_start_long} through {violation_end_long} ({inclusive_days} days)
- [ ] Brief description of the violation: {violation_description}
- [ ] Summary of the provisions violated ({sections_violated}) and of the possible penalties ({tier_summary})
- [ ] Relief requested: {relief}
- [ ] {injunction_text}
- [ ] Time, date and place to appear, set with the court clerk: {court}, {hearing_date_long}
- [ ] Statement that the defendant was advised of the violation
- [ ] Signature and title of the official filing the complaint
- [ ] Defendant's signature acknowledging receipt, or a statement that the defendant refused or could not sign
- [ ] Statement that if the defendant fails to appear, the court may enter a default judgment

## Attachments

- [ ] Copy of each ordinance section violated, attested by the City Clerk, with a statement of where the complete text can be obtained, for service on the defendant and each owner and for filing (80K Manual 2017, pp. 18-19, 23-24) [VERIFY]. Sections: {attest_sections}.
- [ ] Copies of variances, approvals, conditions or consent agreements that affect the property (80K Manual 2017, p. 19)
- [ ] Affidavit of the enforcement official (optional)

## Service and filing

- [ ] Serve the defendant under M.R. Civ. P. 4, and the property owner, if appropriate, by any appropriate method provided in Rule 4 (M.R. Civ. P. 80K(b)(2)), with the citation and complaint and the attested ordinance copy; write the date of service on the copies left (80K Manual 2017, pp. 22-23)
- [ ] Appearance date from the clerk: {hearing_date_long}. Rule 80K sets no minimum period between service and the appearance date; the 2017 manual (p. 12) suggests allowing at least 20 days. [VERIFY: against the court's current Land Use Citation and Complaint form.]
- [ ] File the original citation and complaint, with the return of service completed, with the court clerk as soon as practicable after service (M.R. Civ. P. 80K(b)(3)). Service was on {service_date_long}.
- [ ] Keep photocopies of everything filed, including cover letters

## Evidence for the hearing

- [ ] Extra attested copy of each ordinance section
- [ ] Attested deed, zoning map and tax map showing the property's location
- [ ] Dated photographs taken by the official, with the date each was taken
- [ ] Inspection notes and the case timeline
- [ ] Reinspect the property shortly before the hearing so testimony is current (Legal Issues Manual 2017, p. 92)

## Penalty computation

- **Tier:** {penalty_tier_text}
- **Range per day:** {penalty_range_per_day}
- **Days counted:** {penalty_days} ({violation_start_long} through {violation_end_long}, inclusive)
- **Range for the span:** {penalty_min_total} to {penalty_max_total}
?{penalty_requested_total} - **Requested:** {penalty_requested_total}
?{penalty_warnings} - **Check:** {penalty_warnings}

?{penalty_verify} {penalty_verify}

{penalty_note}
