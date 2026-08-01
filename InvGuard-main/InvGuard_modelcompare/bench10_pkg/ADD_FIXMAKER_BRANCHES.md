# Add FixMaker branches for tx.origin (T5) and overflow (T4)

Your pipeline already has **attack templates** for all 5 classes (T1–T5) and they
all confirm impact. But the class-aware **FixMaker** only has explicit repair
instructions for 3 keys: `access_control`, `unchecked_call`,
`denial_of_service`/`bad_randomness`. Reentrancy is covered by the CEI default.

That leaves **tx.origin (T5)** and **integer_overflow (T4)** with a working
attack but no dedicated fix — they fall through to the CEI default, which won't
repair them, so they'd land in `gate_rejected`.

Two ~6-line additions fix that. In `flow_2_files/agent.py`, find the
`_classaware_fix_instruction = { ... }` dict (around line 2643, the one whose
keys are `"access_control"`, `"unchecked_call"`, `"bad_randomness"`,
`"denial_of_service"`). Add these two entries to that dict, right after the
`"denial_of_service"` entry and before the closing `}.get(_vclass, ...)`:

```python
            "tx_origin": (
                "This is a tx.origin AUTHENTICATION bug. {fn}() uses "
                "`tx.origin` for authorization, which a malicious intermediary "
                "contract can exploit by getting the owner to call it. Replace "
                "every `tx.origin == <owner>` authentication check in {fn}() "
                "with `msg.sender == <owner>`. Do not change anything else."
            ).format(fn=TARGET_FUNCTION),
            "integer_overflow": (
                "This is an INTEGER-OVERFLOW/UNDERFLOW bug. {fn}() performs "
                "arithmetic that can wrap around (an `unchecked {{ }}` block on "
                "0.8+, or implicit wrapping on pragma <0.8.0). Remove the "
                "`unchecked` block so the compiler's built-in checks apply, or "
                "on pre-0.8 add an explicit bound check (e.g. require the result "
                "does not wrap) before writing the result. Preserve intended "
                "behavior for non-overflowing inputs."
            ).format(fn=TARGET_FUNCTION),
```

That's the whole change. No other edits needed — `INVGUARD_VULN_CLASS=tx_origin`
and `INVGUARD_VULN_CLASS=integer_overflow` from the manifest now route to these
instructions. The manifest already passes those exact class strings.

Apply with the patcher (`patch_fixmaker_classes.py`) or by hand; the patcher
backs up the file as `agent.py.bak_fixclasses`.
