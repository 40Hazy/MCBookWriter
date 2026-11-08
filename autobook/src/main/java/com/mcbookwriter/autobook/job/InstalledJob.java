package com.mcbookwriter.autobook.job;

/**
 * autobook/jobs/ 下的一个已安装任务。meta 可能为空（旧版 BookForge 安装）。
 */
public class InstalledJob {
    public String name = "";
    public String titleBase = "";
    public int pageLimit;
    public int segmentCount;
    public boolean llmApplied;
    public JobMeta meta;
    public String error = "";
    public String updatedAt = "";
}
