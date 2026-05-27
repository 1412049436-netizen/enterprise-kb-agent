# 显卡/GPU 行业相关规范查找路径

> 整理时间：2026-05-26
> 用途：GPU/显卡行业标准与合规文件索引

---

## 一、国家标准（中国）

### 计算机/信息技术通用标准

| 标准号 | 名称 | 说明 |
|--------|------|------|
| GB/T 9813 系列 | 微型计算机通用规范 | 含图形显示子系统基本要求 |
| GB/T 15237 | 术语工作 词汇 | 信息技术基础术语 |
| GB/T 5271 系列 | 信息技术 词汇 | 含图形处理相关术语定义 |
| GB/T 34078 | 信息技术 开放系统互连 | 系统互连基础 |

### GPU 专项标准

| 标准号 | 名称 | 状态 |
|--------|------|------|
| — | 图形处理器（GPU）通用规范 | 制定中（CESI 牵头） |
| — | GPU 性能测试方法 | 制定中 |
| — | 人工智能 深度学习框架与GPU适配要求 | 制定中 |

> 注：中国目前尚无已发布的 GPU 专项国家标准。但 CESI（中国电子技术标准化研究院）正在牵头制定 GPU 通用规范和性能测试方法标准，预计 2025-2026 年陆续发布。

### 电子元器件标准（与显卡组件相关）

| 标准号 | 名称 |
|--------|------|
| GB/T 4589 | 半导体器件 分立器件和集成电路 |
| SJ/T 系列 | 电子行业标准（集成电路、PCB等） |

---

## 二、国际标准

### PCI-SIG 规范

| 规范 | 版本 | 说明 |
|------|------|------|
| PCI Express Base Specification | 5.0 / 6.0 | 显卡总线接口基础规范 |
| PCIe Card Electromechanical (CEM) Spec | 5.0 | 显卡物理尺寸与电源规范 |

> 获取地址：https://pcisig.com/specifications

### Khronos 图形 API 标准

| 标准 | 版本 | 说明 |
|------|------|------|
| Vulkan API | 1.4 | 跨平台高性能图形与计算API |
| OpenGL | 4.6 | 经典图形API |
| OpenCL | 3.0 | 异构计算API（含GPU计算） |
| SYCL | 2020 | 单源C++异构编程（含GPU） |

> 获取地址：https://www.khronos.org/registry/

### ISO/IEC 标准

| 标准号 | 名称 |
|--------|------|
| ISO/IEC 19795 系列 | 生物特征识别性能测试（GPU加速相关） |
| ISO/IEC 30137 | 视频监控中生物特征识别（GB/T 44261 采标源） |

---

## 三、厂商技术规范

### NVIDIA

| 资源 | 地址 |
|------|------|
| CUDA Toolkit 文档 | https://docs.nvidia.com/cuda/ |
| GPU 计算能力表 | https://developer.nvidia.com/cuda-gpus |
| nvidia-smi 手册 | `man nvidia-smi` 或 https://developer.nvidia.com/nvidia-system-management-interface |
| 数据中心 GPU 安装指南 | https://docs.nvidia.com/datacenter/ |

### AMD

| 资源 | 地址 |
|------|------|
| ROCm 文档 | https://rocm.docs.amd.com/ |
| GPU 规格与白皮书 | https://www.amd.com/en/products/specifications/graphics |
| AMDGPU 驱动文档 | https://docs.kernel.org/gpu/amdgpu/ |

### Intel

| 资源 | 地址 |
|------|------|
| oneAPI GPU 编程指南 | https://oneapi-src.github.io/ |
| Intel Arc GPU 规格 | https://www.intel.com/content/www/us/en/products/docs/arc-graphics/ |

### 国产 GPU

| 厂商 | 资源 |
|------|------|
| 摩尔线程（Moore Threads） | https://www.mthreads.com/ — MUSA 编程模型文档 |
| 壁仞科技（Biren） | https://www.birentech.com/ |
| 芯动科技（Innosilicon） | https://www.innosilicon.com/ |
| 景嘉微（Jingjia Micro） | https://www.jjmic.com/ |

---

## 四、行业协会与检测机构

| 机构 | 角色 | 地址 |
|------|------|------|
| 中国电子技术标准化研究院（CESI） | GPU 国标核心起草单位 | https://www.cesi.cn |
| 中国计算机行业协会（CCIA） | 团体标准发布 | https://www.ccia.org.cn |
| 中国信息通信研究院（CAICT） | GPU 检测评估 | https://www.caict.ac.cn |
| 国家电子计算机质量检验检测中心 | GPU 产品检测 | http://www.nctc.org.cn |

### CESI 联系人（GPU 标准）

中国电子技术标准化研究院 集成电路测评中心
如需获取 GPU 标准制定进展，可联系 CESI 相关部门获取最新信息。

---

## 五、建议补充

以下内容建议通过具体搜索获取：

- [ ] GB/T 9813.x 微型计算机通用规范 中关于图形子系统的具体条款
- [ ] GPU 通用规范（制定中）的征求意见稿
- [ ] 中国计算机行业协会 GPU 相关团体标准（T/CCIA 系列）
- [ ] Vulkan 兼容性测试套件（VK-GL-CTS）
- [ ] 信通院 GPU 算力评估报告
- [ ] JEDEC 显存标准（GDDR6/GDDR7）— https://www.jedec.org
