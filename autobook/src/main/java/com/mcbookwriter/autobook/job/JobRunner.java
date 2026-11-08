package com.mcbookwriter.autobook.job;

import com.mcbookwriter.autobook.config.AutoBookConfig;
import com.mcbookwriter.autobook.layout.BookPlanner;
import com.mcbookwriter.autobook.layout.MinecraftWidthProvider;
import com.mcbookwriter.autobook.layout.PlannedBook;
import com.mcbookwriter.autobook.writer.BookWriter;
import net.minecraft.client.Minecraft;

import java.io.IOException;
import java.util.List;

public final class JobRunner {
    private JobRunner() {
    }

    public record Settings(int pageLimit, boolean breakAtSentence, Boolean verifyContent) {
    }

    public record Prepared(JobManifest job, Settings settings, List<PlannedBook> books) {
    }

    public static Prepared prepare(String jobName) throws IOException {
        JobManifest job = JobLoader.load(jobName);
        AutoBookConfig config = AutoBookConfig.get();
        Settings settings = resolveSettings(job, config);
        List<PlannedBook> books = BookPlanner.plan(
            job,
            new MinecraftWidthProvider(Minecraft.getInstance().font),
            settings.pageLimit(),
            settings.breakAtSentence()
        );
        return new Prepared(job, settings, books);
    }

    public static void start(String jobName, boolean resume) throws IOException {
        Prepared prepared = prepare(jobName);
        if (prepared.books().isEmpty()) {
            throw new IllegalArgumentException("计划为空");
        }
        BookWriter.get().start(
            jobName,
            prepared.job().sourceHash,
            prepared.books(),
            resume,
            prepared.settings().verifyContent()
        );
    }

    public static Settings resolveSettings(JobManifest job, AutoBookConfig config) {
        int pageLimit = config.pageLimit;
        boolean breakAtSentence = config.breakAtSentence;
        Boolean verifyContent = null;

        if (job.options != null) {
            if (job.options.pageLimit != null) {
                pageLimit = job.options.pageLimit;
            }
            if (job.options.breakAtSentence != null) {
                breakAtSentence = job.options.breakAtSentence;
            }
            if (job.options.verifyContent != null) {
                verifyContent = job.options.verifyContent;
            }
        }
        return new Settings(pageLimit, breakAtSentence, verifyContent);
    }

    public static int effectiveLimit(JobManifest job, Settings settings) {
        int limit = settings.pageLimit() > 0 ? settings.pageLimit() : job.pageLimit;
        return Math.max(1, Math.min(100, limit));
    }
}
