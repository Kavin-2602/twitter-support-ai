# Judge Agreement Report

## Overview
This report evaluates the alignment between the LLM-as-a-judge used in our evaluation framework and human ground-truth annotations.

## Finding
The LLM judge achieved an 83% agreement rate with human annotations. The primary divergence occurred on the "Other" intent category and instances of high customer sarcasm, where the judge incorrectly penalized the agent for escalating issues that it deemed could be auto-handled. This indicates that our evaluation baseline (71.36% Accuracy) may carry a ~17% margin of error due to judge-human misalignment.
