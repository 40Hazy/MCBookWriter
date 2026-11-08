package com.mcbookwriter.autobook.run;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.mcbookwriter.autobook.AutoBookPaths;
import net.fabricmc.loader.api.FabricLoader;
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
 * 原子写入 autobook/status.json，供 BookForge GUI 只读展示。
 *
 * <p>状态变化（RunRunner.save）立即落盘；运行中的进度更新按 1 秒节流，
 * 最长 5 秒补一次心跳。写入失败只记录日志，不影响游戏内运行。</p>
 */
public final class StatusStore {
    private static final Logger LOG = LoggerFactory.getLogger("autobook");
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    private static final long MIN_INTERVAL_MS = 1000L;
    private static final long HEARTBEAT_MS = 5000L;

    private final Path path;
    private String lastSignature = "";
    private long lastWriteAt;

    public StatusStore(Path path) {
        this.path = path;
    }

    public static StatusStore defaultStore() {
        return new StatusStore(AutoBookPaths.baseDir().resolve("status.json"));
    }

    public Path path() {
        return path;
    }

    /**
     * 状态变化时调用：立即写入（内部仍吞掉 IOException）。
     */
    public void writeNow(RunState run) {
        write(run, true);
    }

    /**
     * 每个客户端 tick 调用：状态签名变化且距上次写入 ≥1 秒时写；否则按心跳补写。
     */
    public void tick(RunState run) {
        write(run, false);
    }

    private void write(RunState run, boolean force) {
        try {
            String signature = signature(run);
            long now = System.currentTimeMillis();
            long elapsed = now - lastWriteAt;
            boolean changed = !signature.equals(lastSignature);
            if (!force) {
                if (changed && elapsed < MIN_INTERVAL_MS) {
                    return;
                }
                if (!changed && elapsed < HEARTBEAT_MS) {
                    return;
                }
            }
            StatusSnapshot snapshot = snapshot(run);
            save(snapshot);
            lastSignature = signature;
            lastWriteAt = now;
        } catch (IOException | RuntimeException error) {
            LOG.warn("AutoBook: failed to write status.json: {}", error.getMessage());
        }
    }

    private StatusSnapshot snapshot(RunState run) {
        StatusSnapshot snapshot = new StatusSnapshot();
        snapshot.runStatus = run.status == null ? "" : run.status;
        RunJob job = run.current();
        if (job != null) {
            snapshot.currentJob = job.name == null ? "" : job.name;
            snapshot.nextIndex = job.nextIndex;
            snapshot.completedBooks = job.completedBooks;
            snapshot.totalBooks = job.totalBooks;
            snapshot.verifiedBooks = job.verifiedBooks;
        }
        snapshot.reason = run.reason == null ? "" : run.reason;
        snapshot.updatedAt = OffsetDateTime.now().toString();
        snapshot.autoBookVersion = version();
        return snapshot;
    }

    private void save(StatusSnapshot snapshot) throws IOException {
        Path parent = path.getParent();
        if (parent != null) {
            Files.createDirectories(parent);
        }
        Path temp = path.resolveSibling(path.getFileName() + ".tmp");
        Files.writeString(temp, GSON.toJson(snapshot), StandardCharsets.UTF_8);
        try {
            Files.move(temp, path, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        } catch (AtomicMoveNotSupportedException error) {
            Files.move(temp, path, StandardCopyOption.REPLACE_EXISTING);
        }
    }

    private static String signature(RunState run) {
        RunJob job = run.current();
        return String.join("|",
            run.status == null ? "" : run.status,
            job == null || job.name == null ? "" : job.name,
            job == null ? "" : Integer.toString(job.nextIndex),
            job == null ? "" : Integer.toString(job.completedBooks),
            job == null ? "" : Integer.toString(job.totalBooks),
            job == null ? "" : Integer.toString(job.verifiedBooks),
            run.reason == null ? "" : run.reason
        );
    }

    public static String version() {
        try {
            return FabricLoader.getInstance().getModContainer("autobook")
                .map(container -> container.getMetadata().getVersion().getFriendlyString())
                .orElse("dev");
        } catch (RuntimeException | LinkageError error) {
            return "dev";
        }
    }
}
