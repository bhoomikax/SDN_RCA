# Failed evaluation attempt

The first generalized evaluation attempt on 2026-10-15 stopped during input
validation because pandas inferred one timestamp format from mixed-precision
ISO timestamps. No model fitting or predictions were produced. The directory is
preserved; the generalized parser now accepts the documented mixed ISO format.
