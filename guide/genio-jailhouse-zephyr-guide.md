# Running Zephyr alongside Linux with Jailhouse on Genio 510 and Genio 700 EVKs

**User Guide**

| | |
|---|---|
| Document status | Released |
| Applies to | Genio 510 EVK (MT8370), Genio 700 EVK (MT8390) |
| Software | IoT Yocto v26.0 (`rity-scarthgap-v26.0`) with `meta-mediatek-experimental`; MediaTek Jailhouse `mtk-v1.0.0`; MediaTek Genio Zephyr `mtk-genio-v1.0.0` (Zephyr 4.5) with Zephyr SDK 1.0.1 |
| License | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| Last updated | 2026-10-08 |

---

## Contents

1. [Introduction](#1-introduction)
2. [Requirements](#2-requirements)
3. [Building the Linux image with Jailhouse](#3-building-the-linux-image-with-jailhouse)
4. [Flashing the board](#4-flashing-the-board)
5. [Building Zephyr applications](#5-building-zephyr-applications)
6. [Running Zephyr under Jailhouse](#6-running-zephyr-under-jailhouse)
7. [Running the Genio Zephyr samples](#7-running-the-genio-zephyr-samples)
8. [Troubleshooting](#8-troubleshooting)
9. [Reference](#9-reference)
10. [Related documentation](#10-related-documentation)

---

## 1. Introduction

### 1.1 Purpose and scope

This guide explains how to build, flash and run a mixed-criticality system on
a MediaTek Genio 510 or Genio 700 Evaluation Kit (EVK): Linux runs as the main
operating system, and the Zephyr real-time operating system runs next to it
on dedicated CPU cores, isolated by the Jailhouse partitioning hypervisor.

It covers the complete workflow on your own Linux workstation:

- building an IoT Yocto image that includes Jailhouse, using the
  `meta-mediatek-experimental` layer;
- flashing the image with the Jailhouse device-tree overlay;
- building Zephyr applications and the Genio Zephyr samples;
- enabling Jailhouse, running Zephyr in a cell, and watching its console;
- running Zephyr on a Cortex-A78 core, on two Cortex-A55 cores (SMP), and
  with the audio front end (AFE).

The generic IoT Yocto steps (host preparation, fetching the BSP, flashing
tools, board connection) are described in the
[IoT Yocto Get Started guide][iot-get-started]. This guide refers to it
instead of repeating it, and describes only what is specific to Jailhouse and
Zephyr.

### 1.2 Audience

This guide is for embedded software engineers who evaluate or develop on the
Genio 510 or Genio 700 EVK. It assumes that you are familiar with the Linux
command line, with building images with the Yocto Project, and with the
basics of Zephyr application development.

### 1.3 How the pieces fit together

```
 +------------------------------------------------------------------------+
 |                         Genio EVK (MT8370 / MT8390)                    |
 |                                                                        |
 |   Root cell: Linux (IoT Yocto)          Inmate cell "zephyr": Zephyr   |
 |   - most CPUs, all other devices        - 1 or 2 dedicated CPUs        |
 |   - manages Jailhouse                   - 8 MiB of RAM                 |
 |     (jailhouse enable / cell ...)       - UART1, GPIO 38/40, (AFE)     |
 |   - console: UART0                      - console: UART1               |
 |                                                                        |
 |   ------------------------------------------------------------------   |
 |                   Jailhouse hypervisor (4 MiB of RAM)                  |
 |   CPU and memory partitioning, interrupt routing, and per-pin          |
 |   mediation of the shared GPIO, EINT and clock gate registers          |
 +------------------------------------------------------------------------+
```

The system starts as a normal Linux system. Jailhouse does not run until you
enable it:

1. Linux boots. The Jailhouse device-tree overlay has already kept the
   hypervisor and inmate memory away from Linux.
2. You load the Jailhouse driver and **enable** the hypervisor with the
   *root cell* configuration. Linux keeps running, now as the root cell.
3. You **create** a Zephyr *cell* from its cell configuration. Jailhouse takes
   the cell's CPUs, memory and devices away from Linux.
4. You **load** the Zephyr image into the cell's memory and **start** the
   cell. Zephyr boots on its CPUs and prints to UART1.
5. You can stop, reload and restart the cell as often as you like, without
   rebooting Linux. Destroying the cell gives its resources back to Linux.

Nothing of this persists across a reboot: after each boot, Jailhouse must be
enabled again and the cell created, loaded and started again.

### 1.4 Conventions

- Commands are marked with where they run:
  - **Host**: your Linux workstation;
  - **Board**: a root shell on the EVK, opened with `adb shell` (see
    [Section 4.4](#44-verifying-the-image-on-the-board)).
- `<...>` marks a value to replace. Where commands differ between the boards,
  both variants are given, or the difference is listed in a table.
- Paths such as `$PROJ_ROOT` and `$BUILD_DIR` follow the IoT Yocto Get
  Started guide.

> **Note:** Notes give additional information.
>
> **Caution:** Cautions describe actions that can lose data or need care.

---

## 2. Requirements

### 2.1 Supported boards

| Board | SoC | CPUs | DRAM | Hostname |
|---|---|---|---|---|
| Genio 510 EVK | MT8370 | CPU 0-3: Cortex-A55; CPU 4-5: Cortex-A78 | 4 GiB | `genio-510-evk` |
| Genio 700 EVK | MT8390 | CPU 0-5: Cortex-A55; CPU 6-7: Cortex-A78 | 8 GiB | `genio-700-evk` |

CPU numbers in this guide are Linux logical CPU numbers. The Zephyr cells use
CPU 3 (Cortex-A55) by default; other cells use the Cortex-A78 or two
Cortex-A55 cores (see [Section 6.4](#64-choosing-a-cell)).

### 2.2 Software components

| Component | Source | Notes |
|---|---|---|
| IoT Yocto BSP v26.0 | `https://gitlab.com/mediatek/aiot/bsp/manifest.git`, tag `rity-scarthgap-v26.0` | Yocto Project 5.0 (Scarthgap), Linux 6.6 |
| `meta-mediatek-experimental` | `https://gitlab.com/mediatek/aiot/rity/meta-mediatek-experimental`, branch `scarthgap` | Provides the `jailhouse` recipe (MediaTek Jailhouse), the Jailhouse kernel support and the Jailhouse device-tree overlays |
| MediaTek Jailhouse | `https://github.com/mtk-jailhouse/jailhouse`, release `mtk-v1.0.0` on the branch `mtk-v1.0` | Built by the `jailhouse` recipe from the release branch; you do not need to fetch it yourself |
| Genio Zephyr tree | `https://github.com/mtk-zephyr/mtk-zephyr`, tag `mtk-genio-v1.0.0` | Zephyr 4.5 with the Genio board support |
| Genio Zephyr samples | `https://github.com/mtk-zephyr/samples`, tag `mtk-genio-v1.0.0` | West manifest repository; fetches the Zephyr tree and its modules |
| Zephyr SDK | Installed with `west sdk install` | Version 1.0.1, as set in the tree's `SDK_VERSION` file; only the `aarch64-zephyr-elf` toolchain is needed |

> **Note:** This guide creates the Zephyr workspace at the samples tag
> `mtk-genio-v1.0.0` (see [Section 5.2](#52-creating-the-workspace)), which
> selects the Genio Zephyr tree at its tag of the same name. The development
> branches `mtk-genio-dev` of both repositories are rebased and force-pushed;
> do not base a product on them.

### 2.3 Host computer

**Yocto builds.** Follow the host requirements of the
[IoT Yocto Linux build environment][iot-build-env] page. At the time of
writing, MediaTek verifies builds on Ubuntu 22.04 LTS and asks for at least
400 GiB of free disk space and 64 GiB of RAM for a 16-core system.

**Zephyr builds.** The Genio Zephyr tree is Zephyr 4.5, which needs at least
CMake 3.28, Python 3.12 and the devicetree compiler 1.4.6 (see the
[Zephyr Getting Started Guide][zephyr-gsg]). Ubuntu 24.04 LTS provides these
versions; on Ubuntu 22.04, install newer CMake and Python first. Zephyr builds
need a few GiB of disk space and no special amount of RAM.

You can use one workstation for both, or separate ones.

**Flashing and serial console.** Install the Genio tools (`genio-flash`),
`adb` and `fastboot`, the udev rules, and a serial terminal as described on
the [IoT Yocto Linux tool environment][iot-flash-env] page. This guide uses
`picocom`:

**Host**

```bash
sudo apt install picocom
```

Your user must be a member of the `dialout` group to open serial ports.

### 2.4 Hardware

- A Genio 510 EVK or Genio 700 EVK with its 12 V power adapter.
- Three micro-USB cables:

  | EVK connector | Purpose in this guide |
  |---|---|
  | **USB0** (`Micro USB D/L`) | Flashing, and `adb` access to Linux |
  | **UART0** (CN3200) | Linux console (and hypervisor messages) |
  | **UART1** (CN3201) | Zephyr console |

  Each UART connector has its own USB-to-UART bridge and appears on the host
  as a separate `/dev/ttyUSB<n>` device.
- Optional, for the samples: female-to-female jumper wires for the GPIO
  loopback (2 pins) and the audio (eTDM) loopbacks.

---

## 3. Building the Linux image with Jailhouse

### 3.1 Preparing the host and fetching the BSP

Follow these sections of the IoT Yocto Get Started guide:

1. [Linux build environment][iot-build-env]: install the host packages and
   the `repo` tool.
2. [Build from Source Code][iot-build-code], sections *Project Root*,
   *Download the Recipes* and *Configure Build Environment*. With the v26.0
   release, these steps are:

   **Host**

   ```bash
   mkdir iot-yocto && cd iot-yocto
   export PROJ_ROOT=$(pwd)
   repo init -u https://gitlab.com/mediatek/aiot/bsp/manifest.git -b refs/tags/rity-scarthgap-v26.0
   repo sync
   export TEMPLATECONF=$PROJ_ROOT/src/meta-rity/meta/conf/templates/default/
   source src/poky/oe-init-build-env build
   export BUILD_DIR=$(pwd)
   ```

   `oe-init-build-env` changes into the build directory. Run all `bitbake`
   and `bitbake-layers` commands in this guide from there, in a shell where
   you have sourced `oe-init-build-env`. In a new shell, change into the
   `iot-yocto` directory and repeat the four commands from `export PROJ_ROOT`
   onwards, without `repo init` and `repo sync`.

3. Optionally, set up `DL_DIR` and `SSTATE_DIR` outside the build directory
   (section *Setup DL_DIR and SSTATE_DIR*). This makes rebuilds faster and
   lets you remove the build directory without losing the downloads.

Jailhouse and Zephyr need no NDA repositories. Do not set `NDA_BUILD` unless
you need it for other reasons.

### 3.2 Adding the `meta-mediatek-experimental` layer

The `meta-mediatek-experimental` layer is not part of the BSP manifest.
Clone it next to the other layers, on the branch that matches the BSP
(`scarthgap`), and add it to the build:

**Host**

```bash
git clone -b scarthgap https://gitlab.com/mediatek/aiot/rity/meta-mediatek-experimental.git $PROJ_ROOT/src/meta-mediatek-experimental
bitbake-layers add-layer $PROJ_ROOT/src/meta-mediatek-experimental
```

Check that the layer is active:

**Host**

```bash
bitbake-layers show-layers | grep experimental
```

The output lists the layer with the collection name `experimental` and
priority 8.

Check that the layer builds MediaTek Jailhouse 1.0, which this guide
describes:

**Host**

```bash
grep '^BRANCH' $PROJ_ROOT/src/meta-mediatek-experimental/recipes-kernel/jailhouse/jailhouse_git.bb
```

The output is `BRANCH = "mtk-v1.0"`. If it names another branch, such as
`MTK-Genio`, the clone is an older revision of the layer, which builds an
earlier Jailhouse tree: update it with
`git -C $PROJ_ROOT/src/meta-mediatek-experimental pull` and check again.

> **Note:** As its name says, the layer carries features that are not yet
> part of the main IoT Yocto layers. Use the branch that matches your BSP
> release.

### 3.3 Configuring the build

#### Select the board

Set `MACHINE` as described in the IoT Yocto guide, for example in the shell
before you build:

**Host**

```bash
export MACHINE=genio-510-evk    # or: genio-700-evk
```

The Jailhouse recipe supports only these two machines among the Genio EVKs.

#### Enable Jailhouse

Add the following line to `$BUILD_DIR/conf/local.conf`:

```
IMAGE_INSTALL:append = " jailhouse"
```

The leading space inside the quotes is required.

This one setting turns on everything Jailhouse needs, because the layer
makes all of it depend on `jailhouse` being in `IMAGE_INSTALL`:

| What | Effect |
|---|---|
| `jailhouse` package | The hypervisor firmware, the Jailhouse kernel module (`jailhouse.ko`), the `jailhouse` command-line tool, the nine cell configurations of the board you build for (`MACHINE`) and the demo inmates |
| Linux kernel patches and configuration | Kernel symbol exports for the Jailhouse driver; the kernel stays at EL1 (no VHE) so that Jailhouse can take over EL2; the `mtk-jh-rproc` remote processor driver and RPMsg support (see [Section 7.4](#74-rpmsg-with-linux)); virtual PCI support |
| Device-tree overlay `6.6-Genio-510-Jailhouse-DT.dtbo` or `6.6-Genio-700-Jailhouse-DT.dtbo` | Removes the hypervisor and inmate memory from Linux. It is built with the image but must be selected when you flash (see [Section 4.3](#43-flashing-with-the-jailhouse-overlay)) |

Without the `IMAGE_INSTALL` line, adding the layer changes nothing related to
Jailhouse.

#### Optional settings

These settings are not required. They reduce build time and resource use.

- **Leave out heavy debug tools.** `rity-bringup-image` includes
  `packagegroup-rity-debug`, whose `bcc`, `bpftrace` and `perfetto` packages
  are large builds (`bcc` and `bpftrace` build the Clang/LLVM compiler for the
  target). Jailhouse and Zephyr do not need them. To leave them out, add to
  `local.conf`:

  ```
  RDEPENDS:packagegroup-rity-debug:remove = "bcc bpftrace perfetto"
  ```

- **Limit parallelism on hosts with less memory than recommended.** Building
  with many parallel tasks can run the host out of memory. For example, on a
  20-core host with 32 GiB of RAM, these values in
  `$BUILD_DIR/conf/site.conf` worked reliably:

  ```
  BB_NUMBER_THREADS = "6"
  PARALLEL_MAKE = "-j 8"
  ```

### 3.4 Building the image

This guide uses `rity-bringup-image`: a console image with debug and
development tools and the U-Boot environment tools, and without the AI,
multimedia and graphics stacks of `rity-demo-image`. It builds considerably
faster. The `IMAGE_INSTALL` setting applies to every image, so you can build
`rity-demo-image` instead if you need its features.

**Host**

```bash
bitbake rity-bringup-image
```

A first build takes several hours, depending on the host. Later builds reuse
the shared-state cache and take minutes, or about an hour when the kernel
must be rebuilt.

### 3.5 Checking the build output

The images are in `$BUILD_DIR/tmp/deploy/images/$MACHINE/`. Check that:

- the flashable image is there, for example
  `rity-bringup-image-genio-510-evk.rootfs.wic.img`;
- the Jailhouse overlay was built:

  **Host**

  ```bash
  ls $BUILD_DIR/tmp/deploy/images/$MACHINE/devicetree/ | grep Jailhouse
  ```

  The output is `6.6-Genio-510-Jailhouse-DT.dtbo` or
  `6.6-Genio-700-Jailhouse-DT.dtbo`;
- the image contains Jailhouse:

  **Host**

  ```bash
  grep jailhouse $BUILD_DIR/tmp/deploy/images/$MACHINE/rity-bringup-image-$MACHINE.rootfs.manifest
  ```

  The output contains the `jailhouse` package and the
  `kernel-module-jailhouse-...` package.

---

## 4. Flashing the board

### 4.1 Installing the flashing tools

If you have not done so already, install the Genio tools, `adb`, `fastboot`
and the udev rules as described on the
[IoT Yocto Linux tool environment][iot-flash-env] page, and check the host
with:

**Host**

```bash
genio-config
```

### 4.2 Connecting the board

Connect the board as described in [Board connection][iot-connect]: the 12 V
adapter, and a micro-USB cable to **USB0** (`Micro USB D/L`). For the rest of
this guide, also connect **UART1** (CN3201), and optionally **UART0**
(CN3200), to the host.

### 4.3 Flashing with the Jailhouse overlay

> **Caution:** Flashing erases the whole eMMC of the board.

The Jailhouse overlay must be selected when you flash. `genio-flash`
`--load-dtbo` adds an overlay to the image's default list; the defaults stay
selected.

1. Change into the deploy directory:

   **Host**

   ```bash
   cd $BUILD_DIR/tmp/deploy/images/$MACHINE
   ```

2. Check which overlays will be loaded, without flashing:

   **Host**

   ```bash
   genio-flash -i rity-bringup-image --load-dtbo 6.6-Genio-510-Jailhouse-DT.dtbo --dry-run
   ```

   On the Genio 700 EVK, use `6.6-Genio-700-Jailhouse-DT.dtbo`. To see all
   available overlays, run `genio-flash -i rity-bringup-image --list-dtbo`.

3. Flash:

   **Host**

   ```bash
   genio-flash -i rity-bringup-image --load-dtbo 6.6-Genio-510-Jailhouse-DT.dtbo
   ```

4. Put the board into download mode when `genio-flash` waits for it, as
   described in [Flash Image to Board][iot-flash]:
   1. press and hold the **Download** button;
   2. press and release the **RST** button;
   3. keep holding **Download** until `genio-flash` prints `Erasing 'mmc0'`.

   If `genio-flash` reports that board control failed, it could not switch
   the board into download mode by itself. Use the buttons as described.

`genio-flash` writes the image, the bootloaders and the U-Boot environment,
and then reboots the board.

> **Caution:** The overlay list is stored in the U-Boot environment
> (`list_dtbo`). If you later change the overlays, for example to add one,
> keep `6.6-Genio-<board>-Jailhouse-DT.dtbo` in the list. Without it, Linux
> uses the hypervisor and inmate memory, and Jailhouse cannot be enabled.

### 4.4 Verifying the image on the board

After the board has booted, check that it is visible to `adb` and open a
shell:

**Host**

```bash
adb devices
adb shell
```

The following checks run on the board.

1. The Jailhouse overlay is selected:

   **Board**

   ```bash
   fw_printenv list_dtbo
   ```

   The list contains `6.6-Genio-510-Jailhouse-DT.dtbo` (or
   `6.6-Genio-700-Jailhouse-DT.dtbo`).

2. Linux does not use the Jailhouse memory:

   **Board**

   ```bash
   grep "System RAM" /proc/iomem
   ```

   No `System RAM` range may cover the addresses `6ac00000` to `6bafffff`.
   With the overlay, one range ends at `6abfffff` and the next one starts at
   `6bb00000`, for example:

   ```
   61800000-6abfffff : System RAM
   6bb00000-13fffffff : System RAM
   ```

   (The last range ends at `23fffffff` on the Genio 700 EVK.)

3. The Jailhouse driver matches the running kernel, and the cell
   configurations are installed:

   **Board**

   ```bash
   modinfo -n jailhouse
   ls /usr/share/jailhouse/cells/
   ```

   The first command prints the path of `jailhouse.ko` below
   `/lib/modules/$(uname -r)/`; the second lists the nine cells of your board
   (see [Section 9.2](#92-cells)).

---

## 5. Building Zephyr applications

### 5.1 Installing the host dependencies

Install the Zephyr host dependencies as described in
[Install dependencies][zephyr-gsg-deps] of the Zephyr Getting Started Guide.
On Ubuntu 24.04:

**Host**

```bash
sudo apt install --no-install-recommends git cmake ninja-build gperf ccache dfu-util device-tree-compiler wget python3-dev python3-venv python3-tk xz-utils file make gcc gcc-multilib g++-multilib libsdl2-dev libmagic1
```

Check the versions against the minimums (CMake 3.28, Python 3.12, dtc 1.4.6):

**Host**

```bash
cmake --version
python3 --version
dtc --version
```

### 5.2 Creating the workspace

The Genio samples repository is the west manifest of the workspace. One
`west init` fetches the Genio Zephyr tree, the modules it needs and the
samples, at the matching revisions of the release `mtk-genio-v1.0.0`.

1. Create the workspace directory and a Python virtual environment, and
   install west:

   **Host**

   ```bash
   mkdir ~/genio-zephyr && cd ~/genio-zephyr
   python3 -m venv .venv
   source .venv/bin/activate
   pip install west
   ```

   Activate the virtual environment (`source .venv/bin/activate`) in every
   new shell before you use west.

2. Initialize and fetch the workspace:

   **Host**

   ```bash
   west init -m https://github.com/mtk-zephyr/samples --mr mtk-genio-v1.0.0 .
   west update
   ```

   To save time and disk space, you can fetch only the latest history:
   `west update --narrow -o=--depth=1`.

3. Export the Zephyr CMake package and install the Python packages Zephyr
   needs:

   **Host**

   ```bash
   west zephyr-export
   west packages pip --install
   ```

The workspace now contains:

```
~/genio-zephyr/
├── .venv/       Python virtual environment
├── zephyr/      Genio Zephyr tree
├── modules/     HALs and modules
└── samples/     Genio samples (manifest repository)
```

### 5.3 Installing the Zephyr SDK

Install the Zephyr SDK version that the tree requires (1.0.1, read from
`zephyr/SDK_VERSION`), with only the 64-bit Arm toolchain:

**Host**

```bash
cd ~/genio-zephyr/zephyr
west sdk install --gnu-toolchains aarch64-zephyr-elf
cd ..
```

By default, the SDK is installed in your home directory. Run
`west sdk install --help` for other options.

### 5.4 Board targets

| Board | Single core | Two cores (SMP) |
|---|---|---|
| Genio 510 EVK | `mt8370_genio_510_evk/mt8188/a55` | `mt8370_genio_510_evk/mt8188/a55/smp` |
| Genio 700 EVK | `mt8390_genio_700_evk/mt8188/a55` | `mt8390_genio_700_evk/mt8188/a55/smp` |

- The **single-core** targets build images for one CPU. The same image runs
  on the default Cortex-A55 cell and on the Cortex-A78 cell.
- The **SMP** targets build images for the two-core cells (CPU 2 and 3). A
  single-core image also runs in a two-core cell, on its first CPU only.

### 5.5 Building `hello_world`

From the workspace directory, with the virtual environment active:

**Host**

```bash
west build -p -b mt8370_genio_510_evk/mt8188/a55 -d build/hello_world zephyr/samples/hello_world
```

For the Genio 700 EVK, use `-b mt8390_genio_700_evk/mt8188/a55`.

The image to run is `build/hello_world/zephyr/zephyr.bin`.

### 5.6 Building the Genio samples

The Genio samples are in `samples/` (see [Section 7](#7-running-the-genio-zephyr-samples)).
Build one with `west build`, for example the GPIO loopback:

**Host**

```bash
west build -p -b mt8370_genio_510_evk/mt8188/a55 -d build/gpio_loopback samples/gpio/loopback
```

To build all samples for a board in one step, use twister:

**Host**

```bash
west twister --build-only -T samples -p mt8370_genio_510_evk/mt8188/a55 -O build/twister-samples
```

Each image is then in
`build/twister-samples/<board>/zephyr_gnu/samples/<group>/<sample>/<scenario>/zephyr/zephyr.bin`,
where `<board>` is the board target with `/` replaced by `_`, for example
`mt8370_genio_510_evk_mt8188_a55`.

**SMP images.** Build for the SMP target, for example:

**Host**

```bash
west build -p -b mt8370_genio_510_evk/mt8188/a55/smp -d build/synchronization zephyr/samples/synchronization
```

**Audio images.** Applications that use the audio front end need the
`mtk-afe` snippet:

**Host**

```bash
west build -p -b mt8370_genio_510_evk/mt8188/a55 -S mtk-afe -d build/loopback_dl11_ul8 samples/audio/loopback_dl11_ul8
```

The snippet enables the AFE, selects the eTDM pins and reserves the audio
buffer memory. Without it, the AFE is disabled.

### 5.7 Constraints for Zephyr images

The Genio board targets are prepared for the Jailhouse cells. If you write
your own application, keep in mind:

- **Memory.** The cell gives Zephyr 8 MiB of RAM at address `0x8000`, where
  the image is loaded and started. The image and all its memory must fit
  into this window.
- **Devices.** Zephyr may use only the devices its cell grants (see
  [Section 9.3](#93-resources-of-the-zephyr-cells)). Access to any other
  device either has no effect or stops the cell.
- **GPIO.** The board devicetree leaves the GPIO banks disabled, because the
  pins Zephyr may use depend on the cell. An application that uses GPIO 38
  and 40 enables them in its own devicetree overlay; copy the overlays of
  `samples/gpio/loopback/boards/`.
- **Multi-core.** CPUs are started with PSCI `CPU_ON` through the `smc`
  conduit. The SMP board targets are set up for this.

---

## 6. Running Zephyr under Jailhouse

### 6.1 Opening the Zephyr console (UART1)

Zephyr prints to **UART1** (connector CN3201) at **115200 baud, 8N1**, without
flow control.

1. Find the serial device of UART1. With several USB-to-UART bridges
   connected, list them by ID:

   **Host**

   ```bash
   ls -l /dev/serial/by-id/
   ```

   If you are not sure which one is UART1, unplug the CN3201 cable, list the
   devices, plug it in again and see which device appears.

2. Open the console, replacing `/dev/ttyUSB0` with the UART1 device:

   **Host**

   ```bash
   picocom -b 115200 /dev/ttyUSB0
   ```

   Exit `picocom` with `Ctrl+A`, then `Ctrl+X`.

Keep the console open while you run Zephyr. Only one program may read the
serial port at a time; if two programs read it, each receives only part of
the output.

The Linux console is on UART0, at **921600 baud**. The
hypervisor prints its messages there too, and to its own console buffer
(see [Section 6.7](#67-monitoring)).

### 6.2 Enabling Jailhouse

Open a shell on the board with `adb shell`, and run:

**Board**

```bash
modprobe jailhouse
jailhouse enable /usr/share/jailhouse/cells/$(uname -n).cell
```

`$(uname -n)` is the board's hostname, `genio-510-evk` or `genio-700-evk`,
which is also the name of its root cell configuration.

Check that Jailhouse is running:

**Board**

```bash
jailhouse cell list
```

```
ID      Name                    State             Assigned CPUs           Failed CPUs
0       genio-510-evk           running           0-5
```

The kernel log contains `The Jailhouse is opening.`, and the hypervisor
console shows the hypervisor start-up:

**Board**

```bash
jailhouse console
```

```
Initializing Jailhouse hypervisor mtk-v1.0.0 (0-g<commit>) on CPU <n>
...
Initializing unit: mt8188_clk
Initializing unit: mt8188_eint
Initializing unit: mt8188_gpio
...
Activating hypervisor
```

The version names the release. A build from a later commit of the release
branch shows the number of commits since the release instead of `0`.

> **Note:** Enable Jailhouse once after each boot. `jailhouse cell list`
> prints nothing, and succeeds, when Jailhouse is not enabled.

### 6.3 Running a Zephyr image

1. Copy the image to the board:

   **Host**

   ```bash
   adb push build/hello_world/zephyr/zephyr.bin /root/zephyr.bin
   ```

2. Create the cell, load the image and start it:

   **Board**

   ```bash
   jailhouse cell create /usr/share/jailhouse/cells/$(uname -n)-zephyr.cell
   jailhouse cell load zephyr /root/zephyr.bin -a 0x8000
   jailhouse cell start zephyr
   ```

   - `cell create` takes CPU 3, the cell's memory and its devices away from
     Linux. The cell is named `zephyr`; all Zephyr cells use this name.
   - `cell load` copies the image into the cell's memory. The address
     `-a 0x8000` is required: it is where the cell starts executing.
   - `cell start` starts the cell's CPU.

3. The Zephyr console shows:

   ```
   *** Booting Zephyr OS build <version> ***
   Hello World! mt8370_genio_510_evk/mt8188/a55
   ```

4. Check the cell state:

   **Board**

   ```bash
   jailhouse cell list
   ```

   ```
   ID      Name                    State             Assigned CPUs           Failed CPUs
   0       genio-510-evk           running           0-2,4-5
   1       zephyr                  running           3
   ```

   While the cell exists, Linux does not use its CPU:
   `cat /sys/devices/system/cpu/online` prints `0-2,4-5` on the Genio 510 EVK.

**Helper script.** The samples repository contains
`samples/tools/genio-inmate.sh`, which runs on the board. It loads the driver,
enables Jailhouse if needed, replaces any existing `zephyr` cell, and then
creates, loads and starts the cell. Its optional second argument selects
another cell:

**Host**

```bash
adb push samples/tools/genio-inmate.sh /root/genio-inmate.sh
adb shell 'sh /root/genio-inmate.sh /root/zephyr.bin'
adb shell 'sh /root/genio-inmate.sh /root/zephyr.bin genio-510-evk-zephyr-a78.cell'
```

### 6.4 Choosing a cell

The cell decides which CPUs and devices Zephyr gets. All Zephyr cells load
the image at `0x8000` into the same 8 MiB window and use UART1, so only one
of them can exist at a time.

| Cell configuration (`/usr/share/jailhouse/cells/`) | CPUs on Genio 510 EVK | CPUs on Genio 700 EVK | Use for |
|---|---|---|---|
| `genio-<board>-evk-zephyr.cell` | 3 (Cortex-A55) | 3 (Cortex-A55) | Default: single-core images |
| `genio-<board>-evk-zephyr-a78.cell` | 5 (Cortex-A78) | 7 (Cortex-A78) | Single-core images on a Cortex-A78 |
| `genio-<board>-evk-zephyr-smp.cell` | 2 and 3 (Cortex-A55) | 2 and 3 (Cortex-A55) | SMP images |
| `genio-<board>-evk-zephyr-afe.cell` | 3 | 3 | Audio images |
| `genio-<board>-evk-zephyr-afe-a78.cell` | 5 | 7 | Audio images on a Cortex-A78 |
| `genio-<board>-evk-zephyr-afe-smp.cell` | 2 and 3 | 2 and 3 | Audio images on two cores |
| `genio-<board>-evk-zephyr-rpmsg.cell` | 3 | 3 | Images that exchange RPMsg messages with Linux (see [Section 7.4](#74-rpmsg-with-linux)) |

`<board>` is `510` or `700`. The `-afe` cells grant the same resources as
their counterparts plus the audio front end (see
[Section 9.3](#93-resources-of-the-zephyr-cells)).

To use a different cell, destroy the current one first (see
[Section 6.8](#68-stopping-and-restarting-a-cell)), then create the new one:

**Board**

```bash
jailhouse cell destroy zephyr
jailhouse cell create /usr/share/jailhouse/cells/$(uname -n)-zephyr-a78.cell
jailhouse cell load zephyr /root/zephyr.bin -a 0x8000
jailhouse cell start zephyr
```

**CPU frequency.** Linux sets the clocks of both CPU clusters, the
Cortex-A55 cluster and the Cortex-A78 cluster, through cpufreq and thermal
management. Jailhouse does not partition these clocks, so Zephyr runs at the
frequency that Linux selects for the cluster of its CPUs. The image's default
governor, `schedutil`, selects that frequency from the load on the cluster's
Linux CPUs: when Linux is idle, the cluster slows down, and Zephyr with it.

For latency and timing measurements, select the `performance` governor for
both clusters:

**Board**

```bash
for p in /sys/devices/system/cpu/cpufreq/policy*; do
    echo performance > $p/scaling_governor
done
cat /sys/devices/system/cpu/cpufreq/policy*/scaling_cur_freq
```

The last command shows the frequency of each cluster, in kHz. The setting
does not persist across a reboot; write `schedutil` to return to the default.
Thermal management can still lower the frequency when the SoC is hot.

### 6.5 Running Zephyr on two cores (SMP)

Build the image for the SMP target (see [Section 5.6](#56-building-the-genio-samples))
and run it in the `-zephyr-smp` cell:

**Board**

```bash
jailhouse cell create /usr/share/jailhouse/cells/$(uname -n)-zephyr-smp.cell
jailhouse cell load zephyr /root/zephyr.bin -a 0x8000
jailhouse cell start zephyr
```

Jailhouse starts CPU 2; Zephyr then starts CPU 3 itself with PSCI `CPU_ON`.
The console shows, for example with `samples/synchronization`:

```
*** Booting Zephyr OS build <version> ***
Secondary CPU core 1 (MPID:0x300) is up
thread_a: Hello World from cpu 0 on mt8370_genio_510_evk!
thread_b: Hello World from cpu 1 on mt8370_genio_510_evk!
```

> **Caution:** Run SMP images only in the `-zephyr-smp` and
> `-zephyr-afe-smp` cells. In any other cell the image fails while the cell
> stays `running`, and the hypervisor console shows no error. In a
> `-zephyr-a78` cell it stops before its console starts and prints nothing.
> In a one-core cell such as `-zephyr` it panics after
> `Failed to boot secondary CPU core 1 (MPID:0x200)`. See
> [Section 8](#8-troubleshooting).

### 6.6 Running Zephyr on a Cortex-A78

Single-core images run unchanged on the Cortex-A78; use the `-zephyr-a78`
cell (CPU 5 on the Genio 510 EVK, CPU 7 on the Genio 700 EVK).

> **Note:** As in the Cortex-A55 cells, Linux sets the clock: Zephyr runs
> at the frequency that Linux selects for the Cortex-A78 cluster (see
> [Section 6.4](#64-choosing-a-cell)). Select the `performance` governor
> before you compare the two core types.

### 6.7 Monitoring

**Cell state.** `jailhouse cell list` shows each cell and its state:

| State | Meaning |
|---|---|
| `running` | The cell's CPUs execute the cell. |
| `running/locked` | Running, and the cell has locked the configuration: no cells can be created or destroyed until it unlocks it. |
| `shut down` | The cell exists but does not run, for example after `cell shutdown` or before `cell start`. |
| `failed` | A CPU of the cell was stopped because of an error, for example an access to memory or a device that the cell does not own. The CPU is listed under `Failed CPUs`. |

**Hypervisor console.** The hypervisor reports cell changes and errors in its
console buffer:

**Board**

```bash
jailhouse console        # print the buffer
jailhouse console -f     # print the buffer, then follow new messages (Ctrl+C to stop)
```

Typical messages are `Created cell "zephyr"`, `Started cell "zephyr"` and
`Closing cell "zephyr"`. If a cell fails, the console shows the reason, for
example `Unhandled data read at 0x<address>(4)`. The same messages appear on
UART0.

**Statistics.** `jailhouse cell stats` shows how often the cell's CPUs left
to the hypervisor (VM exits), per reason and per CPU. It needs a terminal, so
start it from an interactive `adb shell`, or with `adb shell -t`:

**Host**

```bash
adb shell -t jailhouse cell stats zephyr
```

If it reports that it cannot find the terminal, set a terminal type that
the board knows, for example `TERM=xterm jailhouse cell stats zephyr`. Press
`c` to switch between the CPUs, `a` to show all CPUs, and `q` to quit. The counters are also available in sysfs, below
`/sys/devices/jailhouse/cells/<id>/statistics/`.

**Linux side.** Messages of the Jailhouse driver, such as
`Created Jailhouse cell "zephyr"`, are in the kernel log (`dmesg`).

### 6.8 Stopping and restarting a cell

| Command (on the board) | Effect |
|---|---|
| `jailhouse cell shutdown zephyr` | Stops the cell. Its CPUs, memory and devices stay assigned to it. |
| `jailhouse cell load zephyr <image> -a 0x8000` | Loads a (new) image into the stopped cell. |
| `jailhouse cell start zephyr` | Starts the cell again. |
| `jailhouse cell destroy zephyr` | Stops the cell and returns its CPUs, memory and devices to Linux. |

For a quick edit-build-run cycle, rebuild on the host, push the image, and
reload it into the same cell:

**Host**

```bash
west build -d build/hello_world
adb push build/hello_world/zephyr/zephyr.bin /root/zephyr.bin
adb shell 'jailhouse cell shutdown zephyr && jailhouse cell load zephyr /root/zephyr.bin -a 0x8000 && jailhouse cell start zephyr'
```

### 6.9 Disabling Jailhouse

**Board**

```bash
jailhouse disable
```

`jailhouse disable` first destroys all cells other than the root cell. Linux
then runs on as before, with all CPUs, and the kernel log contains
`The Jailhouse was closed.`

All CPUs of the root cell must be online in Linux. If you have taken a CPU
offline yourself (for example with `/sys/devices/system/cpu/cpu<n>/online`),
bring it online first; otherwise `jailhouse disable` fails with
`Device or resource busy`.

### 6.10 Optional: checking a cell with the uart-demo inmate

The Jailhouse `uart-demo` inmate is a small bare-metal program that prints a
counter to UART1. It is useful to check the hypervisor and the console
connection independently of Zephyr.

1. Set the UART1 console on the host to **38400 baud**:

   **Host**

   ```bash
   picocom -b 38400 /dev/ttyUSB0
   ```

2. If Zephyr has used UART1 since the board booted, reset the UART's
   MediaTek-specific `HIGHSPEED` register first. Zephyr sets it for its baud
   rate, and `uart-demo` does not reset it:

   **Board**

   ```bash
   devmem2 0x11001224 w 0
   ```

3. Run the demo (Jailhouse must be enabled, and no `zephyr` cell may exist):

   **Board**

   ```bash
   jailhouse cell create /usr/share/jailhouse/cells/$(uname -n)-uart-demo.cell
   jailhouse cell load uart-demo /usr/share/jailhouse/inmates/uart-demo.bin
   jailhouse cell start uart-demo
   ```

   The console shows `Hello 1 from cell!`, `Hello 2 from cell!`, and so on.

4. Destroy the demo cell:

   **Board**

   ```bash
   jailhouse cell destroy uart-demo
   ```

Set the console back to 115200 baud before you run Zephyr again.

---

## 7. Running the Genio Zephyr samples

The `samples/` repository contains applications that test the Genio Zephyr
drivers and print their own verdict. Each sample has a README with its exact
expected output.

| Sample | Checks | Needs |
|---|---|---|
| `system/boot_and_timer` | Boot, board identity, timer frequency and accuracy | Host script |
| `system/memory_window` | The cell grants the memory the image expects | — |
| `uart/rx_interrupt` | Interrupt-driven UART reception under load | Host script |
| `uart/reconfigure` | `uart_configure()` changes the baud rate on the wire | Host script |
| `gpio/loopback` | GPIO output and input, and all EINT trigger modes | One wire |
| `audio/...` | Audio front end: playback, capture and eTDM loopbacks | AFE cell, wires (loopbacks) |

### 7.1 Samples with a host script

Three samples check properties that cannot be observed from the board, and
come with a host-side Python script in the sample's `host/` directory. The
scripts need `pyserial` (`pip install pyserial`) and open the UART1 port
themselves:

1. Close any other program that reads UART1, such as `picocom`.
2. Start the host script as described in the sample's README.
3. Then start the cell with the sample image.

### 7.2 GPIO loopback wiring

`gpio/loopback` uses GPIO 38 and GPIO 40, which are on the 40-pin header:

| SoC GPIO | Header pin |
|---|---|
| GPIO 38 | 22 |
| GPIO 40 | 18 |

Connect header pin 18 and header pin 22 with a wire.

> **Caution:** Do not use a jumper block. Pin 20, between pins 18 and 22, is
> a ground pin; a jumper on 18-20 or 20-22 connects a GPIO to ground.

### 7.3 Audio samples

The audio samples use the audio front end (AFE) and the eTDM ports. They need
all of the following. Most of these prerequisites fail silently when they are
missing: the driver still reports success, but no audio moves.

1. **Build with the `mtk-afe` snippet** (see [Section 5.6](#56-building-the-genio-samples)).
2. **Use an AFE cell**, for example `genio-<board>-evk-zephyr-afe.cell`. The
   ordinary Zephyr cells do not grant the AFE; under them, the cell fails at
   the first AFE access. The AFE cells also own the eTDM pins, so the Zephyr
   application configures their pin function itself.
3. **Keep the audio power domain on.** It is off after boot, and only Linux
   can switch it on. Before you start the cell:

   **Board**

   ```bash
   echo on > /sys/devices/platform/soc/10b10000.afe/power/control
   ```

4. **Wire the loopbacks** that a sample needs (see the sample's README).
   The eTDM signals are on these SoC pins:

   | Port | Signals | SoC pins |
   |---|---|---|
   | eTDM_IN1 | MCK, BCK, LRCK, DI | 125, 126, 127, 128 |
   | eTDM_IN2 | MCK, BCK, WS, D0 | 107, 108, 109, 110 |
   | eTDM_OUT1 | MCK, BCK, WS, D0 | 4, 5, 6, 11 |
   | eTDM_OUT2 | MCK, BCK, WS, D0 | 114, 115, 116, 117 |

   For example, `loopback_dl11_ul8` connects eTDM_OUT1 to eTDM_IN1: pin 5 to
   126, pin 6 to 127, and pin 11 to 128.

Do not use the eTDM ports from Linux while an AFE cell runs: the AFE cells
share the audio front end with Linux.

### 7.4 RPMsg with Linux

The `-zephyr-rpmsg` cells connect Zephyr and Linux through shared memory, for
RPMsg messages. The root cell has a virtual PCI device, an ivshmem device,
whose 1 MiB of shared memory at `0x6ba00000` both cells map; each side
signals the other through the device's interrupt (see
[Section 9.3](#93-resources-of-the-zephyr-cells)). On Linux, the
`mtk-jh-rproc` driver binds to the device as a remote processor. It handles
only the messages: Jailhouse, not the driver, loads and starts Zephyr.

The RPMsg sample of the Genio samples, `samples/rpmsg`, shows the connection.
It has two parts:

- a Zephyr application, `samples/rpmsg/zephyr`: the RPMsg remote. It uses OpenAMP
  over the shared memory, announces an `rpmsg-raw` endpoint and answers each
  message;
- a Linux tool, `samples/rpmsg/linux`: `rpmsg-test` attaches Linux to the remote
  processor and exchanges messages with Zephyr through `/dev/rpmsg<m>`.

Linux needs nothing beyond the image of [Section 3](#3-building-the-linux-image-with-jailhouse): with `jailhouse` in
`IMAGE_INSTALL`, the layer builds the `mtk-jh-rproc` driver and the RPMsg
character device into the kernel.

1. **Build the Zephyr application** in the Zephyr workspace (see
   [Section 5.6](#56-building-the-genio-samples)):

   **Host**

   ```bash
   west build -p -b mt8370_genio_510_evk/mt8188/a55 -d build/rpmsg samples/rpmsg/zephyr
   ```

   For the Genio 700 EVK, use `mt8390_genio_700_evk/mt8188/a55`. The
   application's board overlays describe the virtual PCI host and the
   ivshmem device of the cell; `west` selects them by the board name.

2. **Build the Linux tool** with Ubuntu's cross compiler
   (`sudo apt install gcc-aarch64-linux-gnu`). One binary serves both boards:

   **Host**

   ```bash
   make -C samples/rpmsg/linux
   ```

   The tool is `samples/rpmsg/linux/build/rpmsg-test`. The compiler prints
   one warning, `unused variable 'id'`, which is harmless.

3. **Copy both to the board:**

   **Host**

   ```bash
   adb push build/rpmsg/zephyr/zephyr.bin /root/rpmsg-zephyr.bin
   adb push samples/rpmsg/linux/build/rpmsg-test /root/rpmsg-test
   adb shell chmod +x /root/rpmsg-test
   ```

4. **Find the remote processor.** After `jailhouse enable`, Linux has the
   ivshmem device and a remote processor for it, named `0001:00:00.0`. Keep
   its number in `n`:

   **Board**

   ```bash
   lspci
   n=$(grep -l 0001:00:00.0 /sys/class/remoteproc/*/name |
       sed 's|.*/remoteproc\([0-9]*\)/name|\1|')
   cat /sys/class/remoteproc/remoteproc$n/state
   ```

   ```
   0001:00:00.0 Unassigned class [ff00]: Siemens AG Device [110a:4106]
   detached
   ```

   `n` is `0` on the Genio 510 EVK and `1` on the Genio 700 EVK, where
   `remoteproc0` is the system companion processor (`scp`). Run the
   following steps in the same shell, or set `n` again.

5. **Start Zephyr in the `-zephyr-rpmsg` cell:**

   **Board**

   ```bash
   jailhouse cell create /usr/share/jailhouse/cells/$(uname -n)-zephyr-rpmsg.cell
   jailhouse cell load zephyr /root/rpmsg-zephyr.bin -a 0x8000
   jailhouse cell start zephyr
   ```

   The hypervisor console shows `Shared memory connection established, peer
   cells:` followed by `"genio-<board>-evk"`. On UART1, Zephyr waits for
   Linux:

   ```
   *** Booting Zephyr OS build <version> ***
   ...
   [INFO]  Setting resource table
   [INFO]  Awaiting VIRTIO config ready ...
   ```

6. **Exchange messages.** Run the tool with the number of the remote
   processor. It attaches Linux to Zephyr, then sends a message about every
   2 seconds until you stop it with Ctrl+C:

   **Board**

   ```bash
   /root/rpmsg-test -p $n
   ```

   ```
   ...
   [INFO]  remoteproc device path='/sys/class/remoteproc/remoteproc<n>/state'
   ...
   [INFO]  rpmsg device path='/dev/rpmsg0'
   ...
   [INFO]  send_message  Size: 21
   [INFO]  RPMSG RX  len: 22  msg: 'Hello from Zephyr!  1'
   [INFO]  send_message  Size: 21
   [INFO]  RPMSG RX  len: 22  msg: 'Hello from Zephyr!  2'
   ```

   UART1 shows the other side:

   ```
   [INFO]  VIRTIO config is ready ...
   ...
   [INFO]  Created endpoint for service 'rpmsg-raw'
   [INFO]  RPMSG RX  len: 21  msg: 'Hello from Linux!  1'
   [INFO]  Endpoint for service 'rpmsg-raw' is connected
   [INFO]  send_message  Size: 22
   ```

   The remote processor is now `attached`, and `/dev/rpmsg0` and
   `/dev/rpmsg_ctrl0` exist. The kernel log shows
   `remote processor 0001:00:00.0 is now attached` and
   `creating channel rpmsg-raw`. It also shows `Allocated carveout doesn't
   fit device address request` twice on each attach; the messages pass
   regardless.

7. **Stop: detach Linux, check that it is detached, then destroy the cell:**

   **Board**

   ```bash
   echo detach > /sys/class/remoteproc/remoteproc$n/state
   cat /sys/class/remoteproc/remoteproc$n/state
   ```

   Linux reports `detached; the inmate is still running`, and `/dev/rpmsg0`
   goes away. When the state reads `detached`, destroy the cell; if it
   still reads `attached`, write `detach` again first:

   **Board**

   ```bash
   jailhouse cell destroy zephyr
   ```

   The ivshmem device stays in Linux until `jailhouse disable`.

> **Caution:** Detach before you destroy the cell, and run `rpmsg-test` once
> per attach. The driver does not support `stop` (`Invalid argument`). If
> the cell is destroyed first, the remote processor stays `attached` with a
> stale `/dev/rpmsg0`, and each further run of `rpmsg-test` adds another
> attach: the next Zephyr waits at `Awaiting VIRTIO config ready` and Linux
> logs `msg received with no recipient`. To recover, write `detach` once
> for each attach, until the state reads `detached`.

---

## 8. Troubleshooting

| Symptom | Likely cause | Remedy |
|---|---|---|
| `bitbake` fails with a `PermissionError` when it writes `/proc/self/uid_map` | The host restricts unprivileged user namespaces (for example, AppArmor on Ubuntu 24.04), which `bitbake` needs | Build on the verified Ubuntu 22.04 host, or allow user namespaces for `bitbake` as described in the Yocto Project documentation for your host |
| The host runs out of memory during the Yocto build | Too many parallel build tasks for the host's RAM | Reduce `BB_NUMBER_THREADS` and `PARALLEL_MAKE` (see [Section 3.3](#33-configuring-the-build)) |
| `genio-flash` waits, or reports that board control failed | The board is not in download mode | Use the Download and RST buttons (see [Section 4.3](#43-flashing-with-the-jailhouse-overlay)) |
| `modprobe jailhouse` fails: module not found | The image was built without Jailhouse | Add `IMAGE_INSTALL:append = " jailhouse"`, rebuild and flash (see [Section 3.3](#33-configuring-the-build)) |
| `jailhouse enable` fails, and the kernel log shows `jailhouse: request_mem_region failed for hypervisor memory.` | The Jailhouse overlay is not loaded, so Linux uses the hypervisor memory | Check `fw_printenv list_dtbo` and `/proc/iomem` (see [Section 4.4](#44-verifying-the-image-on-the-board)); flash again with `--load-dtbo` |
| `jailhouse enable` fails with `Invalid argument`, and `jailhouse console` shows `Cell "genio-<board>-evk" has vendor resources, but no unit handles them` | The hypervisor was built without `CONFIG_SOC=mt8188`, so it has no MediaTek units | Build Jailhouse with `CONFIG_SOC=mt8188`, as the IoT Yocto recipe does |
| `jailhouse cell create` fails with `Invalid argument` | Jailhouse is not enabled (for example, after a reboot) | Enable Jailhouse (see [Section 6.2](#62-enabling-jailhouse)) |
| `jailhouse cell create` fails with `File exists` | A cell with the same name exists; all Zephyr cells are named `zephyr` | Destroy the existing cell first (`jailhouse cell destroy zephyr`) |
| `jailhouse cell create` fails with `Device or resource busy` | Another cell uses the same CPUs or pins, for example a `uart-demo` cell, which also uses CPU 3 and UART1 | Destroy the other cell first |
| The cell state is `failed` | The cell accessed memory or a device that it does not own, or the image does not fit into its memory | Read `jailhouse console`: an `Unhandled data read`/`write` message names the address. Check that the image was built for the right board target, uses only the granted devices, and fits into 8 MiB (`system/memory_window`); use an AFE cell for audio images |
| No output on UART1, cell `running` | Wrong serial device or baud rate; another program reads the port; the image was loaded without `-a 0x8000`; the image was built for another board; an SMP image runs in a cell on other CPUs, such as `-zephyr-a78` | Check the device and 115200 baud; run `fuser /dev/ttyUSB<n>` on the host; reload with `-a 0x8000`; rebuild for the right board target; run SMP images only in the `-smp` cells (see [Section 6.5](#65-running-zephyr-on-two-cores-smp)) |
| UART1 shows `Failed to boot secondary CPU core 1 (MPID:0x200)` and a kernel panic; the cell stays `running` | An SMP image runs in a one-core cell, such as `-zephyr`: the hypervisor refuses to start CPU 2, which the cell does not own | Use the `-zephyr-smp` or `-zephyr-afe-smp` cell, or build the image for the single-core target (see [Section 6.5](#65-running-zephyr-on-two-cores-smp)) |
| `uart-demo` prints unreadable characters | UART1 is still in the high-speed mode that Zephyr set, or the terminal is not at 38400 baud | Run `devmem2 0x11001224 w 0` on the board; set the terminal to 38400 baud (see [Section 6.10](#610-optional-checking-a-cell-with-the-uart-demo-inmate)) |
| After a new `-zephyr-rpmsg` cell, Zephyr stays at `Awaiting VIRTIO config ready`, and Linux logs `msg received with no recipient` | The previous cell was destroyed while Linux was attached, so the remote processor is still `attached` | Write `detach` to `/sys/class/remoteproc/remoteproc<n>/state` until it reads `detached`, then run `rpmsg-test` again (see [Section 7.4](#74-rpmsg-with-linux)) |
| `jailhouse cell stats` fails with `setupterm: could not find terminal` | The command was started without a terminal, or with a terminal type unknown to the board | Use `adb shell -t` or an interactive `adb shell`, and set `TERM=xterm` if needed |
| Audio samples run but capture silence or report a DMA position outside the buffer | The audio power domain is off, the cell is not an AFE cell, the image was built without `mtk-afe`, or wires are missing | Work through [Section 7.3](#73-audio-samples) |
| Zephyr code runs slower than expected, or its processing times vary from run to run | Linux's `schedutil` governor lowers the clock of Zephyr's cluster while Linux is idle | Select the `performance` governor (see [Section 6.4](#64-choosing-a-cell)) |
| A Linux CPU is missing from `/sys/devices/system/cpu/online` | A cell uses it | Expected; `jailhouse cell destroy` returns it to Linux |
| Zephyr build fails because CMake or Python is too old | The host provides versions below CMake 3.28 or Python 3.12 | Use Ubuntu 24.04, or install newer versions (see [Section 5.1](#51-installing-the-host-dependencies)) |

---

## 9. Reference

### 9.1 Memory map

The Jailhouse overlay removes four areas from the memory that Linux may use:

| Physical address | Size | Use |
|---|---|---|
| `0x6ac00000` - `0x6affffff` | 4 MiB | Jailhouse hypervisor |
| `0x6b000000` - `0x6b7fffff` | 8 MiB | Inmate memory of the Zephyr cells; Zephyr sees it at `0x8000` |
| `0x6b800000` - `0x6b9fffff` | 2 MiB | Virtual PCI host: configuration space and the BARs of the ivshmem device |
| `0x6ba00000` - `0x6bafffff` | 1 MiB | Shared memory of the ivshmem device, between the root cell and a `-zephyr-rpmsg` cell (reserved, `no-map`) |

The AFE cells also share the audio DMA memory at `0x61000000` (8 MiB) with
Linux.

### 9.2 Cells

The `jailhouse` package installs these cell configurations in
`/usr/share/jailhouse/cells/` (`<board>` is `510` or `700`):

| File | Cell name | Description |
|---|---|---|
| `genio-<board>-evk.cell` | `genio-<board>-evk` | Root cell (system configuration): Linux, all CPUs, and a virtual PCI host with one ivshmem device. Used by `jailhouse enable`. |
| `genio-<board>-evk-zephyr.cell` | `zephyr` | Zephyr on CPU 3 |
| `genio-<board>-evk-zephyr-a78.cell` | `zephyr` | Zephyr on a Cortex-A78 (CPU 5 / CPU 7) |
| `genio-<board>-evk-zephyr-smp.cell` | `zephyr` | Zephyr on CPU 2 and 3 |
| `genio-<board>-evk-zephyr-afe.cell` | `zephyr` | As `-zephyr`, plus the audio front end |
| `genio-<board>-evk-zephyr-afe-a78.cell` | `zephyr` | As `-zephyr-a78`, plus the audio front end |
| `genio-<board>-evk-zephyr-afe-smp.cell` | `zephyr` | As `-zephyr-smp`, plus the audio front end |
| `genio-<board>-evk-zephyr-rpmsg.cell` | `zephyr` | As `-zephyr`, plus the ivshmem device shared with Linux, for RPMsg |
| `genio-<board>-evk-uart-demo.cell` | `uart-demo` | The `uart-demo` inmate on CPU 3 |

The image contains only the cells of the board it was built for. The
hypervisor, the driver, the tool and the cells of a release belong together:
the cell configuration format of MediaTek Jailhouse 1.0 is revision 15, and
cells built from upstream Jailhouse or from other trees do not load.

### 9.3 Resources of the Zephyr cells

All Zephyr cells grant:

| Resource | Details |
|---|---|
| CPUs | See [Section 9.2](#92-cells) |
| Memory | 8 MiB at physical address `0x6b000000`, mapped at `0x8000`; the image is loaded and started at `0x8000` |
| UART1 | Registers at `0x11001200`, interrupt SPI 142, clock gate 23 of `infracfg_ao`, and its pins GPIO 33 and 34 |
| GPIO | GPIO 38 and GPIO 40 (header pins 22 and 18), with their external interrupts EINT 38 and EINT 40 |

The AFE cells additionally grant:

| Resource | Details |
|---|---|
| Audio front end | Registers at `0x10b10000` (64 KiB), and the audio clock and reset controls, shared with Linux |
| Audio DMA memory | 8 MiB at `0x61000000`, shared with Linux |
| Secure monitor call | `MTK_SIP_AUDIO_CONTROL` |
| eTDM pins | GPIO 4-6, 11, 107-110, 114-117 and 125-128 |

The `-zephyr-rpmsg` cells additionally grant:

| Resource | Details |
|---|---|
| ivshmem device | Virtual PCI device `00:00.0`, the second of its two peers; in Linux, the first peer, it is `0001:00:00.0` |
| Shared memory | At `0x6ba00000`: a 4 KiB state table (read-only), 768 KiB that both peers can write, and 16 KiB of output for each peer, writable by that peer only |
| Interrupt | The device's interrupt, SPI 74 (GIC interrupt ID 106) of the cell; in Linux, SPI 72 (ID 104) |

Jailhouse mediates the GPIO, external interrupt and clock gate registers that
Linux and the cells share: each cell can read and change only the fields of
the pins and clock gates it owns. External interrupts of a cell's pins are
delivered to the cell. The pin configuration registers (pull, drive strength,
input enable) are not mediated and stay with Linux.

To adapt a cell, for example to give Zephyr other pins, edit its block in
the table of your board in MediaTek Jailhouse,
`configs/arm64/genio-<board>-evk-cells.c`, and rebuild Jailhouse; in IoT
Yocto, add the change as a patch to the `jailhouse` recipe, for example in a
`.bbappend`. The cell keeps its file name. The comments at the top of the
table and of `configs/arm64/genio-evk.h` describe the lists. The build
checks the CPUs, pins and interrupts; `jailhouse-config-check` checks the
cells against each other and against the root cell (see the repository's
`CONTRIBUTING.md`). The CPUs of the `-smp` cells must be the cores that the
Zephyr SMP board variants enable, in `boards/mediatek/common/genio-evk-smp.dtsi`
of the Genio Zephyr tree.

### 9.4 CPU and MPIDR map

Multi-core Zephyr images address CPUs by their MPIDR value.

| Linux CPU | Genio 510 EVK | Genio 700 EVK |
|---|---|---|
| 0 | Cortex-A55, MPIDR `0x000` | Cortex-A55, MPIDR `0x000` |
| 1 | Cortex-A55, `0x100` | Cortex-A55, `0x100` |
| 2 | Cortex-A55, `0x200` | Cortex-A55, `0x200` |
| 3 | Cortex-A55, `0x300` | Cortex-A55, `0x300` |
| 4 | Cortex-A78, `0x600` | Cortex-A55, `0x400` |
| 5 | Cortex-A78, `0x700` | Cortex-A55, `0x500` |
| 6 | — | Cortex-A78, `0x600` |
| 7 | — | Cortex-A78, `0x700` |

Under Jailhouse, PSCI calls from a cell must use the `smc` conduit. A cell can
start only its own CPUs; `CPU_ON` for any other CPU returns `DENIED`.

### 9.5 On-board files

| Path | Content |
|---|---|
| `/usr/sbin/jailhouse` | Jailhouse command-line tool |
| `/lib/firmware/jailhouse.bin` | Hypervisor firmware, loaded by `jailhouse enable` |
| `/lib/modules/<kernel>/updates/driver/jailhouse.ko` | Jailhouse driver |
| `/usr/share/jailhouse/cells/` | Cell configurations |
| `/usr/share/jailhouse/inmates/` | Demo inmates (`uart-demo.bin`, `gic-demo.bin`, `ivshmem-demo.bin`) |
| `/usr/libexec/jailhouse/` | Helper tools of the `jailhouse` command, for example `jailhouse-cell-stats` |
| `/sys/devices/jailhouse/` | Hypervisor and cell state, and statistics |

### 9.6 Command summary

| Command (on the board) | Purpose |
|---|---|
| `modprobe jailhouse` | Load the Jailhouse driver |
| `jailhouse enable /usr/share/jailhouse/cells/$(uname -n).cell` | Start the hypervisor; Linux becomes the root cell |
| `jailhouse cell create <cell file>` | Create a cell and move its resources from Linux to the cell |
| `jailhouse cell load zephyr <image> -a 0x8000` | Load a Zephyr image |
| `jailhouse cell start zephyr` | Start the cell |
| `jailhouse cell list` | List the cells and their state |
| `jailhouse cell stats zephyr` | Show VM exit statistics (needs a terminal) |
| `jailhouse console [-f]` | Show (and follow) the hypervisor console |
| `jailhouse cell shutdown zephyr` | Stop the cell, keep its resources |
| `jailhouse cell destroy zephyr` | Remove the cell and return its resources to Linux |
| `jailhouse disable` | Destroy all cells and stop the hypervisor |

### 9.7 Known limitations

- Jailhouse and its cells do not persist across a reboot. Enable Jailhouse
  and start the cell again after each boot.
- Only one Zephyr cell can exist at a time. All Zephyr cells use the same
  memory window, UART1 and GPIO pins.
- Zephyr can use only the devices that its cell grants. Other devices stay
  with Linux.
- The AFE cells share the audio front end, its clocks and the audio power
  domain with Linux. Linux must keep the audio power domain on and must not
  use the eTDM ports while an AFE cell runs.
- Linux sets the clocks of both CPU clusters. Zephyr runs at the frequency
  that Linux selects for the cluster of its CPUs (see
  [Section 6.4](#64-choosing-a-cell)).
- Multi-core cells start their CPUs only through PSCI over `smc`.
- Linux can change the pin configuration (pull, drive strength, input
  enable) of the cells' pins; Jailhouse does not mediate these registers.
- Linux cannot use the hardware debounce or the event registers of its
  external interrupts: Jailhouse ignores Linux's writes to them.
- Keeping Linux's power management away from a cell's devices, such as the
  audio front end, relies on Linux: the power domains' bus protection stays
  with Linux.
- The AFE cells do not get the audio front end's interrupt; the Zephyr audio
  driver polls.
- The AFE cells can write the whole reset block (`toprgu`), so that Zephyr
  can reset the audio subsystem. Such a cell can also reset other subsystems
  and reach the watchdog; trust AFE cells accordingly.
- Linux does not notice when a `-zephyr-rpmsg` cell is destroyed: detach
  Linux first (see [Section 7.4](#74-rpmsg-with-linux)).
- The MediaTek Jailhouse release notes list all limitations of the release
  (see [Section 10](#10-related-documentation)).

---

## 10. Related documentation

| Document | Address |
|---|---|
| IoT Yocto: Get Started | <https://genio.mediatek.com/doc/iot-yocto/latest/sw/yocto/get-started.html> |
| IoT Yocto: Linux build environment | <https://genio.mediatek.com/doc/iot-yocto/latest/sw/yocto/get-started/env-setup/build-env-linux.html> |
| IoT Yocto: Linux tool environment | <https://genio.mediatek.com/doc/iot-yocto/latest/sw/yocto/get-started/env-setup/flash-env-linux.html> |
| IoT Yocto: Build from Source Code | <https://genio.mediatek.com/doc/iot-yocto/latest/sw/yocto/get-started/build-code.html> |
| IoT Yocto: Board connection | <https://genio.mediatek.com/doc/iot-yocto/latest/sw/yocto/get-started/connect.html> |
| IoT Yocto: Flash Image to Board | <https://genio.mediatek.com/doc/iot-yocto/latest/sw/yocto/get-started/flash.html> |
| Zephyr Getting Started Guide | <https://docs.zephyrproject.org/latest/develop/getting_started/index.html> |
| Genio Zephyr samples, with the hardware setup in `doc/hardware.md` and the audio prerequisites in `audio/README.md` | <https://github.com/mtk-zephyr/samples> |
| Genio Zephyr tree | <https://github.com/mtk-zephyr/mtk-zephyr> |
| MediaTek Jailhouse | <https://github.com/mtk-jailhouse/jailhouse> |
| MediaTek Jailhouse `mtk-v1.0` release notes | <https://github.com/mtk-jailhouse/jailhouse/blob/mtk-v1.0/Documentation/mtk-v1.0-release-notes.md> |
| Jailhouse project | <https://github.com/siemens/jailhouse> |

[iot-get-started]: https://genio.mediatek.com/doc/iot-yocto/latest/sw/yocto/get-started.html
[iot-build-env]: https://genio.mediatek.com/doc/iot-yocto/latest/sw/yocto/get-started/env-setup/build-env-linux.html
[iot-flash-env]: https://genio.mediatek.com/doc/iot-yocto/latest/sw/yocto/get-started/env-setup/flash-env-linux.html
[iot-build-code]: https://genio.mediatek.com/doc/iot-yocto/latest/sw/yocto/get-started/build-code.html
[iot-connect]: https://genio.mediatek.com/doc/iot-yocto/latest/sw/yocto/get-started/connect.html
[iot-flash]: https://genio.mediatek.com/doc/iot-yocto/latest/sw/yocto/get-started/flash.html
[zephyr-gsg]: https://docs.zephyrproject.org/latest/develop/getting_started/index.html
[zephyr-gsg-deps]: https://docs.zephyrproject.org/latest/develop/getting_started/index.html#install-dependencies

---

## Revision history

| Revision | Date | Changes |
|---|---|---|
| 0.9 | 2026-10-04 | Initial draft for review |
| 0.9.1 | 2026-10-08 | UART0 named by its board label only. Linux sets the clocks of both CPU clusters; use the `performance` governor for measurements (Sections 6.4, 6.6, 9.7). How an SMP image fails in a cell other than an SMP cell (Section 6.5). Two new troubleshooting entries. The hypervisor of mtk-v1.0: its start-up messages (Section 6.2), and pin configuration registers that stay with Linux (Sections 9.3, 9.7). |
| 1.0 | 2026-10-08 | First release, for MediaTek Jailhouse `mtk-v1.0.0` and Genio Zephyr `mtk-genio-v1.0.0`. RPMsg with Linux (Section 7.4). The layer's `jailhouse` recipe builds the release branch `mtk-v1.0` and installs the cells of one board (Sections 2.2, 3.3, 4.4, 9.2). The Zephyr workspace is created at the release tag (Section 5.2). Known limitations in step with the release notes (Section 9.7). Two new troubleshooting entries. |
