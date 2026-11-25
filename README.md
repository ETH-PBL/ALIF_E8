# e8-vit-quickstart

## Citation

If you use this work, please cite:

```bibtex
@misc{bonazzi2026tinymlhitsmemorywall,
      title={TinyML Hits the Memory Wall: A Benchmark of Ten Sub-Watt Edge Devices},
      author={Pietro Bonazzi and Luigi Capogrosso and Ahmet Celik and Rosanna Manzo and Marco Giordano and Szymon Ruciński and Jonathan Hungerbuehler and Michele Magno},
      year={2026},
      eprint={2611.03392},
      archivePrefix={arXiv},
      primaryClass={cs.AR},
      url={https://arxiv.org/abs/2611.03392},
}
```

## Overview

A from-scratch guide to running a Vision Transformer on the Alif Ensemble E8 (Ethos-U85 NPU):
train or finetune a simple ViT, quantize and compile it, build the firmware, flash it, and run
it on the board while reading the on-device latency.

The demo model is DeiT-tiny, a pure Vision Transformer. Its int8 model runs with 99.9 percent
of the operators on the E8 NPU, at about 174 ms per inference.

## The E7 to E8 question

The E8 uses the same toolchain as the E7, so the same Docker image works for both. The only E8
specific changes are the Vela accelerator flag (`ethos-u85-256`), a one-time device setting in
the Security Toolkit, and the OSPI flasher for models too large for MRAM. Details in
[docs/01-environment.md](docs/01-environment.md).

## Why the E8

The E7 NPU accelerates convolutions only, so transformer attention falls back to the CPU. The
E8 NPU accelerates transformer operators natively, which is what makes a ViT viable on-device.

## Layout

```
src/
  model.py        DeiT-tiny with tanh-GELU set for NPU export
  train.py        finetune or train on an ImageFolder dataset
  export_vela.py  PyTorch to ONNX to int8 TFLite to Vela (Ethos-U85)
firmware/
  img_class_uart.patch  UART mode for the ML kit img_class use case
deploy/
  run_e8.py           host driver: send an image over UART, read latency and top-5
  send_xmodem.py      program a model into OSPI over XMODEM
  img_class_hp.json   Security Toolkit config for the app
  flasher_hp.json     Security Toolkit config for the OSPI flasher
docker/
  Dockerfile          the shared E7 and E8 build environment
  docker-compose.yml
docs/
  01-environment.md    Docker, toolchain, and the versions this guide was checked with
  02-train-export.md   train a ViT and export int8 plus Vela
  03-build-firmware.md patch and build the E8 img_class firmware
  04-flash-run.md      flash to OSPI and MRAM, run, measure
```

## Quickstart

1. Set up the environment: [docs/01-environment.md](docs/01-environment.md).
2. Train or use the pretrained model, then export to int8 and Vela:
   [docs/02-train-export.md](docs/02-train-export.md).
3. Patch the ML kit and build the firmware: [docs/03-build-firmware.md](docs/03-build-firmware.md).
4. Flash and run on the board: [docs/04-flash-run.md](docs/04-flash-run.md).

## Expected results

| Step | Result for the pretrained DeiT-tiny |
|---|---|
| Export | int8 TFLite 6.45 MB, input quantization (0.018658, -14), 1395 operators on the NPU and 1 on the CPU (99.9 percent), 1.0 MB activation SRAM |
| Firmware build | `mram.bin` 0.73 MB (app) and `ext_flash.bin` 5.87 MB (model) |
| On the board | per image `RESULT:5,<ms>` and five `CLASS:<idx>,<score>` lines. A brown bear image gives the brown bear class at about 174 ms, matching the int8 model on the PC |

The latency is measured on-device with the Cortex-M55 cycle counter, and the NPU coverage comes
from the Vela summary, so both numbers are measured rather than estimated. Which parts were
re-run from this repo is listed at the end of [docs/04-flash-run.md](docs/04-flash-run.md).

## Details that trip people up

- Set every GELU in the model to its tanh approximation before ONNX export. The default GELU
  becomes a Flex op the microcontroller runtime cannot run. See `src/model.py`.
- Build the firmware with `-DCONSOLE_UART=4`. With the kit default the console is silent on
  the J-Link USB port. See [docs/03-build-firmware.md](docs/03-build-firmware.md).
- When flashing the app, pad the binary to a 16-byte multiple, and run the SE tools under a
  pseudo terminal so you can see their output. See [docs/04-flash-run.md](docs/04-flash-run.md).
