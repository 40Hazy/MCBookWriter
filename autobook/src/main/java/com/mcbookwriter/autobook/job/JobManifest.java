package com.mcbookwriter.autobook.job;

import java.util.List;

public class JobManifest {
    public int version;
    public String titleBase;
    public int pageLimit;
    public String sourceHash;
    public JobOptions options;
    public List<JobSegment> segments;
}
