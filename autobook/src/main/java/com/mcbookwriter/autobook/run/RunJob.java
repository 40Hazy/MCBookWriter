package com.mcbookwriter.autobook.run;

/**
 * 运行中的一个书本任务，对应 autobook/jobs/ 下的一个 job.json。
 */
public class RunJob {
    public String name = "";
    public String status = RunState.JOB_PENDING;
    public int nextIndex;
    public int completedBooks;
    public int totalBooks;
    public int totalPages;
    public int verifiedBooks;
    public String planHash = "";
    public String error = "";
    public String addedAt = "";
    public String startedAt = "";
    public String finishedAt = "";
}
