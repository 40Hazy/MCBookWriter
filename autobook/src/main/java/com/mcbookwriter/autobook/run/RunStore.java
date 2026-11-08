package com.mcbookwriter.autobook.run;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParseException;
import com.google.gson.JsonParser;
import com.mcbookwriter.autobook.AutoBookPaths;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.OffsetDateTime;

/**
 * 运行状态的读写。run.json 不存在但存在旧 queue.json 时，自动迁移一次。
 */
public final class RunStore {
    private static final Logger LOG = LoggerFactory.getLogger("autobook");
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    private final Path path;
    private final Path legacyPath;

    public RunStore(Path path, Path legacyPath) {
        this.path = path;
        this.legacyPath = legacyPath;
    }

    public static RunStore defaultStore() {
        return new RunStore(AutoBookPaths.runFile(), AutoBookPaths.legacyQueueFile());
    }

    public Path path() {
        return path;
    }

    public RunState load() throws IOException {
        if (Files.isRegularFile(path)) {
            try {
                RunState state = GSON.fromJson(Files.readString(path, StandardCharsets.UTF_8), RunState.class);
                if (state == null) {
                    state = new RunState();
                }
                state.ensureDefaults();
                return state;
            } catch (JsonParseException error) {
                throw new IOException("Invalid run file: " + path, error);
            }
        }
        if (Files.isRegularFile(legacyPath)) {
            return migrateLegacy();
        }
        RunState state = new RunState();
        state.createdAt = OffsetDateTime.now().toString();
        return state;
    }

    public void save(RunState state) throws IOException {
        Path parent = path.getParent();
        if (parent != null) {
            Files.createDirectories(parent);
        }
        Path temp = path.resolveSibling(path.getFileName() + ".tmp");
        Files.writeString(temp, GSON.toJson(state), StandardCharsets.UTF_8);
        try {
            Files.move(temp, path, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        } catch (AtomicMoveNotSupportedException error) {
            Files.move(temp, path, StandardCopyOption.REPLACE_EXISTING);
        }
    }

    private RunState migrateLegacy() throws IOException {
        String text = Files.readString(legacyPath, StandardCharsets.UTF_8);
        try {
            JsonObject root = JsonParser.parseString(text).getAsJsonObject();
            RunState run = new RunState();
            run.version = 2;
            run.createdAt = OffsetDateTime.now().toString();
            run.reason = "migrated from queue.json";

            JsonArray jobs = root.has("jobs") && root.get("jobs").isJsonArray()
                ? root.getAsJsonArray("jobs")
                : new JsonArray();
            for (JsonElement element : jobs) {
                if (!element.isJsonObject()) {
                    continue;
                }
                JsonObject legacy = element.getAsJsonObject();
                RunJob job = new RunJob();
                job.name = string(legacy, "name", "");
                job.status = mapLegacyStatus(string(legacy, "status", "pending"));
                job.nextIndex = integer(legacy, "nextIndex", 0);
                job.completedBooks = integer(legacy, "completedBooks", 0);
                job.totalBooks = integer(legacy, "totalBooks", 0);
                job.error = string(legacy, "error", "");
                job.addedAt = run.createdAt;
                if (RunState.JOB_RUNNING.equals(job.status) || RunState.JOB_PAUSED.equals(job.status)) {
                    job.startedAt = run.createdAt;
                }
                run.jobs.add(job);
            }

            boolean active = root.has("active") && root.get("active").getAsBoolean();
            boolean suspended = run.jobs.stream()
                .anyMatch(job -> RunState.JOB_PAUSED.equals(job.status));
            if (run.jobs.isEmpty()) {
                run.status = RunState.RUN_CANCELLED;
            } else if (active) {
                run.status = suspended ? RunState.RUN_PAUSED : RunState.RUN_QUEUING;
            } else {
                run.status = run.allTerminal() ? RunState.RUN_COMPLETED : RunState.RUN_QUEUING;
            }
            run.currentIndex = integer(root, "currentIndex", 0);
            run.normalize();
            run.updatedAt = run.createdAt;

            save(run);
            Path backup = legacyPath.resolveSibling(legacyPath.getFileName() + ".bak");
            Files.move(legacyPath, backup, StandardCopyOption.REPLACE_EXISTING);
            LOG.info("AutoBook: migrated queue.json to run.json ({} jobs)", run.jobs.size());
            return run;
        } catch (RuntimeException error) {
            throw new IOException("Invalid legacy queue file: " + legacyPath, error);
        }
    }

    private static String mapLegacyStatus(String status) {
        return switch (status) {
            case "running" -> RunState.JOB_PAUSED;
            case "completed" -> RunState.JOB_COMPLETED;
            case "failed" -> RunState.JOB_FAILED;
            case "cancelled" -> RunState.JOB_CANCELLED;
            default -> RunState.JOB_QUEUED;
        };
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
}
