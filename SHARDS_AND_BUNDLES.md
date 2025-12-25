# ArkhamMirror Shards & Bundles Reference

> Comprehensive inventory of shards and use-case bundles for the SHATTERED architecture

**Last Updated:** 2025-12-24

---

## Table of Contents

1. [Philosophy](#philosophy)
2. [Bundles by User Base](#bundles-by-user-base)
3. [Shard Inventory](#shard-inventory)
4. [Priority Build Order](#priority-build-order)
5. [The Pattern](#the-pattern)

---

## Philosophy

ArkhamMirror isn't a product — it's a **platform**. The shards are the products. Or rather, *bundles* of shards configured for specific use cases.

**Core Principles:**

- Build domain-agnostic infrastructure that supports domain-specific applications
- Lower the bar for contribution so non-coders can build custom shards
- Provide utility to people in need, not just those who can pay
- Local-first: data never leaves the user's machine unless they want it to

**The Meta-Pattern:**

```
INGEST → EXTRACT → ORGANIZE → ANALYZE → ACT
  │         │          │          │        │
  │         │          │          │        └── Export, Generate, Notify
  │         │          │          └── ACH, Contradictions, Patterns
  │         │          └── Timeline, Graph, Matrix, Inventory
  │         └── Entities, Claims, Events, Relationships
  └── Documents, Data, Communications, Records
```

- **Core shards** handle INGEST and EXTRACT
- **Domain shards** handle ORGANIZE and ANALYZE
- **Output shards** handle ACT

---

## Bundles by User Base

### 📰 Journalists & Investigators

#### OSINT Kit
| Shard | Purpose |
|-------|---------|
| `social-media-archive` | Platform archiving, account correlation |
| `entity-extraction` | People, orgs, places identification |
| `relationship-graph` | Network mapping between entities |
| `timeline` | Chronological event reconstruction |
| `wayback-integration` | Historical snapshots, deleted content |
| `geospatial` | Location mapping, movement tracking |

#### FOIA Tracker
| Shard | Purpose |
|-------|---------|
| `letter-generator` | FOIA request templates |
| `alert-manager` | Deadline tracking, follow-up reminders |
| `document-classifier` | Response categorization |
| `comparison-engine` | Redaction analysis, version comparison |
| `public-records` | Agency database integration |

#### Source Network Manager
| Shard | Purpose |
|-------|---------|
| `entity-extraction` | Source identification |
| `relationship-graph` | Source relationship mapping |
| `annotation` | Secure notes on sources |
| `credibility-scorer` | Source reliability tracking |
| `timeline` | What each source knew and when |

#### Publication Prep
| Shard | Purpose |
|-------|---------|
| `claim-extractor` | Extract assertions from draft |
| `citation-tracer` | Verify sources support claims |
| `contradiction-engine` | Internal consistency check |
| `report-generator` | Fact-check report generation |

#### Tip Line Manager
| Shard | Purpose |
|-------|---------|
| `ingest` | Multi-channel intake |
| `deduplication` | Identify repeat/related tips |
| `tagging` | Triage and categorization |
| `workflow-manager` | Assignment and follow-up |
| `alert-manager` | Priority notifications |

---

### 🎓 Academics & Researchers

#### Literature Review
| Shard | Purpose |
|-------|---------|
| `academic-sources` | PubMed, arxiv, journal integration |
| `claim-extractor` | Extract findings from papers |
| `citation-tracer` | Build citation graphs |
| `contradiction-engine` | Find conflicting findings |
| `summary-generator` | Synthesize across papers |
| `relationship-graph` | Map research landscape |

#### Research Log
| Shard | Purpose |
|-------|---------|
| `timeline` | Experiment chronology |
| `ach` | Hypothesis evaluation |
| `annotation` | Notes and observations |
| `version-control` | Track evolving understanding |
| `tagging` | Categorize findings |

#### Grant Writer
| Shard | Purpose |
|-------|---------|
| `academic-sources` | Find relevant citations |
| `alert-manager` | Deadline tracking |
| `checklist-generator` | Funder requirements |
| `report-generator` | Proposal assembly |

#### Thesis Assembler
| Shard | Purpose |
|-------|---------|
| `citation-tracer` | Ensure consistent citations |
| `contradiction-engine` | Argument consistency |
| `comparison-engine` | Draft version tracking |
| `report-generator` | Chapter assembly |

#### Peer Review Assistant
| Shard | Purpose |
|-------|---------|
| `claim-extractor` | Identify assertions |
| `citation-tracer` | Verify sources |
| `credibility-scorer` | Assess methodology |
| `report-generator` | Review report |

#### Data Provenance
| Shard | Purpose |
|-------|---------|
| `timeline` | Transformation history |
| `audit-trail` | Change logging |
| `version-control` | Dataset versions |
| `report-generator` | Reproducibility documentation |

---

### ⚖️ Legal (Non-Lawyer)

#### Tenant Defense
| Shard | Purpose |
|-------|---------|
| `ingest` | Photos, emails, texts, leases |
| `timeline` | Violation chronology |
| `regulatory-database` | Housing code matching |
| `letter-generator` | Complaint letters |
| `evidence-packet` | Hearing preparation |

#### Employment Rights
| Shard | Purpose |
|-------|---------|
| `timeline` | Incident documentation |
| `entity-extraction` | Who said/did what |
| `regulatory-database` | Labor law elements |
| `ach` | Evaluate claim strength |
| `evidence-packet` | EEOC complaint prep |

#### Consumer Protection
| Shard | Purpose |
|-------|---------|
| `contract-parser` | Warranty extraction |
| `timeline` | Communication log |
| `letter-generator` | Demand letters |
| `evidence-packet` | Small claims packet |

#### Family Court Prep
| Shard | Purpose |
|-------|---------|
| `timeline` | Custody-relevant events |
| `email-parser` | Communication analysis |
| `entity-extraction` | Witness identification |
| `evidence-packet` | Court documentation |

#### Immigration Docs
| Shard | Purpose |
|-------|---------|
| `document-classifier` | Supporting evidence organization |
| `checklist-generator` | Visa-type requirements |
| `alert-manager` | Deadline tracking |
| `evidence-packet` | Application assembly |

#### Bankruptcy Prep
| Shard | Purpose |
|-------|---------|
| `financial-statement-parser` | Asset/debt extraction |
| `checklist-generator` | Required documents |
| `form-parser` | Schedule completion |
| `report-generator` | Means test documentation |

---

### 🏥 Healthcare Self-Advocacy

#### Chronic Illness Manager
| Shard | Purpose |
|-------|---------|
| `medical-record-parser` | Lab results, visit notes |
| `timeline` | Symptom and treatment chronology |
| `pattern-detector` | Flare triggers, correlations |
| `ach` | Treatment effectiveness evaluation |
| `report-generator` | Doctor visit summaries |

#### Insurance Fighter
| Shard | Purpose |
|-------|---------|
| `timeline` | Denial and appeal tracking |
| `letter-generator` | Appeal letters |
| `regulatory-database` | Coverage requirements |
| `evidence-packet` | Medical necessity documentation |

#### Diagnosis Quest
| Shard | Purpose |
|-------|---------|
| `medical-record-parser` | Test results organization |
| `timeline` | Symptom progression |
| `ach` | Differential diagnosis evaluation |
| `academic-sources` | Research relevant conditions |
| `report-generator` | Specialist visit prep |

#### Medication Manager
| Shard | Purpose |
|-------|---------|
| `medical-record-parser` | Medication list extraction |
| `pattern-detector` | Side effect correlation |
| `alert-manager` | Refill reminders |
| `contradiction-engine` | Interaction flagging |

#### Caregiver Coordinator
| Shard | Purpose |
|-------|---------|
| `medical-record-parser` | Multi-patient records |
| `alert-manager` | Appointment scheduling |
| `workflow-manager` | Care handoffs |
| `report-generator` | Status summaries |

#### Mental Health Tracker
| Shard | Purpose |
|-------|---------|
| `timeline` | Mood and trigger logging |
| `pattern-detector` | Episode triggers |
| `annotation` | Therapy session notes |
| `report-generator` | Provider summaries |

---

### 🏛️ Civic Engagement

#### Local Government Watch
| Shard | Purpose |
|-------|---------|
| `meeting-minutes-parser` | Extract actions, votes |
| `entity-extraction` | Official identification |
| `timeline` | Legislative history |
| `contradiction-engine` | Promise vs action |
| `relationship-graph` | Donor-vote correlation |

#### Campaign Finance
| Shard | Purpose |
|-------|---------|
| `financial-data` | FEC/state filing integration |
| `entity-extraction` | Donor identification |
| `pattern-detector` | Bundling detection |
| `relationship-graph` | Money flow mapping |
| `network-analyzer` | Coordination patterns |

#### Redistricting Analyzer
| Shard | Purpose |
|-------|---------|
| `geospatial` | District mapping |
| `government-data` | Demographic data |
| `comparison-engine` | Before/after analysis |
| `report-generator` | Impact documentation |

#### Ballot Measure Research
| Shard | Purpose |
|-------|---------|
| `financial-data` | Funding sources |
| `claim-extractor` | Campaign claims |
| `contradiction-engine` | Claim vs reality |
| `public-records` | Similar measures elsewhere |

#### Public Records Requester
| Shard | Purpose |
|-------|---------|
| `letter-generator` | Request templates |
| `alert-manager` | Deadline tracking |
| `workflow-manager` | Multi-request management |
| `comparison-engine` | Response analysis |

#### Community Organizing
| Shard | Purpose |
|-------|---------|
| `entity-extraction` | Stakeholder identification |
| `relationship-graph` | Power mapping |
| `timeline` | Issue history |
| `workflow-manager` | Action planning |

---

### 💼 Small Business / Freelance

#### Contract Analyzer
| Shard | Purpose |
|-------|---------|
| `contract-parser` | Clause extraction |
| `comparison-engine` | Standard vs actual terms |
| `alert-manager` | Obligation deadlines |
| `pattern-detector` | Unusual term flagging |

#### Client Dispute Prep
| Shard | Purpose |
|-------|---------|
| `email-parser` | Communication log |
| `timeline` | Project chronology |
| `comparison-engine` | Scope creep documentation |
| `evidence-packet` | Dispute documentation |

#### IP Protection
| Shard | Purpose |
|-------|---------|
| `search` | Prior art research |
| `news-archive` | Trademark monitoring |
| `alert-manager` | Registration deadlines |
| `letter-generator` | Cease & desist |

#### Vendor Vetting
| Shard | Purpose |
|-------|---------|
| `public-records` | Business registration |
| `news-archive` | Complaint research |
| `credibility-scorer` | Reliability assessment |
| `report-generator` | Due diligence summary |

#### Compliance Tracker
| Shard | Purpose |
|-------|---------|
| `regulatory-database` | Requirement monitoring |
| `alert-manager` | Deadline tracking |
| `checklist-generator` | Documentation requirements |
| `audit-trail` | Compliance evidence |

#### Partnership Evaluator
| Shard | Purpose |
|-------|---------|
| `public-records` | Background research |
| `financial-data` | Financial health |
| `ach` | Opportunity evaluation |
| `report-generator` | Decision documentation |

---

### 🏠 Personal / Family

#### Estate Settlement
| Shard | Purpose |
|-------|---------|
| `document-classifier` | Sort incoming documents |
| `entity-extraction` | Account/asset identification |
| `checklist-generator` | Task list generation |
| `alert-manager` | Probate deadlines |
| `report-generator` | Estate summary |

#### Estate Planning
| Shard | Purpose |
|-------|---------|
| `document-classifier` | Document inventory |
| `entity-extraction` | Beneficiary mapping |
| `checklist-generator` | Planning checklist |
| `report-generator` | Letter of instruction |

#### Divorce Documentation
| Shard | Purpose |
|-------|---------|
| `financial-statement-parser` | Asset tracking |
| `email-parser` | Communication log |
| `timeline` | Key events |
| `evidence-packet` | Court preparation |

#### Elder Care Coordinator
| Shard | Purpose |
|-------|---------|
| `medical-record-parser` | Health tracking |
| `financial-statement-parser` | Financial oversight |
| `alert-manager` | Medication, appointments |
| `workflow-manager` | Care coordination |

#### Adoption Research
| Shard | Purpose |
|-------|---------|
| `public-records` | Agency vetting |
| `checklist-generator` | Requirements by type |
| `alert-manager` | Process deadlines |
| `document-classifier` | Home study prep |

#### Insurance Inventory
| Shard | Purpose |
|-------|---------|
| `document-classifier` | Policy organization |
| `contract-parser` | Coverage extraction |
| `comparison-engine` | Gap analysis |
| `alert-manager` | Renewal tracking |

---

### 🔬 Hobbyist / Enthusiast

#### Genealogy Research
| Shard | Purpose |
|-------|---------|
| `public-records` | Vital records integration |
| `entity-extraction` | Person identification |
| `relationship-graph` | Family tree building |
| `contradiction-engine` | Conflicting records |
| `timeline` | Generational chronology |

#### True Crime Analysis
| Shard | Purpose |
|-------|---------|
| `timeline` | Event reconstruction |
| `entity-extraction` | Person/place identification |
| `ach` | Theory evaluation |
| `contradiction-engine` | Witness inconsistencies |
| `relationship-graph` | Connection mapping |

#### Sports Analytics
| Shard | Purpose |
|-------|---------|
| `pattern-detector` | Performance patterns |
| `timeline` | Season/career tracking |
| `comparison-engine` | Player/team comparison |
| `report-generator` | Analysis reports |

#### Collecting/Authentication
| Shard | Purpose |
|-------|---------|
| `timeline` | Provenance tracking |
| `credibility-scorer` | Source assessment |
| `comparison-engine` | Authenticity verification |
| `news-archive` | Market research |

#### Conspiracy Debunking
| Shard | Purpose |
|-------|---------|
| `claim-extractor` | Identify assertions |
| `citation-tracer` | Source verification |
| `contradiction-engine` | Internal inconsistencies |
| `credibility-scorer` | Source reliability |
| `report-generator` | Debunking documentation |

#### Historical Research
| Shard | Purpose |
|-------|---------|
| `timeline` | Event chronology |
| `entity-extraction` | Historical figures |
| `contradiction-engine` | Conflicting accounts |
| `citation-tracer` | Primary source tracking |
| `wayback-integration` | Historical documents |

---

### 🛡️ Security & Privacy

#### Stalker Documentation
| Shard | Purpose |
|-------|---------|
| `timeline` | Incident logging |
| `ingest` | Evidence preservation |
| `geospatial` | Location tracking |
| `evidence-packet` | Restraining order prep |

#### Doxxing Response
| Shard | Purpose |
|-------|---------|
| `entity-extraction` | Exposed info tracking |
| `letter-generator` | Takedown requests |
| `checklist-generator` | Protection steps |
| `alert-manager` | Monitoring |

#### Data Breach Response
| Shard | Purpose |
|-------|---------|
| `entity-extraction` | Affected account inventory |
| `checklist-generator` | Response steps |
| `alert-manager` | Credit monitoring |
| `timeline` | Breach timeline |

#### Device Audit
| Shard | Purpose |
|-------|---------|
| `ingest` | App/permission data |
| `pattern-detector` | Anomaly detection |
| `report-generator` | Audit report |

#### Threat Assessment
| Shard | Purpose |
|-------|---------|
| `ach` | Threat actor analysis |
| `entity-extraction` | Actor identification |
| `credibility-scorer` | Threat credibility |
| `timeline` | Incident history |

---

### 🌍 Activist / NGO

#### Human Rights Documentation
| Shard | Purpose |
|-------|---------|
| `ingest` | Incident recording |
| `entity-extraction` | Victim/perpetrator identification |
| `timeline` | Event chronology |
| `geospatial` | Incident mapping |
| `audit-trail` | Chain of custody |
| `evidence-packet` | Report preparation |

#### Environmental Monitoring
| Shard | Purpose |
|-------|---------|
| `public-records` | Permit tracking |
| `timeline` | Violation history |
| `geospatial` | Impact mapping |
| `entity-extraction` | Polluter identification |
| `report-generator` | Violation documentation |

#### Corporate Accountability
| Shard | Purpose |
|-------|---------|
| `financial-data` | Corporate research |
| `entity-extraction` | Supply chain mapping |
| `news-archive` | Practice documentation |
| `contradiction-engine` | Greenwashing detection |
| `relationship-graph` | Ownership structure |

#### Election Monitoring
| Shard | Purpose |
|-------|---------|
| `ingest` | Incident reporting |
| `geospatial` | Incident mapping |
| `pattern-detector` | Anomaly detection |
| `report-generator` | Observation reports |

#### Refugee Assistance
| Shard | Purpose |
|-------|---------|
| `document-classifier` | Case documentation |
| `news-archive` | Country condition research |
| `checklist-generator` | Legal status requirements |
| `timeline` | Case history |

---

### 🎮 Creative / Content

#### Worldbuilding Bible
| Shard | Purpose |
|-------|---------|
| `contradiction-engine` | Consistency checking |
| `timeline` | Historical chronology |
| `entity-extraction` | Character/place tracking |
| `relationship-graph` | Relationship mapping |

#### Research for Fiction
| Shard | Purpose |
|-------|---------|
| `search` | Topic research |
| `timeline` | Period accuracy |
| `claim-extractor` | Fact collection |
| `annotation` | Research notes |

#### Content Authenticity
| Shard | Purpose |
|-------|---------|
| `timeline` | Creation timestamp proof |
| `audit-trail` | Version history |
| `comparison-engine` | Plagiarism defense |

#### Collaboration Tracker
| Shard | Purpose |
|-------|---------|
| `entity-extraction` | Contributor identification |
| `audit-trail` | Contribution logging |
| `version-control` | Change tracking |

#### Rights Management
| Shard | Purpose |
|-------|---------|
| `contract-parser` | License extraction |
| `alert-manager` | Expiration tracking |
| `entity-extraction` | Licensee tracking |

---

### 💰 Financial Analysis

#### Investment Research
| Shard | Purpose |
|-------|---------|
| `financial-data` | SEC filings, market data |
| `financial-statement-parser` | Statement analysis |
| `pattern-detector` | Trend detection |
| `news-archive` | Company news |
| `summary-generator` | Research synthesis |

#### Financial Statement Analyzer
| Shard | Purpose |
|-------|---------|
| `financial-statement-parser` | Data extraction |
| `pattern-detector` | Ratio analysis, red flags |
| `comparison-engine` | Period-over-period |
| `contradiction-engine` | Internal inconsistencies |
| `report-generator` | Analysis report |

#### Fraud Detection
| Shard | Purpose |
|-------|---------|
| `benford-analyzer` | Statistical distribution |
| `pattern-detector` | Transaction anomalies |
| `duplicate-transaction` | Duplicate detection |
| `timeline` | Activity chronology |
| `relationship-graph` | Entity connections |

#### Tax Document Organizer
| Shard | Purpose |
|-------|---------|
| `document-classifier` | Document categorization |
| `financial-statement-parser` | Data extraction |
| `checklist-generator` | Required documents |
| `alert-manager` | Deadline tracking |

#### Personal Finance Forensics
| Shard | Purpose |
|-------|---------|
| `financial-statement-parser` | Statement parsing |
| `duplicate-transaction` | Fee detection |
| `pattern-detector` | Subscription tracking |
| `timeline` | Spending history |

#### Crypto Trail Tracker
| Shard | Purpose |
|-------|---------|
| `entity-extraction` | Wallet identification |
| `relationship-graph` | Transaction flow |
| `timeline` | Transaction history |
| `pattern-detector` | Mixing detection |

---

### 🏢 Corporate Audit/Compliance

#### Contract Review Suite
| Shard | Purpose |
|-------|---------|
| `contract-parser` | Clause extraction |
| `alert-manager` | Deadline tracking |
| `comparison-engine` | Standard deviation flagging |
| `pattern-detector` | Non-standard terms |
| `checklist-generator` | Obligation tracking |

#### Compliance Checker
| Shard | Purpose |
|-------|---------|
| `regulatory-database` | Requirement mapping |
| `comparison-engine` | Policy vs practice |
| `pattern-detector` | Violation detection |
| `report-generator` | Compliance report |
| `audit-trail` | Evidence documentation |

#### Vendor Audit
| Shard | Purpose |
|-------|---------|
| `contract-parser` | Contract terms |
| `pattern-detector` | Performance issues |
| `credibility-scorer` | Risk assessment |
| `report-generator` | Audit report |

#### Expense Audit
| Shard | Purpose |
|-------|---------|
| `form-parser` | Expense extraction |
| `pattern-detector` | Policy violations |
| `duplicate-transaction` | Duplicate detection |
| `benford-analyzer` | Statistical analysis |

#### Timesheet Analyzer
| Shard | Purpose |
|-------|---------|
| `form-parser` | Time entry extraction |
| `pattern-detector` | Anomaly detection |
| `comparison-engine` | Allocation validation |
| `report-generator` | Analysis report |

#### Form Validation
| Shard | Purpose |
|-------|---------|
| `form-parser` | Field extraction |
| `comparison-engine` | Completeness checking |
| `pattern-detector` | Copy-paste detection |
| `contradiction-engine` | Consistency checking |

#### Internal Controls Testing
| Shard | Purpose |
|-------|---------|
| `approval-chain-validator` | Authorization verification |
| `pattern-detector` | Segregation of duties |
| `audit-trail` | Control evidence |
| `report-generator` | Test documentation |

#### Regulatory Filing Prep
| Shard | Purpose |
|-------|---------|
| `regulatory-database` | Requirements |
| `checklist-generator` | Filing requirements |
| `contradiction-engine` | Cross-filing consistency |
| `report-generator` | Filing package |

---

### 📊 Due Diligence

#### M&A Due Diligence
| Shard | Purpose |
|-------|---------|
| `document-classifier` | Data room organization |
| `contract-parser` | Material contracts |
| `financial-statement-parser` | Financial analysis |
| `entity-extraction` | Key relationships |
| `ach` | Risk evaluation |
| `report-generator` | Due diligence report |

#### Startup Vetting
| Shard | Purpose |
|-------|---------|
| `public-records` | Founder backgrounds |
| `financial-data` | Cap table analysis |
| `news-archive` | Company coverage |
| `credibility-scorer` | Risk assessment |
| `ach` | Investment thesis evaluation |

#### Real Estate Due Diligence
| Shard | Purpose |
|-------|---------|
| `public-records` | Title search, permits |
| `timeline` | Property history |
| `geospatial` | Environmental analysis |
| `document-classifier` | Document organization |

#### Litigation History
| Shard | Purpose |
|-------|---------|
| `public-records` | Court records |
| `timeline` | Case chronology |
| `pattern-detector` | Litigation patterns |
| `report-generator` | Risk summary |

#### Reputation Research
| Shard | Purpose |
|-------|---------|
| `news-archive` | Media analysis |
| `social-media-archive` | Social sentiment |
| `pattern-detector` | Complaint aggregation |
| `report-generator` | Reputation summary |

---

### 🔎 Fraud Investigation

#### Expense Fraud
| Shard | Purpose |
|-------|---------|
| `entity-extraction` | Vendor identification |
| `pattern-detector` | Ghost vendor patterns |
| `duplicate-transaction` | Split transaction detection |
| `geospatial` | Address analysis |
| `relationship-graph` | Vendor connections |

#### Payroll Fraud
| Shard | Purpose |
|-------|---------|
| `entity-extraction` | Employee identification |
| `pattern-detector` | Ghost employee patterns |
| `timeline` | Termination gaps |
| `comparison-engine` | Rate change analysis |

#### Invoice Fraud
| Shard | Purpose |
|-------|---------|
| `duplicate-transaction` | Duplicate detection |
| `entity-extraction` | Vendor validation |
| `pattern-detector` | Pricing anomalies |
| `comparison-engine` | Market rate comparison |

#### Insurance Fraud
| Shard | Purpose |
|-------|---------|
| `timeline` | Claim chronology |
| `contradiction-engine` | Statement inconsistencies |
| `pattern-detector` | Claim patterns |
| `relationship-graph` | Claimant networks |

#### Benefits Fraud
| Shard | Purpose |
|-------|---------|
| `document-classifier` | Eligibility documents |
| `contradiction-engine` | Documentation inconsistencies |
| `pattern-detector` | Lifestyle indicators |
| `comparison-engine` | Eligibility verification |

#### Grant/Subsidy Fraud
| Shard | Purpose |
|-------|---------|
| `comparison-engine` | Application comparison |
| `timeline` | Fund usage tracking |
| `pattern-detector` | Outcome anomalies |
| `report-generator` | Audit documentation |

---

### 📋 Quality Assurance / Process Audit

#### Documentation Audit
| Shard | Purpose |
|-------|---------|
| `form-parser` | Completeness checking |
| `comparison-engine` | Template compliance |
| `version-control` | Version tracking |
| `report-generator` | Audit report |

#### Process Compliance
| Shard | Purpose |
|-------|---------|
| `approval-chain-validator` | Step verification |
| `timeline` | Timestamp analysis |
| `pattern-detector` | Deviation detection |
| `audit-trail` | Evidence capture |

#### Data Quality
| Shard | Purpose |
|-------|---------|
| `deduplication` | Duplicate detection |
| `pattern-detector` | Format validation |
| `contradiction-engine` | Referential integrity |
| `report-generator` | Quality report |

#### Service Level Verification
| Shard | Purpose |
|-------|---------|
| `timeline` | Response time analysis |
| `pattern-detector` | Resolution tracking |
| `comparison-engine` | SLA comparison |
| `report-generator` | Performance report |

#### Training Compliance
| Shard | Purpose |
|-------|---------|
| `entity-extraction` | Certification tracking |
| `alert-manager` | Expiration alerts |
| `pattern-detector` | Gap analysis |
| `checklist-generator` | Requirements tracking |

---

### 🏦 Banking / Lending

#### Loan File Review
| Shard | Purpose |
|-------|---------|
| `document-classifier` | File completeness |
| `form-parser` | Data extraction |
| `contradiction-engine` | Consistency checking |
| `pattern-detector` | Red flag detection |

#### Underwriting Audit
| Shard | Purpose |
|-------|---------|
| `comparison-engine` | Guideline compliance |
| `pattern-detector` | Exception patterns |
| `audit-trail` | Decision documentation |
| `report-generator` | Audit report |

#### Collateral Verification
| Shard | Purpose |
|-------|---------|
| `comparison-engine` | Valuation analysis |
| `public-records` | Title verification |
| `document-classifier` | Insurance confirmation |

#### Servicing Audit
| Shard | Purpose |
|-------|---------|
| `timeline` | Payment application |
| `financial-statement-parser` | Escrow analysis |
| `comparison-engine` | Modification compliance |

#### BSA/AML Review
| Shard | Purpose |
|-------|---------|
| `pattern-detector` | Transaction patterns |
| `entity-extraction` | Customer identification |
| `relationship-graph` | Network analysis |
| `report-generator` | SAR preparation |
| `credibility-scorer` | Customer risk rating |

---

### 🏗️ Construction / Project Management

#### Change Order Analysis
| Shard | Purpose |
|-------|---------|
| `comparison-engine` | Scope creep detection |
| `contract-parser` | Pricing validation |
| `approval-chain-validator` | Approval tracking |
| `timeline` | Change history |

#### Invoice Verification
| Shard | Purpose |
|-------|---------|
| `comparison-engine` | Work completion validation |
| `contract-parser` | Rate compliance |
| `duplicate-transaction` | Duplicate detection |
| `timeline` | Progress tracking |

#### Permit/Inspection Tracker
| Shard | Purpose |
|-------|---------|
| `public-records` | Status monitoring |
| `alert-manager` | Deadline tracking |
| `pattern-detector` | Violation flagging |
| `timeline` | Inspection history |

#### Contractor Vetting
| Shard | Purpose |
|-------|---------|
| `public-records` | License verification |
| `news-archive` | Complaint history |
| `credibility-scorer` | Reference validation |
| `report-generator` | Vetting summary |

#### Delay Documentation
| Shard | Purpose |
|-------|---------|
| `timeline` | Cause analysis |
| `entity-extraction` | Responsibility mapping |
| `evidence-packet` | Claim preparation |
| `report-generator` | Delay report |

---

### 🏫 Education / Academic Integrity

#### Plagiarism Investigation
| Shard | Purpose |
|-------|---------|
| `comparison-engine` | Text similarity |
| `citation-tracer` | Source tracing |
| `report-generator` | Investigation report |

#### Research Integrity
| Shard | Purpose |
|-------|---------|
| `pattern-detector` | Data fabrication |
| `comparison-engine` | Image manipulation |
| `benford-analyzer` | Statistical anomalies |
| `report-generator` | Integrity report |

#### Credential Verification
| Shard | Purpose |
|-------|---------|
| `public-records` | Degree confirmation |
| `document-classifier` | Transcript analysis |
| `credibility-scorer` | Certification validation |

#### Grant Compliance
| Shard | Purpose |
|-------|---------|
| `financial-statement-parser` | Fund usage tracking |
| `comparison-engine` | Requirement verification |
| `checklist-generator` | Reporting requirements |
| `report-generator` | Compliance report |

#### Title IX Documentation
| Shard | Purpose |
|-------|---------|
| `timeline` | Incident tracking |
| `entity-extraction` | Party identification |
| `evidence-packet` | Case documentation |
| `workflow-manager` | Process tracking |

---

### 🚗 Insurance Claims

#### Auto Claim Analysis
| Shard | Purpose |
|-------|---------|
| `comparison-engine` | Damage consistency |
| `financial-statement-parser` | Estimate validation |
| `geospatial` | Accident analysis |
| `pattern-detector` | Fraud indicators |

#### Property Claim Review
| Shard | Purpose |
|-------|---------|
| `document-classifier` | Inventory verification |
| `comparison-engine` | Valuation analysis |
| `contract-parser` | Coverage mapping |

#### Workers Comp Investigation
| Shard | Purpose |
|-------|---------|
| `timeline` | Injury chronology |
| `medical-record-parser` | Medical review |
| `pattern-detector` | Activity correlation |
| `contradiction-engine` | Statement analysis |

#### Disability Claim Review
| Shard | Purpose |
|-------|---------|
| `medical-record-parser` | Evidence analysis |
| `pattern-detector` | Activity correlation |
| `timeline` | Duration patterns |

#### Subrogation Research
| Shard | Purpose |
|-------|---------|
| `ach` | Liability determination |
| `entity-extraction` | Third-party identification |
| `timeline` | Recovery tracking |
| `report-generator` | Subrogation report |

---

### 🗳️ Political / Campaign

#### Donor Research
| Shard | Purpose |
|-------|---------|
| `financial-data` | Contribution records |
| `entity-extraction` | Donor identification |
| `pattern-detector` | Bundling detection |
| `relationship-graph` | Employer analysis |

#### Lobbyist Tracking
| Shard | Purpose |
|-------|---------|
| `public-records` | Registration data |
| `timeline` | Meeting logs |
| `financial-data` | Expenditure analysis |
| `relationship-graph` | Issue correlation |

#### Political Ad Analysis
| Shard | Purpose |
|-------|---------|
| `claim-extractor` | Assertion extraction |
| `contradiction-engine` | Claim verification |
| `financial-data` | Funding disclosure |
| `pattern-detector` | Targeting patterns |

#### Voting Record Compiler
| Shard | Purpose |
|-------|---------|
| `government-data` | Vote records |
| `timeline` | Position tracking |
| `contradiction-engine` | Flip-flop detection |
| `relationship-graph` | Donor correlation |

#### Dark Money Tracer
| Shard | Purpose |
|-------|---------|
| `financial-data` | Funding records |
| `entity-extraction` | Shell company identification |
| `relationship-graph` | Funding chain analysis |
| `public-records` | Corporate records |

---

### 🌐 Supply Chain / Procurement

#### Vendor Validation
| Shard | Purpose |
|-------|---------|
| `public-records` | Entity verification |
| `entity-extraction` | Ownership research |
| `regulatory-database` | Sanction screening |
| `credibility-scorer` | Risk assessment |

#### Pricing Analysis
| Shard | Purpose |
|-------|---------|
| `financial-data` | Market rates |
| `comparison-engine` | Historical trends |
| `pattern-detector` | Volume discount validation |

#### Contract Compliance
| Shard | Purpose |
|-------|---------|
| `contract-parser` | Term extraction |
| `timeline` | Delivery verification |
| `comparison-engine` | Quality documentation |
| `alert-manager` | SLA tracking |

#### Conflict Minerals
| Shard | Purpose |
|-------|---------|
| `entity-extraction` | Source tracing |
| `document-classifier` | Certification verification |
| `audit-trail` | Chain of custody |

#### Ethical Sourcing
| Shard | Purpose |
|-------|---------|
| `news-archive` | Labor practice research |
| `regulatory-database` | Environmental compliance |
| `document-classifier` | Certification tracking |
| `report-generator` | Sourcing report |

---

## Shard Inventory

### TIER 1: Core Infrastructure
*Used by nearly everything (~90%+ of bundles)*

| Shard | Description | Status |
|-------|-------------|--------|
| `frame` | Core orchestration, service registry, event bus | ✅ Exists |
| `database` | Persistence, querying, indexing | 🔨 Needed |
| `ingest` | Document intake, format detection, queuing | ✅ Exists (needs update) |
| `parse` | Text extraction, structure detection, chunking | ✅ Exists (needs update) |
| `embed` | Vector embedding, semantic indexing | ✅ Exists (needs update) |
| `search` | Full-text + semantic search | ✅ Exists (needs update) |
| `llm-service` | LLM abstraction, prompt management, response parsing | 🔨 Needed (standardize) |
| `export` | Multi-format output (PDF, HTML, MD, JSON, CSV) | 🔨 Needed (standardize) |
| `entity-extraction` | People, orgs, places, dates, custom entities | 🔨 Needed |
| `ocr` | Image/scan text extraction | 🔨 Needed |

---

### TIER 2: Analytical Core
*Used by many bundles (~50-75%)*

| Shard | Description | Status |
|-------|-------------|--------|
| `timeline` | Chronological event visualization and analysis | ✅ Exists (needs update) |
| `ach` | Analysis of Competing Hypotheses | ✅ Exists |
| `contradiction-engine` | Inconsistency detection across documents | ✅ Exists (needs update) |
| `relationship-graph` | Entity relationship mapping and visualization | ✅ Exists (needs update) |
| `pattern-detector` | Anomaly and pattern identification | 🔨 Needed |
| `claim-extractor` | Extract specific assertions from text | 🔨 Needed |
| `summary-generator` | Document/corpus summarization | 🔨 Needed |
| `comparison-engine` | Diff analysis between documents/versions | 🔨 Needed |
| `deduplication` | Find duplicate/near-duplicate content | 🔨 Needed |
| `credibility-scorer` | Source reliability assessment | 🔨 Needed |

---

### TIER 3: Domain Bridges
*Connect to external data/systems (~20-35%)*

| Shard | Description | Status |
|-------|-------------|--------|
| `public-records` | Court records, property records, corporate filings | 🔨 Needed |
| `regulatory-database` | Laws, regulations, compliance requirements | 🔨 Needed |
| `financial-data` | SEC filings, market data, company info | 🔨 Needed |
| `news-archive` | News aggregation, historical search | 🔨 Needed |
| `social-media-archive` | Platform archiving, account correlation | 🔨 Needed |
| `academic-sources` | PubMed, arxiv, journal databases | 🔨 Needed |
| `government-data` | Census, voting records, spending data | 🔨 Needed |
| `wayback-integration` | Internet Archive access, historical snapshots | 🔨 Needed |

---

### TIER 4: Document Type Specialists
*Parse specific document types (~15-30%)*

| Shard | Description | Status |
|-------|-------------|--------|
| `contract-parser` | Clause extraction, obligation identification | 🔨 Needed |
| `financial-statement-parser` | Balance sheet, income statement, cash flow | 🔨 Needed |
| `medical-record-parser` | Lab results, visit notes, medication lists | 🔨 Needed |
| `meeting-minutes-parser` | Agenda, votes, action items extraction | 🔨 Needed |
| `email-parser` | Thread reconstruction, attachment handling | 🔨 Needed |
| `form-parser` | Field extraction, completeness checking | 🔨 Needed |
| `legal-document-parser` | Case citations, holdings, procedural history | 🔨 Needed |
| `spreadsheet-analyzer` | Formula validation, cross-reference checking | 🔨 Needed |

---

### TIER 5: Analysis Specialists
*Specialized analytical techniques (~10-25%)*

| Shard | Description | Status |
|-------|-------------|--------|
| `benford-analyzer` | Statistical distribution analysis for fraud | 🔨 Needed |
| `network-analyzer` | Graph algorithms, centrality, communities | 🔨 Needed |
| `geospatial` | Location mapping, proximity analysis | 🔨 Needed |
| `sentiment-analyzer` | Tone, bias, emotional content detection | 🔨 Needed |
| `citation-tracer` | Follow references back to primary sources | 🔨 Needed |
| `duplicate-transaction` | Match transactions across accounts/systems | 🔨 Needed |
| `approval-chain-validator` | Verify proper authorization sequences | 🔨 Needed |

---

### TIER 6: Output / Action
*Generate deliverables (~20-60%)*

| Shard | Description | Status |
|-------|-------------|--------|
| `report-generator` | Narrative report assembly from findings | 🔨 Needed |
| `evidence-packet` | Legal-ready documentation bundling | 🔨 Needed |
| `checklist-generator` | Task list creation from requirements | 🔨 Needed |
| `letter-generator` | Complaint letters, FOIA requests, correspondence | 🔨 Needed |
| `presentation-builder` | Slide deck generation from findings | 🔨 Needed |
| `alert-manager` | Deadline tracking, threshold notifications | 🔨 Needed |
| `case-file-exporter` | Structured export for external systems | 🔨 Needed |

---

### TIER 7: Collaboration / Workflow
*Multi-user and process support (~20-50%)*

| Shard | Description | Status |
|-------|-------------|--------|
| `annotation` | User notes, highlights, comments on documents | 🔨 Needed |
| `tagging` | Custom categorization, filtering | 🔨 Needed |
| `workflow-manager` | Multi-step process tracking, handoffs | 🔨 Needed |
| `audit-trail` | Change logging, user action tracking | 🔨 Needed |
| `access-control` | Permissions, sharing, redaction | 🔨 Needed |
| `version-control` | Document version tracking, comparison | 🔨 Needed |

---

### TIER 8: UI / Shell
*User interface components*

| Shard | Description | Status |
|-------|-------------|--------|
| `ui-shell` | Main application shell, navigation, theming | ✅ Exists |
| `dashboard` | Overview, status, quick actions | ✅ Exists (needs update) |

---

## Shard Frequency Analysis

| Shard | Est. Bundle Usage | Priority |
|-------|-------------------|----------|
| `frame` | 100% | CRITICAL |
| `ingest` | 100% | CRITICAL |
| `parse` | 100% | CRITICAL |
| `database` | 100% | CRITICAL |
| `search` | 95% | CRITICAL |
| `embed` | 90% | CRITICAL |
| `llm-service` | 85% | CRITICAL |
| `export` | 85% | CRITICAL |
| `entity-extraction` | 80% | HIGH |
| `timeline` | 75% | HIGH |
| `summary-generator` | 70% | HIGH |
| `relationship-graph` | 70% | HIGH |
| `ocr` | 70% | HIGH |
| `contradiction-engine` | 65% | HIGH |
| `report-generator` | 60% | HIGH |
| `ach` | 60% | HIGH |
| `pattern-detector` | 55% | MEDIUM |
| `tagging` | 50% | MEDIUM |
| `claim-extractor` | 50% | MEDIUM |
| `comparison-engine` | 45% | MEDIUM |
| `annotation` | 40% | MEDIUM |
| `deduplication` | 40% | MEDIUM |
| `alert-manager` | 35% | MEDIUM |
| `public-records` | 35% | MEDIUM |
| `checklist-generator` | 30% | MEDIUM |
| `audit-trail` | 30% | MEDIUM |
| `news-archive` | 30% | MEDIUM |
| `regulatory-database` | 30% | MEDIUM |
| `contract-parser` | 30% | MEDIUM |
| `form-parser` | 30% | MEDIUM |
| `credibility-scorer` | 25% | MEDIUM |
| `financial-data` | 25% | MEDIUM |
| `email-parser` | 25% | MEDIUM |
| `spreadsheet-analyzer` | 25% | MEDIUM |
| `workflow-manager` | 25% | MEDIUM |
| `version-control` | 25% | MEDIUM |
| `letter-generator` | 20% | LOW |
| `evidence-packet` | 20% | LOW |
| `geospatial` | 20% | LOW |
| `citation-tracer` | 20% | LOW |
| `access-control` | 20% | LOW |
| `legal-document-parser` | 20% | LOW |
| `financial-statement-parser` | 20% | LOW |
| `wayback-integration` | 20% | LOW |
| `government-data` | 20% | LOW |
| `network-analyzer` | 20% | LOW |
| `duplicate-transaction` | 15% | LOW |
| `sentiment-analyzer` | 15% | LOW |
| `social-media-archive` | 15% | LOW |
| `academic-sources` | 15% | LOW |
| `presentation-builder` | 15% | LOW |
| `case-file-exporter` | 15% | LOW |
| `document-classifier` | 15% | LOW |
| `medical-record-parser` | 10% | LOW |
| `meeting-minutes-parser` | 10% | LOW |
| `benford-analyzer` | 10% | LOW |
| `approval-chain-validator` | 10% | LOW |

---

## Priority Build Order

### Phase 1: Foundation (CRITICAL)
*Must exist for anything to work*

1. `frame` ✅
2. `database`
3. `ingest` (update)
4. `parse` (update)
5. `embed` (update)
6. `search` (update)
7. `llm-service` (standardize)
8. `export` (standardize)

### Phase 2: Core Analysis (HIGH)
*Enables most analytical workflows*

9. `entity-extraction`
10. `ocr`
11. `timeline` (update)
12. `ach` ✅ (update for parity)
13. `contradiction-engine` (update)
14. `relationship-graph` (update)
15. `summary-generator`
16. `report-generator`

### Phase 3: Enhancement (MEDIUM)
*Significant value-add for many use cases*

17. `pattern-detector`
18. `claim-extractor`
19. `comparison-engine`
20. `deduplication`
21. `credibility-scorer`
22. `annotation`
23. `tagging`
24. `alert-manager`
25. `checklist-generator`

### Phase 4: Domain Bridges (MEDIUM)
*Connect to external world*

26. `public-records`
27. `regulatory-database`
28. `financial-data`
29. `news-archive`

### Phase 5: Document Specialists (LOW-MEDIUM)
*As needed for specific bundles*

30. `contract-parser`
31. `form-parser`
32. `email-parser`
33. `spreadsheet-analyzer`
34. `financial-statement-parser`
35. `legal-document-parser`

### Phase 6: Everything Else (LOW)
*Build when someone needs it*

36+ All remaining shards

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| **Total Bundles** | 67 |
| **Total User Bases** | 17 |
| **Total Unique Shards** | 58 |
| **Shards Existing** | 11 |
| **Shards Needed** | 47 |
| **Critical Priority** | 8 |
| **High Priority** | 8 |
| **Medium Priority** | 19 |
| **Low Priority** | 23 |

---

## Notes

- Existing shards marked with ✅ need updates to meet v5 manifest standards
- "Standardize" means functionality exists but is scattered across shards — consolidate into single service shard
- Bundle shard lists are illustrative, not exhaustive — actual bundles may include additional shards
- Priority is based on frequency across bundles, not complexity or effort
- Local-first architecture is assumed — shards should work offline where possible
- Privacy-sensitive bundles (medical, legal, personal) especially require local-first design

---

*This document is a living reference. Update as scope evolves.*
