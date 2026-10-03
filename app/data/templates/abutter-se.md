+++
title = "Special exception abutter notice"
group = "Zoning notices"
order = 50
description = "First-class mailing to abutters at least 14 days before a special exception permit issues (§ 275-5.20A(2))."
notes = """
§ 275-5.20A(2): at least 14 days before issuing a special exception permit, the CEO notifies abutting property owners by first class mail of the nature of the application, the name of the applicant and the address of the property. The mailing gives abutters a fourteen-day comment period. "Abutter" is defined in § 275-3.2 and includes the property across the street, road, public way or private way.

- Keep the list of names and addresses the notice went to (§ 275-5.20A(2)(d)).
- A property owner's failure to receive the notice does not invalidate the CEO's action (§ 275-5.20A(2)(e)).
- When the permit issues, send the second letter with the appeal right (template: special exception decision to abutters).
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
name = "zoning_district"
label = "Zoning district"
kind = "text"
required = true
section = "Application"

[[fields]]
name = "district_section"
label = "Section listing the special exception"
kind = "text"
required = true
section = "Application"
help = "The district regulation that lists this use as a special exception, for example § 275-5.x."

[[fields]]
name = "use_description"
label = "Nature of the application"
kind = "textarea"
rows = 4
required = true
section = "Application"
help = "The proposed use as the applicant describes it (§ 275-5.20A(1)(b))."

[[fields]]
name = "mailing_date"
label = "Date of mailing"
kind = "date"
required = true
default = "today"
section = "Application"

[[computed]]
name = "comment_by"
from = "mailing_date"
days = 14
+++
{letter_date_long}

**By first class mail**

To: Abutting property owners

**Re: Application for a special exception permit**
Property: {property_address}
Tax map and lot: {map_lot}

Dear property owner:

The Code Enforcement Office has received an application for a special exception permit for property that abuts yours. Section 275-5.20A(2) of the Code of the City of Waterville requires the Code Enforcement Officer to notify abutting property owners by first class mail at least 14 days before issuing a special exception permit, so that abutters have a fourteen-day comment period. You are receiving this notice as an abutter as defined in § 275-3.2.

## The application

- **Applicant:** {applicant_name}
- **Property:** {property_address} (tax map and lot {map_lot})
- **Zoning district:** {zoning_district}
- **Use proposed:** {use_description}
- **Special exception listed in:** {district_section}

## How the application is decided

The Code Enforcement Officer will decide the application under § 275-5.20B. The standards include whether the use will be compatible with the general character of the neighborhood in design, scale and bulk; whether it will have a significant detrimental effect on the use and peaceful enjoyment of abutting property from noise, vibrations, fumes, odor, dust, light or glare; emergency vehicle access; traffic and lighting safety on adjacent streets; buffers, screening and landscaping; and adequate provision for wastewater, solid waste, erosion, stormwater, fire protection water and hazardous materials.

## Comments

To comment, write to the Code Enforcement Office, 7 College Avenue, Waterville, Maine 04901, or call {office_phone}, by **{comment_by_long}**. The permit will not be issued before that date.

If the permit is issued, you will receive a second letter telling you of the decision and of your right to appeal it (§ 275-5.20A(2)(f)).

Sincerely,

{signer_name}
{signer_title}
City of Waterville, Code Enforcement Office
