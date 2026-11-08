package com.mcbookwriter.autobook.job;

/**
 * BookForge 安装 job 时写入的任务元数据，对应 autobook/jobs/&lt;任务名&gt;.meta.json（schema v1）。
 *
 * <p>未知字段由 Gson 自动忽略；元数据只用于展示，不参与真正的 job 校验。</p>
 */
public class JobMeta {
    public int schema;
    public String titleBase = "";
    public int bookCount;
    public int totalPages;
    public int pageLimit;
    public boolean reviewed;
    public boolean llmApplied;
    public String sourceHash = "";
    public String generatedAt = "";
    public String generatorVersion = "";

    public void ensureDefaults() {
        if (titleBase == null) {
            titleBase = "";
        }
        if (sourceHash == null) {
            sourceHash = "";
        }
        if (generatedAt == null) {
            generatedAt = "";
        }
        if (generatorVersion == null) {
            generatorVersion = "";
        }
    }
}
