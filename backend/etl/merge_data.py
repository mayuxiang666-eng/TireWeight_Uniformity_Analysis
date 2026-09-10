import os
import shutil
import datetime
import pyarrow as pa
import pyarrow.parquet as pq

# 默认滚动保留窗口（天）
DEFAULT_RETENTION_DAYS = 31

# PyArrow 流式读取批次大小（行数）——控制单批内存峰值
BATCH_SIZE = 50000


def get_data_dir():
    etl_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(etl_dir)
    candidates = [
        os.path.join(root_dir, "backend", "data"),
        os.path.join(etl_dir, "data"),
        os.path.join(os.getcwd(), "backend", "data"),
        os.path.join(root_dir, "data"),
        os.path.join(os.getcwd(), "data"),
    ]
    for p in candidates:
        p_abs = os.path.abspath(p)
        if os.path.exists(os.path.join(p_abs, "yield_flat_table_joined_100.parquet")) or \
           os.path.exists(os.path.join(p_abs, "yield_flat_table_joined_100_cleaned.parquet")):
            return p_abs
    target = os.path.abspath(os.path.join(root_dir, "backend", "data"))
    os.makedirs(target, exist_ok=True)
    return target


def _build_inc_barcode_set(inc_table: pa.Table) -> set:
    """从增量 Arrow Table 中提取所有非空 barcode 字符串集合（用于去重过滤）"""
    if "barcode" not in inc_table.schema.names:
        return set()
    bc_col = inc_table.column("barcode")
    bc_set = set()
    for val in bc_col.to_pylist():
        if val is not None:
            bc_set.add(str(val))
    return bc_set


def _apply_cutoff(table: pa.Table, cutoff_date: str) -> pa.Table:
    """
    按时间窗口裁剪：保留 tu_first_loc_timestamp IS NULL 或 >= cutoff_date 的行。
    纯 PyArrow compute 操作，无需 pandas 转换。
    """
    import pyarrow.compute as pc

    if "tu_first_loc_timestamp" not in table.schema.names:
        return table

    ts_col = table.column("tu_first_loc_timestamp")
    cutoff_ts = pa.scalar(datetime.datetime.strptime(cutoff_date, "%Y-%m-%d"), type=pa.timestamp("s"))

    # 尝试 cast 到 timestamp，无法转换的变为 null
    try:
        ts_cast = pc.cast(ts_col, pa.timestamp("s"), safe=False)
    except Exception:
        try:
            import pandas as pd
            ts_series = pd.to_datetime(table.column("tu_first_loc_timestamp").to_pandas(), errors="coerce")
            ts_cast = pa.array(ts_series, type=pa.timestamp("s"))
        except Exception:
            return table  # 无法处理时原样保留

    is_null_mask   = pc.is_null(ts_cast)
    is_gte_mask    = pc.greater_equal(ts_cast, cutoff_ts)
    keep_mask      = pc.or_(is_null_mask, is_gte_mask)

    return table.filter(keep_mask)


def _filter_base_batch(batch: pa.RecordBatch, inc_barcodes: set, cutoff_date: str) -> pa.Table:
    """
    过滤一个 base batch：
    1. 排除 barcode 在 inc_barcodes 集合中的行（已在增量中被新版覆盖）
    2. 按 cutoff_date 裁剪滚动窗口
    """
    import pyarrow.compute as pc

    table = pa.Table.from_batches([batch])

    # 1. 去除增量中已有的 barcode（barcode 不在集合中，或 barcode 为 null 的行保留）
    if inc_barcodes and "barcode" in table.schema.names:
        bc_col = table.column("barcode")
        # 逐行判断是否 NOT IN inc_barcodes
        keep_flags = []
        for val in bc_col.to_pylist():
            if val is None:
                keep_flags.append(True)   # null barcode 保留
            else:
                keep_flags.append(str(val) not in inc_barcodes)
        keep_mask = pa.array(keep_flags, type=pa.bool_())
        table = table.filter(keep_mask)

    if len(table) == 0:
        return table

    # 2. 时间窗口裁剪
    table = _apply_cutoff(table, cutoff_date)
    return table


def merge_main(
    base_parquet: str = None,
    incremental_parquet: str = None,
    new_watermark: str = None,
    retention_days: int = DEFAULT_RETENTION_DAYS
) -> bool:
    data_dir = get_data_dir()

    if base_parquet is None:
        base_parquet = os.path.join(data_dir, "yield_flat_table_joined_100.parquet")
    if incremental_parquet is None:
        incremental_parquet = os.path.join(data_dir, "yield_incremental.parquet.tmp")

    # --- 检查增量文件 ---
    if not os.path.exists(incremental_parquet):
        print(f"[Merge] 未找到增量文件: {incremental_parquet}，跳过合并。")
        return True

    # --- 滚动窗口裁剪日期 ---
    cutoff_date = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=retention_days)
    ).strftime("%Y-%m-%d")

    print(f"\n--- 合并阶段: PyArrow 流式低内存合并 ---")

    # Step 1：读取增量文件（16 MB 左右，完全加载进内存）
    try:
        inc_table = pq.read_table(incremental_parquet)
        inc_count = len(inc_table)
        print(f"  增量数据: {inc_count:,} 行，已加载至内存")
    except Exception as e:
        print(f"[Merge Error] 读取增量 Parquet 失败: {e}")
        return False

    # Step 2：提取增量 barcode 集合（用于 base 去重过滤，仅存字符串，约 5 MB）
    inc_barcodes = _build_inc_barcode_set(inc_table)
    print(f"  增量唯一 barcode 数: {len(inc_barcodes):,}（hash set 约 {len(inc_barcodes)*50//1024//1024:.0f} MB）")

    # Step 3：对增量本身做时间窗口裁剪
    inc_table = _apply_cutoff(inc_table, cutoff_date)
    print(f"  增量数据裁剪后: {len(inc_table):,} 行（滚动窗口截止 {cutoff_date}）")

    base_exists = os.path.exists(base_parquet)
    if base_exists:
        try:
            pf = pq.ParquetFile(base_parquet)
            base_row_groups = pf.metadata.num_row_groups
            print(f"  本地已有数据: {pf.metadata.num_rows:,} 行，{base_row_groups} 个 Row Group")
        except Exception as e:
            print(f"[Merge Warning] 读取本地 Parquet 元数据失败，将以增量数据作为全量基础: {e}")
            base_exists = False
    else:
        print("  本地 Parquet 不存在，将以增量数据作为全量基础。")

    print(f"  滚动窗口: 保留最近 {retention_days} 天（截止 {cutoff_date}）")

    # --- Step 4：流式写出合并结果 ---
    os.makedirs(os.path.dirname(base_parquet), exist_ok=True)
    tmp_out = base_parquet + ".merging.tmp"

    # 清理上次崩溃遗留的 tmp 文件
    if os.path.exists(tmp_out):
        try:
            os.remove(tmp_out)
            print(f"  [Cleanup] 已清理上次遗留的临时文件: {tmp_out}")
        except Exception:
            pass

    writer = None
    total_written = 0

    try:
        print(f"\n--- 合并阶段: PyArrow 流式写回主 Parquet ---")

        # Step 4a：先写入增量数据（新版本优先）
        if len(inc_table) > 0:
            schema = inc_table.schema
            writer = pq.ParquetWriter(tmp_out, schema, compression="snappy")
            writer.write_table(inc_table)
            total_written += len(inc_table)
            print(f"  已写入增量数据: {len(inc_table):,} 行")
            del inc_table  # 及时释放

        # Step 4b：流式处理 base 数据，每批 BATCH_SIZE 行
        if base_exists:
            batch_idx = 0
            for batch in pf.iter_batches(batch_size=BATCH_SIZE):
                filtered = _filter_base_batch(batch, inc_barcodes, cutoff_date)
                if len(filtered) == 0:
                    batch_idx += 1
                    continue

                # 如果 writer 还未初始化（纯 base 模式）
                if writer is None:
                    writer = pq.ParquetWriter(tmp_out, filtered.schema, compression="snappy")

                writer.write_table(filtered)
                total_written += len(filtered)
                batch_idx += 1
                if batch_idx % 10 == 0:
                    print(f"  已处理 base 数据 {batch_idx} 批，累计写入: {total_written:,} 行...")

            print(f"  base 数据处理完成，共 {batch_idx} 批")

    except Exception as e:
        print(f"[Merge Error] PyArrow 流式写回 Parquet 失败: {e}")
        import traceback
        traceback.print_exc()
        if writer:
            try:
                writer.close()
            except Exception:
                pass
        if os.path.exists(tmp_out):
            os.remove(tmp_out)
        return False
    finally:
        if writer:
            try:
                writer.close()
            except Exception:
                pass

    # --- Step 5：原子替换（Windows 兼容：后端 DuckDB 持有读取句柄时 os.replace 会拒绝，降级 copy2）---
    if not os.path.exists(tmp_out) or total_written == 0:
        print(f"[Merge Warning] 合并结果为空或临时文件丢失，跳过替换。")
        return False

    replaced = False
    last_err = None
    for attempt in range(1, 4):
        try:
            os.replace(tmp_out, base_parquet)
            replaced = True
            break
        except PermissionError as pe:
            last_err = pe
            if attempt == 1:
                print(f"  [Replace] os.replace 被 Windows 文件锁拒绝，尝试 copy2 覆盖写入...")
            try:
                # shutil.copy2 在共享读锁下可成功覆盖内容
                shutil.copy2(tmp_out, base_parquet)
                os.remove(tmp_out)
                replaced = True
                break
            except Exception as ce:
                import time
                print(f"  [Replace] copy2 第 {attempt} 次失败 ({ce})，{2}s 后重试...")
                time.sleep(2)

    if not replaced:
        print(f"[Merge Error] 无法替换主 Parquet 文件，文件被锁定: {last_err}")
        print(f"  合并结果已保存至临时文件: {tmp_out}")
        print(f"  请关闭后端服务后手动执行替换，或重新运行 ETL。")
        return False

    print(f"  [Success] PyArrow 流式写回完成: {base_parquet}（{total_written:,} 行）")


    # --- Step 6：同步镜像到备用 data/ 目录 ---
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for alt_dir in [os.path.join(root_dir, "data"), os.path.join(root_dir, "backend", "data")]:
        if os.path.isdir(alt_dir) and os.path.abspath(alt_dir) != os.path.abspath(os.path.dirname(base_parquet)):
            try:
                alt_output = os.path.join(alt_dir, os.path.basename(base_parquet))
                shutil.copy2(base_parquet, alt_output)
                print(f"  [Mirror] 同步基表镜像至: {alt_output}")
            except Exception:
                pass

    # --- Step 7：清理增量临时文件 ---
    try:
        os.remove(incremental_parquet)
        print(f"  已删除增量临时文件: {incremental_parquet}")
    except Exception as e:
        print(f"[Merge Warning] 删除增量临时文件失败（可忽略）: {e}")

    return True


if __name__ == "__main__":
    merge_main()
