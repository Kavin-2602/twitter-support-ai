# Golden Set Annotation Notes

## Data Loss Incident
During the creation of the 200-row stratified golden set, a mid-project file corruption incident resulted in the loss of 132 rows of manual annotations. These 132 rows were subsequently relabelled during a distinct, secondary session. One row was permanently corrupted and dropped, resulting in a final count of 199 rows.

## Annotator Drift & Risks
Because the labelling was performed across two separate sessions under different conditions, there is a systemic risk of annotator drift. The subjective boundaries of fuzzy intent categories (specifically the "Other" bucket) may have shifted between the first and second pass, meaning the ground-truth dataset may contain internal inconsistencies.

This drift must be considered when interpreting the 71.36% intent accuracy baseline, as some agent "failures" on edge cases could actually represent valid interpretations that merely conflict with the annotator's shifting criteria.
