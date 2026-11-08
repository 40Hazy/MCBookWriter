package com.mcbookwriter.autobook.progress;

public class RunState {
    public int version = 1;
    public String jobName;
    public String sourceHash;
    public String planHash;
    public int nextIndex;
    public int completedBooks;
    public int totalBooks;
    public int totalPages;
    public int verifiedBooks;
    public boolean forceRewrite;
    public String updatedAt;
}
