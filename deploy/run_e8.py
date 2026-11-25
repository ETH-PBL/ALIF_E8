import argparse
import time
import numpy as np
from PIL import Image
import serial

MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)


def preprocess(path, scale, zp, size=224):
    im = Image.open(path).convert("RGB").resize((size, size))
    x = (np.asarray(im, np.float32) / 255.0 - MEAN) / STD
    a = np.round(x / scale + zp).clip(-128, 127).astype(np.int8)
    return a.tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyACM0")
    ap.add_argument("--scale", type=float, required=True)
    ap.add_argument("--zero_point", type=int, required=True)
    ap.add_argument("--labels", default="")
    ap.add_argument("--drop_first_label", type=int, default=1)
    ap.add_argument("images", nargs="+")
    args = ap.parse_args()

    labels = []
    if args.labels:
        labels = open(args.labels).read().splitlines()
        if args.drop_first_label and labels and "background" in labels[0].lower():
            labels = labels[1:]

    ser = serial.Serial(args.port, 115200, timeout=3)
    time.sleep(0.7)
    banner = ser.read(ser.in_waiting or 0).decode(errors="replace")
    if banner.strip():
        print("[banner]\n" + banner.strip() + "\n[/banner]")
    ser.reset_input_buffer()

    for path in args.images:
        data = preprocess(path, args.scale, args.zero_point)
        ser.write(data)
        ser.flush()
        ms = None
        classes = []
        t0 = time.time()
        while time.time() - t0 < 45:
            line = ser.readline().decode(errors="replace").strip()
            if not line:
                continue
            if line.startswith("RESULT"):
                ms = line.split(",")[1]
            elif line.startswith("CLASS:"):
                idx, score = line[len("CLASS:"):].split(",")
                classes.append((int(idx), float(score)))
            elif line == "END":
                break
        print(f"=== {path.split('/')[-1]} ===")
        print(f"  inference {ms} ms")
        for idx, score in classes:
            name = labels[idx] if 0 <= idx < len(labels) else str(idx)
            print(f"    [{idx}] {score:.3f} {name}")

    ser.close()


if __name__ == "__main__":
    main()
