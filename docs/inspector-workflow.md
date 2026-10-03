# Serving Waterville's Code Inspector: Workflow Research and Integration Options

Prepared 2026-10-03 from six research passes over city web pages, the Waterville code corpus in this repo, Maine statutes and rules, MOCA training manuals, industry surveys and vendor material. The draft then went through three reviews: a working-CEO realism check, a fact-check and an engineering fit check. Each factual claim cites a URL or file path. Anything marked **(inferred)** has no direct source. Anything marked **(unverified)** came from a reviewer or a secondary source and still needs a primary-source check.

Repo paths below are relative to `/home/dev/waterville/.claude/worktrees/inspector-workflow/`.

## Executive summary

- **The inspector is a three-person office doing legal work on paper.** Waterville's Code Enforcement Office (Director Dan Bradstreet, CEO Adam Bradstreet, Ordinance Compliance Officer Todd Buckmore) issues permits from fillable PDFs, books inspections by phone and takes complaints by appointment. Every decision can be appealed de novo to the ZBA, so each one has to rest on a citable section.
- **Field inspections and complaint visits fill most of the day; a Q&A tool can't touch them.** The product helps at the desk: intake questions, code research across city and state law, enforcement letters and legal clocks. You should pitch it as a research desk for that part of the job.
- **The first slice is a gated "cite-it" staff mode.** Section numbers come first, the controlling text is quoted, and the answer shows the enforcement chain. Exact-citation lookup and copy buttons come with it. A staff key gates it and exempts it from the public rate limits, and every answer carries a "research aid" stamp. About one week of work, evaluated against the live index.
- **Several legal details need primary-source checks before any drafter or deadline tool ships.** The penalty tiers in 30-A §4452(3), NOV appealability under §2691(4), the §4103 30-day rule, and the Rule 80E and 80K timings all fall in this group. The draft got some of these wrong, and a tool that encodes them wrong does more harm than no tool.
- **Licensing and ownership come before anything that republishes or stores data.** eCode360's terms forbid republishing, ICC text needs a license, and the app runs in the developer's Azure subscription under a "City of Waterville" header. Written city authorization and a decision on who holds the records should come before copy-out features, NOV drafting, logging or complaint intake.

**"Flip."** No product, program, role or person called "Flip" turned up in code inspection, in Waterville, or in common municipal permitting software. Searches covered the web (2026-10-03), vendor directories and a grep of this repo. The likeliest explanation is a dictation error for "the city code inspector" **(inferred)**. Question 1 in section 7 asks the city to confirm.

---

## 1. The inspector in Waterville

### Office and staff
- **Office:** Code Enforcement at 7 College Avenue. Phone 207-680-4208, fax 207-873-1480. Open Mon-Thu, 7:00-5:00. Source: https://waterville-me.gov/218/Code-Enforcement. The office appears to share the building with the Fire Department **(inferred; not stated on the cited page)**.
- **Staff** (https://waterville-me.gov/m/directory/department?did=42):
  - Daniel (Dan) Bradstreet, Code Enforcement Director, 207-680-4231
  - Adam Bradstreet, Code Enforcement Officer, 207-680-4229
  - Todd Buckmore, Ordinance Compliance Officer, 207-680-4224. His duties are not published.
- **CEO secretary.** The building permit form says inspections are booked with a "CEO secretary" (https://www.waterville-me.gov/DocumentCenter/View/1336/Building-Permit-Application-PDF). That person is not in the staff directory. Who books inspections today is unknown.
- **History.** Dan Bradstreet was hired in 2017 to replace Garth Collins. Collins had run the office alone for about 12 years after a 2003-04 cut from 2.5 staff to 1 (https://www.centralmaine.com/2017/09/18/waterville-hires-new-code-enforcement-officer/).
- **Planning is a separate department.** City Planner Ann Beverage staffs the Planning Board (https://waterville-me.gov/236/Planning-Department). Dan Bradstreet attends Planning Board meetings as staff: he briefs zoning amendments and reports on whether approval conditions are met (https://www.waterville-me.gov/AgendaCenter/ViewFile/Minutes/_04082025-20).
- **Board of Zoning Appeals.** The CEO is the staff contact. The board hears appeals of CEO decisions filed within 30 days, de novo (https://waterville-me.gov/294/Board-of-Zoning-Appeals; `output/markdown/code/275-zoning.md` § 275-6.2E).
- **Fire Department coordination.** Fire runs the General Life Safety Review on building permits, rental registration, business license inspections and short-term rental inspections (sections 2.2 and 2.6). The Fire Chief may designate the Director of Code Enforcement to help with fire code work (§ 210-9, `output/markdown/code/210-public-safety.md`). How joint inspections and referrals work day to day is not documented anywhere we found.

### Legal role under Maine law
- **Definition and certification.** A CEO is a certified municipal employee who enforces laws in five areas: shoreland zoning, land use, internal plumbing, subsurface wastewater and building standards. A CEO must be certified within 12 months of hire, and certificates last 6 years (30-A M.R.S. §4451, https://legislature.maine.gov/statutes/30-A/title30-Asec4451.html). MOCA lists Legal Issues as its own certification area alongside the five, plus Rule 80K (https://www.maine.gov/moca/programs/code-enforcement/resources), and the 2009 CEO Info Guide says a CEO must pass the Legal Issues exam plus one specialty exam per area (`ecode/archived/decd-ceo-info-guide-2009.pdf`, pp.5-13). The current rule text in 08-003 CMR ch.1 should be checked for the Legal Issues requirement **(unverified)**.
- **Powers** (30-A §4452(1), https://legislature.maine.gov/statutes/30-A/title30-Asec4452.html):
  - Enter property at reasonable hours. Entering a building needs the owner's or occupant's consent.
  - Issue a summons.
  - Represent the town in District Court when the municipal officers authorize it.
- **Civil penalties** (30-A §4452(3), same URL, verified 2026-10-03). Keep these tiers separate in any tool:
  - Starting construction or a land use activity without a required permit: $100 minimum, $2,500 maximum (para. A).
  - A specific violation: $100 minimum, $5,000 maximum (para. B).
  - A violation of the listed shoreland laws in an area zoned for resource protection: up to $10,000 (para. B-1).
  - Up to $25,000 "when it is shown that there has been a previous conviction of the same party within the past 2 years" (para. F). A repeat complaint or a second NOV does not meet that test.
  - Per-day assessment: the introduction to subsection 3 says monetary penalties "may be assessed on a per-day basis." The statute has no sentence making each day a separate violation. Waterville's general penalty section uses that wording for city ordinances (§ 5-2.9).
  - A prevailing municipality must be awarded attorney fees, expert fees and costs unless special circumstances apply (para. D).
- **Rule 80K court work** needs a separate certification and written authorization from the municipal officers (80K Manual 2017, https://www.maine.gov/moca/sites/maine.gov.moca/files/80k-manual-2017.pdf).
- **MUBEC.** "The Maine Uniform Building and Energy Code must be enforced in a municipality that has more than 4,000 residents" (10 M.R.S. §9724(1), https://legislature.maine.gov/statutes/10/title10sec9724.html). Waterville has about 15,800 people **(2020 Census figure, not checked against a primary source here)**.
- **Rule renumbering.** MOCA now lists the MUBEC and CEO rules as 08-003 CMR chs.1-8. Its laws-and-rules page says chapters 2 through 8 took effect April 7, 2026 (https://www.maine.gov/moca/programs/code-enforcement/laws-rules). Chapter 1 (CEO certification) is listed under 08-003, but we found no effective date for it. The repo still cites 16-642 CMR (`ecode/state_sources.toml`).

### What the inspector issues or decides (city code)
- **Building permits, inspections, notices and orders, records for the life of the structure:** §§ 127-2, 127-5 (`output/markdown/code/127-building-and-energy-code.md`).
- **Certificates of occupancy.** § 127-6 says the CEO shall issue a CO "if requested" once the building meets MUBEC and the Life Safety Code. The building permit form and the life-safety review form both say a CO is needed before occupancy.
- **Discretionary zoning approvals** (all in `output/markdown/code/275-zoning.md`):
  - Special exceptions, which need a 14-day abutter mailing and a second letter giving appeal rights (§ 275-5.20)
  - Expansion of nonconforming uses (§ 275-4.2F)
  - Home occupations and day care (§§ 275-4.11, 275-4.16)
  - Fences over 6 ft (§ 275-4.26B(2))
  - Earth removal of 100-999 cu yd (§ 275-4.12C)
  - Chicken permits with a $25 inspection (§ 275-4.33F)
  - Jobsite trailer renewals (§ 275-4.31)
  - Disability-access permits (§ 275-6.2E(4)(g))
- **Shoreland.** The shoreland zone covers land within 250 ft of the Kennebec River and Messalonskee Stream. The Planning Board approves shoreland applications and the CEO issues the permit (§ 275-4.27B-F). The CEO also handles expansions and reconstruction of nonconforming shoreland structures, with footprint caps of 800 sq ft or 30% (1,000 sq ft or 30% within 75 ft) and a 90-day recording deadline for expansion plans (§ 275-4.27K(3)). Small fills, signs, temporary docks and access stairways in the stream protection district are CEO approvals too (§ 275-4.27H(8)(a), J). Vegetation clearing and timber harvesting jurisdiction were not researched.
- **Floodplain Administrator:** two-part flood hazard permits, a 72-hour review of the elevation certificate, certificates of compliance within 10 working days (`output/markdown/code/145-floodplain-management.md`).
- **Enforcement of other chapters:** property maintenance (Ch. 205), historic preservation (§ 161-12), subdivision and site plan conditions (§ 244-10.2), cannabis (§ 180-16).
- **Vacate orders:** the Fire Chief or CEO can order a structure vacated for up to 24 hours under imminent danger (§ 210-10).
- **Dangerous buildings.** 17 M.R.S. §§2851 and 2856 are in the corpus (`ecode/state_sources.toml`). They set up a separate process of council hearing, order and possible demolition, apart from the 24-hour vacate order. How Waterville runs that process was not researched, and it fits cases like 224 County Road (section 2.5).
- **Electrical:** a separate Municipal Electrical Inspector, appointed by the City Manager, covers 1- and 2-family work (§ 127-9). The person in that post is unknown.
- **Plumbing.** No building permit may issue for work involving plumbing until a plumbing permit under the Maine plumbing code is in hand (§ 275-4.27H(12)(b)). The permits page links the state HHE-211 plumbing form (https://waterville-me.gov/225/Building-Permit-Applications). Chapter 127 does not name the Local Plumbing Inspector. In a mostly sewered city, internal plumbing permits likely far outnumber subsurface permits **(inferred)**, and this report covers them only lightly.

---

## 2. The workflow, step by step

Unless noted, the city sources are https://waterville-me.gov/218/Code-Enforcement and the building permit PDF (https://www.waterville-me.gov/DocumentCenter/View/1336/Building-Permit-Application-PDF).

### 2.1 Intake (counter, phone, email, online)
- **What they do.** Answer "do I need a permit," "what can I build or run here" and setback questions. The city page tells people to contact the office and does not list allowed uses.
- **Stated scope limits.** The city page says the office gives no landlord-tenant or legal advice, does not handle civil or boundary disputes, and does not inspect existing buildings for suspected violations unless renovation is under way. That last line sits uneasily with the office's actual enforcement record. It enforces Ch. 205 property maintenance on existing buildings, can order buildings vacated (§ 210-10), and declared 224 County Road unfit for occupancy (section 2.5). The likely reading is "no pre-sale or courtesy interior inspections" **(inferred)**. Section 7 asks the city to confirm, and section 4 keeps habitability and hazard complaints routed toward Code and Fire.
- **Other steady inquiries.** Zoning compliance letters, violation-history requests and FOAA requests from attorneys, title searchers and lenders. Open permits tend to surface at real estate sales **(inferred; common in Maine practice, no Waterville data)**.
- **Code consulted.** Ch. 275 zoning (use tables, dimensional standards such as R-C in § 275-5.3D) and Ch. 127.
- **Tools.**
  - Seven PDF applications (https://waterville-me.gov/225/Building-Permit-Applications).
  - No online permitting portal. Online Services links only to state renewals, the AxisGIS tax map, tax payments and vital records (https://waterville-me.gov/316/Online-Services).
  - The website appears to run on CivicPlus CivicEngage **(inferred from the FormCenter, DocumentCenter and AgendaCenter URL patterns)**.
- **Time sinks.**
  - The same questions come in by phone and at the counter.
  - Out-of-scope calls (tenant, boundary).
  - The Gorham ME CEO job description lists "frequent interruptions" as a job condition (https://www.gorhammaine.gov/sites/g/files/vyhlif4456/f/uploads/code_enforcement_officer_job_description.pdf). Treating Gorham as a proxy for Waterville is **inferred**.

### 2.2 Plan review and completeness
- **What they do.**
  - Check map, lot and zone, setbacks, lot coverage, foundation type and the scaled site plan. The CEO may require a boundary survey.
  - Decide whether a Fire Department General Life Safety Review applies: new construction, renovation of more than 75% of the space, life-safety changes, change of occupancy, or solar. That review's fee is 0.15% of construction cost (https://www.waterville-me.gov/DocumentCenter/View/904/General-Life-Safety-Review-PDF).
  - Check the city gates that must clear before a permit:
    - Planning Board approval for work in site plan or subdivision scope (§ 244-2.2B; thresholds in § 275-6.4C)
    - Historic certificate of appropriateness (§ 161-7)
    - Plumbing permit (§ 275-4.27H(12)(b))
    - Fire Chief site inspection (§ 127-4)
    - Private road completion (§ 275-4.24)
  - Check the state and utility gates **(unverified for Waterville; raised in review)**:
    - State Fire Marshal construction and barrier-free permits for many commercial and multifamily projects (25 M.R.S. §2448)
    - Architect accessibility certification (5 M.R.S. §4594-F, which 30-A §4451(2-A) lists among building standards laws)
    - Sewer connection approval from the Waterville Sewerage District and water service from the Kennebec Water District
    - Public Works street-opening and driveway permits; MaineDOT entrance permits on state roads
    - DEP NRPA permits near protected resources, and asbestos notification before demolition (06-096 CMR 425)
- **Code consulted.** MUBEC (2021 I-codes with Maine amendments), NFPA 101, Ch. 275, shoreland (§ 275-4.27, 06-096 CMR 1000), floodplain (Ch. 145), subsurface (10-144 CMR 241).
- **Legal clocks.** Check each against current primary text before a tool encodes it:
  - 30-A §4103: a written decision not made within 30 days "constitutes a refusal" of the permit by the licensing authority (fact-check of https://legislature.maine.gov/statutes/30-A/title30-Asec4103.html). Whether this governs a Waterville building permit under MUBEC and Ch. 127 is a legal question for the City Solicitor **(unverified application)**.
  - The LPI must reject an incomplete HHE-200 application in writing within 14 days and issue a permit within 20 days after review (10-144 CMR 241 §4, https://www.maine.gov/dhhs/sites/maine.gov.dhhs/files/rule-2023-10/10-144%20CMR%20Ch%20241%20Subsurface%20Wastewater%20Disposal%20Rule.pdf).
  - The shoreland model ordinance sets 35-day completeness and decision clocks (06-096 CMR 1000 §16).
  - Permit decisions should be written with findings of fact and conclusions of law (Mills v. Eliot, 2008 ME 134, per Legal Issues Manual 2017 pp.64-66, https://www.maine.gov/moca/sites/maine.gov.moca/files/legal-issues-manual-2017.pdf).
- **Time sinks.**
  - Incomplete applications. Waterville has no data. In Bellevue, WA, 78% of 276 sampled residential applications were missing at least one document (https://bellevuewa.gov/sites/default/files/media/pdf_document/2026/dsd-08042026-govstreamai-case-study-early-results.pdf).
  - Gate checks done by hand across 7 city chapters plus state agencies and utilities **(inferred)**.

### 2.3 Permit issuance and fees
- **What they do.**
  - Issue and sign the permit.
  - Set the fee. Building fees follow a schedule "available from the City offices and/or on the City website" (§ 127-3A). No such schedule was found online. Ch. 173 Appendix A covers business licenses only (`output/markdown/attachments/wa3904-173a-appendix-a-licenses-and-permit-fee-schedule.md`).
  - Charge after-the-fact permits double, capped at $500, rising to $1,000 if no permit is obtained within 30 days of a violation notice (§ 127-3B, amended 5-20-2025).
  - Electrical fees are printed on the electrical form: $45 single-family minimum, $75 for services through 800A ($85 above), $0.50 per opening (https://www.waterville-me.gov/DocumentCenter/View/1419/Electrical-Permit-Application-PDF).
- **Time sinks.**
  - Fee questions with no public schedule to point to **(inferred)**.
  - Code editions disagree. The city page lists 2015 MUBEC and 2017 NEC, the form cites NFPA 101 2018, and the state adopted the 2021 I-codes effective April 7, 2025 (https://aiamaine.org/aiamainenews/2025/2/27/updated-maine-building-codes).
  - Permit closeout. Expired and open permits need follow-up, and CO denials need letters. No Waterville data exists on volume **(inferred)**.

### 2.4 Field inspections and certificates of occupancy
- **What the permit form requires.** At least three inspections: foundation (footings, walls, drainage), framing before cover, and final before occupancy. Missing an inspection call can cost $100/day, and a permit is void if work does not start within 6 months (building permit PDF). Separate electrical, plumbing and mechanical permits apply.
- **What a full MUBEC sequence likely adds.** The 2021 IECC calls for insulation and energy verification and, for most new homes, air-leakage testing and duct testing before final (IECC R402.4.1.2 and R403.3.5, which the corpus holds only as reference stubs). Plumbing rough-in and final inspections come from the LPI under the state plumbing code, and electrical inspection happens before insulation or drywall. Waterville's actual inspection practice beyond the three-stage minimum is unknown, and section 7 asks.
- **Septic:** two inspections, after site preparation and before backfill, on 24 hours' notice (10-144 CMR 241).
- **Third parties.** The CEO may accept certified third-party inspection reports (§ 127-5B).
- **Demolition.** The CEO confirms pre-demolition abatement before a demolition permit (https://www.centralmaine.com/2025/02/12/waterville-building-razed-to-make-way-for-apartment-complex/).
- **Tools.** Phone booking. Field device unknown.
- **Time sinks.**
  - Driving between sites, scheduling and re-inspections. These likely take the largest share of the week **(inferred; no Waterville data)**.
  - Inspectors need ICC, NEC, UPC and NFPA 101 text on site, and the corpus holds only reference stubs because of copyright (`docs/open-items.md` item 2).
  - Vendors stress offline apps because basements and rural sites have no signal (https://opengov.com/article/opengov-launches-mobile-app/) **(vendor claim)**.

### 2.5 Complaints and enforcement, through Rule 80K
- **Intake.**
  - The online Report a Concern form covers potholes, streetlights, traffic signals and trash only (https://waterville-me.gov/FormCenter/General-Forms-4/Report-Concerns-65).
  - A property-maintenance complaint means calling or emailing the CEO to book an appointment, filling out a paper complaint form and bringing a photo.
  - Common categories in Maine towns include junk and unregistered vehicles, which Ch. 205 covers (two or more unregistered vehicles, § 205-4C), and automobile graveyards and junkyards (30-A §3751 et seq., listed in §4452(5)). Volume in Waterville is unknown.
  - Habitability complaints (no heat, sewage, unsafe wiring) may also involve the local health officer under 22 M.R.S. §451 et seq. **(unverified; who holds that role in Waterville is unknown)**.
- **Process.** The steps below come from the 2017 MOCA Legal Issues Manual, chs.6-7, and are training recommendations unless a statute is cited:
  1. Detect and log the violation, then do the site visit and take photos.
  2. Get consent to inspect, or a Rule 80E administrative inspection warrant. The manual gives 24 hours' notice to the owner, inspection within 10 days and return within 10 days (Legal Issues Manual pp.87-88). These timings have not been checked against the current text of M.R. Civ. P. 80E **(unverified)**.
  3. Give oral notice or post a stop-work notice.
  4. Send written notices of violation. The manual recommends up to three, each written as an order that cites the ordinance section, sets a deadline and states the appeal right and the penalties. That is MOCA practice, not a statutory checklist.
     - **Appealability.** Under 30-A §2691(4), "absent an express provision in a charter or ordinance that certain decisions of its code enforcement officer or board of appeals are only advisory or may not be appealed, a notice of violation or an enforcement order by a code enforcement officer under a land use ordinance is reviewable on appeal by the board of appeals" (https://legislature.maine.gov/statutes/30-A/title30-Asec2691.html, verified 2026-10-03). Whether Waterville's ordinance contains such a provision is open (section 7).
     - **Town of Freeport v. Greenlaw** (Me. 1992) is a finality case: an NOV the owner did not appeal cannot be attacked later in the enforcement action. That makes the appeal-right language in a notice matter, but the case itself is not a list of required contents **(reviewer's reading; confirm with the Solicitor)**.
  5. Negotiate a consent agreement, signed by the municipal officers unless the CEO has delegated authority.
  6. File a Rule 80K Land Use Citation (80K Manual 2017 chs.4-5, pp.12-24):
     - The hearing is at least 20 days after service.
     - Owners are identified from registry deeds, not assessor records.
     - An attested ordinance copy is attached.
     - The citation is filed within 20 days of service.
     - These timings come from the 2017 manual and need a check against the current text of M.R. Civ. P. 80K **(unverified)**.
- **City code.**
  - Ch. 205: written notice to the owner and the mortgagee with a deadline, then a $100/day civil penalty, plus abatement with cost recovery (§§ 205-7, 205-8).
  - Zoning: a written notice, and the City Solicitor and Council are notified (§ 275-6.1A).
  - Fire-damaged buildings: secured in 24 hours, permit within 90 days, work begun within 120 days (§ 205-6).
- **Real cases.**
  - 224 County Road (2023): declared unfit for occupancy; the city removed 21 tons of debris (https://www.centralmaine.com/2023/08/01/waterville-house-where-suspicious-fire-occurred-had-history-of-code-violations-unsanitary-conditions/).
  - 6 Main Place: Kennebec Superior Court awarded the city $12,000 in April 2025, and a lien now sits on the property (https://www.sunjournal.com/2025/04/28/waterville-settles-lawsuit-against-main-place-llc-for-12000/).
- **Time sinks.**
  - Complaint site visits and re-inspections.
  - NOVs and 80K filings are drafted by hand, and wording errors can sink a case.
  - Notice histories run for years.
  - Penalty tiers are easy to mix up. The manuals' $2,500 figure is still the current maximum for work without a permit, while a specific violation now carries up to $5,000 (§4452(3)(A)-(B)).

### 2.6 Rental registration
- Ch. 215 (Ord. 54-2023): voluntary, free, no inspections. The Fire Department runs it through a CivicPlus form. Registrations expire Oct 31. Council will consider a mandatory ordinance if fewer than 90% of buildings register (`output/markdown/code/215-rental-housing-registration.md`; https://waterville-me.gov/FormCenter/Residential-Rental-Unit-Registration-5/Residential-Rental-Unit-Registration-69).
- An annual inspection checklist was dropped after landlord opposition (https://www.bangordailynews.com/2023/01/18/news/waterville-rental-registry-debate/).
- Code uses the data for owner and manager contacts. The format it receives is unknown.
- Related: business licenses need Fire and Code inspection before the Clerk issues them (https://www.waterville-me.gov/187/Business-Licenses). Short-term rentals need a $120 license plus a Fire inspection (§ 275-4.35).

### 2.7 Boards and appeals
- **ZBA staff work** (§ 275-6.2H). The CEO:
  - takes the application and the $25 fee
  - schedules the hearing within 45 days
  - mails notice to owners within 300 ft at least 14 days ahead
  - notifies the Planning Board
  - presents at the hearing
- **After the hearing.** Shoreland variances go to DEP within 7 days. Superior Court appeals under Rule 80B must be filed within 45 days.
- **Planning Board:** staff briefings and condition-compliance reports (Planning Board minutes linked in section 1).
- **Time sinks.** Evening meetings, and defending each interpretation de novo.

### 2.8 Record keeping, reporting and certification upkeep
- **Records:**
  - Building permit records are kept for the life of the structure (§ 127-5C).
  - Shoreland records are permanent, with a biennial summary to DEP (§ 275-6.1B).
  - Floodplain records are permanent (§ 145-7).
  - HHE-200 records are kept until the building is removed or connected to sewer (10-144 CMR 241 §4(D)).
  - Records are public under FOAA. Files are organized by map and lot (Legal Issues Manual pp.19, 47).
- **Reports:**
  - Annual LPI report to the municipal officers
  - Annual certificate of appointment to MOCA (08-003 CMR ch.1 §3.4)
  - 25% of plumbing fees remitted to the state (10-144 CMR 241)
- **Certification upkeep.** Recertification takes 12 contact hours per area every 6 years, counted per code for building standards (08-003 CMR ch.1 §5). Coverage when the one certified person in an area is out is unknown.
- **Tools.** Unknown. Peer towns use TRIO and Vision (Gorham job description).

---

## 3. Pain points ranked by inspector time

Waterville publishes no volumes, so this ranking is **inferred**. It weighs how often each task likely comes up against how long it takes. Keep one bias in mind: the research started from what a Q&A tool could address, so desk tasks are better documented than field work. A working CEO would probably put items 1 and 2 at the top, and the product cannot shorten either. The pilot baseline in section 6 should replace this list with real data.

1. **Field inspections, scheduling and travel.** Footing through final for every permit, septic inspections, re-inspections, phone booking with no visible scheduler (sections 2.4, 1).
2. **Complaint response and site visits.** Property maintenance, junk vehicles, unsafe buildings, multi-year cases like 6 Main Place (section 2.5).
3. **Repetitive intake questions by phone and at the counter.** Zoning use, setbacks, fences, sheds, permit type and fees. Each goes to staff because there is no portal, no allowed-use list and no fee schedule online (Code Enforcement page, Online Services page). Bellevue staff estimated 152 hours saved in one month with an AI assistant (Bellevue case study).
4. **Incomplete applications and back-and-forth.** Paper forms have no completeness check, and gates span 7 city chapters plus state agencies and utilities (section 2.2).
5. **Code research across silos.** One answer can need eCode360, legislature.maine.gov, state rules, the ICC viewer and the MOCA manuals. NEEP's January 2025 gap analysis counted 90 mentions of knowledge gaps and code misinterpretation, the most cited issue between code officials and design professionals (Fig. 20, https://neep.org/sites/default/files/media-files/neep_code_enforcement_gap_analysis_final_updated.pdf).
6. **Enforcement drafting and case files.** NOVs, 2nd and 3rd notices, 80K packets with deed-based ownership and attested ordinances, multi-year histories (Legal Issues Manual ch.7; 80K Manual).
7. **Tracking legal clocks.** 14, 20, 30, 35, 45 and 60-day clocks, 72-hour and 10-working-day floodplain clocks, 90-day recording, 6 and 12-month variance lapses (section 2 sources).
8. **Board preparation.** ZBA notices and hearings, Planning Board condition checks.
9. **Records requests and closeout.** Compliance letters, violation-history and FOAA requests, open permits found at sale.
10. **Periodic reporting.** DEP biennial, LPI annual, MOCA appointment.
11. **Stale public information.** Code editions on the city page. Fixing it costs little time, but the confusion it spreads costs more.

---

## 4. Where this product fits

### What exists today
The product is a public, anonymous chat at POST /api/chat (`app/main.py`), under a page header reading "City of Waterville, Maine" (`app/web/index.html`).
- **Retrieval:** two hybrid searches with the semantic ranker, 5 city chunks and 4 state chunks (`app/main.py:146-185`). The state bucket is shared by statutes, rules and roughly 10 manuals, and weak manual chunks already crowd it (`docs/open-items.md` item 1).
- **Prompt:** written for "members of the public." It requires "Use only the numbered sources," keeps answers short and falls back to the City Clerk (`app/main.py:51-64`).
- **Model:** the deploy picks gpt-5-mini first, with reasoning=low (`infra/deploy.sh:82-94`). `max_completion_tokens` (default 1500) includes reasoning tokens.
- **Logging:** container stdout goes to a Log Analytics workspace with 30-day retention (`infra/main.bicep`). The app writes only search and model errors there; uvicorn access logs run too but hold no question text.
- **Rate limits:** 6 per minute and 60 per day per IP, keyed on the last X-Forwarded-For hop, plus a 3,000 per day global cap (`app/main.py:42-140`). Limits live in memory per replica, and the app scales to 2 replicas (`infra/main.bicep`), so effective per-IP limits can double.
- **Capacity:** the chat deployment has 50K tokens per minute, shared by every user (`infra/main.bicep` `chatCapacity`).
- **History:** client-side only. `app.js` sends the last 6 messages and the server trims assistant turns to 2,000 characters.
- **Citations:** chips that open a source panel showing the chunk text with the cited passage highlighted and an "Open original" link to eCode360 or a PDF page (`app/web/app.js`, `app/web/source.js`). No clipboard code exists.
- **Framing:** the middleware sets no X-Frame-Options and no CSP (`app/main.py:271-280`), so any site can iframe the app today.
- **Corpus:** the local `output/chunks.jsonl` holds city text only (1,028 code, 121 attachment, 1 new_law chunks). The state chunks are in the live index (`docs/open-items.md`). ICC, UPC and ASHRAE text is stub-only (`ecode/state_sources.toml`). 30-A §§2691, 4103, 4353 and 4453 are not in `state_sources.toml` yet.
- **Ownership:** the deployment runs in the developer's Azure subscription. Who holds its data for FOAA and retention purposes is undecided.

### (a) Public-facing deflection: fewer repetitive calls to the office

Every A-row answer follows three rules. It never says "no permit needed" as a final answer. It ends with "Confirm with Code Enforcement before you build." It is CEO-approved content for the top questions, with the served answer version logged. A resident who builds on a wrong "no permit needed" will argue reliance, and that argument gets stronger if the bot sits on waterville-me.gov.

| # | Option | Step served | What changes for the inspector | What we build | Effort | Risks |
|---|---|---|---|---|---|---|
| A1 | **Top-question tuning plus "what to bring"**: fence, shed, deck, pool, sign, home occupation, conversion to 3 units, chickens. Each answer ends with the § citation, a checklist that mirrors the building permit PDF fields, and the confirm-first line | 2.1, 2.2 | Fewer interruptions; more complete walk-ins | `app/main.py` (prompt additions), new `app/checklists.toml`, `app/web/app.js` render | M | Reliance claims; CEO sign-off on each answer; answer versioning |
| A2 | **Scope triage**: tenant-rights advice, boundary lines and civil disputes get a pointer elsewhere. Habitability, no-heat, sewage, structural and fire-hazard complaints route to Code or Fire, never away | 2.1, 2.5 | Fewer out-of-scope calls without losing life-safety complaints | `app/main.py` prompt rule | S | Turning away a complaint the city must take; wording needs CEO review |
| A3 | **Permit-type router plus life-safety review trigger**: "add a deck / heat pump / apartment" maps to the forms needed and says whether the Fire review applies | 2.1, 2.2 | Applicants arrive with the right forms | New `city_form` kind in `ecode/state_sources.toml` and `ecode/state.py` with its own HEADER and source_type; add it to `LOCAL_TYPES` and `SOURCE_LABELS` in `app/main.py`; index recreate and refresh; `app/checklists.toml` | M-L | Without the new kind, forms land in the state bucket labeled "State guidance manual, may be dated" (`ecode/state.py:35-38, 178`); form versions drift |
| A4 | **Fee estimator from published formulas only**: electrical line items and the 0.15% life-safety fee. Flags the missing building schedule and never guesses | 2.3 | Fewer fee calls | Small calculator in `app/main.py`; depends on the A3 ingest | M | Liability if a fee is wrong; label every figure "estimate, confirm with the office" |
| A5 | **Printable complaint form**: a prefilled version of the city's own paper form for the resident to bring to the appointment. Nothing stored on our side | 2.5 | Arrives at the appointment with facts written down | View in `app/web/` | S | Low. A stored version (photos, addresses) is L: a storage account, a Storage Table/Blob Data Contributor role for the app identity, SDK dependencies, upload abuse controls on an anonymous endpoint, and city custody of the records first. Stored complainant data also raises retaliation and FOAA concerns, and third-party photos are weak 80K evidence |
| A6 | **Embed on the city site**. Framing works today; add `frame-ancestors` to limit it to the city domain | 2.1 | Reaches residents where they already look | `app/web/embed.html`, CSP header in `app/main.py` | S | City-site traffic may hit the 3,000/day global cap and the 50K TPM quota; branding; the city controls its site |
| A7a | **Question log**: question text, cited ids and a no-answer flag as a JSON line to stdout, landing in the existing Log Analytics workspace (30-day retention) | 2.1, 3 | Raw material for the digest | Log line in `app/main.py`; PII scrub (regex for street addresses, phone numbers and emails, plus a name filter) | S | Questions name addresses and people; privacy notice on the public page; city retention policy |
| A7b | **Weekly digest to the CEO**: top cited sections, unanswered rate, recurring topics | 2.1, 3 | The CEO sees which ordinances confuse people | Scheduled KQL query plus Logic App or ACS Email in `infra/main.bicep` | M | ACS Email needs a verified sender domain |

### (b) Inspector-facing tools

All staff output carries the stamp "Research aid, not a determination of the Code Enforcement Officer." Staff features sit behind a gate (B0).

| # | Option | Step served | What changes for the inspector | What we build | Effort | Risks |
|---|---|---|---|---|---|---|
| B0 | **Staff gate and rate-limit exemption**: a `STAFF_KEY` secret checked from a request header; staff requests skip the per-IP limits. The toggle stays off the public page | All | Staff behind one city NAT stop sharing 6/min and 60/day; works on cellular in the field | `app/main.py` header check and limiter bypass; secret in `infra/main.bicep` | S | Shared key can leak; rotate it. Replaced later by B9 |
| B1 | **Staff "cite-it" mode**: section numbers first, verbatim quotes, the enforcement chain (city section to penalty tier to 30-A §4452 to Rule 80K), conflicts and amendments named, no Clerk fallback. More chunks and tokens | 2.2-2.7 | One search replaces 4-5 silos; answers can be pasted into findings after checking | `STAFF_SYSTEM_PROMPT` and `mode` field in `app/main.py`; refactor `search()` to take k; staff view behind B0 | S | Over-reliance; answers stay advisory, and the CEO's interpretation is what gets appealed |
| B2 | **Copy citation / copy answer with citations**, added to the existing source panel and answer | 2.5, 2.7 | Paste into an NOV or ZBA memo without retyping | `app/web/app.js`, `app/web/source.js` | S | Republishes eCode360 text; needs the city authorization in section 7 Q12 first |
| B3 | **Section lookup by citation**: normalize "205-7", "sec. 205-7" or "§ 205-7A" to the parent section, run a filter-only query on `citation eq '<norm>'` ordered by chunk index and return every chunk (65 citations span several chunks) | All | Fast lookups at the desk | `app/main.py` `search()`; escape single quotes in the OData literal; test cases | S | State citation formats differ and need their own patterns |
| B4 | **Chapter and source filters**: chips for Ch. 205, 275, state rules or manuals, using `chapter_number` and `source_type`, which are already filterable and facetable (`azure/index.json`) | All | Narrows noise from manual chunks | `app/main.py` OData filter, `/api/facets`, UI chips. No schema change | S-M | OData injection if values are not escaped |
| B5 | **Currency and conflict notes as a curated source**: a "staff notes" chunk with a URL and a UI label, covering 16-642 to 08-003 CMR, SPO and DECD names, the stale editions on the city page, and the separate §4452(3) penalty tiers. Ingest 08-003 CMR and current 30-A §§2691, 4103, 4353, 4453 through `ecode/state_sources.toml` | 2.3, 2.5 | Fewer wrong rule numbers and wrong penalty tiers in notices | New entries in `ecode/state_sources.toml`; a new source_type and label; refresh job run | S-M | Bare prompt text would conflict with "Use only the numbered sources"; a wrong "current" claim is worse than none, so the CEO reviews each note |
| B6 | **NOV and letter drafter**: 1st, 2nd and 3rd NOVs, special-exception abutter letter, ZBA notice. Contents follow city templates and the MOCA manual recommendations, with appeal language set by the Waterville ordinance under §2691(4). Editable text or .docx | 2.5, 2.7 | Drafting time drops; the CEO edits and signs | `/api/draft` route in `app/main.py`, new view, python-docx in `pyproject.toml` | M | Depends on B9 auth: a public route would let anyone produce official-looking notices. City templates and Solicitor review required; never auto-send |
| B7 | **Deadline calculator with citations**: trigger event in, every resulting clock out, each with its section | 2.2, 2.5, 2.7 | Fewer missed clocks | Rules table, `/api/deadlines` route, Maine and city holiday calendar, an inclusive/exclusive counting convention, `[dependency-groups] dev = ["pytest"]` in `pyproject.toml` and a test suite from scratch | M-L | A wrong date can void an action; every clock needs primary-source text and CEO validation |
| B8 | **"What applies to this project" gate checklist**: project type, district, footprint, impervious area, shoreland, flood and historic flags in; ordered approvals with sections out, including state and utility gates | 2.2 | Faster completeness checks | `app/checklists.toml`, route and view | M-L | Needs the zoning map and FIRM, which are not in the corpus |
| B9 | **Staff auth and saved case notebooks** (Entra ID through Container Apps Easy Auth) | 2.5, 2.8 | Research stays attached to a case | `infra/main.bicep` authConfigs plus Cosmos or Table; principal check in `app/main.py`; server-side history with a larger window | M-L | Needs an Entra app registration; city IT must create it or grant admin consent if staff use the city tenant; drafts become FOAA records |
| B10 | **80K packet assembler**: citation fields, required attachments list, penalty tier, inclusive dates | 2.5 | Court prep time drops **(inferred)** | Extends B6; depends on B9 | M | High legal stakes; needs 80K-certified review and the current Rule 80K text |
| B11 | **Offline source cache**: a service worker caches viewed sections and the chapter table of contents. Q&A still needs a connection | 2.4 | Re-read a section in a basement | Service worker in `app/web/` (the UI is already responsive) | M | Thin value until ICC text is licensed |
| B12 | **Change alerts**: before push, fetch id plus a content hash for code chunks from the index, compare with the new chunks, and email changed citations with their history and `legislation_through` fields | 2.3, 2.8 | Learns about amendments without checking eCode360 | `ecode/azure.py` push, `infra/refresh.sh`, Logic App or ACS Email in `infra/main.bicep` | M | Email domain setup; republishes ordinance text (Q12) |
| B13 | **Reporting helpers**: DEP biennial and LPI annual reports | 2.8 | Report assembly | Needs the city's permit data source | L | Blocked on an unknown system |

### Cross-cutting risks
- **eCode360 licensing.** The Terms of Use limit content to "personal use only and not for commercial exploitation" and forbid republishing "for commercial, non-profit or public purposes" (https://ecode360.com/docs/TOS.html). robots.txt disallows `/print/`, which `ecode/export.py:64` fetches, so the weekly refresh job keeps doing it (https://ecode360.com/robots.txt). Enacted ordinance text is arguably public domain under Veeck and Georgia v. PRO **(inferred legal reading)**. The risk grows with B2, B6 and B12, which all copy ordinance text out. The clean fix is written authorization from the City or a data export from General Code, settled before those features ship.
- **ICC text.** The I-codes are copyrighted. ICC also owns General Code (eCode360) (https://www.iccsafe.org/about/periodicals-and-newsroom/international-code-council-welcomes-general-code-llc-to-its-family-of-companies/). Inspector-grade framing, egress, guard and fire-separation answers need a license (`docs/open-items.md` item 2). Until then, staff answers should link the free ICC read-only viewer.
- **Liability.** Interpretations are appealable de novo (§ 275-6.2E), and eCode360 itself says it "should not be relied upon as the definitive authority." Staff output carries the research-aid stamp, and anything used in a signed document gets checked against the primary source, following Bellevue's "staff validate before replying" model. Screenshots of an ungated staff answer could turn up at a ZBA hearing as "the city's tool said," which is why B0 comes first.
- **Ownership and records.** The app runs in the developer's subscription under a city header. Logs (A7), stored complaints (A5), drafts (B6) and notebooks (B9) all create records someone must hold, retain and produce under FOAA. Settle custody with the city before building any of them.
- **Index changes.** `azure/index.json` comes from `python -m ecode.azure schema`. A new source_type or a new filterable field means `ecode.azure push --recreate` plus a refresh run. A3, A4 and B5 need this; B4 does not.

---

## 5. Competitive landscape

| Layer | Products | What they do | Covers Waterville ordinance plus Maine law with pinpoint citations? | Source |
|---|---|---|---|---|
| Model-code AI | ICC AI Navigator (Digital Codes Premium); UpCodes Copilot ($59-68/user/mo Professional) | Q&A over I-codes and state amendments | No municipal ordinances | https://solutions.iccsafe.org/digital-codes-premium-ai-navigator ; https://cms-v2.up.codes/pricing |
| AI plan review | CivCheck (Clariti), Archistar PreCheck, CodeComply.ai (integrated into the CivicPlus Civic Impact Platform), Blitz, GreenLite | Check drawings against codes for large-city queues | No; no enforcement or field use. Seattle pilot: 87% of in-scope intake rejection reasons caught, cost unsettled, Accela integration 6+ months | https://seattle.gov/documents/Departments/Performance/Publications/2026CivCheckEvaluationReport.pdf ; https://www.civicplus.com/news/nn/civicplus-brings-ai-building-plan-review-codecomply-ai/ |
| Permitting systems of record | OpenGov, Tyler EnerGov (plus ARInspect), Accela, GovWell (130+ municipalities), Municity (ICC), iWorQ (~$2k-14.5k/yr in public quotes), Citizenserve ($900-1,800/user/yr) | Permits, inspections, cases; applicant-facing AI intake | No citation-first ordinance Q&A for the inspector | https://opengov.com/products/permitting-and-licensing/ ; https://www.insightpartners.com/ideas/govwell-raises-25m-series-a-led-by-insight-partners-to-build-the-ai-operating-system-for-modern-government/ ; https://capterra.com/p/123695/Citizenserve-Code-Enforcement/ |
| Resident chatbots | Polimorphic, Citibot, Govstream.ai PermitGuide | Deflect calls; route residents to permits | General answers; no ordinance-grade citations. Govstream also has staff assistants (Bellevue) | https://www.semafor.com/article/07/08/2025/ai-startup-polimorphic-raises-186-million-for-local-government-chatbots ; Bellevue case study |
| Code hosting | eCode360 (General Code/ICC), Municode (CivicPlus) | Host ordinances; keyword search | No generative Q&A found | https://gocodebook.com/compare/ecode360 |
| Applicant tools | PermitFlow, PermitsAIge | Serve contractors and applicants | Not sold to cities | https://permitsaige.com/directory/me/waterville-me |

Pricing for UpCodes, iWorQ and Citizenserve and the GovWell and Seattle figures come from the cited pages and were not re-checked in review.

**Our gap.** A city-plus-state legal research desk for a small Maine office. It needs:
- one index joining city ordinance, Title 30-A and Title 38, MUBEC rules, 10-144 CMR 241, 06-096 CMR 1000 and the MOCA manuals
- pinpoint citations that can be pasted into an NOV or a ZBA memo after checking
- consistent counter and desk answers
- change alerts
- a price a 3-person office can carry (current fixed cost is about $85-100/month plus model usage, `README.md` line 209)

Our weaknesses: no ICC text, no permitting features, no GIS, nothing for the field work that fills most of the week. Position the product as a complement to whatever system of record the city adopts, and do not build permitting **(inferred strategy)**.

---

## 6. Recommended first slice (about one week) and pilot

### Slice: gated "cite-it" staff mode
1. **Day 1. Gate and corpus.**
   - Add B0: a `STAFF_KEY` header check, staff exemption from the per-IP limits, and no toggle on the public page.
   - Add 30-A §§2691, 4103, 4353, 4453 and 08-003 CMR as `[[source]]` entries in `ecode/state_sources.toml`, rebuild the image and run the refresh job. Section 2 eval questions depend on them.
   - Evaluate against the live index, which already holds the state chunks. Skip regenerating `output/chunks.jsonl`: that needs `python -m ecode` (`ecode/__main__.py:43-44`), a full eCode360 re-crawl at 1.5 s per page plus about 9 minutes of state PDFs, and it rewrites tracked files in `output/`. If you want a local copy, run `uv run python -m ecode --out <scratch dir>` outside `output/`.
2. **Days 1-2. B1.**
   - Add `STAFF_SYSTEM_PROMPT` and a `mode` field on the chat request in `app/main.py`, honored only with a valid staff key.
   - Staff answers lead with section numbers, quote the controlling text, trace the enforcement chain with the correct §4452(3) tier, and end with the research-aid stamp.
   - Refactor `search()` to take k. Size staff K and the token budget against the 50K TPM deployment, and remember that reasoning tokens count against `max_completion_tokens`.
   - Fold in open item 1 (manual heading breadcrumbs, `docs/open-items.md`) if time allows, since staff answers need §4452, the 80K Manual and the Legal Issues Manual together in 4 state slots.
3. **Day 3. B3.** Pin exact citations: `§ 205-7` returns every chunk of that section first.
4. **Day 3. B2.** Add "Copy citation" and "Copy answer with citations." Ship it to pilot staff only until the city answers Q12.
5. **Day 4. B5, minimal.** Add a curated "staff notes" source with a URL: 16-642 to 08-003 CMR, the stale editions on the city page, and the four §4452(3) penalty tiers. No bare prompt facts.
6. **Day 5. Eval.**
   - Build a 30-question set from section 2 (setbacks, Ch. 205 notice, special exception notice, shoreland expansion, ZBA timing, after-the-fact fees, penalty tiers, NOV appealability).
   - Run it against the deployed endpoint with the staff key. The other route is to grant your Entra principal Cognitive Services OpenAI User and Search Index Data Reader, since Azure OpenAI has key auth disabled (`infra/main.bicep`).
   - Add pytest as a dev dependency and score citation correctness by hand.

**Cost.** Today's answer reads about 9 chunks averaging 1,370 characters, roughly 3,100 input tokens of sources (`output/chunks.jsonl`). A staff answer at 8 city and 6 state chunks would read about 4,800 tokens before the prompt and history **(inferred estimate)**. At pilot volume, three staff users, the monthly delta over the $85-100 fixed cost should be small, and the pilot should measure it.

Defer the NOV drafter (B6) and the 80K assembler (B10) until B9 exists and the city supplies templates.

### Pilot with the city (4-6 weeks)
- **Users:** Dan Bradstreet, Adam Bradstreet and Todd Buckmore, at the desk. Field use waits until ICC text is licensed; until then the tool covers ordinance, state law and procedure.
- **Baseline (week 0):** for 10 real questions, time how long it takes to find the controlling section with today's tools. Keep a one-week tally of phone and counter questions by topic, and a rough split of hours among field, complaints, desk and meetings.
- **Pilot rule:** any tool output used in a signed NOV, decision, letter or ZBA finding gets checked against eCode360 or the statute first, and the CEO logs that check.

**What to measure:**

| Metric | Target or use |
|---|---|
| Staff queries per week, and share of staff answers used in a letter, memo or finding | Adoption |
| Time to controlling section | Same 10-question protocol against baseline |
| Citation accuracy | CEO marks each answer right, partial or wrong; target 90% or more right on the eval set **(proposed threshold)** |
| Outputs used in signed documents, and share checked against the primary source | Must be 100% |
| Answers flagged legally risky | Count and examples |
| Cost per staff query | Tokens and dollars from the deployment metrics |
| Repeat-question call volume | Only if A2 and A7 ship in phase 2; tally sheet comparison |

- **Exit decision:** go or no-go on B9 (auth and notebooks), then B6 (NOV drafter, which depends on B9), and on the public deflection features.

---

## 7. Open questions for the city (to Nathan Bernard)

1. Was "Flip" a person, vendor or program the office uses, or a dictation slip for "city code inspector"?
2. Does Code Enforcement track permits, inspections and complaints in software (TRIO, Vision, iWorQ, Excel, paper)? Is there an export or API? Is an online permitting system planned, for example CivicPlus Community Development?
3. Annual volumes: building permits, inspections, complaints, NOVs, special exceptions, ZBA cases, Rule 80K filings. Roughly how do staff hours split among field inspections, complaints, desk work and meetings?
4. Roughly how many phone, email and counter questions arrive per week, and which 10 repeat most? How many are compliance letters, violation-history or FOAA requests?
5. Who books inspections today? Is there still a "CEO secretary"?
6. What are the Ordinance Compliance Officer's duties?
7. Who is the Local Plumbing Inspector, the Municipal Electrical Inspector (§ 127-9), the appointed building official (25 M.R.S. §2351-A) and the local health officer?
8. Which certifications do staff hold, including Rule 80K? Does Council authorize staff to prosecute, or does the City Solicitor handle all court work? Who covers when a certified person is out?
9. Which code editions are enforced today: the 2021 I-codes or the "2015 MUBEC" on the web page? Which NEC and NFPA 101 editions?
10. Which inspections does the office require beyond foundation, framing and final: insulation, energy and blower-door reports, plumbing rough-in?
11. Does "no inspections of existing buildings unless renovation is under way" mean no courtesy or pre-sale inspections? How do habitability and unsafe-building complaints reach Code or Fire?
12. Will the City authorize, in writing, our indexing and display of the Waterville Code from eCode360, or request a data export from General Code under its contract?
13. Where is the current building and electrical permit fee schedule (§ 127-3A), and when was it last adopted?
14. Does the city hold an ICC Digital Codes Premium license, and do its terms allow indexing for staff-only use?
15. Can the city provide the Official Zoning Map, FIRM, shoreland and historic district boundaries as GIS layers, or parcel-to-zone data from AxisGIS?
16. Does the office have standard NOV, stop-work, consent-agreement, abutter-notice and decision-letter templates? Must the Solicitor approve AI-drafted text, and what disclaimer language is required?
17. Does any Waterville charter or ordinance provision make NOVs advisory or unappealable under 30-A §2691(4)? Who signs consent agreements?
18. Does 30-A §4103's 30-day refusal rule apply to Waterville building permits? (For the City Solicitor.)
19. How are the DEP biennial shoreland report and the annual LPI report produced today?
20. Does the city use Microsoft 365 or Entra ID for staff sign-in, and would city IT create an app registration or grant admin consent?
21. Would staff use the tool at the desk, in the field, or both? On what device, and how is connectivity at typical sites?
22. Who should own the deployment and its data? Is logging anonymized public questions acceptable, and what privacy notice, retention schedule and FOAA custody apply? The same question covers any stored complaints or drafts.
23. Does the Fire Department share rental registration data with Code in a usable format, and what is the registration rate against the 90% threshold (§ 215-7C)?
24. Would the city embed the public assistant on waterville-me.gov, and who controls that site?
25. Is there a budget line or grant (for example the state regionalization pilot) that could fund an inspector-facing tool?

---

## Sources

**Waterville city pages and forms**
- https://waterville-me.gov/218/Code-Enforcement
- https://waterville-me.gov/m/directory/department?did=42
- https://waterville-me.gov/225/Building-Permit-Applications
- https://www.waterville-me.gov/DocumentCenter/View/1336/Building-Permit-Application-PDF
- https://www.waterville-me.gov/DocumentCenter/View/904/General-Life-Safety-Review-PDF
- https://www.waterville-me.gov/DocumentCenter/View/1419/Electrical-Permit-Application-PDF
- https://waterville-me.gov/316/Online-Services
- https://waterville-me.gov/FormCenter/General-Forms-4/Report-Concerns-65
- https://waterville-me.gov/FormCenter/Residential-Rental-Unit-Registration-5/Residential-Rental-Unit-Registration-69
- https://www.waterville-me.gov/187/Business-Licenses
- https://waterville-me.gov/236/Planning-Department
- https://waterville-me.gov/294/Board-of-Zoning-Appeals
- https://www.waterville-me.gov/AgendaCenter/ViewFile/Minutes/_04082025-20

**Waterville code (repo corpus, from eCode360 WA3904)**
- `output/markdown/code/127-building-and-energy-code.md`
- `output/markdown/code/145-floodplain-management.md`
- `output/markdown/code/161-historic-preservation.md`
- `output/markdown/code/173-licenses-and-permits.md`
- `output/markdown/code/205-property-maintenance.md`
- `output/markdown/code/210-public-safety.md`
- `output/markdown/code/215-rental-housing-registration.md`
- `output/markdown/code/244-subdivision-of-land-site-plan-review.md`
- `output/markdown/code/275-zoning.md`
- `output/markdown/attachments/wa3904-173a-appendix-a-licenses-and-permit-fee-schedule.md`

**Maine statutes, rules and manuals**
- 30-A M.R.S. §2691: https://legislature.maine.gov/statutes/30-A/title30-Asec2691.html
- 30-A M.R.S. §4103: https://legislature.maine.gov/statutes/30-A/title30-Asec4103.html
- 30-A M.R.S. §4451: https://legislature.maine.gov/statutes/30-A/title30-Asec4451.html
- 30-A M.R.S. §4452: https://legislature.maine.gov/statutes/30-A/title30-Asec4452.html
- 10 M.R.S. §9724: https://legislature.maine.gov/statutes/10/title10sec9724.html
- 25 M.R.S. ch. 313: https://legislature.maine.gov/statutes/25/title25ch313.pdf
- MOCA code enforcement laws and rules: https://www.maine.gov/moca/programs/code-enforcement/laws-rules
- MOCA code enforcement resources: https://www.maine.gov/moca/programs/code-enforcement/resources
- 08-003 CMR ch.1: https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/003c001%20%28see%20PL%202025%2C%20c.%20388%29_0.docx
- 10-144 CMR 241: https://www.maine.gov/dhhs/sites/maine.gov.dhhs/files/rule-2023-10/10-144%20CMR%20Ch%20241%20Subsurface%20Wastewater%20Disposal%20Rule.pdf
- 06-096 CMR 1000: https://www.maine.gov/sos/sites/maine.gov.sos/files/content/assets/096c1000.docx
- Legal Issues Manual 2017: https://www.maine.gov/moca/sites/maine.gov.moca/files/legal-issues-manual-2017.pdf
- 80K Manual 2017: https://www.maine.gov/moca/sites/maine.gov.moca/files/80k-manual-2017.pdf
- CEO Info Guide 2009: `ecode/archived/decd-ceo-info-guide-2009.pdf`
- Maine 2021 I-code adoption: https://aiamaine.org/aiamainenews/2025/2/27/updated-maine-building-codes

**News**
- https://www.centralmaine.com/2017/09/18/waterville-hires-new-code-enforcement-officer/
- https://www.centralmaine.com/2023/08/01/waterville-house-where-suspicious-fire-occurred-had-history-of-code-violations-unsanitary-conditions/
- https://www.centralmaine.com/2025/02/12/waterville-building-razed-to-make-way-for-apartment-complex/
- https://www.sunjournal.com/2025/04/28/waterville-settles-lawsuit-against-main-place-llc-for-12000/
- https://www.bangordailynews.com/2023/01/18/news/waterville-rental-registry-debate/

**Industry, peers and vendors**
- Gorham CEO job description: https://www.gorhammaine.gov/sites/g/files/vyhlif4456/f/uploads/code_enforcement_officer_job_description.pdf
- NEEP gap analysis (Jan 2025): https://neep.org/sites/default/files/media-files/neep_code_enforcement_gap_analysis_final_updated.pdf
- Bellevue Govstream.ai case study: https://bellevuewa.gov/sites/default/files/media/pdf_document/2026/dsd-08042026-govstreamai-case-study-early-results.pdf
- Seattle CivCheck evaluation: https://seattle.gov/documents/Departments/Performance/Publications/2026CivCheckEvaluationReport.pdf
- CivicPlus and CodeComply.ai: https://www.civicplus.com/news/nn/civicplus-brings-ai-building-plan-review-codecomply-ai/
- ICC AI Navigator: https://solutions.iccsafe.org/digital-codes-premium-ai-navigator
- UpCodes pricing: https://cms-v2.up.codes/pricing
- OpenGov permitting and mobile: https://opengov.com/products/permitting-and-licensing/ ; https://opengov.com/article/opengov-launches-mobile-app/
- GovWell: https://www.insightpartners.com/ideas/govwell-raises-25m-series-a-led-by-insight-partners-to-build-the-ai-operating-system-for-modern-government/
- Citizenserve: https://capterra.com/p/123695/Citizenserve-Code-Enforcement/
- Polimorphic: https://www.semafor.com/article/07/08/2025/ai-startup-polimorphic-raises-186-million-for-local-government-chatbots
- GoCodebook on eCode360: https://gocodebook.com/compare/ecode360
- PermitsAIge: https://permitsaige.com/directory/me/waterville-me
- ICC acquisition of General Code: https://www.iccsafe.org/about/periodicals-and-newsroom/international-code-council-welcomes-general-code-llc-to-its-family-of-companies/
- eCode360 terms and robots: https://ecode360.com/docs/TOS.html ; https://ecode360.com/robots.txt

**This repo**
- `app/main.py`, `app/web/index.html`, `app/web/app.js`, `app/web/source.js`
- `ecode/__main__.py`, `ecode/state.py`, `ecode/state_sources.toml`, `ecode/export.py`, `ecode/azure.py`
- `azure/index.json`, `infra/main.bicep`, `infra/deploy.sh`, `infra/refresh.sh`
- `README.md`, `docs/open-items.md`, `output/chunks.jsonl`
