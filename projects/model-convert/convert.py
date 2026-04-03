#!/usr/bin/env python3
"""
Generic model converter: .pt -> .onnx, .onnx -> .om, .pt -> .onnx -> .om
"""
import argparse
import subprocess
import sys
import zipfile
import pickletools
from pathlib import Path


SAFE_PICKLE_PREFIXES = ("torch", "collections", "_codecs", "numpy")


def inspect_pt_imports(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        pkl_names = [n for n in zf.namelist() if n.endswith("data.pkl")]
        if not pkl_names:
            raise ValueError(f"No data.pkl found in {path} — not a valid torch archive")
        with zf.open(pkl_names[0]) as f:
            data = f.read()
    imports = []
    for opcode, arg, _ in pickletools.genops(data):
        if opcode.name == "GLOBAL":
            imports.append(arg)
    return imports


def check_pt_loadable(path: Path):
    imports = inspect_pt_imports(path)
    unsafe = [i for i in imports if not any(i.startswith(p) for p in SAFE_PICKLE_PREFIXES)]
    if unsafe:
        print(f"[!] Cannot load {path.name} as a generic model.")
        print(f"    It requires framework-specific classes:")
        for imp in unsafe:
            print(f"      - {imp}")
        print()
        print("    Export to ONNX first using the framework's own image, then convert .onnx -> .om here.")
        sys.exit(1)


def pt_to_onnx(pt_path: Path, onnx_path: Path, input_shape: list[int], opset: int):
    import torch

    check_pt_loadable(pt_path)
    print(f"[*] Loading {pt_path} ...")
    obj = torch.load(pt_path, map_location="cpu", weights_only=True)

    if isinstance(obj, torch.nn.Module):
        model = obj.eval()
    elif isinstance(obj, dict) and all(isinstance(v, torch.Tensor) for v in obj.values()):
        print("[!] File is a state dict, not a full model — cannot export to ONNX without model definition.")
        sys.exit(1)
    else:
        print(f"[!] Unexpected object type: {type(obj)}")
        sys.exit(1)

    dummy = torch.zeros(input_shape)
    print(f"[*] Exporting to {onnx_path} (opset {opset}) ...")
    torch.onnx.export(model, dummy, str(onnx_path), opset_version=opset, verbose=False)
    print(f"[+] Saved: {onnx_path}")


def simplify_onnx(onnx_path: Path) -> Path:
    try:
        import onnx
        from onnxsim import simplify
    except ImportError:
        print("[!] onnx-simplifier not installed, skipping simplification")
        return onnx_path

    simplified_path = onnx_path.with_stem(onnx_path.stem + "_sim")
    print(f"[*] Simplifying ONNX model ...")
    import onnx
    model = onnx.load(str(onnx_path))
    model_sim, ok = simplify(model)
    if ok:
        onnx.save(model_sim, str(simplified_path))
        print(f"[+] Simplified: {simplified_path}")
        return simplified_path
    else:
        print("[!] Simplification failed, using original")
        return onnx_path


def onnx_to_om(onnx_path: Path, om_path: Path, chip: str, extra_atc_args: list[str]):
    atc_cmd = [
        "atc",
        f"--model={onnx_path}",
        f"--output={om_path.with_suffix('')}",  # atc appends .om itself
        "--framework=5",  # 5 = ONNX
        f"--soc_version={chip}",
    ] + extra_atc_args

    print(f"[*] Running ATC: {' '.join(atc_cmd)}")
    result = subprocess.run(atc_cmd)
    if result.returncode != 0:
        print(f"[!] ATC failed with exit code {result.returncode}")
        sys.exit(result.returncode)
    print(f"[+] Saved: {om_path}")


def om_to_onnx(om_path: Path, onnx_path: Path, chip: str):
    # ATC reverse: --mode=5 dumps the original ONNX if the .om was compiled from ONNX
    atc_cmd = [
        "atc",
        "--mode=5",
        f"--om={om_path}",
        f"--json={onnx_path}",
        f"--soc_version={chip}",
    ]
    print(f"[*] Running ATC reverse: {' '.join(atc_cmd)}")
    result = subprocess.run(atc_cmd)
    if result.returncode != 0:
        print(f"[!] ATC reverse failed with exit code {result.returncode}")
        sys.exit(result.returncode)
    print(f"[+] Saved: {onnx_path}")


def main():
    parser = argparse.ArgumentParser(description="Generic model converter for Ascend NPU")
    parser.add_argument("input", type=Path, help="Input model file (.pt, .onnx, .om)")
    parser.add_argument("output", type=Path, help="Output model file (.onnx, .om)")
    parser.add_argument("--chip", default="Ascend910B1", help="Ascend chip type for ATC (default: Ascend910B1)")
    parser.add_argument("--input-shape", help="Input shape for .pt -> .onnx, e.g. 1,3,640,640")
    parser.add_argument("--opset", type=int, default=17, help="ONNX opset version (default: 17)")
    parser.add_argument("--simplify", action="store_true", help="Run onnx-simplifier before ATC")
    parser.add_argument("--inspect", action="store_true", help="Inspect .pt pickle imports and exit")
    parser.add_argument("--atc", nargs=argparse.REMAINDER, default=[], help="Extra args passed directly to atc")
    args = parser.parse_args()

    src = args.input.suffix.lower().lstrip(".")
    dst = args.output.suffix.lower().lstrip(".")

    if args.inspect:
        if src != "pt":
            print("[!] --inspect only applies to .pt files")
            sys.exit(1)
        imports = inspect_pt_imports(args.input)
        print(f"Pickle GLOBAL imports in {args.input.name}:")
        for imp in imports:
            safe = any(imp.startswith(p) for p in SAFE_PICKLE_PREFIXES)
            tag = "OK " if safe else "[!]"
            print(f"  {tag} {imp}")
        sys.exit(0)

    if src == "pt" and dst == "onnx":
        if not args.input_shape:
            print("[!] --input-shape required for .pt -> .onnx (e.g. --input-shape 1,3,640,640)")
            sys.exit(1)
        shape = [int(x) for x in args.input_shape.split(",")]
        pt_to_onnx(args.input, args.output, shape, args.opset)

    elif src == "onnx" and dst == "om":
        onnx_path = args.input
        if args.simplify:
            onnx_path = simplify_onnx(onnx_path)
        onnx_to_om(onnx_path, args.output, args.chip, args.atc)

    elif src == "pt" and dst == "om":
        if not args.input_shape:
            print("[!] --input-shape required for .pt -> .om (e.g. --input-shape 1,3,640,640)")
            sys.exit(1)
        shape = [int(x) for x in args.input_shape.split(",")]
        tmp_onnx = args.input.with_suffix(".onnx")
        pt_to_onnx(args.input, tmp_onnx, shape, args.opset)
        if args.simplify:
            tmp_onnx = simplify_onnx(tmp_onnx)
        onnx_to_om(tmp_onnx, args.output, args.chip, args.atc)

    elif src == "om" and dst == "onnx":
        om_to_onnx(args.input, args.output, args.chip)

    else:
        print(f"[!] Unsupported conversion: .{src} -> .{dst}")
        print("    Supported: .pt->.onnx, .onnx->.om, .pt->.om, .om->.onnx")
        sys.exit(1)


if __name__ == "__main__":
    main()
