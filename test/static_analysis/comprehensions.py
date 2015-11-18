[a + 1 for a in [1, 2]]

#! 3 type-error-operation
[a + '' for a in [1, 2]]
#! 3 type-error-operation
(a + '' for a in [1, 2])

#! 12 type-error-not-iterable
[a for a in 1]

tuple(str(a) for a in [1])

#! 8 type-error-operation
tuple(a + 3 for a in [''])

# ----------
# Some variables within are not defined
# ----------

#! 12 name-error
[1 for a in NOT_DEFINFED for b in a if 1]

#! 25 name-error
[1 for a in [1] for b in NOT_DEFINED if 1]

#! 12 name-error
[1 for a in NOT_DEFINFED for b in [1] if 1]

#! 19 name-error
(1 for a in [1] if NOT_DEFINED)
