package com.mcbookwriter.autobook.run;

/**
 * 写给 BookForge 只读消费的运行状态快照，对应 autobook/status.json（schema v1）。
 */
public class StatusSnapshot {
    public int schema = 1;
    public String runStatus = "";
    public String currentJob = "";
    public int nextIndex;
    public int completedBooks;
    public int totalBooks;
    public int verifiedBooks;
    public String reason = "";
    public String updatedAt = "";
    public String autoBookVersion = "";
}
