package com.mcbookwriter.autobook.job;

import com.google.gson.Gson;
import com.mcbookwriter.autobook.AutoBookPaths;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

public final class JobLoader {
    private static final Gson GSON = new Gson();

    private JobLoader() {
    }

    public static JobManifest load(String name) throws IOException {
        Path jobsDir = AutoBookPaths.jobsDir();
        String fileName = name.endsWith(".json") ? name : name + ".json";
        Path path = jobsDir.resolve(fileName).normalize();

        if (!path.startsWith(jobsDir)) {
            throw new IOException("Invalid job path: " + name);
        }
        if (!Files.isRegularFile(path)) {
            throw new IOException("Job not found: " + path);
        }

        JobManifest job = GSON.fromJson(Files.readString(path, StandardCharsets.UTF_8), JobManifest.class);
        validate(job);
        return job;
    }

    private static void validate(JobManifest job) {
        if (job == null) {
            throw new IllegalArgumentException("Job file is empty");
        }
        if (job.version != 1) {
            throw new IllegalArgumentException("Unsupported job version: " + job.version);
        }
        if (job.titleBase == null || job.titleBase.isBlank()) {
            throw new IllegalArgumentException("titleBase is missing");
        }
        if (job.pageLimit < 1 || job.pageLimit > 100) {
            throw new IllegalArgumentException("pageLimit must be between 1 and 100");
        }
        if (job.segments == null || job.segments.isEmpty()) {
            throw new IllegalArgumentException("segments is empty");
        }
        for (JobSegment segment : job.segments) {
            if (segment.text == null || segment.text.isBlank()) {
                throw new IllegalArgumentException("segment " + segment.index + " has no text");
            }
        }
    }
}
