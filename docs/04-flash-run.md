# 4. Flash and run on the E8

Two things get flashed: the model into external OSPI flash, and the app into MRAM. If your
model fits MRAM you can skip the OSPI part and flash a single binary.

Serial ports on this board shift by which USB is connected. Always confirm the mapping first:

```
ls -la /dev/serial/by-id/
```

The SEGGER J-Link entry is the SE UART used for flashing. Set the port accordingly in the SE
tools config file `isp_config_data.cfg` (`comport /dev/ttyACMx`). Flashing needs the J15 jumper
in the SEUART position.

## Two things that make the SE tools look broken when they are not

1. A binary must be a multiple of 16 bytes, or app-write-mram aborts with a size warning. Pad
   it before generating the table of contents (the `mram.bin` from step 3 needs this):

```
BIN=build/images/ethos-u-img_class.bin
SZ=$(stat -c%s $BIN)
PAD=$(( (16 - SZ % 16) % 16 ))
[ $PAD -gt 0 ] && dd if=/dev/zero bs=1 count=$PAD >> $BIN
```

2. The SE tools write their progress to the terminal only, not to stdout. If you pipe or
   capture the output you see zero bytes and it looks like a silent crash. Run them under a
   pseudo terminal to see the real messages:

```
printf 'y\n' | script -qec "./app-write-mram" /tmp/flash.log
```

A good result ends with `100%` and `Done`.

## A. Program the model into OSPI (only for the external-flash build)

The Security Toolkit does not program OSPI. Use the usb-to-ospi-flasher, a small app that runs
on the board, receives a file over USB serial, and writes it to the OSPI flash.

Build the flasher once:

```
git clone https://github.com/alifsemi/alif_usb-to-ospi-flasher
cd alif_usb-to-ospi-flasher
cpackget add https://github.com/alifsemi/alif_ensemble-Azure-RTOS/releases/download/v2.0.0/AlifSemiconductor.ThreadX.2.0.0.pack
cbuild alif.csolution.yml --context flasher.release+DevKit-E8-HP --packs --update-rte
```

Expected: `out/flasher/DevKit-E8-HP/release/flasher.bin`, about 137 KB.

Flash the flasher to MRAM with the config from this repo:

```
cd <se-tools>
cp <flasher>/out/flasher/DevKit-E8-HP/release/flasher.bin build/images/alif-img.bin
cp <repo>/deploy/flasher_hp.json build/config/
./app-gen-toc -f build/config/flasher_hp.json
printf 'y\n' | script -qec "./app-write-mram" /tmp/flash.log
```

Reset the board. The flasher enumerates a CDC serial device on the MCU USB port (a separate
connector from the PRG J-Link USB), listed under `by-id` as an AlifSemiconductor Devkit device.

Send the model to OSPI over XMODEM:

```
python3 deploy/send_xmodem.py /dev/ttyACMx <kit>/build_e8_deit/bin/sectors/img_class/ext_flash.bin
```

Expected: a first line with the file size and about 45,900 packets, a progress line every 200
packets, and after a few minutes `RESULT: OK`. The model now lives in OSPI at 0xC0000000 and
is read at runtime.

## B. Flash the app into MRAM

Copy the app binary and the config from this repo into the SE tools, pad the binary as shown
above, generate the table of contents, and write:

```
cd <se-tools>
cp <kit>/build_e8_deit/bin/sectors/img_class/mram.bin build/images/ethos-u-img_class.bin
cp <repo>/deploy/img_class_hp.json build/config/
./app-gen-toc -f build/config/img_class_hp.json
printf 'y\n' | script -qec "./app-write-mram" /tmp/flash.log
```

`deploy/img_class_hp.json` places the app at MRAM address 0x80008000 and boots it on the
high-performance core. With the MCU USB cable of step A still connected the J-Link port can
move from ttyACM0 to ttyACM1, so check `isp_config_data.cfg` again.

## C. Run and measure

The console is the app UART4, selected by the J15 jumper. Flashing uses the SEUART position,
so switch J15 to the U4 position and reset the board. The console appears on the J-Link virtual
COM port.

Send an image and read the result with the host driver. Use the input scale and zero point
that step 2 printed for your model, and a label file with one class name per line (for the
ImageNet demo the one from the kit, for your own classes `runs/vit/labels.txt`):

```
python3 deploy/run_e8.py --port /dev/ttyACM0 \
  --scale 0.01865844 --zero_point -14 \
  --labels <kit>/resources/img_class/labels/labels_mobilenet_v2_1.0_224.txt \
  image1.jpg
```

The driver resizes the image to 224x224, applies the ImageNet mean and std, quantizes with the
scale and zero point, and sends the 150,528 bytes over the console. The board answers with
`RESULT:5,<ms>`, five `CLASS:<idx>,<score>` lines, and `END`.

Expected output per image:

```
=== image1.jpg ===
  inference <ms> ms
    [<idx>] <score> <class name>
    (five lines)
```

For the pretrained DeiT-tiny demo a brown bear image gives class 294, brown bear, at about
174 ms, and the top classes match the int8 model on the PC exactly.

## What the numbers mean

- The latency is measured on-device with the Cortex-M55 cycle counter around the inference, so
  it is real, not estimated.
- The NPU versus CPU split comes from the Vela summary in step 2. Higher NPU coverage means
  fewer CPU fallback operators and lower latency.

## What was checked where

The on-device result above (174 ms, brown bear) was measured on a DevKit-E8 with the same UART
handler logic and these flashing steps. The firmware patch in this repo is a cleaned version of
that firmware: the same handler, on the stock model class with the GATHER operator added. The
export in step 2 and the firmware build in step 3 were re-run from this repo on a clean kit
checkout and produce the outputs listed in those steps. The binaries from that re-run were not
flashed again.
