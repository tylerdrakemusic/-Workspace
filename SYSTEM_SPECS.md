# System Specifications — Tyler's Alienware Aurora R7

**Last Updated:** April 3, 2026
**Service Tag:** 8HT9XM2
**Dell Support:** https://www.dell.com/support/home/en-us/product-support/servicetag/8HT9XM2

---

## System Overview

| Component | Detail |
|-----------|--------|
| **Model** | Alienware Aurora R7 |
| **Manufacturer** | Alienware (Dell) |
| **Motherboard** | Alienware 0VDT73 (Rev A00) |
| **Form Factor** | Mid-Tower ATX |
| **PSU** | **460W** (Active PFC, Part# YJ13V / 64GT2) |
| **BIOS** | Alienware v1.0.25 (Sep 2021) |
| **PCIe Slot** | PCIe 3.0 x16 |

---

## CPU

| Spec | Value |
|------|-------|
| **Model** | Intel Core i7-8700 @ 3.20 GHz |
| **Cores / Threads** | 6 / 12 |
| **Max Turbo** | 4.60 GHz |
| **Architecture** | Coffee Lake (8th Gen) |
| **Socket** | LGA 1151 v2 |
| **TDP** | 65W |

---

## GPU (Discrete)

| Spec | Value |
|------|-------|
| **Model** | NVIDIA GeForce GTX 1060 6GB |
| **VRAM** | 6 GB GDDR5 |
| **CUDA Cores** | 1280 |
| **Compute Capability** | 6.1 |
| **Driver** | 572.61 (v32.0.15.7261, Feb 2025) |
| **TDP** | 120W |

### Integrated GPU
- Intel UHD Graphics 630 (Driver 27.20.100.9664)

---

## RAM

| Spec | Value |
|------|-------|
| **Total** | 64 GB DDR4 |
| **Configuration** | 4x 16GB |
| **Speed** | 3200 MHz |
| **Part Number** | Kingston KF3200C16D4/16GX (Kingston FURY) |
| **Slots** | 4/4 occupied |

---

## Storage

| Drive | Size | Type | Interface | Mount |
|-------|------|------|-----------|-------|
| **TOSHIBA DT01ACA100** | 931 GB | Internal HDD | SATA | C: (NTFS, 702 GB, 107 GB free) |
| **Samsung PSSD T7** | 1.86 TB | External SSD (USB) | USB/SCSI | F: (exFAT, 1863 GB, 1543 GB free) |
| (Partition) | — | — | — | G: "Tyler's Healthy Volume" (NTFS, 228 GB, 116 GB free) |

---

## Operating System

| Spec | Value |
|------|-------|
| **OS** | Windows 10 Home 64-bit |
| **Build** | 19045 (22H2) |

---

## Software / AI Stack

| Package | Version |
|---------|---------|
| **Python** | 3.11.4 (C:\G\) |
| **PyTorch** | 2.7.0+cu128 |
| **CUDA Toolkit** | 12.8 |
| **diffusers** | 0.37.1 |
| **huggingface_hub** | 1.8.0 |
| **xformers** | 0.0.26.post1 (incompatible — built for PyTorch 2.3/CUDA 12.1) |
| **HF_TOKEN** | Set as User env variable |
| **HF_HUB_DISABLE_XET** | Required ("1") — XET CDN connections get reset on this network |

---

## GPU Upgrade Notes

### Current Limitations
- **460W PSU** limits GPU options to ~170W TDP cards without PSU replacement
- **6GB VRAM** causes heavy swapping on AI models (SVD-XT takes ~14 hrs)
- **PCIe 3.0 x16** — compatible with all modern GPUs (PCIe is backward compatible)
- **ATX PSU** — standard form factor, easy to replace

### Upgrade Options (April 2026 pricing)

| GPU | VRAM | TDP | PSU Needed | Price | SVD-XT Est. |
|-----|------|-----|-----------|-------|-------------|
| RTX 3060 12GB | 12 GB | 170W | 460W OK | ~$250 | ~1-2 hr |
| RTX 4060 8GB | 8 GB | 115W | 460W OK | ~$300 | ~45 min |
| RTX 4060 Ti 16GB | 16 GB | 160W | 460W OK | ~$400 | ~30 min |
| RTX 3090 (used) | 24 GB | 350W | 750W+ | ~$600 | ~10-15 min |
| RTX 4070 Ti 12GB | 12 GB | 285W | 700W+ | ~$810 | ~5-10 min |
| RTX 4070 Ti Super 16GB | 16 GB | 285W | 700W+ | ~$800 | ~5-10 min |

### PSU Part Info
- Current: **460W** (Dell Part# YJ13V / Assy 64GT2)
- Upgrade: Any standard ATX 750W+ (e.g., Corsair RM750e ~$80-100)

---

## Known Issues / Workarounds

- **xFormers incompatible** — Warning only, doesn't block execution. Would need `pip install xformers` matching PyTorch 2.7/CUDA 12.8
- **HuggingFace XET downloads fail** — Set `HF_HUB_DISABLE_XET=1` env var before any HF download
- **WinError 10054** — Intermittent connection resets to HF CDN. Retries usually work. Not Defender-related.
- **No NVMe/SSD as boot drive** — C: is on a mechanical HDD (TOSHIBA DT01ACA100). An NVMe SSD boot drive would significantly improve load times.
