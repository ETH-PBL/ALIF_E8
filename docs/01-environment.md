# 1. Environment

## Does the E7 Docker work for the E8?

Yes. The E8 uses the same toolchain as the E7, so the same container builds, exports,
and flashes for both boards. The tools are identical:

- ARM GCC bare-metal compiler
- CMSIS Toolbox (cbuild, cpackget, csolution) and the AlifSemiconductor Ensemble pack
- Alif ML embedded evaluation kit with the Vela compiler
- Alif Security Toolkit (app-gen-toc, app-write-mram)

There are only three E8 specific differences, and none of them need a different container:

1. Vela targets the Ethos-U85 NPU with `--accelerator-config ethos-u85-256`, instead of the
   E7 Ethos-U55.
2. The Security Toolkit device must be set to the E8 part once (a config value, not a new
   tool). See [03-build-firmware.md](03-build-firmware.md).
3. Large models that do not fit MRAM are programmed into external OSPI flash with the
   usb-to-ospi-flasher. This extra tool is only needed for the OSPI path.

## Why the E8 matters for a ViT

The E7 NPU (Ethos-U55) accelerates convolutions only, so transformer attention and softmax
fall back to the slow M55 CPU. The E8 NPU (Ethos-U85) accelerates transformer operators
natively, which is what makes a Vision Transformer run fast on-device.

## Option A: the container

Place the extracted Alif Security Toolkit directory in the build context as `docker/se-tools/`,
or comment out the `COPY se-tools/` line to build without flashing support.

```
cd docker
docker build -t alif-dev .
```

Run it, mounting the repo as the workspace:

```
docker run -it --rm -v $(pwd)/..:/workspace alif-dev
```

For flashing on Linux, pass the serial devices (uncomment the devices block in
`docker-compose.yml`, or add flags):

```
docker run -it --rm --device=/dev/ttyACM0 --device=/dev/ttyACM1 -v $(pwd)/..:/workspace alif-dev
```

Inside the container the ML kit is at `$ML_KIT` (`/home/alif/ml-kit`), checked out at the
commit this guide was written for, and the SE tools are at `$SE_TOOLS`.

## Option B: your own machine

Python packages for training and export:

```
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

`onnx2tf` does not declare its own dependencies, so `requirements.txt` lists them explicitly
(`onnx_graphsurgeon`, `onnxsim`, `sng4onnx`, `sne4onnx`, `tf_keras`, `ai-edge-litert`, `psutil`).

The ML kit, pinned to the commit the firmware patch applies to:

```
git clone https://github.com/alifsemi/alif_ml-embedded-evaluation-kit
cd alif_ml-embedded-evaluation-kit
git checkout 9061be9411ec48b0d9acd39b597cfd077fc2fceb
git submodule update --init --recursive
python3 set_up_default_resources.py
```

`set_up_default_resources.py` creates the kit's own Python environment with Vela. After it
finishes, the compiler is at `<kit>/resources_downloaded/env/bin/vela` and its config at
`<kit>/scripts/vela/ensemble_vela.ini`.

For the firmware you also need the Arm GNU toolchain (`arm-none-eabi-gcc`) on PATH and cmake.

## Versions this guide was checked with

| Tool | Version |
|---|---|
| Python | 3.10 |
| torch, torchvision, timm | 2.3.1, 0.18.1, 1.0.28 |
| onnx, onnxruntime, onnxsim, onnx_graphsurgeon | 1.17.0, 1.23.0, 0.4.36, 0.5.8 |
| onnx2tf | 1.28.8 |
| tensorflow, tf_keras, ai-edge-litert | 2.19.0, 2.19.0, 2.1.0 |
| Vela | 4.4.1 |
| Arm GNU toolchain | 12.3.Rel1 |
| cmake | 3.28 |
| ML kit | commit `9061be94` |

The export and the firmware build in steps 2 and 3 were run with these versions on a Linux
host. The container installs the Arm GNU toolchain 13.3.rel1 and unpinned Python packages, so
versions inside it can differ.

## Board and cables

- DevKit-E8, Cortex-M55 HP at 400 MHz with an Ethos-U85-256 NPU.
- 5.5 MB on-chip MRAM, 9.75 MB SRAM, external OSPI flash for large weights.
- The PRG USB port is the SEGGER J-Link and carries both the SE UART (flashing) and the app
  console UART4, selected by the J15 jumper.
- The MCU USB port is separate and is used by the usb-to-ospi-flasher.

Next: [02-train-export.md](02-train-export.md).
