# Proof swift.force_unwrap_risk:fixtures.swift.vertical.force_unwrap_risk.swift:4:12

- Tier: 2
- Kind: repro_steps
- Supported: True

## Trigger
Call `loadTitle` such that `value` is nil, reaching fixtures/swift/vertical/force_unwrap_risk.swift:4.

## Expected
Process crashes on force unwrap of a nil optional.

## Steps
1. Enter `loadTitle` with `value` = nil.
2. Follow path: 2 nodes; 1 path(s) explored; operand `value` nilness=unknown
3. Execute the force unwrap at line 4.
4. Observe a runtime crash (EXC_BAD_INSTRUCTION / unexpectedly found nil).
