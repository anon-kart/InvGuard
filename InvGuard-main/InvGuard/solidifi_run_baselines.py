#!/usr/bin/env python3
"""
solidifi_run_baselines.py — Run SOTA repair tools on SolidiFI cases
====================================================================
Drives each baseline tool on the selected 150 cases and collects patches.

Supported tools (in order of practical runnability):
  1. SolGPT     — OpenAI API, easiest to run
  2. sGuard     — Docker or local Java
  3. sGuard+    — Docker or local Java
  4. SmartFix   — Python + VeriSmart
  5. TIPS       — Python
  6. Elysium    — bytecode-level, Docker
  7. SmartShield— bytecode-level, Docker

USAGE:
  # Run SolGPT on all 150 cases:
  python solidifi_run_baselines.py \
      --manifest solidifi_manifest.json \
      --tool solgpt \
      --out-dir results/solidifi_baselines

  # Run sGuard via Docker:
  python solidifi_run_baselines.py \
      --manifest solidifi_manifest.json \
      --tool sguard \
      --out-dir results/solidifi_baselines

  # Run all tools sequentially:
  python solidifi_run_baselines.py \
      --manifest solidifi_manifest.json \
      --tool all \
      --out-dir results/solidifi_baselines
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TOOLS = ["solgpt", "sguard", "sguardplus", "smartfix", "tips", "elysium", "smartshield"]


# ─── SolGPT ─────────────────────────────────────────────────────────
# SolGPT (Napoli & Gatteschi 2023) sends the vulnerable contract to
# ChatGPT with a prompt asking for a corrected version.  We replicate
# their published methodology using the OpenAI API.

SOLGPT_SYSTEM = (
    "You are a smart contract security expert. You will be given a Solidity "
    "smart contract that contains a vulnerability. Your task is to fix the "
    "vulnerability while preserving the contract's intended functionality. "
    "Return ONLY the complete fixed Solidity source code, nothing else. "
    "Do not change the contract name, pragma version, or external interface "
    "unless strictly required by the fix. Do not add comments explaining "
    "the fix."
)

SOLGPT_USER = (
    "The following Solidity contract contains a {vuln_class} vulnerability. "
    "Please provide the corrected version of the complete contract.\n\n"
    "```solidity\n{source}\n```"
)

VULN_CLASS_LABELS = {
    "reentrancy": "reentrancy",
    "integer_overflow": "integer overflow/underflow",
    "unchecked_call": "unchecked external call",
    "tx_origin": "tx.origin authentication bypass",
}


def run_solgpt(manifest, out_dir, model="gpt-4o-mini"):
    """Run SolGPT-style repair using OpenAI API."""
    try:
        from openai import OpenAI
        client = OpenAI()
    except Exception as e:
        print(f"[solgpt] OpenAI client init failed: {e}")
        print("         Set OPENAI_API_KEY and install openai package.")
        return

    tool_dir = Path(out_dir) / "solgpt"
    tool_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for i, entry in enumerate(manifest):
        stem = entry["stem"]
        sol_path = entry["contract"]
        vuln_class = entry["extra_env"].get("INVGUARD_VULN_CLASS", "unknown")
        label = VULN_CLASS_LABELS.get(vuln_class, vuln_class)

        print(f"  [{i+1}/{len(manifest)}] {stem} ({label})", flush=True)

        try:
            source = Path(sol_path).read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            results.append({"stem": stem, "status": "read_error", "error": str(e)})
            continue

        prompt = SOLGPT_USER.format(vuln_class=label, source=source)

        t0 = time.time()
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SOLGPT_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=4096,
            )
            reply = resp.choices[0].message.content or ""
            elapsed = round(time.time() - t0, 2)

            patched = _extract_solidity(reply)
            if patched:
                patch_path = tool_dir / f"{stem}.sol"
                patch_path.write_text(patched, encoding="utf-8")
                results.append({
                    "stem": stem, "status": "patch_generated",
                    "patch_file": str(patch_path), "elapsed_sec": elapsed,
                    "tokens_used": resp.usage.total_tokens if resp.usage else 0,
                })
            else:
                raw_path = tool_dir / f"{stem}.raw.txt"
                raw_path.write_text(reply, encoding="utf-8")
                results.append({
                    "stem": stem, "status": "no_solidity_extracted",
                    "raw_file": str(raw_path), "elapsed_sec": elapsed,
                })

        except Exception as e:
            elapsed = round(time.time() - t0, 2)
            results.append({
                "stem": stem, "status": "api_error",
                "error": str(e)[:300], "elapsed_sec": elapsed,
            })

    summary_path = tool_dir / "_summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)

    generated = sum(1 for r in results if r["status"] == "patch_generated")
    print(f"\n  [solgpt] {generated}/{len(manifest)} patches generated")
    print(f"  [solgpt] Results saved to {tool_dir}")
    return results


def _extract_solidity(text):
    """Extract Solidity source from LLM response."""
    m = re.search(r"```(?:solidity)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    if re.search(r"pragma\s+solidity", text):
        return text.strip()
    return None


# ─── sGuard / sGuard+ ───────────────────────────────────────────────

SGUARD_DOCKER = "eguard/sguard:latest"
SGUARDPLUS_DOCKER = "sguardplus/sguardplus:latest"


def run_sguard(manifest, out_dir, variant="sguard"):
    """Run sGuard or sGuard+ via Docker."""
    docker_image = SGUARD_DOCKER if variant == "sguard" else SGUARDPLUS_DOCKER
    tool_dir = Path(out_dir) / variant
    tool_dir.mkdir(parents=True, exist_ok=True)

    if not shutil.which("docker"):
        print(f"  [{variant}] Docker not found. Install Docker or run manually.")
        _write_manual_script(manifest, tool_dir, variant)
        return

    results = []
    for i, entry in enumerate(manifest):
        stem = entry["stem"]
        sol_path = os.path.abspath(entry["contract"])
        sol_dir = os.path.dirname(sol_path)
        sol_name = os.path.basename(sol_path)

        print(f"  [{i+1}/{len(manifest)}] {stem}", flush=True)

        out_stem_dir = tool_dir / stem
        out_stem_dir.mkdir(exist_ok=True)

        t0 = time.time()
        try:
            cmd = [
                "docker", "run", "--rm",
                "-v", f"{sol_dir}:/input:ro",
                "-v", f"{out_stem_dir}:/output",
                docker_image,
                f"/input/{sol_name}",
                "-o", "/output/patched.sol",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            elapsed = round(time.time() - t0, 2)

            patch_path = out_stem_dir / "patched.sol"
            if patch_path.is_file():
                results.append({
                    "stem": stem, "status": "patch_generated",
                    "patch_file": str(patch_path), "elapsed_sec": elapsed,
                })
            else:
                (out_stem_dir / "stderr.txt").write_text(proc.stderr, encoding="utf-8")
                results.append({
                    "stem": stem, "status": "no_output",
                    "returncode": proc.returncode, "elapsed_sec": elapsed,
                })
        except subprocess.TimeoutExpired:
            results.append({"stem": stem, "status": "timeout", "elapsed_sec": 120})
        except Exception as e:
            results.append({"stem": stem, "status": "error", "error": str(e)[:300]})

    summary_path = tool_dir / "_summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)

    generated = sum(1 for r in results if r["status"] == "patch_generated")
    print(f"\n  [{variant}] {generated}/{len(manifest)} patches generated")
    return results


# ─── SmartFix ────────────────────────────────────────────────────────

def run_smartfix(manifest, out_dir, smartfix_dir=None):
    """Run SmartFix. Requires local clone of SmartFix repo + VeriSmart."""
    tool_dir = Path(out_dir) / "smartfix"
    tool_dir.mkdir(parents=True, exist_ok=True)

    if not smartfix_dir:
        smartfix_dir = os.environ.get("SMARTFIX_DIR", "")
    if not smartfix_dir or not os.path.isdir(smartfix_dir):
        print("  [smartfix] SMARTFIX_DIR not set or not found.")
        print("             Clone https://github.com/cheonsa/smartfix and set SMARTFIX_DIR.")
        _write_manual_script(manifest, tool_dir, "smartfix")
        return

    results = []
    for i, entry in enumerate(manifest):
        stem = entry["stem"]
        sol_path = os.path.abspath(entry["contract"])
        print(f"  [{i+1}/{len(manifest)}] {stem}", flush=True)

        out_stem = tool_dir / stem
        out_stem.mkdir(exist_ok=True)

        t0 = time.time()
        try:
            cmd = [
                sys.executable,
                os.path.join(smartfix_dir, "smartfix.py"),
                "--source", sol_path,
                "--output", str(out_stem / "patched.sol"),
                "--timeout", "300",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=360, cwd=smartfix_dir)
            elapsed = round(time.time() - t0, 2)

            patch_path = out_stem / "patched.sol"
            if patch_path.is_file():
                results.append({
                    "stem": stem, "status": "patch_generated",
                    "patch_file": str(patch_path), "elapsed_sec": elapsed,
                })
            else:
                (out_stem / "log.txt").write_text(
                    proc.stdout + "\n" + proc.stderr, encoding="utf-8")
                results.append({
                    "stem": stem, "status": "no_output",
                    "returncode": proc.returncode, "elapsed_sec": elapsed,
                })
        except subprocess.TimeoutExpired:
            results.append({"stem": stem, "status": "timeout", "elapsed_sec": 360})
        except Exception as e:
            results.append({"stem": stem, "status": "error", "error": str(e)[:300]})

    summary_path = tool_dir / "_summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)

    generated = sum(1 for r in results if r["status"] == "patch_generated")
    print(f"\n  [smartfix] {generated}/{len(manifest)} patches generated")
    return results


# ─── TIPS ────────────────────────────────────────────────────────────

def run_tips(manifest, out_dir, tips_dir=None):
    """Run TIPS. Requires local clone."""
    tool_dir = Path(out_dir) / "tips"
    tool_dir.mkdir(parents=True, exist_ok=True)

    if not tips_dir:
        tips_dir = os.environ.get("TIPS_DIR", "")
    if not tips_dir or not os.path.isdir(tips_dir):
        print("  [tips] TIPS_DIR not set or not found.")
        print("         Clone https://github.com/AnoFEEv/TIPS and set TIPS_DIR.")
        _write_manual_script(manifest, tool_dir, "tips")
        return

    results = []
    for i, entry in enumerate(manifest):
        stem = entry["stem"]
        sol_path = os.path.abspath(entry["contract"])
        print(f"  [{i+1}/{len(manifest)}] {stem}", flush=True)

        out_stem = tool_dir / stem
        out_stem.mkdir(exist_ok=True)

        t0 = time.time()
        try:
            cmd = [
                sys.executable,
                os.path.join(tips_dir, "tips.py"),
                sol_path,
                "--output", str(out_stem),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=300, cwd=tips_dir)
            elapsed = round(time.time() - t0, 2)

            patches = list(out_stem.glob("*.sol"))
            if patches:
                results.append({
                    "stem": stem, "status": "patch_generated",
                    "patch_file": str(patches[0]), "elapsed_sec": elapsed,
                })
            else:
                (out_stem / "log.txt").write_text(
                    proc.stdout + "\n" + proc.stderr, encoding="utf-8")
                results.append({
                    "stem": stem, "status": "no_output",
                    "returncode": proc.returncode, "elapsed_sec": elapsed,
                })
        except subprocess.TimeoutExpired:
            results.append({"stem": stem, "status": "timeout", "elapsed_sec": 300})
        except Exception as e:
            results.append({"stem": stem, "status": "error", "error": str(e)[:300]})

    summary_path = tool_dir / "_summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)
    generated = sum(1 for r in results if r["status"] == "patch_generated")
    print(f"\n  [tips] {generated}/{len(manifest)} patches generated")
    return results


# ─── Generic Docker runner (Elysium, SmartShield) ────────────────────

DOCKER_IMAGES = {
    "elysium": "smartbugs/elysium:latest",
    "smartshield": "smartbugs/smartshield:latest",
}


def run_docker_tool(manifest, out_dir, tool_name):
    """Generic Docker-based tool runner."""
    tool_dir = Path(out_dir) / tool_name
    tool_dir.mkdir(parents=True, exist_ok=True)

    docker_image = DOCKER_IMAGES.get(tool_name)
    if not docker_image:
        print(f"  [{tool_name}] No Docker image configured.")
        _write_manual_script(manifest, tool_dir, tool_name)
        return

    if not shutil.which("docker"):
        print(f"  [{tool_name}] Docker not found.")
        _write_manual_script(manifest, tool_dir, tool_name)
        return

    results = []
    for i, entry in enumerate(manifest):
        stem = entry["stem"]
        sol_path = os.path.abspath(entry["contract"])
        sol_dir = os.path.dirname(sol_path)
        sol_name = os.path.basename(sol_path)

        print(f"  [{i+1}/{len(manifest)}] {stem}", flush=True)
        out_stem = tool_dir / stem
        out_stem.mkdir(exist_ok=True)

        t0 = time.time()
        try:
            cmd = [
                "docker", "run", "--rm",
                "-v", f"{sol_dir}:/input:ro",
                "-v", f"{out_stem}:/output",
                docker_image,
                f"/input/{sol_name}",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            elapsed = round(time.time() - t0, 2)

            patches = list(out_stem.glob("*.sol")) + list(out_stem.glob("*.bin"))
            if patches:
                results.append({
                    "stem": stem, "status": "patch_generated",
                    "patch_file": str(patches[0]), "elapsed_sec": elapsed,
                })
            else:
                results.append({
                    "stem": stem, "status": "no_output",
                    "returncode": proc.returncode, "elapsed_sec": elapsed,
                })
        except subprocess.TimeoutExpired:
            results.append({"stem": stem, "status": "timeout"})
        except Exception as e:
            results.append({"stem": stem, "status": "error", "error": str(e)[:300]})

    summary_path = tool_dir / "_summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)
    generated = sum(1 for r in results if r["status"] == "patch_generated")
    print(f"\n  [{tool_name}] {generated}/{len(manifest)} patches generated")
    return results


# ─── Manual script fallback ──────────────────────────────────────────

def _write_manual_script(manifest, tool_dir, tool_name):
    """Write a shell script the user can adapt when the tool isn't auto-runnable."""
    script = tool_dir / f"run_{tool_name}.sh"
    lines = ["#!/bin/bash", f"# Manual runner for {tool_name}",
             f"# Generated for {len(manifest)} contracts", ""]
    for entry in manifest:
        lines.append(f"# {entry['stem']}")
        lines.append(f"# Input: {entry['contract']}")
        lines.append(f"# Output: {tool_dir}/{entry['stem']}/patched.sol")
        lines.append(f"mkdir -p {tool_dir}/{entry['stem']}")
        lines.append(f"# <run {tool_name} on {entry['contract']}> > {tool_dir}/{entry['stem']}/patched.sol")
        lines.append("")
    script.write_text("\n".join(lines), encoding="utf-8")
    os.chmod(str(script), 0o755)
    print(f"  [{tool_name}] Wrote manual script: {script}")
    print(f"  [{tool_name}] Edit and run it after installing the tool.")


# ─── Main ────────────────────────────────────────────────────────────

TOOL_RUNNERS = {
    "solgpt": lambda m, o: run_solgpt(m, o),
    "sguard": lambda m, o: run_sguard(m, o, variant="sguard"),
    "sguardplus": lambda m, o: run_sguard(m, o, variant="sguardplus"),
    "smartfix": lambda m, o: run_smartfix(m, o),
    "tips": lambda m, o: run_tips(m, o),
    "elysium": lambda m, o: run_docker_tool(m, o, "elysium"),
    "smartshield": lambda m, o: run_docker_tool(m, o, "smartshield"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, help="solidifi_manifest.json")
    ap.add_argument("--tool", required=True,
                    help=f"Tool name or 'all'. Options: {', '.join(TOOLS)}")
    ap.add_argument("--out-dir", default="results/solidifi_baselines")
    ap.add_argument("--solgpt-model", default="gpt-4o-mini",
                    help="OpenAI model for SolGPT baseline")
    ap.add_argument("--only", default="",
                    help="Comma-separated stems to run (subset)")
    args = ap.parse_args()

    manifest = json.load(open(args.manifest))
    if args.only:
        only = set(s.strip() for s in args.only.split(","))
        manifest = [e for e in manifest if e["stem"] in only]

    print(f"Loaded {len(manifest)} cases from {args.manifest}")

    tools = TOOLS if args.tool == "all" else [args.tool.lower()]

    for tool in tools:
        if tool not in TOOL_RUNNERS:
            print(f"Unknown tool: {tool}. Options: {', '.join(TOOLS)}")
            continue
        print(f"\n{'='*60}")
        print(f"  Running {tool} on {len(manifest)} contracts")
        print(f"{'='*60}")
        if tool == "solgpt":
            run_solgpt(manifest, args.out_dir, model=args.solgpt_model)
        else:
            TOOL_RUNNERS[tool](manifest, args.out_dir)


if __name__ == "__main__":
    main()
