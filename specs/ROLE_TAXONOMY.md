# SemiSkill — Semiconductor Role Taxonomy & Skill Seed Catalog

Purpose: the authoritative list of **every role × every level** across a semiconductor company,
each mapped to a **role-enablement Agent Skill** to be generated, security-verified, and published
into SemiSkill. This file is the work-list for the catalog-seeding phase (Phase G of
`ULTRA_PLAN_PROMPT.md`). Every generated skill must pass the L4/L6 verification pipeline and the
human approval gate before it appears in SharePoint — no seed skill is exempt.

Skill slug convention: `<function>/<role-or-task>-<level?>`. One "role guide" skill per role, plus
per-task skills where a role owns distinct workflows.

---

## 1. Universal seniority ladder (applies across all functions)

### 1a. Individual-contributor (IC) / technical track
| Level band | Titles | Typical level code | Skill-tier tag |
|---|---|---|---|
| Entry / Fresher | Intern, Graduate Trainee, Apprentice, Fresher | I0 / E0 | `fresher` |
| Junior | Junior Engineer, Associate Engineer, Engineer I/II | E1–E2 | `junior` |
| Intermediate | Engineer, Engineer III, Design Engineer | E3 | `intermediate` |
| Senior | Senior Engineer, Senior Design/Verification Engineer | E4 | `senior` |
| Staff | Staff Engineer | E5 | `staff` |
| Senior Staff | Senior Staff Engineer | E6 | `senior-staff` |
| Principal | Principal Engineer | E7 | `principal` |
| Senior Principal / Distinguished | Senior Principal Engineer, Distinguished Engineer | E8 | `distinguished` |
| Fellow | Fellow, Senior Fellow, Technical VIP | E9 | `fellow` |
| Architect track | Design Architect, SoC Architect, Chief Architect | (parallel to E6–E9) | `architect` |

### 1b. Management / leadership track
| Level band | Titles | Skill-tier tag |
|---|---|---|
| Lead | Team Lead, Tech Lead, Lead Engineer | `lead` |
| First-line manager | Engineering Manager, Manager | `manager` |
| Mid manager | Senior Manager | `senior-manager` |
| Director | Director, Design Director | `director` |
| Senior Director | Senior Director | `senior-director` |
| VP | Vice President, Group VP | `vp` |
| SVP/EVP | Senior/Executive Vice President | `evp` |
| C-suite | CEO, CTO, COO, CFO, CHRO, CMO, CIO, CSO, GM/President BU | `exec` |
| Board | Board Member, Chairperson | `board` |

Each functional role below inherits the relevant ladder. The seeding phase produces one skill per
(role × level) where the level materially changes the workflow (e.g., `rtl-design-fresher` vs
`rtl-design-architect`), and one shared "role guide" skill otherwise.

---

## 2. Engineering — Design & Verification (Front-End / RTL)
- **RTL / Logic Design** — RTL Design Engineer, Digital Design Engineer, Micro-architecture Engineer,
  RTL Lead, Design Architect. Skills: `design/rtl-design`, `design/microarchitecture-spec`,
  `design/rtl-lint-cdc`, `design/clock-reset-architecture`, `design/low-power-uPF-design`.
- **Design Verification (DV)** — Verification Engineer, DV Engineer, UVM Engineer, Formal Verification
  Engineer, Verification Lead, Verification Architect. Skills: `dv/uvm-testbench`,
  `dv/coverage-closure`, `dv/formal-property-verification`, `dv/assertion-sva`,
  `dv/verification-plan`, `dv/regression-triage`.
- **SoC Integration & Architecture** — SoC Architect, System Architect, Integration Engineer,
  Performance Architect, Chief Architect. Skills: `arch/soc-architecture`, `arch/performance-modeling`,
  `arch/ip-integration`, `arch/bus-noc-fabric`, `arch/power-performance-area-tradeoff`.
- **IP Design** — IP Design Engineer, IP Verification Engineer, IP Product Owner.
  Skills: `ip/ip-design`, `ip/ip-hardening`, `ip/ip-qualification`.
- **DFT (Design-for-Test)** — DFT Engineer, DFT Architect, Scan/MBIST Engineer.
  Skills: `dft/scan-insertion`, `dft/mbist`, `dft/atpg-patterns`, `dft/jtag-boundary-scan`.
- **Low Power** — Low Power Design Engineer, Power Architect. Skills: `lowpower/upf-cpf`,
  `lowpower/power-intent-verification`, `lowpower/dvfs-strategy`.

## 3. Engineering — Physical Design / Back-End
- Physical Design Engineer, PnR Engineer, Floorplanning Engineer, CTS Engineer, PD Lead, PD Architect.
  Skills: `pd/floorplanning`, `pd/place-and-route`, `pd/clock-tree-synthesis`, `pd/congestion-fix`.
- **Static Timing Analysis (STA)** — STA Engineer, Timing Signoff Engineer, Timing Architect.
  Skills: `sta/timing-constraints-sdc`, `sta/timing-closure`, `sta/ocv-aocv`, `sta/eco-timing`.
- **Physical Verification / Signoff** — PV Engineer, Signoff Engineer. Skills: `signoff/drc-lvs`,
  `signoff/ir-drop-em`, `signoff/antenna-density`, `signoff/lec-formal-equivalence`.
- **Library / PDK / Standard Cell** — Library Characterization Engineer, PDK Engineer.
  Skills: `lib/liberty-characterization`, `lib/pdk-qualification`.

## 4. Engineering — Analog / Mixed-Signal / RF
- Analog Design Engineer, Mixed-Signal Designer, RF Engineer, Layout Engineer (Analog),
  Analog Architect. Skills: `analog/schematic-design`, `analog/spice-simulation`,
  `analog/analog-layout`, `analog/rf-frontend-design`, `analog/pll-adc-dac-design`,
  `analog/esd-io-design`.

## 5. Engineering — CAD / EDA / Design Enablement / Methodology
- CAD Engineer, EDA Engineer, Methodology Engineer, Flow Developer, Design Infrastructure Engineer,
  Release/Integration Engineer. Skills: `cad/flow-automation`, `cad/tcl-scripting`,
  `cad/eda-tool-integration`, `cad/compute-farm-lsf`, `cad/pdk-flow-release`, `cad/git-design-data-mgmt`.

## 6. Engineering — Silicon Validation / Post-Silicon / Product & Test
- **Post-Silicon Validation** — Silicon Validation Engineer, Bring-up Engineer, Characterization
  Engineer. Skills: `postsi/silicon-bringup`, `postsi/characterization`, `postsi/debug-triage`.
- **Product Engineering** — Product Engineer, Yield Engineer, Failure Analysis Engineer.
  Skills: `prodeng/yield-analysis`, `prodeng/failure-analysis`, `prodeng/binning-strategy`.
- **Test Engineering** — Test Engineer, ATE Engineer, Test Program Developer, Test Hardware Engineer.
  Skills: `test/ate-program`, `test/test-hardware-loadboard`, `test/test-time-optimization`.

## 7. Engineering — Process / Fab / Manufacturing (Foundry & IDM)
- Process Integration Engineer, Process Engineer (Litho/Etch/Diffusion/Thin-Films/CMP),
  Equipment Engineer, Yield Enhancement Engineer, Defect/Metrology Engineer, Fab Manager.
  Skills: `fab/process-integration`, `fab/litho-opc`, `fab/etch-process`, `fab/spc-control`,
  `fab/defect-metrology`, `fab/equipment-maintenance`, `fab/yield-ramp`.
- **Packaging & Assembly** — Package Design Engineer, Assembly Engineer, Thermal Engineer,
  Signal-Integrity Engineer. Skills: `pkg/package-design`, `pkg/thermal-analysis`,
  `pkg/signal-power-integrity`, `pkg/advanced-2_5d-3d-packaging`.

## 8. Engineering — Reliability & Quality
- Reliability Engineer, Quality Engineer, Qualification Engineer, FA Engineer, Automotive/Functional-
  Safety (ISO 26262) Engineer. Skills: `quality/reliability-qual`, `quality/iso26262-functional-safety`,
  `quality/apqp-ppap`, `quality/8d-rca`, `quality/jedec-qualification`.

## 9. Engineering — Firmware / Embedded / Software / Systems
- Firmware Engineer, Embedded Software Engineer, Device Driver Engineer, BSP Engineer, Validation
  SW Engineer, Systems Engineer, Applications Engineer, Field Applications Engineer (FAE),
  Solutions Architect. Skills: `sw/firmware-development`, `sw/device-drivers`, `sw/rtos-bsp`,
  `sw/emulation-fpga-prototyping`, `sys/systems-engineering`, `sys/applications-engineering`,
  `sys/fae-customer-enablement`, `sys/reference-design`.

## 10. Product & Program
- **Product Management** — Product Manager, Senior PM, Product Line Manager, Director of Product,
  VP Product. Skills: `product/prd-authoring`, `product/roadmap-planning`, `product/mrd-market-req`,
  `product/pricing-strategy`, `product/competitive-analysis`, `product/lifecycle-eol`.
- **Product Marketing** — Product Marketing Manager, Technical Marketing Engineer (TME).
  Skills: `pmm/positioning-messaging`, `pmm/technical-collateral`, `pmm/launch-plan`,
  `pmm/datasheet-authoring`, `pmm/design-win-enablement`.
- **Program / Project Management** — Program Manager, Project Manager, NPI Program Manager, PMO Lead,
  Scrum Master. Skills: `program/npi-program-mgmt`, `program/schedule-critical-path`,
  `program/risk-register`, `program/tapeout-checklist`, `program/agile-scrum`.

## 11. Sales & Business Development
- Sales Engineer, Account Manager, Regional Sales Manager, Distribution Manager, Business Development
  Manager, Sales Director, VP Sales, CRO. Skills: `sales/technical-pre-sales`,
  `sales/account-planning`, `sales/design-win-pipeline`, `sales/rfq-quote`, `sales/crm-hygiene`,
  `sales/distributor-management`, `sales/forecasting`, `bd/partnership-deals`.

## 12. Marketing (Corporate / Digital / Brand)
- Marketing Manager, Digital Marketing Specialist, Content Marketing Manager, Brand Manager,
  Events/Field Marketing, Marketing Analyst, CMO. Skills: `mktg/campaign-planning`,
  `mktg/content-seo`, `mktg/social-media`, `mktg/webinar-events`, `mktg/marketing-analytics`,
  `mktg/pr-comms`, `mktg/brand-guidelines`.

## 13. Finance
- **FP&A** — Financial Analyst, FP&A Manager, Finance Business Partner, Finance Director, VP Finance,
  CFO. Skills: `finance/fpa-budgeting`, `finance/forecast-modeling`, `finance/variance-analysis`,
  `finance/capex-opex`, `finance/business-case-roi`.
- **Accounting** — Accountant, Cost Accountant, GL Accountant, AP/AR Specialist, Controller.
  Skills: `finance/month-end-close`, `finance/cost-accounting`, `finance/accounts-payable`,
  `finance/accounts-receivable`, `finance/revenue-recognition`.
- **Treasury / Tax / Audit** — Treasury Analyst, Tax Manager, Internal Auditor.
  Skills: `finance/treasury-cash-mgmt`, `finance/tax-compliance`, `finance/internal-audit-sox`.

## 14. HR & Payroll
- **HR** — HR Generalist, HR Business Partner, Talent Acquisition / Recruiter, L&D Specialist,
  Comp & Benefits Analyst, HR Director, CHRO. Skills: `hr/recruiting-sourcing`,
  `hr/interview-scorecard`, `hr/onboarding`, `hr/performance-review`, `hr/comp-benefits-benchmark`,
  `hr/learning-development`, `hr/employee-relations`, `hr/org-design`, `hr/hrbp-partnering`.
- **Payroll** — Payroll Specialist, Payroll Manager, Payroll Analyst. Skills: `payroll/payroll-run`,
  `payroll/payroll-compliance-tax`, `payroll/timesheet-attendance`, `payroll/equity-rsu-admin`,
  `payroll/expense-reimbursement`.

## 15. Operations / Supply Chain / Procurement
- Operations Manager, Supply Chain Planner, Demand Planner, Procurement/Sourcing Manager, Buyer,
  Logistics Coordinator, Foundry/OSAT Relationship Manager, Ops Director, COO.
  Skills: `ops/demand-supply-planning`, `ops/procurement-sourcing`, `ops/supplier-scorecard`,
  `ops/foundry-osat-mgmt`, `ops/inventory-mgmt`, `ops/logistics-export-compliance`, `ops/s_and_op`.

## 16. IT / Infrastructure / Security
- IT Support Engineer, Systems Administrator, DevOps Engineer, Cloud Engineer, Network Engineer,
  Information Security Engineer, CISO. Skills: `it/helpdesk-support`, `it/compute-storage-admin`,
  `it/devops-cicd`, `it/cloud-infra`, `it/network-admin`, `sec/infosec-controls`,
  `sec/identity-access-mgmt`, `sec/incident-response`.

## 17. Legal / IP / Compliance
- Legal Counsel, IP/Patent Attorney, Patent Engineer, Contracts Manager, Compliance Officer,
  Export-Control Specialist, General Counsel. Skills: `legal/contract-review`,
  `legal/patent-drafting`, `legal/ip-portfolio-mgmt`, `legal/export-control-itar-ear`,
  `legal/nda-management`, `legal/regulatory-compliance`.

## 18. Executive Leadership
- CEO, President, COO, CTO, CFO, CHRO, CMO, CIO, CSO/CISO, CRO, GM (Business Unit), Board.
  Skills: `exec/strategy-okrs`, `exec/board-reporting`, `exec/investor-relations`,
  `exec/ma-diligence`, `exec/org-scaling`, `exec/executive-briefing`.

---

## 19. Cross-cutting skill families (apply to every role/level)
- Level-adaptive onboarding guides: `onboarding/<function>-<level>` (fresher → architect/exec).
- Career-ladder & competency maps: `career/<function>-competency-matrix`.
- Universal productivity: `common/status-reporting`, `common/meeting-notes`, `common/doc-writing`,
  `common/interviewing`, `common/mentoring`, `common/okr-goal-setting`.

## 20. Seeding rules (enforced by the pipeline)
1. Every seed skill is generated as a proper Agent Skill (`SKILL.md` + assets), then submitted through
   L1 like any other — **no back-door inserts** into the SharePoint catalog.
2. Each seed skill runs the full L4/L6 verification pipeline and requires human approval before publish.
3. Tag every seed skill with `function`, `role`, `level-tier`, and `owner` metadata for L3 search/faceting.
4. De-duplicate against community submissions; a seed skill is superseded (not deleted) when a better
   human-authored one is approved.
5. Generate in waves by function (Design/Verification first — the company's core), verify each wave,
   publish, then proceed — mirroring the AIOS phased, evaluated rollout.
