* AI4MS Stata analysis template
* This file is a human-editable draft. Main analysis requires G3 approval.

version 18.0
clear all
set more off
set varabbrev off
capture log close _all

args project_dir run_id input_dta output_dir
if `"`project_dir'"' == "" | `"`run_id'"' == "" | `"`input_dta'"' == "" | `"`output_dir'"' == "" {
    display as error "usage: do analysis_template.do project_dir run_id input_dta output_dir"
    exit 198
}

cd `"`project_dir'"'
log using `"`output_dir'/`run_id'.smcl"', replace name(ai4ms_smcl)
log using `"`output_dir'/`run_id'.log"', text replace name(ai4ms_text)

display as text "AI4MS_RUN_ID=`run_id'"
display as text "AI4MS_STARTED_AT=$S_DATE $S_TIME"
about
display as text "AI4MS_ADOPATH"
adopath

* These values are rendered from the approved Analysis Plan.
local outcome  "innovation_quality"
local treatment "ai_adoption"
local controls "firm_size leverage roa"
local panel_id "firm_id"
local time_id "year"
local cluster_id "firm_id"

use `"`input_dta'"', clear
datasignature
describe
misstable summarize `outcome' `treatment' `controls'

foreach variable in `outcome' `treatment' `controls' `panel_id' `time_id' `cluster_id' {
    capture confirm variable `variable'
    if _rc {
        display as error "AI4MS_PREFLIGHT_MISSING_VARIABLE=`variable'"
        exit 111
    }
}

capture isid `panel_id' `time_id'
if _rc {
    display as error "AI4MS_PREFLIGHT_PANEL_KEY_NOT_UNIQUE"
    duplicates report `panel_id' `time_id'
    exit 459
}

xtset `panel_id' `time_id'
set seed 20260716

* ---------------------------------------------------------------------------
* AI4MS HUMAN-EDITABLE ANALYSIS BLOCK
* Every semantic edit creates a new do-file revision and may invalidate G3.
* ---------------------------------------------------------------------------

regress `outcome' `treatment' `controls', vce(cluster `cluster_id')
estimates store baseline_ols

xtreg `outcome' `treatment' `controls' i.`time_id', fe vce(cluster `cluster_id')
estimates store baseline_fe

etable, estimates(baseline_ols baseline_fe) cstat(_r_b) cstat(_r_se) showstars
collect export `"`output_dir'/main_results.xlsx"', replace

* Add design-specific diagnostics and robustness tests from the approved plan.

* ---------------------------------------------------------------------------
* END HUMAN-EDITABLE ANALYSIS BLOCK
* ---------------------------------------------------------------------------

estimates save `"`output_dir'/baseline_fe.ster"', replace
display as text "AI4MS_COMPLETED_AT=$S_DATE $S_TIME"
log close ai4ms_text
log close ai4ms_smcl
exit 0

