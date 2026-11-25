FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake ninja-build git curl wget unzip tar xz-utils \
    ca-certificates python3.10 python3.10-venv python3.10-dev python3-pip \
    picocom xxd libusb-1.0-0 usbutils \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1

ARG GCC_URL=https://developer.arm.com/-/media/Files/downloads/gnu/13.3.rel1/binrel/arm-gnu-toolchain-13.3.rel1-x86_64-arm-none-eabi.tar.xz
RUN mkdir -p /opt/arm && curl -fSL "$GCC_URL" | tar -xJ -C /opt/arm --strip-components=1
ENV GCC_TOOLCHAIN_13_3_1=/opt/arm/bin
ENV PATH="/opt/arm/bin:${PATH}"
RUN arm-none-eabi-gcc --version

ARG CMSIS_TB_URL=https://github.com/Open-CMSIS-Pack/cmsis-toolbox/releases/download/2.13.0/cmsis-toolbox-linux-amd64.tar.gz
RUN mkdir -p /opt/cmsis-toolbox && curl -fSL "$CMSIS_TB_URL" | tar -xz -C /opt/cmsis-toolbox --strip-components=1
ENV PATH="/opt/cmsis-toolbox/bin:${PATH}"
ENV CMSIS_PACK_ROOT=/home/alif/.cache/arm/packs
ENV CMSIS_COMPILER_ROOT=/opt/cmsis-toolbox/etc
RUN cbuild --version

RUN useradd -ms /bin/bash alif && mkdir -p /home/alif/.cache/arm/packs && chown -R alif:alif /home/alif
USER alif
WORKDIR /home/alif

RUN cpackget init && \
    cpackget add ARM::CMSIS@6.1.0 && \
    cpackget add ARM::CMSIS-Compiler@2.1.0 && \
    cpackget add AlifSemiconductor::Ensemble@2.1.0

ARG ML_KIT_COMMIT=9061be9411ec48b0d9acd39b597cfd077fc2fceb
RUN git clone https://github.com/alifsemi/alif_ml-embedded-evaluation-kit /home/alif/ml-kit && \
    cd /home/alif/ml-kit && git checkout $ML_KIT_COMMIT && git submodule update --init --recursive

RUN cd /home/alif/ml-kit && python3 set_up_default_resources.py

RUN python3 -m pip install --user --no-cache-dir \
    torch torchvision timm onnx onnxruntime onnxsim onnx_graphsurgeon sng4onnx sne4onnx onnx2tf \
    tensorflow tf_keras ai-edge-litert psutil numpy pillow pyserial xmodem opencv-python-headless

# SE tools are proprietary. Place the extracted directory in the build context as se-tools/.
# Comment this out to build without flashing support.
COPY --chown=alif:alif se-tools/ /home/alif/se-tools/

ENV SE_TOOLS=/home/alif/se-tools
ENV ML_KIT=/home/alif/ml-kit
ENV PATH="/home/alif/se-tools:${PATH}"

RUN mkdir -p /workspace
WORKDIR /workspace
CMD ["/bin/bash"]
