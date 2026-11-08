package com.mcbookwriter.autobook.job;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class JobCatalogTest {
    @TempDir
    Path tempDir;

    @Test
    void listsJobWithMeta() throws Exception {
        Path jobs = jobsDir();
        Files.writeString(jobs.resolve("三体1.json"), jobJson("三体1", 100, true, 36), StandardCharsets.UTF_8);
        Files.writeString(jobs.resolve("三体1.meta.json"), metaJson(1, "三体1", 13, 1195), StandardCharsets.UTF_8);

        List<InstalledJob> list = new JobCatalog(jobs).list();

        assertEquals(1, list.size());
        InstalledJob job = list.get(0);
        assertEquals("三体1", job.name);
        assertEquals("三体1", job.titleBase);
        assertEquals(100, job.pageLimit);
        assertEquals(36, job.segmentCount);
        assertTrue(job.llmApplied);
        assertEquals("", job.error);
        assertNotNull(job.meta);
        assertEquals(13, job.meta.bookCount);
        assertEquals(1195, job.meta.totalPages);
        assertTrue(job.meta.reviewed);
        assertEquals("0.7.0", job.meta.generatorVersion);
    }

    @Test
    void fallsBackToJobWhenMetaMissingOrInvalid() throws Exception {
        Path jobs = jobsDir();
        Files.writeString(jobs.resolve("三体2.json"), jobJson("三体2", 80, true, 2), StandardCharsets.UTF_8);

        InstalledJob noMeta = new JobCatalog(jobs).list().get(0);
        assertNull(noMeta.meta);
        assertEquals("三体2", noMeta.titleBase);
        assertEquals(80, noMeta.pageLimit);
        assertTrue(noMeta.llmApplied);
        assertEquals(2, noMeta.segmentCount);

        Files.writeString(jobs.resolve("三体2.meta.json"), metaJson(2, "三体2", 1, 1), StandardCharsets.UTF_8);
        assertNull(new JobCatalog(jobs).list().get(0).meta);

        Files.writeString(jobs.resolve("三体2.meta.json"), "{not json", StandardCharsets.UTF_8);
        assertNull(new JobCatalog(jobs).list().get(0).meta);

        Files.writeString(
            jobs.resolve("三体2.meta.json"),
            "{\"schema\":1,\"unknown\":{\"ignored\":true}}",
            StandardCharsets.UTF_8
        );
        JobMeta partial = new JobCatalog(jobs).list().get(0).meta;
        assertNotNull(partial);
        assertEquals("", partial.titleBase);
        assertEquals(0, partial.bookCount);
    }

    @Test
    void flagsBrokenOrUnsupportedJob() throws Exception {
        Path jobs = jobsDir();
        Files.writeString(jobs.resolve("broken.json"), "{not json", StandardCharsets.UTF_8);
        Files.writeString(
            jobs.resolve("unsupported.json"),
            jobJson("unsupported", 100, false, 1).replace("\"version\":1", "\"version\":2"),
            StandardCharsets.UTF_8
        );

        List<InstalledJob> list = new JobCatalog(jobs).list();

        assertEquals(2, list.size());
        assertFalse(list.get(0).error.isBlank());
        assertFalse(list.get(1).error.isBlank());
        assertTrue(list.get(1).error.contains("version"));
    }

    @Test
    void ignoresMetaFilesAndMissingDirectory() throws Exception {
        Path jobs = jobsDir();
        Files.writeString(jobs.resolve("三体1.meta.json"), metaJson(1, "三体1", 1, 1), StandardCharsets.UTF_8);

        assertTrue(new JobCatalog(jobs).list().isEmpty());
        assertTrue(new JobCatalog(tempDir.resolve("missing")).list().isEmpty());
    }

    private Path jobsDir() throws Exception {
        Path jobs = tempDir.resolve("jobs");
        Files.createDirectories(jobs);
        return jobs;
    }

    private static String jobJson(String title, int pageLimit, boolean llmApplied, int segments) {
        StringBuilder segmentJson = new StringBuilder();
        for (int index = 1; index <= segments; index++) {
            if (index > 1) {
                segmentJson.append(',');
            }
            segmentJson.append("{\"index\":").append(index).append(",\"text\":\"正文\"}");
        }
        return "{\"version\":1,\"titleBase\":\"" + title + "\",\"pageLimit\":" + pageLimit
            + ",\"sourceHash\":\"" + "a".repeat(64) + "\""
            + ",\"options\":{\"llmApplied\":" + llmApplied + "}"
            + ",\"segments\":[" + segmentJson + "]}";
    }

    private static String metaJson(int schema, String title, int books, int pages) {
        return "{\"schema\":" + schema + ",\"titleBase\":\"" + title + "\""
            + ",\"bookCount\":" + books + ",\"totalPages\":" + pages
            + ",\"pageLimit\":100,\"reviewed\":true,\"llmApplied\":true"
            + ",\"sourceHash\":\"" + "a".repeat(64) + "\""
            + ",\"generatedAt\":\"2026-01-01T00:00:00+00:00\",\"generatorVersion\":\"0.7.0\"}";
    }
}
