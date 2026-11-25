# 2. Train and export a simple ViT

The demo model is DeiT-tiny, a pure Vision Transformer (5.7 M params). This step produces the
int8 model that the NPU runs.

Run the commands from the repo root. `PYTHONPATH=src` points Python at the `src` folder.

## Option A: use the pretrained ImageNet model (fastest path)

For the demo you can skip training and export the ImageNet-pretrained DeiT-tiny directly. Go
straight to the export step below (it defaults to the pretrained 1000-class model).

## Option B: train or finetune on your own classes

`train.py` finetunes DeiT-tiny on an ImageFolder dataset. Layout:

```
data/
  train/<class_name>/*.jpg
  val/<class_name>/*.jpg
```

```
PYTHONPATH=src python3 src/train.py --data_dir data --epochs 10 --batch 32
```

The recipe is AdamW with learning rate 1e-4, weight decay 1e-2, a cosine schedule,
cross-entropy loss, and the usual ImageNet augmentation (random resized crop to 224 and
horizontal flip). To train from randomly initialized weights instead of the pretrained
backbone, add `--pretrained 0`.

Expected output: one line `train <n> val <n> classes <n>`, a loss line every 50 iterations,
per epoch `[ep<k>] loss <x> val_acc <y> <t>s`, and at the end `DONE best val_acc <y>`. Outputs
go to `runs/vit/`:

- `vit_best.pt` and `vit_last.pt`, the checkpoints
- `labels.txt`, one class name per line in the order of the model outputs

## The one critical export detail: tanh GELU

The default GELU in the ViT exports to an ONNX Erf op, which onnx2tf turns into a TensorFlow
Flex op that the microcontroller runtime cannot run. The model in this repo sets every GELU to
its tanh approximation before export (see `src/model.py`). This decomposes GELU into ops the
NPU supports and keeps NPU coverage at 99.9 percent. Do not skip this. If you finetune, the
model already trains with the tanh GELU, so training and export match.

## Export to int8 TFLite and compile with Vela

`export_vela.py` runs the whole chain:

1. PyTorch to ONNX (opset 17), input 1x3x224x224.
2. ONNX to full-integer int8 TFLite with onnx2tf. The calibration set is the first 48 jpg
   images of a folder you pass, resized to 224 and normalized with the ImageNet mean and std.
   Use images that look like your deployment data.
3. Vela for the Ethos-U85 with 256 MACs.

Pretrained ImageNet model, weights placed in OSPI (needed because the DeiT weights are about
5.4 MB, larger than what fits in MRAM with the app):

```
VELA_BIN=<kit>/resources_downloaded/env/bin/vela \
VELA_INI=<kit>/scripts/vela/ensemble_vela.ini \
PYTHONPATH=src python3 src/export_vela.py \
  --tag deit --calib_dir <path/to/calib/jpgs> \
  --system_config Ethos_U85_SRAM_OSPI
```

For a finetuned checkpoint, add `--ckpt runs/vit/vit_best.pt --num_classes <n>`. If your int8
model is small enough to fit MRAM, use `--system_config Ethos_U85_SRAM_MRAM` instead.

## Expected output

For the pretrained DeiT-tiny the script prints (about 4.5 minutes on a laptop CPU):

```
ONNX <repo>/export/deit.onnx
int8 tflite 6.45 MB
input quant (scale, zero_point): (0.01865844801068306, -14)
  Total SRAM used                               1047.86 KiB
  Total DRAM used                               5507.23 KiB
  CPU operators = 1 (0.1%)
  NPU operators = 1395 (99.9%)
  CPU operator types: GATHER
vela model export/vela_deit/deit_full_integer_quant_vela.tflite 5.87 MB
```

What the lines mean:

- `input quant` is the scale and zero point of the int8 input. Write these two numbers down,
  the host driver in step 4 needs them. They depend on the calibration images, so yours can
  differ slightly.
- `Total SRAM used` is the activation memory the firmware must provide (about 1 MB here).
- `Total DRAM used` is the weight storage. With the OSPI system config Vela reports the
  external flash under this name.
- `CPU operator types` lists what Vela could not place on the NPU. The firmware must register
  exactly these operators. For DeiT-tiny it is one GATHER, the selection of the class token
  after the last normalization layer, just before the classification head.

The file `export/vela_deit/deit_full_integer_quant_vela.tflite` is what the firmware embeds.

Next: [03-build-firmware.md](03-build-firmware.md).
