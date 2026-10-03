+++
title = "ZBA hearing notice"
group = "Zoning notices"
order = 60
description = "Notice of a Zoning Board of Appeals public hearing for mailing to owners within 300 feet and for the newspaper (§ 275-6.2H)."
notes = """
§ 275-6.2H, Zoning Board of Appeals procedure:

- (2) $25 fee plus the cost of advertising; the CEO issues a dated receipt.
- (3) The CEO schedules the hearing within 45 days of the filing of the application.
- (4) Notice of the day, time and place is given to the applicant and published at least two times in a newspaper in general circulation in Waterville, the first publication not less than 14 days before the hearing. The notice identifies the property, the applicant and the nature of the application.
- (5) A copy goes by first class mail to the owners of all property within 300 feet, at least 14 days before the hearing. Owners are the parties the Assessor lists as those against whom taxes are assessed; send to the last-known address and keep the list in the record.
- (6) Notify the Planning Board forthwith after the filing.
- Shoreland variances: send the application to Maine DEP 20 days before the Board acts (§ 275-6.2E(4)(c)).
"""

[[fields]]
name = "applicant_name"
label = "Applicant"
kind = "text"
required = true
section = "Application"

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
required = true
from_case = "map_lot"
section = "Application"

[[fields]]
name = "application_kind"
label = "Kind of application"
kind = "select"
required = true
section = "Application"
options = [
  { value = "admin_appeal", label = "Administrative appeal of a CEO decision (§ 275-6.2E(1))" },
  { value = "variance", label = "Variance (§ 275-6.2E(4))" },
  { value = "misc_appeal", label = "Miscellaneous appeal (§ 275-6.2E(3))" },
  { value = "referral", label = "Referral by the Code Enforcement Officer (§ 275-6.2E(2))" },
]

[[fields]]
name = "application_summary"
label = "Nature of the application"
kind = "textarea"
rows = 4
required = true
section = "Application"
help = "What the applicant asks for, in plain words. Name the section involved."

[[fields]]
name = "filed_date"
label = "Date the application was filed"
kind = "date"
required = true
section = "Application"

[[fields]]
name = "shoreland"
label = "Variance in the shoreland zone?"
kind = "select"
default = "no"
section = "Application"
options = [
  { value = "no", label = "No" },
  { value = "yes", label = "Yes" },
]

[[fields]]
name = "dep_sent_date"
label = "Date the application went to Maine DEP"
kind = "date"
section = "Application"
required_when = { shoreland = ["yes"] }

[[fields]]
name = "hearing_date"
label = "Hearing date"
kind = "date"
required = true
section = "Hearing"

[[fields]]
name = "hearing_time"
label = "Hearing time"
kind = "text"
required = true
section = "Hearing"
help = "For example 6:00 p.m."

[[fields]]
name = "hearing_place"
label = "Hearing place"
kind = "text"
required = true
section = "Hearing"

[variants.application_kind.admin_appeal]
kind_text = "an administrative appeal of a decision of the Code Enforcement Officer under § 275-6.2E(1)"

[variants.application_kind.variance]
kind_text = "a variance under § 275-6.2E(4)"

[variants.application_kind.misc_appeal]
kind_text = "a miscellaneous appeal under § 275-6.2E(3)"

[variants.application_kind.referral]
kind_text = "a matter referred to the Board by the Code Enforcement Officer under § 275-6.2E(2)"

[[computed]]
name = "hearing_limit"
from = "filed_date"
days = 45

[[computed]]
name = "notice_by"
from = "hearing_date"
days = -14

[[checks]]
kind = "max_days"
from = "filed_date"
to = "hearing_date"
days = 45
message = "The hearing is within 45 days of the filing (§ 275-6.2H(3))."

[[checks]]
kind = "min_days"
from = "letter_date"
to = "hearing_date"
days = 14
message = "This notice is dated at least 14 days before the hearing, as mailing and the first publication require (§ 275-6.2H(4), (5))."

[[checks]]
kind = "min_days"
from = "dep_sent_date"
to = "hearing_date"
days = 20
message = "Maine DEP had the shoreland variance application at least 20 days before the hearing (§ 275-6.2E(4)(c)); the Board may not act sooner."
when = { shoreland = ["yes"] }
+++
# Notice of public hearing

**City of Waterville Zoning Board of Appeals**

The Waterville Zoning Board of Appeals will hold a public hearing on **{hearing_date_long} at {hearing_time}** at {hearing_place} on the following application.

- **Applicant:** {applicant_name}
- **Property:** {property_address} (tax map and lot {map_lot})
- **Application:** {kind_text}
- **Nature of the application:** {application_summary}

You are receiving this notice by first class mail because the Assessor's records list you as the owner of property within 300 feet of the property involved (§ 275-6.2H(5) of the Code of the City of Waterville).

Any person may attend the hearing. A party may appear in person, or by agent or attorney (§ 275-6.2H(7)). Written comments may be sent to the Code Enforcement Office, 7 College Avenue, Waterville, Maine 04901, before the hearing. [VERIFY: that the Board takes written comments into its record; § 275-6.2H does not say.] Questions: {office_phone}.

Dated {letter_date_long}.

{signer_name}
{signer_title}
City of Waterville, Code Enforcement Office, for the Zoning Board of Appeals
