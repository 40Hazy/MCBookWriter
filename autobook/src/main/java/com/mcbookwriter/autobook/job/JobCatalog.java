package com.mcbookwriter.autobook.job;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.mcbookwriter.autobook.AutoBookPaths;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Stream;

/**
 * 列出 autobook/jobs/ 下的任务并读取可选的 meta.json。
 *
 * <p>meta 缺失、损坏或 schema 不为 1 时忽略元数据，回退到直接读取 job；
 * job 本身损坏时仍返回条目，便于命令行提示错误。</p>
 */
public final class JobCatalog {
    private static final Gson GSON = new Gson();
    private static final int META_SCHEMA = 1;
    private static final String JOB_SUFFIX = ".json";
    private static final String META_SUFFIX = ".meta.json";

    private final Path jobsDir;

    public JobCatalog(Path jobsDir) {
        this.jobsDir = jobsDir;
    }

    public static JobCatalog defaultCatalog() {
        return new JobCatalog(AutoBookPaths.jobsDir());
    }

    public Path jobsDir() {
        return jobsDir;
    }

    public List<InstalledJob> list() {
        if (!Files.isDirectory(jobsDir)) {
            return List.of();
        }
        List<Path> files;
        try (Stream<Path> stream = Files.list(jobsDir)) {
            files = stream
                .filter(Files::isRegularFile)
                .filter(JobCatalog::isJobFile)
                .sorted(Comparator.comparing(path -> path.getFileName().toString()))
                .toList();
        } catch (IOException error) {
            return List.of();
        }
        List<InstalledJob> jobs = new ArrayList<>(files.size());
        for (Path file : files) {
            jobs.add(read(file));
        }
        return jobs;
    }

    private static boolean isJobFile(Path path) {
        String name = path.getFileName().toString();
        return name.endsWith(JOB_SUFFIX) && !name.endsWith(META_SUFFIX);
    }

    private InstalledJob read(Path file) {
        InstalledJob installed = new InstalledJob();
        String fileName = file.getFileName().toString();
        installed.name = fileName.substring(0, fileName.length() - JOB_SUFFIX.length());
        installed.updatedAt = modified(file);
        installed.meta = readMeta(file);

        try {
            JsonObject job = readObject(file);
            int version = integer(job, "version", 0);
            if (version != 1) {
                throw new IOException("不支持的 job version: " + version);
            }
            installed.titleBase = string(job, "titleBase", installed.name);
            installed.pageLimit = integer(job, "pageLimit", 0);
            JsonObject options = object(job, "options");
            if (options != null) {
                installed.llmApplied = bool(options, "llmApplied", false);
            }
            JsonElement segments = job.get("segments");
            installed.segmentCount = segments != null && segments.isJsonArray()
                ? segments.getAsJsonArray().size()
                : 0;
        } catch (IOException | RuntimeException error) {
            installed.error = message(error);
        }
        return installed;
    }

    private JobMeta readMeta(Path jobFile) {
        String fileName = jobFile.getFileName().toString();
        Path metaPath = jobFile.resolveSibling(
            fileName.substring(0, fileName.length() - JOB_SUFFIX.length()) + META_SUFFIX
        );
        if (!Files.isRegularFile(metaPath)) {
            return null;
        }
        try {
            JsonObject root = readObject(metaPath);
            if (integer(root, "schema", 0) != META_SCHEMA) {
                return null;
            }
            JobMeta meta = GSON.fromJson(root, JobMeta.class);
            if (meta == null) {
                return null;
            }
            meta.ensureDefaults();
            return meta;
        } catch (IOException | RuntimeException error) {
            return null;
        }
    }

    private static JsonObject readObject(Path path) throws IOException {
        String text = Files.readString(path, StandardCharsets.UTF_8);
        JsonElement element = JsonParser.parseString(text);
        if (!element.isJsonObject()) {
            throw new IOException("JSON 根节点不是对象: " + path.getFileName());
        }
        return element.getAsJsonObject();
    }

    private static String modified(Path path) {
        try {
            return OffsetDateTime.ofInstant(
                Files.getLastModifiedTime(path).toInstant(),
                ZoneId.systemDefault()
            ).toString();
        } catch (IOException error) {
            return "";
        }
    }

    private static JsonObject object(JsonObject parent, String key) {
        JsonElement value = parent.get(key);
        return value != null && value.isJsonObject() ? value.getAsJsonObject() : null;
    }

    private static String string(JsonObject object, String key, String fallback) {
        JsonElement value = object.get(key);
        return value == null || value.isJsonNull() ? fallback : value.getAsString();
    }

    private static int integer(JsonObject object, String key, int fallback) {
        JsonElement value = object.get(key);
        if (value == null || value.isJsonNull()) {
            return fallback;
        }
        try {
            return value.getAsInt();
        } catch (NumberFormatException | IllegalStateException error) {
            return fallback;
        }
    }

    private static boolean bool(JsonObject object, String key, boolean fallback) {
        JsonElement value = object.get(key);
        if (value == null || value.isJsonNull()) {
            return fallback;
        }
        try {
            return value.getAsBoolean();
        } catch (IllegalStateException error) {
            return fallback;
        }
    }

    private static String message(Throwable error) {
        String text = error.getMessage();
        return text == null || text.isBlank() ? error.getClass().getSimpleName() : text;
    }
}
