"""种子数据：3 个预置测试账号 + 扫描项目根「学习资料」真实文件夹入库 + 示例 DDL。

知识库来源优先级：
1) <项目根>/学习资料/ 真实目录（12 门课程的 doc/docx/ppt/pptx/pdf/txt/md）；
2) 若该目录不存在，降级使用内置 DOC_MAIN / DOC_COCO 两份 markdown 样例，保证部署不崩。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Course, DDL, DocumentFile, User
from ..security import hash_password
from .ingest import FOLDER_COURSE_MAP, get_or_create_course, ingest_file
from .parser import SUPPORTED_EXT

logger = logging.getLogger("zhinan.seed")

TEST_ACCOUNTS = [
    {"username": "demo1", "password": "echo123456", "nickname": "小南",
     "email": "", "seed_scope": "demo1"},
    {"username": "demo2", "password": "echo123456", "nickname": "小Echo",
     "email": "", "seed_scope": "demo2"},
    {"username": "demo3", "password": "echo123456", "nickname": "新生小白",
     "email": "", "seed_scope": ""},
]

# 旧 5 份 markdown 资料：「学习资料」目录不可见时的轻量回退。
DOC_MAIN = {
    "数据结构-第5章-树与二叉树（课件）.md": """# 第5章 树与二叉树

## 5.1 树的基本概念
树是 n(n≥0) 个结点的有限集合。结点的度是其所拥有的子树数；树的度是树内各结点度的最大值。森林是 m 棵互不相交的树的集合。

## 5.2 二叉树的性质
性质1：在二叉树的第 i 层上至多有 2^(i-1) 个结点。性质2：深度为 k 的二叉树至多有 2^k - 1 个结点。性质3：对任何二叉树 T，若终端结点数为 n0，度为 2 的结点数为 n2，则 n0 = n2 + 1。具有 n 个结点的完全二叉树的深度为 ⌊log2 n⌋ + 1。

## 5.3 二叉树的遍历
二叉树的遍历是指按某条搜索路径巡访树中每个结点，使得每个结点均被访问一次且仅被访问一次。
先序遍历（前序遍历）：访问根结点、先序遍历左子树、先序遍历右子树，记作 NLR。
中序遍历：中序遍历左子树、访问根结点、中序遍历右子树，记作 LNR。
后序遍历：后序遍历左子树、后序遍历右子树、访问根结点，记作 LRN。
层序遍历：自上而下、自左而右逐层访问结点，需借助队列实现。
已知中序遍历和先序遍历可以唯一确定一棵二叉树；已知中序和后序也能唯一确定；但已知先序和后序不能唯一确定二叉树。
遍历的非递归实现借助显式栈：中序遍历时先沿左子树入栈，再弹出访问并转向右子树。层序遍历借助队列，先将根入队，出队访问后把其左右孩子入队。
线索二叉树：利用二叉链表中的空指针域存放指向结点在某种遍历次序下的前驱和后继的指针，加线索的过程称为线索化。

## 5.4 哈夫曼树及其应用
哈夫曼树又称最优二叉树，是带权路径长度 WPL 最小的二叉树。构造方法：从森林中选取两棵根结点权值最小的树合并，重复 n-1 次。哈夫曼编码是前缀编码，可用于数据压缩，出现频率高的字符编码短。

## 5.5 树与森林的转换
孩子兄弟表示法：每个结点含第一个孩子指针和右兄弟指针。树转二叉树：左指针指向第一个孩子，右指针指向右兄弟。森林转二叉树：先把各树转为二叉树，再依次把后一棵作为前一棵的右子树。
""",
    "数据结构-图专题复习（笔记）.md": """# 图论专题复习笔记

## 图的遍历
深度优先搜索 DFS：从某顶点出发访问后，访问其未被访问的邻接点，递归进行；借助递归栈，时间复杂度邻接表 O(n+e)、邻接矩阵 O(n²)。
广度优先搜索 BFS：按层次访问，借助队列实现，时间复杂度同 DFS。
DFS 可判断图的连通性、求连通分量；BFS 可求无权图的单源最短路径。

## 最短路径
Dijkstra 算法：单源最短路，贪心策略，每次选取距离源点最近且未确定的顶点，要求边权非负，时间复杂度 O(n²)。
Floyd 算法：求所有顶点对之间的最短路径，动态规划思想，三重循环，时间复杂度 O(n³)，允许负权边但不允许负权回路。
SPFA 是队列优化的 Bellman-Ford，可处理负权边。

## 最小生成树
Prim 算法：从某顶点出发，不断将「距离生成树最近」的顶点加入，适合稠密图，O(n²)。
Kruskal 算法：将边按权值排序，依次选择不构成回路的边，借助并查集，适合稀疏图，O(e log e)。

## 拓扑排序与关键路径
拓扑排序：对 AOV 网，重复选择入度为 0 的顶点输出并删除其出边；若输出顶点数小于总顶点数，说明网中存在回路。拓扑序列不唯一。
关键路径：AOE 网中从源点到汇点的最长路径，其上活动均为关键活动，关键活动最早开始时间等于最迟开始时间。缩短工期应压缩关键路径上的活动。

## 图的存储结构
邻接矩阵：一维数组存顶点、二维数组存边，适合稠密图，判断两点相邻 O(1)。邻接表：每个顶点挂边链表，适合稀疏图，找某顶点所有邻接点高效。
""",
    "数据结构-期末试题（2024-2025学年）.md": """# 数据结构期末试题（2024-2025 学年）

## 一、选择题
1. 设一棵完全二叉树有 700 个结点，则叶子结点个数为（ B ）A.349 B.350 C.351 D.352
2. 下列排序算法中，不稳定的是（ C ）A.冒泡排序 B.直接插入排序 C.快速排序 D.归并排序
3. 对 n 个元素的快速排序，平均时间复杂度为 O(n log n)，最坏情况为 O(n²)，最坏情况出现在序列已经有序时。
4. 栈的进出原则是后进先出 LIFO，队列是先进先出 FIFO。
5. 二分查找要求顺序存储且关键字有序，平均查找长度约为 log2(n+1) - 1。

## 二、应用题
1. 给定先序序列 ABDECF 与中序序列 DBEAFC，画出对应二叉树并给出后序序列。解：A 为根，左子树 DBE，右子树 FC；逐层递推可得后序序列 DEBFCA。
2. 对关键字序列 {49, 38, 65, 97, 76, 13, 27} 进行一趟快速排序（以49为枢轴）：结果为 27 38 13 49 76 97 65。
3. 已知一图的邻接矩阵，写出从顶点 v0 出发的 DFS 与 BFS 序列。

## 三、算法设计题
设计一个算法判断二叉树是否为平衡二叉树：递归计算左右子树高度，任意结点左右子树高度差超过 1 则不平衡，时间复杂度 O(n)。
""",
    "操作系统-第3章-进程管理（课件）.md": """# 第3章 进程管理

## 3.1 进程的基本概念
进程是程序在一个数据集合上运行的过程，是系统进行资源分配和调度的独立单位。进程由程序段、数据段和进程控制块 PCB 三部分组成。PCB 是进程存在的唯一标志。
进程的三种基本状态：就绪（已获得除 CPU 外的所有资源）、运行（占有 CPU）、阻塞（等待某事件发生）。五态模型增加创建态和终止态。

## 3.2 进程同步与互斥
临界资源是一次仅允许一个进程使用的资源。进程互斥指的是多个进程不能同时进入临界区访问临界资源；进程同步指多个协作进程因合作而产生的时序约束。
信号量机制：信号量 S 表示资源数目。P 操作（wait）：S 减 1，若 S<0 则进程阻塞入等待队列；V 操作（signal）：S 加 1，若 S≤0 则唤醒一个等待进程。
经典同步问题：生产者-消费者问题需要 3 个信号量：互斥访问缓冲区的 mutex=1、空缓冲区 empty=n、满缓冲区 full=0。读者-写者问题、哲学家进餐问题同理分析。
管程是代表共享资源的数据结构以及由对该共享数据结构实施操作的一组过程所组成的资源管理程序，可保证进程互斥。

## 3.3 死锁
死锁产生的四个必要条件：互斥条件、请求和保持条件、不可剥夺（不可抢占）条件、循环等待条件。破坏任一条件即可预防死锁。
处理策略：预防（破坏必要条件，如资源有序分配破坏循环等待）、避免（银行家算法，系统进入安全状态才分配资源）、检测与解除（资源分配图化简、撤销进程）。
银行家算法：寻找安全序列，使每个进程都能获得最大需求并顺利完成。

## 3.4 进程调度
调度算法：先来先服务 FCFS 有利于长作业不利于短作业；短作业优先 SJF 平均等待时间最短但可能产生饥饿；时间片轮转 RR 适合交互系统；优先级调度；高响应比优先 HRRN 响应比 =（等待时间+要求服务时间）/要求服务时间，克服饥饿。
多级反馈队列调度：设置多个优先级递减、时间片递增的队列，新进程进入最高优先级队列，用完时间片降级，兼顾响应与吞吐。

## 3.5 线程
线程是进程中的一个执行实体，是被系统独立调度和分派的基本单位。线程自己不拥有系统资源，只拥有运行中必不可少的少量资源（寄存器、栈、PC），同进程内线程切换开销小，共享进程的地址空间和资源。用户级线程由用户空间库管理，内核级线程由内核直接管理。
""",
    "操作系统-内存管理（笔记）.md": """# 操作系统内存管理复习笔记

## 连续分配
单一连续分配、固定分区分配、动态分区分配。动态分区分配算法：首次适应 First Fit（从低址开始找第一个满足的空闲区，性能通常最好）、最佳适应 Best Fit（找最小的满足分区，产生大量小碎片）、最坏适应 Worst Fit、邻近适应 Next Fit。
内部碎片是分配给进程的分区内部未被利用的部分；外部碎片是分区之间难以利用的小空闲区，可用紧凑（拼接）技术解决。

## 分页与分段
分页存储：将进程地址空间分为固定大小的页，内存分为同等大小的块，页表实现页号到块号的映射。地址结构：页号 + 页内偏移。逻辑地址转物理地址：物理地址 = 块号 × 页大小 + 偏移。多级页表减少页表占用的连续内存；引入快表 TLB 加速地址变换。
分段存储：按程序逻辑单位（主程序、子程序、数据段）划分，段长可变，段表含段长和基址。分页对用户透明、一维地址；分段对用户可见、二维地址，便于共享和保护。
段页式：先分段、段内再分页，兼顾两者优点。

## 虚拟内存
虚拟内存基于局部性原理，允许进程部分装入即可运行，逻辑容量由地址字长决定。请求分页在分页基础上增加请求调页（缺页中断）和页面置换功能。
页面置换算法：最佳置换 OPT（淘汰以后最长时间不使用的页，理论最优不可实现）、先进先出 FIFO（可能出现 Belady 异常：分配页框增多缺页反而增加）、最近最久未使用 LRU（利用寄存器栈实现，性能接近 OPT 开销大）、Clock 算法/最近未用 NRU（循环扫描访问位，开销小）。
抖动（颠簸）：进程频繁缺页导致系统忙于页面调度、CPU 利用率骤降，原因是进程分配的物理块太少或工作集过大，可通过降低多道程序度缓解。

## 内存扩充技术
覆盖：程序分段装入，无需操作系统特殊支持。交换：内存紧张时将进程整体换出到对换区。
""",
}

DOC_COCO = {
    "计算机组成原理-第4章-存储系统（课件）.md": """# 第4章 存储系统

## 4.1 存储器层次结构
存储层次：寄存器 → 高速缓存 Cache → 主存 → 辅存，自上而下速度越来越慢、容量越来越大、位价越来越低。Cache-主存层次解决速度问题，主存-辅存层次解决容量问题，均基于程序访问的局部性原理（时间局部性与空间局部性）。

## 4.2 Cache 三种映射方式
直接映射：主存块只能映射到唯一的 Cache 行，行号 = 主存块号 mod Cache 行数。地址结构：标记 Tag + 行号 + 块内地址。实现简单、冲突率高。
全相联映射：主存块可映射到任意 Cache 行，标记为主存块号。灵活、冲突率低，但标记比较电路复杂、成本高，适合小容量 Cache。
组相联映射：折中方案，Cache 分组，组间直接映射、组内全相联。地址结构：标记 + 组号 + 块内地址。常见有 2 路、4 路组相联。
替换算法：随机 RAND、先进先出 FIFO、最近最少使用 LRU（最常用，命中率高）、最不经常使用 LFU。
写策略：写直达（write through，同时写 Cache 和主存，一致性好）、写回（write back，只写 Cache，替换时才写回主存，需脏位）。

## 4.3 Cache 命中率与性能
命中率 h = Nc / (Nc + Nm)，其中 Nc 为命中次数，Nm 为访问主存次数。平均访问时间 ta = h × tc + (1 - h) × tm。Cache 容量、块大小、相联度都会影响命中率。

## 4.4 虚拟存储器
虚拟存储器由主存和辅存构成，借助页表实现虚拟地址到物理地址的转换，由 MMU 硬件完成。TLB 是页表的 Cache。页面大小通常 4KB，缺页由操作系统处理。快表 TLB 命中则无需访问内存中的页表。

## 4.5 主存与 CPU 连接
SRAM 快但贵（做 Cache），DRAM 慢但密度高（做主存），需要定时刷新。存储器扩展：位扩展增加字长，字扩展增加容量。DRAM 刷新按行进行，刷新对 CPU 透明。
""",
    "计算机组成原理-指令系统与流水线（笔记）.md": """# 指令系统与流水线复习笔记

## 指令格式
指令 = 操作码 OP + 地址码。按地址码个数：零地址、一地址、二地址、三地址指令。扩展操作码技术：短操作码留出前缀给长操作码，增加指令种类。

## 寻址方式
立即寻址：操作数在指令中，最快。直接寻址：地址码给出操作数的内存地址。间接寻址：地址码指向的单元存放操作数地址，需两次访存。寄存器寻址：操作数在寄存器中，不访存。寄存器间接寻址：寄存器中存放操作数地址。相对寻址：PC + 偏移，用于转移指令与程序浮动。基址寻址面向操作系统，变址寻址面向用户处理数组。

## CISC 与 RISC
CISC 指令复杂、长度可变、访存不受限；RISC 指令精简、定长、只有 LOAD/STORE 访存、流水线友好、面向寄存器、大量使用硬布线控制器。x86 属 CISC，ARM/MIPS/RISC-V 属 RISC。

## 指令流水线
五段流水线：取指 IF、译码 ID、执行 EX、访存 MEM、写回 WB。流水线加速比趋近于段数 n，吞吐率在满流水时每周期完成一条指令。
流水线冒险：结构冒险（硬件资源冲突，如指令存储器与数据存储器分设解决）、数据冒险（后指令依赖前指令结果，用旁路/转发、暂停解决）、控制冒险（转移指令改变 PC，用分支预测、延迟槽解决）。
超标量：多条流水线并行发射多条指令；超流水：更深分段提高主频。

## 例题
一条指令执行分为取指 2ns、分析 1ns、执行 3ns，顺序执行 10 条指令需 60ns；若采用流水线且各段可并行，流水线周期为最长段时间 3ns，执行 10 条指令约需 (3+2+1) + (10-1)×3 = 33ns（视分段方式而定）。
""",
}

# --- 真实「学习资料」目录的顶层课程名 → demo 用户分配 ---
# demo1 分配：理工科核心 6 门；demo2 分配：硬件/基础 4 门；
# 剩余 2 门（大学物理下、概率论）demo1 再分；
# demo1 还会额外拥有「计算机导论」1 份轻资料。
DEMO1_FOLDERS = {"数据结构", "计算机网络", "数据库", "算法设计与分析",
                "离散数学", "面向对象编程", "大学物理下", "概率与统计",
                "计算机导论"}
DEMO2_FOLDERS = {"C++", "模拟电子线路", "电路", "计算机逻辑基础"}
# 不分配给任何人，留给后续用户上传：无需专门排除，未匹配的顶层文件夹会跳过。


SUPPORTED_EXT = SUPPORTED_EXT  # noqa: PLW0127 - 本文件使用 parser.SUPPORTED_EXT 常量校验扩展名
CATALOG_FILENAME = "materials_catalog.json"


# ----------------------------- 工具函数 -----------------------------
def _project_root() -> Path:
    """定位项目根：backend/../..（config.py 位于 backend/app/）。"""
    return Path(__file__).resolve().parents[3]


def _find_materials_dir() -> Path | None:
    """寻找项目根下的「学习资料」文件夹，找不到返回 None。"""
    p = _project_root() / "学习资料"
    if p.exists() and p.is_dir():
        return p
    # 允许部署时通过环境变量指定一个可访问的位置
    env = os.environ.get("ZHINAN_MATERIALS_DIR")
    if env:
        ep = Path(env)
        if ep.exists() and ep.is_dir():
            return ep
    return None


def _load_catalog(data_dir: str | Path) -> dict | None:
    """加载 data-processing 生成的 materials_catalog.json；找不到返回 None。
    优先用 catalog 作为「单一事实来源」驱动入库，确保与清洗方案 C 保持一致。"""
    path = Path(data_dir) / CATALOG_FILENAME
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            logger.exception("catalog.json 解析失败，降级为原始目录扫描")
    return None


def _iter_supported_files(root: Path) -> list[Path]:
    """递归 yield 所有支持扩展名的真实文件。"""
    files: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in SUPPORTED_EXT:
            files.append(p)
    # 按路径排序，确保每次入库顺序稳定
    files.sort(key=lambda x: str(x))
    return files


def _folder_of(path: Path, root: Path) -> str:
    """返回资料在「学习资料」下的顶层目录名（即课程名）。"""
    rel = path.relative_to(root)
    parts = rel.parts
    return parts[0] if parts else ""


def _copy_into_data_area(src: Path, dst_dir: Path, course_folder: str, safe_prefix: str) -> Path:
    """把 src 复制到 data_dir/uploads/<user>/<course>/，重名时追加序号防冲突。"""
    dst_course = dst_dir / safe_prefix / course_folder
    dst_course.mkdir(parents=True, exist_ok=True)
    dst = dst_course / src.name
    if dst.exists():
        stem = src.stem
        i = 1
        while True:
            cand = dst_course / f"{stem}__{i}{src.suffix}"
            if not cand.exists():
                dst = cand
                break
            i += 1
    with open(src, "rb") as fr, open(dst, "wb") as fw:
        fw.write(fr.read())
    return dst


def _make_standard_course(folder: str) -> str:
    """顶层目录名 → 标准课程名。"""
    return FOLDER_COURSE_MAP.get(folder, folder)


def seed_ddls(db: Session, user: User) -> None:
    """按用户真实入库的课程匹配生成示例 DDL。"""
    now = datetime.now()

    def _find(name_contains: str) -> Course | None:
        for c in db.query(Course).filter_by(user_id=user.id).all():
            if name_contains in (c.name or ""):
                return c
        return None

    samples = [
        ("数据结构 第6章图论作业", "教材 P163 习题 6.2、6.5，手写作答拍照上传",
         timedelta(hours=20), "high", "数据结构"),
        ("算法设计与分析：动态规划专题作业", "DP 6 道典型题，附状态转移方程说明",
         timedelta(days=4), "high", "算法设计"),
        ("操作系统 实验3：进程调度模拟", "实现 RR 与优先级调度并对比平均周转时间",
         timedelta(days=6), "high", "操作系统"),
        ("计算机网络：传输层习题", "学习通第三章作业，限时 90 分钟",
         timedelta(days=8), "medium", "计算机网络"),
        ("操作系统 小论文：内存管理技术演进", "3000字，查重率低于 15%",
         timedelta(days=14), "low", "操作系统"),
        ("大学物理（下）：电磁感应章习题", "习题册 11.5、11.7、11.12",
         timedelta(days=10), "medium", "大学物理"),
        ("离散数学 小测（第5章代数系统）", "线下闭卷小测，1小时",
         timedelta(days=3), "high", "离散数学"),
        ("小组展示：图算法在导航中的应用", "PPT + 10 分钟讲解",
         timedelta(days=20), "low", "数据结构"),
    ]
    for title, detail, delta, pri, contains in samples:
        course = _find(contains)
        db.add(DDL(user_id=user.id,
                   course_id=course.id if course else None,
                   title=title, detail=detail,
                   due_at=now + delta,
                   priority=pri,
                   source="seed"))
    db.commit()


# ----------------------------- 主入口 -----------------------------
async def _ingest_from_catalog(db: Session, user: User, catalog: dict, scope: str,
                               scope_prefix: str, data_dir: Path,
                               max_per_user: int | None = None) -> int:
    """优先按 materials_catalog.json 驱动入库：catalog 已是方案C处理后的单一事实来源。
    返回成功入库的文件数。"""
    uploads_dir = Path(data_dir) / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    user_node = catalog.get(scope) or {}
    courses: dict = user_node.get("courses") or {}
    entries: list[tuple[str, dict]] = []  # (course, entry)
    for course_name, items in courses.items():
        for it in items:
            entries.append((course_name, it))
    # 保持稳定顺序：按课程名 + relative_path
    entries.sort(key=lambda t: (t[0], t[1].get("relative_path", "")))

    succeeded = failed = 0
    for course_name, it in entries:
        if max_per_user and succeeded >= max_per_user:
            break
        src_path = it.get("path") or it.get("full_path") or ""
        filename = it.get("filename") or Path(src_path).name
        parse_mode = it.get("parse_mode") or "full"
        if not src_path or not os.path.exists(src_path):
            logger.warning("catalog 条目文件不存在，已跳过：%s", src_path)
            failed += 1
            continue
        # skip blocked 扩展
        if Path(filename).suffix.lower() not in SUPPORTED_EXT:
            logger.warning("catalog 条目扩展名不在 parser 支持列表中，跳过：%s", filename)
            failed += 1
            continue
        try:
            dst = _copy_into_data_area(Path(src_path), uploads_dir, course_name, scope_prefix)
            await ingest_file(db, user.id, str(dst), filename,
                              forced_course_name=course_name,
                              forced_doc_type=it.get("doc_type"),
                              original_source_path=Path(src_path))
            db.commit()
            succeeded += 1
            if succeeded % 10 == 0:
                logger.info("[%s] 已入库 %d …", scope, succeeded)
        except Exception as exc:  # noqa: BLE001
            # 方案 C 最终兜底：即使 parser/ingest 都失败，至少以 files 行写入元数据，保证 catalog 里每份条目都在 DB 中有记录
            logger.warning("catalog 资料 ingest 主流程失败，执行最终兜底写 files 表：%s → %s",
                           filename, exc)
            try:
                from sqlalchemy import text as sqla_text  # noqa: F401 - keep imports local
                content_text = (
                    f"【数据库级兜底占位条目】文件名：{filename}\n"
                    f"所属课程：{course_name}\n"
                    f"资料类型：{it.get('doc_type') or '学习资料'}\n"
                    f"原始文件路径：{src_path}\n"
                    f"入库失败原因：{exc!s}"
                )
                course_obj = get_or_create_course(db, user.id, course_name)
                size = os.path.getsize(src_path) if os.path.exists(src_path) else 0
                from ..models import DocumentFile  # re-imported for robustness
                row = DocumentFile(
                    user_id=user.id,
                    course_id=course_obj.id if course_obj else None,
                    filename=filename,
                    file_type=Path(filename).suffix.lower().lstrip("."),
                    size=size,
                    stored_path=str(dst),
                    content=content_text,
                    outline="[]",
                    tags=json.dumps({
                        "course": course_name,
                        "type": it.get("doc_type") or "学习资料",
                        "keywords": [], "sections": [],
                    }, ensure_ascii=False),
                    status="metadata_only",
                    chunk_count=0,
                )
                db.add(row)
                db.commit()
                succeeded += 1
            except Exception as exc2:  # noqa: BLE001
                failed += 1
                logger.warning("catalog 资料兜底入库也失败，已跳过：%s | %s", filename, exc2)
    logger.info("用户 %s 基于 catalog 入库：成功 %d 份，跳过 %d 份",
                user.username, succeeded, failed)
    return succeeded


async def _ingest_folder(db: Session, user: User, materials_dir: Path,
                         scope_folders: set[str], scope_prefix: str,
                         data_dir: Path,
                         max_per_user: int | None = None) -> int:
    """把 materials_dir 下属于 scope_folders 的文件，拷贝一份到 data/uploads/<scope_prefix>/，
    然后走 ingest_file 入库。返回成功入库的文件数。"""
    uploads_dir = Path(data_dir) / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    succeeded, failed = 0, 0
    src_files = _iter_supported_files(materials_dir)
    for src in src_files:
        folder = _folder_of(src, materials_dir)
        if folder not in scope_folders:
            continue
        if max_per_user and succeeded >= max_per_user:
            break
        try:
            course_folder = folder  # 用课程顶层目录作为 dst 子目录
            dst = _copy_into_data_area(src, uploads_dir, course_folder, scope_prefix)
            await ingest_file(db, user.id, str(dst), src.name,
                              original_source_path=str(src))
            db.commit()
            succeeded += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            logger.warning("种子资料入库失败（已跳过）：%s → %s", src.name, exc)
    logger.info("用户 %s 真实资料入库：成功 %d 份，跳过 %d 份", user.username, succeeded, failed)
    return succeeded


async def _seed_fallback_md(db: Session, user: User, docs: dict[str, str],
                            scope_prefix: str, data_dir: Path) -> None:
    """fallback：把写死的 markdown 内容写到文件，再走 ingest。"""
    seed_dir = Path(data_dir) / "seed_files" / scope_prefix
    seed_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in docs.items():
        path = seed_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        try:
            await ingest_file(db, user.id, str(path), filename)
        except Exception:  # noqa: BLE001
            logger.exception("回退 md 资料入库失败: %s", filename)


async def seed_if_empty(db: Session, data_dir: str | None = None) -> None:
    if db.query(User).filter_by(username="demo1").first():
        return
    data_dir = data_dir or settings.data_dir
    materials_dir = _find_materials_dir()
    catalog = _load_catalog(data_dir)

    logger.info("初始化预置测试账号与演示数据 …")
    if catalog is not None:
        meta = catalog.get("_meta", {})
        logger.info("检测到清洗后的 catalog.json：共 %d 门课程，%d 份文件（扫描于 %s）",
                    meta.get("total_courses", 0), meta.get("total_files", 0),
                    meta.get("scanned_at", ""))
        logger.info("  parse_mode 分布：%s", meta.get("parse_mode_distribution", {}))
    elif materials_dir is not None:
        logger.info("未检测到 catalog.json，将按真实知识库目录扫描：%s", materials_dir)
    else:
        logger.warning("未找到 catalog.json 与「学习资料」目录，将使用内置 markdown 演示资料作为回退。")

    for acc in TEST_ACCOUNTS:
        user = User(username=acc["username"],
                    password_hash=hash_password(acc["password"]),
                    nickname=acc["nickname"],
                    email=acc["email"])
        db.add(user)
        db.commit()

        scope = acc["seed_scope"]

        # 优先级：catalog → 目录扫描 → markdown 回退
        if catalog is not None and scope:
            await _ingest_from_catalog(db, user, catalog, scope=scope,
                                       scope_prefix=acc["username"],
                                       data_dir=Path(data_dir),
                                       max_per_user=None)
        else:
            folder_set: set[str] = set()
            if scope == "demo1":
                folder_set = DEMO1_FOLDERS
            elif scope == "demo2":
                folder_set = DEMO2_FOLDERS
            if materials_dir is not None and folder_set:
                await _ingest_folder(db, user, materials_dir, folder_set,
                                     scope_prefix=acc["username"],
                                     data_dir=Path(data_dir),
                                     max_per_user=80)
            else:
                md_map = DOC_MAIN if scope == "demo1" else DOC_COCO if scope == "demo2" else {}
                if md_map:
                    await _seed_fallback_md(db, user, md_map, scope_prefix=acc["username"],
                                           data_dir=data_dir)
        if scope == "demo1":
            seed_ddls(db, user)

    logger.info("演示数据初始化完成：demo1/demo2/demo3（密码均为 echo123456）。")


def run_seed(session_factory, data_dir: str | None = None) -> None:
    db = session_factory()
    try:
        asyncio.run(seed_if_empty(db, data_dir))
    finally:
        db.close()
