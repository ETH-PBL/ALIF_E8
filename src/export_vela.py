import os
import re
import glob
import subprocess
import argparse
import numpy as np
import torch
from PIL import Image

from model import build_vit

MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)


def build_calib(calib_dir, out, n=48):
    ps = sorted(glob.glob(os.path.join(calib_dir, "*.jpg")))[:n]
    if not ps:
        raise FileNotFoundError(f"no calib jpgs in {calib_dir}")
    arr = np.stack([
        ((np.asarray(Image.open(p).convert("RGB").resize((224, 224)), np.float32) / 255) - MEAN) / STD
        for p in ps
    ]).astype("float32")
    np.save(out, arr)
    return out


def read_input_quant(tflite_path):
    import tensorflow as tf
    it = tf.lite.Interpreter(model_path=tflite_path)
    it.allocate_tensors()
    q = it.get_input_details()[0]["quantization"]
    return q


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="")
    ap.add_argument("--num_classes", type=int, default=1000)
    ap.add_argument("--tag", default="deit")
    ap.add_argument("--out", default="export")
    ap.add_argument("--calib_dir", required=True)
    ap.add_argument("--vela_bin", default=os.environ.get("VELA_BIN", "vela"))
    ap.add_argument("--vela_ini", default=os.environ.get("VELA_INI", ""))
    ap.add_argument("--system_config", default="Ethos_U85_SRAM_OSPI")
    args = ap.parse_args()
    args.out = os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)

    guard = os.path.join(args.out, "calibration_image_sample_data_20x128x128x3_float32.npy")
    if not os.path.exists(guard):
        np.save(guard, np.random.rand(20, 128, 128, 3).astype("float32"))

    model = build_vit(num_classes=args.num_classes, pretrained=not args.ckpt).eval()
    if args.ckpt:
        sd = torch.load(args.ckpt, map_location="cpu")
        model.load_state_dict(sd["model"] if "model" in sd else sd)

    onnx_p = os.path.join(args.out, f"{args.tag}.onnx")
    torch.onnx.export(
        model, torch.randn(1, 3, 224, 224), onnx_p, opset_version=17,
        input_names=["input"], output_names=["out"], do_constant_folding=True,
    )
    print("ONNX", onnx_p, flush=True)

    calib = build_calib(args.calib_dir, os.path.join(args.out, f"calib_{args.tag}.npy"))
    tf_dir = os.path.join(args.out, f"{args.tag}_tf")
    r = subprocess.run(
        ["onnx2tf", "-i", onnx_p, "-o", tf_dir, "-oiqt",
         "-cind", "input", calib, "[[[[0,0,0]]]]", "[[[[1,1,1]]]]"],
        cwd=args.out, capture_output=True, text=True,
    )
    fq = glob.glob(os.path.join(tf_dir, "*full_integer_quant.tflite"))
    if not fq:
        print("onnx2tf FAIL\n", r.stdout[-800:], r.stderr[-800:])
        raise SystemExit(1)
    tfl = fq[0]
    print(f"int8 tflite {os.path.getsize(tfl)/1e6:.2f} MB", flush=True)
    try:
        print("input quant (scale, zero_point):", read_input_quant(tfl), flush=True)
    except Exception as e:
        print("input quant read skipped:", e, flush=True)

    vela_out = os.path.join(args.out, f"vela_{args.tag}")
    cmd = [args.vela_bin, "--output-dir", vela_out, "--accelerator-config", "ethos-u85-256", "--optimise", "Performance"]
    if args.vela_ini:
        cmd += ["--config", args.vela_ini, "--system-config", args.system_config, "--memory-mode", "Shared_Sram"]
    cmd += [tfl]
    v = subprocess.run(cmd, capture_output=True, text=True)
    if v.returncode != 0:
        print("vela FAIL\n", v.stdout[-800:], v.stderr[-800:])
        raise SystemExit(1)
    for line in v.stdout.splitlines():
        if any(s in line for s in ["CPU operators", "NPU operators", "SRAM used", "DRAM used", "Flash used"]):
            print("  " + line.strip())
    cpu = sorted(set(re.findall(r"Warning \(supported operators\) operator:(\w+)", v.stdout)))
    print("  CPU operator types:", ", ".join(cpu) if cpu else "none")
    vela_tfl = glob.glob(os.path.join(vela_out, "*_vela.tflite"))[0]
    print(f"vela model {os.path.relpath(vela_tfl)} {os.path.getsize(vela_tfl)/1e6:.2f} MB", flush=True)


if __name__ == "__main__":
    main()
