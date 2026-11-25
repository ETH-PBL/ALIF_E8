# 3. Build the E8 firmware

The firmware is the `img_class` use case of the Alif ML embedded evaluation kit with a small
patch from this repo, built for the E8 and pointed at the Vela model from step 2. It runs in
UART mode: it reads a preprocessed image over the console, runs one inference, and prints the
latency and the top-5 classes.

## Apply the firmware patch

The stock `img_class` use case takes its images from the kit's camera interface and shows the
result on the display. `firmware/img_class_uart.patch` changes four files of the kit:

| File | Change |
|---|---|
| `source/use_case/img_class/src/UseCaseHandler.cc` | UART mode. Prints `READY`, reads one int8 frame from the console straight into the input tensor, times the inference with the Cortex-M55 cycle counter, prints `RESULT:5,<ms>`, five `CLASS:<idx>,<score>` lines, and `END`. |
| `source/application/api/fwk/tflm/source/MobileNetModel.cc` | Registers the GATHER operator, the one operator Vela leaves on the CPU for DeiT-tiny. |
| `source/application/api/fwk/tflm/include/MobileNetModel.hpp` | Raises the operator count of the resolver from 7 to 8. |
| `source/hal/source/platform/alif/source/retarget_alif.c` | Console input no longer echoes every received byte, which a binary image upload needs. |

The patch applies to the kit commit pinned in step 1:

```
cd <kit>
git checkout 9061be9411ec48b0d9acd39b597cfd077fc2fceb
git apply <repo>/firmware/img_class_uart.patch
```

Inside the container `<kit>` is `$ML_KIT` and `<repo>` is `/workspace`.

If your own model leaves other operators on the CPU (step 2 prints them as
`CPU operator types`), register them next to the GATHER line in `MobileNetModel.cc` and raise
the count in `MobileNetModel.hpp` by the same number.

## Configure the Security Toolkit for the E8 (once)

The Security Toolkit device is a global setting. In the SE tools directory, set the device to
the E8 part in `utils/global-cfg.db` and `utils/app-global-cfg.db` under `DEVICE.Part#` and
`DEVICE.Revision`:

- `Part#` = `E8 (AE822FA0E5597LS0) - 5.5 MRAM / 9.75 SRAM`
- `Revision` = `A1`

app-write-mram auto-detects the part and aborts on a mismatch, so this must match the board.

## Build

Run cmake from the kit directory with the Arm GNU toolchain on PATH.
`MODEL_IN_EXT_FLASH=ON` splits the output into a small app for MRAM and the model for OSPI.
`IMAGE_SIZE` is the model input size. The activation buffer must cover the SRAM that Vela
reported in step 2 (0x00200000 is 2 MB, enough for the 1 MB of DeiT-tiny). `CONSOLE_UART=4`
puts the console on UART4, the one that reaches the J-Link USB port. The kit default is UART2
and gives no output there.

```
cd <kit>
export PATH=/opt/arm/bin:$PATH
cmake -B build_e8_deit \
  -DTARGET_PLATFORM=alif -DTARGET_SUBSYSTEM=RTSS-HP \
  -DTARGET_BOARD=DevKit-e8 -DETHOS_U_NPU_ID=U85 \
  -DCMAKE_TOOLCHAIN_FILE=scripts/cmake/toolchains/bare-metal-gcc.cmake \
  -DUSE_CASE_BUILD=img_class -DML_FRAMEWORK=TensorFlowLiteMicro \
  -Dimg_class_MODEL_PATH=<repo>/export/vela_deit/deit_full_integer_quant_vela.tflite \
  -Dimg_class_LABELS_TXT_FILE=<kit>/resources/img_class/labels/labels_mobilenet_v2_1.0_224.txt \
  -Dimg_class_IMAGE_SIZE=224 \
  -Dimg_class_ACTIVATION_BUF_SZ=0x00200000 \
  -Dimg_class_MODEL_IN_EXT_FLASH=ON \
  -DCONSOLE_UART=4
cmake --build build_e8_deit -j8
```

Use absolute paths for the model and the labels file. The labels file is required by the kit
build. In UART mode the board sends class indices and the host maps them to names, so for your
own classes you still pass this file here and use your `runs/vit/labels.txt` on the host.

For a model that fits MRAM, drop `MODEL_IN_EXT_FLASH` and use the matching Vela
`Ethos_U85_SRAM_MRAM` build from step 2.

## Expected output

The configure step ends with `Build files have been written to: <kit>/build_e8_deit`. The build
takes about 5 minutes and ends with:

```
[100%] Linking CXX executable bin/ethos-u-img_class.axf
[100%] Built target ethos-u-img_class
```

The binaries for the board:

```
build_e8_deit/bin/sectors/img_class/
  mram.bin        0.73 MB, the app, goes to MRAM
  ext_flash.bin   5.87 MB, the model, goes to OSPI at 0xC0000000
```

For a MRAM-only build there is a single `mram.bin` that contains both the app and the model.

Next: [04-flash-run.md](04-flash-run.md).
