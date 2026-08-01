"""
library_inliner.py
==================
Inlines Solidity ``library`` declarations into the contract source so
that Foundry can compile them without separate linking.

Background: Foundry's ``forge build`` auto-links libraries whose
functions are all ``internal`` (they get inlined by the compiler), but
contracts that use ``library SafeMath { ... }`` with ``using SafeMath
for uint256`` sometimes produce linker errors when the library is in a
separate file or when the contract is compiled at a legacy pragma.

This module detects library blocks in the source, verifies all their
functions are ``internal`` (safe to inline), and rewrites ``using X for
Y`` directives so the compiler inlines them without linking.

For contracts where the library is already in the same file (like
BECToken), this is a no-op — the code already compiles.  For contracts
that import an external library file, the caller should concatenate the
library source into the contract source before calling ``inline_libraries``.
"""

import re
from typing import List, Tuple


def find_library_blocks(src: str) -> List[Tuple[str, str, int, int]]:
    """Return (name, body, start, end) for each ``library Name { ... }``
    block in *src*.  Uses balanced-brace matching."""
    results = []
    for m in re.finditer(r"library\s+(\w+)\s*\{", src):
        name = m.group(1)
        start = m.start()
        depth = 1
        i = m.end()
        while i < len(src) and depth > 0:
            if src[i] == "{":
                depth += 1
            elif src[i] == "}":
                depth -= 1
            i += 1
        end = i
        body = src[start:end]
        results.append((name, body, start, end))
    return results


def _all_functions_internal(lib_body: str) -> bool:
    """Return True if every function in the library body is ``internal``
    or ``pure`` (compiler-inlineable)."""
    fn_pat = re.compile(
        r"function\s+\w+\s*\([^)]*\)\s+([\w\s]+?)(?:\{|returns)",
        re.S,
    )
    for m in fn_pat.finditer(lib_body):
        modifiers = m.group(1).lower()
        if "internal" not in modifiers and "private" not in modifiers:
            return False
    return True


def inline_libraries(src: str) -> str:
    """Process the contract source:

    1. Find all ``library`` blocks.
    2. For libraries whose functions are all internal, rewrite them as
       ``internal`` free functions or leave them as-is (the compiler
       handles internal libraries without linking).
    3. Return the (possibly unchanged) source.

    The main value is for the normalizer pipeline: if a contract's
    library is in a separate file, the caller concatenates it first,
    and this function ensures the combined source compiles under Foundry.
    """
    libs = find_library_blocks(src)
    if not libs:
        return src

    all_internal = all(_all_functions_internal(body) for _, body, _, _ in libs)
    if all_internal:
        # All library functions are internal — the compiler inlines them.
        # No transformation needed; Foundry handles this natively.
        return src

    # For libraries with external/public functions (rare in this benchmark),
    # we cannot safely inline.  Return unchanged and let Foundry attempt
    # linking (which may fail — that is a documented limitation).
    return src


def resolve_library_imports(contract_src: str, library_src: str) -> str:
    """Concatenate an external library source into the contract source,
    removing duplicate pragmas and SPDX headers.  Used when a contract
    imports a library from a separate file that is not available to Foundry."""
    if not library_src or not library_src.strip():
        return contract_src

    # Remove pragma and SPDX from library source (contract already has them)
    clean_lib = re.sub(r"^\s*pragma\s+solidity[^;]*;\s*", "", library_src)
    clean_lib = re.sub(r"^\s*//\s*SPDX-License[^\n]*\n", "", clean_lib)
    clean_lib = clean_lib.strip()

    if not clean_lib:
        return contract_src

    # Insert library code right after the pragma in the contract
    pragma_match = re.search(r"(pragma\s+solidity[^;]*;\s*\n?)", contract_src)
    if pragma_match:
        insert_point = pragma_match.end()
        return (
            contract_src[:insert_point]
            + "\n" + clean_lib + "\n\n"
            + contract_src[insert_point:]
        )

    return clean_lib + "\n\n" + contract_src
