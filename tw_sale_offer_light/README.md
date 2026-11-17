# Offerta light

A separate Sales menu for standard quotations alongside the Pons solar workflow.
The standalone form is based on the native Odoo 20 sale form (LGPL-3) and deliberately
avoids inheriting solar UI changes. Recheck it when upgrading Odoo's major version.

Light offers use native line taxes, discounts, pricing, numbering and PDF reports.
No extra solar project is created on confirmation; normal product-driven project
and stock behavior still applies. Solar-only total adjustments are disallowed.
Existing solar orders remain unchanged. Standard product taxes are configurable
on each line; this module does not change product or company tax defaults.

The Boolean classification is retained when copying an offer. The dedicated menu
lists only light offers; the usual sales lists may still include them for reporting.
The same native sale ACLs and record rules apply; no additional privileges or sudo.

## 20.0.1.0.0
- Add the Offerta light menu and isolated standard form.
- Keep native confirmation, invoice preparation and email/PDF handling for light offers.
