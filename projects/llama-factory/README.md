# LLaMA-Factory (Ascend NPU)

LLM fine-tuning (LoRA / QLoRA) with [LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory)
on Ascend NPU. ModelArts-compatible — runs as `ma-user` (uid 1000, gid 100).

> **Build verified, runtime untested.** The image builds and was exercised
> offline on an arm64 Mac (see *What was actually verified* below), but no Ascend
> device was available. Anything that needs the NPU itself is a first attempt —
> confirm each step's stated observable against real hardware.

## Why this one is a thin layer

Unlike `projects/yolo/` and `projects/nanochat/`, this image does **not** rebuild
or re-pin the CANN / torch / torch_npu stack. It layers on
`quay.io/ascend/llamafactory`, which Ascend builds and tests against real
devices. Re-pinning that stack blind is how you get an image that imports
cleanly but cannot see a device.

That means there is no `depends_on` in `dockerfile-compose.yaml` — the base is
external to this repo (`standalone: true`).

## Offline constraint

The target NPU box has **no route out**. Everything the image needs is installed
or baked at build time; `HF_HUB_OFFLINE=1` is set so a stray hub id fails loudly
rather than hanging. Run the preflight before building — it fails if any config
references something that would have to be downloaded at run time:

```bash
./projects/llama-factory/preflight-offline.sh
```

`PIP_INDEX_URL` is a build ARG only and deliberately does **not** persist into
the runtime image: a leftover index URL would point an air-gapped box at a
mirror it cannot reach, turning a clear "no network" into a confusing timeout.

## Build

```bash
# Both variants via the factory (from the repo root)
python build.py --target llama-factory-0.9.5-npu-a3
python build.py --target llama-factory-0.9.5-npu-a2

# Or directly — note the context is the REPO ROOT, not this directory
docker build --platform linux/arm64 \
  -f projects/llama-factory/Dockerfile \
  -t llama-factory:0.9.5-npu-a3 .
```

The base is multi-gigabyte; expect a long first pull. Available upstream bases:

| Tag | Target |
|---|---|
| `0.9.5-npu-a3`, `0.9.4-npu-a3` | A3 |
| `0.9.5-npu-a2`, `0.9.4-npu-a2` | A2 |
| `latest-a3-ubuntu`, `latest-a3-openeuler` | A3, rolling |
| `latest-910b-ubuntu`, `latest-910b-openeuler` | 910b, rolling |

Override with `--build-arg BASE_IMAGE=...`.

The default pip index is upstream PyPI, not the Tsinghua mirror used by
`dockerfiles/python.dockerfile` — that mirror returned **403 Forbidden** from the
build network while `pypi.org` returned 200, and pip reports a 403 as the
misleading `from versions: none`, which reads like a bad version pin. Pass a
mirror explicitly if your network needs one:

```bash
--build-arg PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
```

## Run

Mounting `/dev/davinci*` alone is the most common failure: `torch_npu` then
imports fine but finds no usable device. The host driver directories are
required too.

```bash
docker run -it --rm \
  --device /dev/davinci0 \
  --device /dev/davinci_manager \
  --device /dev/devmm_svm \
  --device /dev/hisi_hdc \
  -v /usr/local/dcmi:/usr/local/dcmi:ro \
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi:ro \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
  -v /etc/ascend_install.info:/etc/ascend_install.info:ro \
  -v /mnt/obs/models:/home/ma-user/work/models:ro \
  -v /mnt/local/output:/home/ma-user/output \
  --shm-size 16g \
  quay.io/service-delivery-hub/llama-factory:0.9.5-npu-a3
```

Check the host sees its devices *before* reaching for Docker flags — `npu-smi info`
should print a table of healthy chips, and `ls /dev/davinci*` one node per chip.
No container flag fixes a host that cannot see its own accelerators.

### The two storage mounts differ on purpose

| Mount | Mode | Holds |
|---|---|---|
| `/home/ma-user/work/models` | **read-only** | base weights from OBS |
| `/home/ma-user/output` | read-write, **local disk** | checkpoints and adapters |

`HF_HOME` deliberately does **not** point at the weights mount. The huggingface
cache writes lock files and metadata even when it downloads nothing, so a
read-only `HF_HOME` fails with errors that never mention permissions.

Never write checkpoints straight to a fuse-mounted bucket either — the writes are
slow enough to stall a training step. Write to local disk, sync to OBS after.

## Train

```bash
llamafactory-cli train /home/ma-user/llama-factory/configs/npu-a3-lora.yaml
```

| Config | Notes |
|---|---|
| `npu-a3-lora.yaml` | bf16 LoRA, rank 8, Qwen3-4B-Instruct |
| `npu-a3-qlora.yaml` | 4-bit bnb QLoRA; sets `double_quantization: false`, **required** by the bitsandbytes NPU backend |
| `_base/sft-lora.yaml` | reference fragment only — `llamafactory-cli` does not merge includes |

Both configs point `model_name_or_path` at a local path under the read-only
mount, not a hub id: the image sets `HF_HUB_OFFLINE=1`, so a hub id is a run that
fails late, after the queue wait and container start. Stage weights to
`${OBS_MODELS_DIR}/Qwen3-4B-Instruct-2507` first.

## Baked-in datasets

`identity`, `alpaca_en_demo`, `alpaca_zh_demo` (2,090 records) ship in the image
deliberately: an NPU box may sit on a network where Hugging Face is slow or
unreachable, and a run that dies 40 minutes in on a dataset fetch wastes the
session.

`data/dataset_info.json` is trimmed to exactly these three — LLaMA-Factory
validates every registered entry, so a registration whose file is absent breaks
the run. Add both the file and its entry when you add a dataset.

Both configs pin `dataset_dir: /home/ma-user/llama-factory/data` absolutely.
`llamafactory-cli` resolves the default (`data`) against the *current working
directory*, and this image's `WORKDIR` is `/home/ma-user` — without the pin,
training fails to find `dataset_info.json` unless you happen to `cd` first.
Change the pin if you relocate the datasets.

## Notebook

A `llama-factory-npu` kernel is registered as "LLaMA-Factory (Ascend NPU)" so the
image can back a ModelArts notebook. JupyterLab is intentionally omitted —
ModelArts provides its own.

## No HEALTHCHECK, deliberately

Measured on `0.9.5-npu-a3` (arm64, no device attached):

- `import torch` and `llamafactory-cli` **fail** with `Failed to load the backend
  extension: torch_npu`, ultimately
  `ImportError: libascend_hal.so: cannot open shared object file` — that library
  comes from the host driver.
- With `TORCH_DEVICE_BACKEND_AUTOLOAD=0`, `import llamafactory` **succeeds**
  (returns `0.9.5`), and `bitsandbytes` imports fine.

So a healthcheck *is* technically possible off-device — but only by disabling the
very backend load that determines whether the image can train, which would go
green on a box with no usable NPU. A check that cannot fail for the reason you
care about is worse than no check. Readiness is the sequence above, run by a
human against real hardware.

## What was actually verified

Built and exercised on an arm64 Mac (native, no emulation), base
`quay.io/ascend/llamafactory:0.9.5-npu-a3` → final image **13.1 GB**.

| Check | Result |
|---|---|
| `docker build --platform linux/arm64` | passes; `buildx --check` reports no warnings |
| `bitsandbytes` present | **was absent from the base** — now installed (0.50.2) and imports on aarch64 |
| `tensorboard`, `ipykernel` | installed (2.21.0 / 6.29.5); kernelspec `llama-factory-npu` registered |
| `ma-user` creation | base has no `ma-user` and uid 1000 is free, so the conditional `useradd` fires |
| Runtime identity | `uid=1000(ma-user) gid=100(users)` |
| Dir ownership | `output`, `.cache/huggingface`, `work/models` all `1000:100` |
| `PIP_INDEX_URL` leak | absent from the runtime env, as intended |
| Datasets load with `--network none` | all 3 load, 2,090 records total |
| Hub id with `--network none` | correctly blocked (`OSError`) by `HF_HUB_OFFLINE=1` |
| `qwen3_nothink` template | present in the base at `template.py:1980` |
| `double_quantization: false` | matches upstream, which does `not is_torch_npu_available()` in `webui/runner.py` |
| `llamafactory-cli train <config>` | reaches `libascend_hal.so` — a **missing-device** failure, not a network one |

**Not verified, needs hardware:** that training actually runs, throughput, memory
headroom, whether the LoRA/QLoRA hyperparameters converge, and template behavior
at run time (`transformers` probes `torch_npu` just to *check* for NPU, so even
the template registry cannot be introspected off-device).
