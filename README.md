# lidar-coverage

[中文](#中文) · [English](#english) · [Latest report](https://dogzzl1xy.github.io/lidar-coverage-pipeline/)

---

## 中文

这个工具用来找出美国人口普查 county subdivision（镇、乡等）中缺少现代 LiDAR 的区域。它计算每个区域有多大比例的面积被 2015 年及以后采集的 LiDAR 覆盖，比例低于阈值（默认 5%）就记为缺口。可以按单个州、多个州或全美本土（48 州加 DC，`CONUS`）运行。分析只使用覆盖范围和元数据，不下载点云。

2026-10-06 的全美结果见[报告页面](https://dogzzl1xy.github.io/lidar-coverage-pipeline/)：35,309 个区域中，只用 hobuinc 清单时有 2,306 个低于 5%，加上 USGS 官方 3DEP 索引后为 420 个。所有批次的采集日期都已用点云 GPS 时间核实。

### 安装

需要 Python 3.12 及以上和 [uv](https://docs.astral.sh/uv/)。

```bash
uv tool install git+https://github.com/DOGZzl1xy/lidar-coverage-pipeline
```

参与开发：

```bash
git clone https://github.com/DOGZzl1xy/lidar-coverage-pipeline && cd lidar-coverage-pipeline && uv sync
```

开发环境中在命令前加 `uv run`。

### 使用

```bash
lidar-coverage --state RI
lidar-coverage --states RI MA PA --coverage-threshold 10 --output-dir outputs_ne
lidar-coverage --states CONUS --output-dir outputs
lidar-coverage --states CONUS --supplement-3dep-index --output-dir outputs_with_3dep
lidar-coverage-validate outputs
```

也可以用配置文件运行，例如 `lidar-coverage --config configs/conus.yaml` 或 `configs/conus_with_3dep.yaml`。命令行参数会覆盖配置文件里的同名设置。

Python 调用：

```python
from lidar_coverage import run

summary = run(["RI", "MA"], output_dir="outputs_ne")  # 返回每州一行的汇总表
```

默认情况下：

- 每次运行下载最新的 hobuinc LiDAR 清单（约 9 MB）；`--offline` 使用本地缓存。人口普查边界下载一次后缓存在 `data/cache/`。
- 使用包内自带的年份核实表（62 个批次，每条附证据）；`--no-vintage-overrides` 只用批次名称里的年份。
- 批次的年份取最后一次采集的年份，跨越 2015 年的批次算作现代数据。

### 常用参数

| 参数 | 说明 |
| --- | --- |
| `--state` / `--states` | 州代码；`CONUS` 表示本土 48 州加 DC |
| `--coverage-threshold` | 缺口阈值（百分比），默认 `5` |
| `--min-year` | 现代 LiDAR 的最早年份，默认 `2015` |
| `--supplement-3dep-index` | 加入 USGS 官方 3DEP 索引的覆盖范围（包含尚未转成 EPT、因而不在 hobuinc 清单里的批次） |
| `--vintage-overrides CSV` / `--no-vintage-overrides` | 换用其他核实表，或不使用核实表 |
| `--skip-existing` | 断点续跑：参数和输入都相同时复用已完成的州 |
| `--offline` / `--refresh-cache` | 只用缓存 / 重新下载所有输入 |
| `--preflight` | 只检查数据源是否可用，不做空间分析 |

### 输出

每个州（`<st>` 为小写州代码）：

| 文件 | 内容 |
| --- | --- |
| `<st>_cousub_coverage_all.csv` / `.geojson` | 每个区域一条记录 |
| `<st>_cousub_coverage_under_threshold.csv` / `.geojson` | 只含缺口 |
| `<st>_coverage_summary.md` | 州摘要 |

整批：`batch_summary.csv` / `.md`（每州一行）、`unresolved_collections.csv`（判断不出年份、未计入的批次）、`run_manifest.json`（参数、输入地址和哈希、运行状态）。

字段：`GEOID`、`town_name`、`state`、`base_area_m2`、`covered_area_m2`、`gap_area_m2`、`coverage_pct`、`lidar_batch_count`（同一批次的不同名称只计一次）、`data_vintage_note`。

### 数据来源

- 边界：Census TIGER/Line 2024 COUSUB（剔除编码为 `00000` 的 "County subdivisions not defined" 占位区域）。
- LiDAR 覆盖范围：[`hobuinc/usgs-lidar`](https://github.com/hobuinc/usgs-lidar) 的 `boundaries/resources.geojson`；可选加入 USGS 3DEP Elevation Index 的 work unit。
- 面积在 EPSG:5070 下计算，重叠的覆盖范围合并后只算一次。

### 维护工具

```bash
uv run python scripts/fetch_usgs_workunits.py
uv run --extra verify python scripts/sample_ept_acquisition_dates.py KY_FullState --nodes 48
```

第一个脚本从 USGS 拉取官方采集日期（只拉属性）。第二个脚本从点云中抽取几十个小块（每个批次 5 到 65 MB），读取其中的 GPS 时间，用来核实批次的实际采集年份。

### 开发

```bash
uv run ruff check src scripts tests
uv run python -m unittest discover -s tests
```

`SPEC.md` 是分析与输出规范，`Progress.md` 记录当前结果、核实记录和待办，`docs/index.html` 是报告页面的源文件。

---

## English

Finds U.S. Census county subdivisions (towns, townships and similar units) that lack modern LiDAR. For each one it computes the share of the area covered by LiDAR collected in 2015 or later and reports a gap when that share is below a threshold (5% by default). It runs for one state, a list of states, or the contiguous 48 states plus DC (`CONUS`). The analysis uses footprints and metadata only and never downloads point clouds.

The 2026-10-06 national results are in the [report](https://dogzzl1xy.github.io/lidar-coverage-pipeline/): of 35,309 county subdivisions, 2,306 fall below 5% with the hobuinc inventory alone and 420 after adding the official USGS 3DEP index. Every collection's acquisition date was checked against GPS times in its point cloud.

### Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install git+https://github.com/DOGZzl1xy/lidar-coverage-pipeline
```

For development:

```bash
git clone https://github.com/DOGZzl1xy/lidar-coverage-pipeline && cd lidar-coverage-pipeline && uv sync
```

In a development checkout, prefix commands with `uv run`.

### Usage

```bash
lidar-coverage --state RI
lidar-coverage --states RI MA PA --coverage-threshold 10 --output-dir outputs_ne
lidar-coverage --states CONUS --output-dir outputs
lidar-coverage --states CONUS --supplement-3dep-index --output-dir outputs_with_3dep
lidar-coverage-validate outputs
```

You can also run from a config file, such as `lidar-coverage --config configs/conus.yaml` or `configs/conus_with_3dep.yaml`. Command-line options override settings in the file.

From Python:

```python
from lidar_coverage import run

summary = run(["RI", "MA"], output_dir="outputs_ne")  # one summary row per state
```

By default:

- Each run downloads the latest hobuinc LiDAR inventory (about 9 MB); `--offline` uses the cached copy. Census boundaries are downloaded once and cached in `data/cache/`.
- The reviewed vintage table bundled with the package (62 collections, each with evidence) is applied; `--no-vintage-overrides` uses only years parsed from collection names.
- A collection's vintage is its latest acquisition year, so collections that span 2015 count as modern.

### Options

| Option | Meaning |
| --- | --- |
| `--state` / `--states` | State codes; `CONUS` means the 48 contiguous states plus DC |
| `--coverage-threshold` | Gap threshold in percent, default `5` |
| `--min-year` | Earliest year that counts as modern, default `2015` |
| `--supplement-3dep-index` | Add footprints from the official USGS 3DEP index, which includes collections not yet converted to EPT and so missing from the hobuinc inventory |
| `--vintage-overrides CSV` / `--no-vintage-overrides` | Use another reviewed table, or none |
| `--skip-existing` | Resume: reuse finished states when settings and inputs are unchanged |
| `--offline` / `--refresh-cache` | Use cached inputs only / re-download every input |
| `--preflight` | Check that the sources are reachable without running the analysis |

### Outputs

Per state (`<st>` is the lower-case state code):

| File | Content |
| --- | --- |
| `<st>_cousub_coverage_all.csv` / `.geojson` | One record per county subdivision |
| `<st>_cousub_coverage_under_threshold.csv` / `.geojson` | Gap records only |
| `<st>_coverage_summary.md` | State summary |

Per run: `batch_summary.csv` / `.md` (one row per state), `unresolved_collections.csv` (collections left out because their vintage is unknown), and `run_manifest.json` (parameters, input URLs and hashes, run status).

Fields: `GEOID`, `town_name`, `state`, `base_area_m2`, `covered_area_m2`, `gap_area_m2`, `coverage_pct`, `lidar_batch_count` (aliases of one collection count once), and `data_vintage_note`.

### Data sources

- Boundaries: Census TIGER/Line 2024 COUSUB, without the `00000` "County subdivisions not defined" placeholders.
- LiDAR footprints: `boundaries/resources.geojson` from [`hobuinc/usgs-lidar`](https://github.com/hobuinc/usgs-lidar), optionally plus USGS 3DEP Elevation Index work units.
- Areas are computed in EPSG:5070, and overlapping footprints are merged so no area counts twice.

### Maintainer tools

```bash
uv run python scripts/fetch_usgs_workunits.py
uv run --extra verify python scripts/sample_ept_acquisition_dates.py KY_FullState --nodes 48
```

The first downloads official acquisition dates from USGS (attributes only). The second reads GPS times from a few dozen small point-cloud blocks (5 to 65 MB per collection) to check when a collection was actually flown.

### Development

```bash
uv run ruff check src scripts tests
uv run python -m unittest discover -s tests
```

`SPEC.md` defines the analysis and outputs, `Progress.md` holds current results, review records and open items, and `docs/index.html` is the source of the report page.
