+++
title = "Permit decision with findings and conclusions"
group = "Decisions"
order = 70
description = "Decision letter on a permit or approval with findings of fact and conclusions of law on every review standard."
notes = """
Practice: the MOCA Legal Issues Manual (2017), pp. 65-67, advises written findings of fact and conclusions of law for approvals as well as denials and conditional approvals, citing the Right to Know Law, 1 M.R.S. § 407, and Mills v. Town of Eliot, 2008 ME 134, 955 A.2d 258, where the court remanded a decision because the CEO had made no findings. [VERIFY: Mills v. Town of Eliot and 1 M.R.S. § 407 against the primary text; the corpus holds only the manual's summary.]

- Findings of fact: the applicant and their relationship to the property, the location, the project and its key elements, and the evidence submitted by the applicant and by others.
- Conclusions of law: link those facts to each review standard in the ordinance. Address every standard, including after one that fails (Legal Issues Manual, p. 66).
- Special exceptions: standards in § 275-5.20B(1)-(8), conditions in § 275-5.20C, duration in § 275-5.20D. Send the abutter decision letter too (§ 275-5.20A(2)(f)).
- Appeal: § 275-6.2E(1) gives 30 days to appeal a CEO decision under Chapter 275 to the ZBA.
"""

[[fields]]
name = "applicant_name"
label = "Applicant"
kind = "text"
required = true
section = "Application"

[[fields]]
name = "applicant_address"
label = "Applicant mailing address"
kind = "textarea"
rows = 3
required = true
section = "Application"

[[fields]]
name = "applicant_relation"
label = "Applicant's relationship to the property"
kind = "text"
required = true
default = "owner"
section = "Application"
help = "For example owner, tenant with written authority, or purchaser under contract."

[[fields]]
name = "property_address"
label = "Property address"
kind = "text"
required = true
from_case = "address"
section = "Application"

[[fields]]
name = "map_lot"
label = "Tax map and lot"
kind = "text"
from_case = "map_lot"
section = "Application"

[[fields]]
name = "zoning_district"
label = "Zoning district"
kind = "text"
section = "Application"

[[fields]]
name = "application_kind"
label = "Kind of permit or approval"
kind = "select"
required = true
section = "Application"
options = [
  { value = "special_exception", label = "Special exception permit (§ 275-5.20)" },
  { value = "zoning_other", label = "Other approval under Chapter 275 (Zoning)" },
  { value = "building", label = "Building permit (Chapter 127)" },
  { value = "other", label = "Other permit" },
]

[[fields]]
name = "permit_name"
label = "Permit or approval, as named in the ordinance"
kind = "text"
required = true
section = "Application"
help = "For example: special exception permit for a home occupation, § 275-4.11."

[[fields]]
name = "standards_section"
label = "Sections that set the review standards"
kind = "text"
required = true
section = "Application"

[[fields]]
name = "application_date"
label = "Date the complete application was received"
kind = "date"
required = true
section = "Application"

[[fields]]
name = "findings"
label = "Findings of fact"
kind = "textarea"
rows = 10
required = true
ai = true
ai_prompt = "numbered findings of fact for a permit decision: the applicant and their relationship to the property, the location, the project and its key elements, and the evidence submitted. Number each finding"
section = "Findings and conclusions"
default = """1. The applicant is {applicant_name}, the {applicant_relation} of the property at {property_address}.
2. [FILL: describe the project and its key elements: use, size, setbacks, parking, hours.]
3. [FILL: list the evidence submitted by the applicant: plans, letters, reports.]
4. [FILL: list comments or evidence from abutters or others, or state that none were received.]"""

[[fields]]
name = "conclusions"
label = "Conclusions of law"
kind = "textarea"
rows = 10
section = "Findings and conclusions"
help = "Leave blank for a special exception to get one paragraph per § 275-5.20B standard to fill in."

[[fields]]
name = "decision"
label = "Decision"
kind = "select"
required = true
section = "Decision"
options = [
  { value = "approved", label = "Approved" },
  { value = "approved_conditions", label = "Approved with conditions" },
  { value = "denied", label = "Denied" },
]

[[fields]]
name = "conditions"
label = "Conditions of approval"
kind = "textarea"
rows = 5
section = "Decision"
required_when = { decision = ["approved_conditions"] }

[variants.application_kind.special_exception]
standards_block = """For each standard of § 275-5.20B, the Code Enforcement Officer concludes as follows. A special exception must meet every standard.

1. **Definition and other law (§ 275-5.20B(1)).** [FILL: the use meets or does not meet the definition for this special exception and complies or does not comply with applicable state and federal law, because ... (findings nos. ...)]
2. **Character of the neighborhood (§ 275-5.20B(2)).** [FILL: compatible or not with the general character of the neighborhood in design, scale and bulk, because ...]
3. **Effect on abutting property (§ 275-5.20B(3)).** [FILL: noise, vibrations, fumes, odor, dust, light or glare, because ...]
4. **Emergency access (§ 275-5.20B(4)).** [FILL: adequate access for emergency vehicles, because ...]
5. **Traffic and lighting (§ 275-5.20B(5)).** [FILL: no safety hazard to motorists on adjacent streets from exterior lighting or traffic, because ...]
6. **Buffers, screening and landscaping (§ 275-5.20B(6)).** [FILL: meets the district requirements, because ...]
7. **Public facilities and environment (§ 275-5.20B(7)).** [FILL: wastewater and solid waste, erosion, stormwater and snow runoff, fire protection water, hazardous materials, as applicable ...]
8. **Performance standards (§ 275-5.20B(8)).** [FILL: conforms to the Article IV performance standards that apply ...]"""
kind_appeal = "Under § 275-6.2E(1) of the Code of the City of Waterville, any interested party may appeal this decision to the Waterville Zoning Board of Appeals within 30 days of the decision, which is by **{appeal_by_long}**. The Board hears the appeal de novo. File the appeal with the Code Enforcement Office; the fee is $25 plus the cost of advertising (§ 275-6.2H(2))."
kind_extra = "Under § 275-5.20D, a special exception permit is valid for as long as the property owner to whom it was issued continues to operate the specific use and remains in compliance with Chapter 275. It expires if that owner stops the use for any reason or sells the property. Under § 275-5.20C, a violation of a condition of approval is a violation of Chapter 275."

[variants.application_kind.zoning_other]
standards_block = "[FILL: for each review standard in {standards_section}, state the standard, the findings that bear on it (by number) and whether it is met. Address every standard.]"
kind_appeal = "Under § 275-6.2E(1) of the Code of the City of Waterville, any interested party may appeal this decision to the Waterville Zoning Board of Appeals within 30 days of the decision, which is by **{appeal_by_long}**. The Board hears the appeal de novo. File the appeal with the Code Enforcement Office; the fee is $25 plus the cost of advertising (§ 275-6.2H(2))."
kind_extra = ""

[variants.application_kind.building]
standards_block = "[FILL: for each requirement in {standards_section} and the Maine Uniform Building and Energy Code that applies, state the requirement, the findings that bear on it (by number) and whether it is met.]"
kind_appeal = "[VERIFY: the appeal route and deadline for a building permit decision under Chapter 127 and the Maine Uniform Building and Energy Code. Chapter 127 names no appeal board; under 30-A M.R.S. § 2691(4) a board of appeals may hear only the subject matter a charter or ordinance specifies. The likely route is 30-A M.R.S. § 4103(5), which allows an appeal from the licensing authority's refusal to grant a permit to the municipal officers or to a board of appeals established under section 2691; 30-A M.R.S. § 4101 applies that subchapter to any municipal ordinance requiring a permit in connection with the construction, demolition, improvement or alteration of any building. Section 4103(5) sets no deadline.]"
kind_extra = ""

[variants.application_kind.other]
standards_block = "[FILL: for each review standard in {standards_section}, state the standard, the findings that bear on it (by number) and whether it is met. Address every standard.]"
kind_appeal = "[VERIFY: the appeal route and deadline for this kind of decision.]"
kind_extra = ""

[variants.decision.approved]
decision_text = "Based on these findings of fact and conclusions of law, the application for a {permit_name} is **approved**."

[variants.decision.approved_conditions]
decision_text = "Based on these findings of fact and conclusions of law, the application for a {permit_name} is **approved with the conditions below**.\n\n## Conditions of approval\n\n{conditions}"

[variants.decision.denied]
decision_text = "Based on these findings of fact and conclusions of law, the application for a {permit_name} is **denied** because the standards named above are not met."

[[computed]]
name = "appeal_by"
from = "letter_date"
days = 30
+++
{letter_date_long}

{applicant_name}
{applicant_address}

**Re: Decision on application for a {permit_name}**
Property: {property_address}
?{map_lot} Tax map and lot: {map_lot}
?{zoning_district} Zoning district: {zoning_district}

Dear {applicant_name}:

This letter is the decision of the Code Enforcement Officer on your application received {application_date_long}. It states the findings of fact and the conclusions of law on each review standard in {standards_section}.

## Findings of fact

{findings}

## Conclusions of law

?{conclusions} {conclusions}
!{conclusions} {standards_block}

## Decision

{decision_text}

?{kind_extra} {kind_extra}

## Right to appeal

{kind_appeal}

If you have questions about this decision, call the Code Enforcement Office at {office_phone}.

Sincerely,

{signer_name}
{signer_title}
City of Waterville, Code Enforcement Office
