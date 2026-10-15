# Failed evaluation attempt

The fixed-split evaluator correctly refused the 25-experiment candidate because
its established split is defined only for logical IDs 1–19. No model fit or
predictions were produced. The fixed evaluation is rerun using a separately
saved 1–19 subset, after verifying it is byte-equivalent by rows to the prior
candidate used for the 13/6 neural comparison.
